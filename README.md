# Cortex - MLOps Backbone

> Cortex is the shared AI/ML backbone that every downstream service depends on for feature
> management, model versioning, real-time inference, drift detection, and automated retraining.

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                        Cortex MLOps Backbone                    │
│                                                                 │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────┐   │
│  │ Feature Store│  │Model Registry│  │   Serving Layer      │   │
│  │  :8001       │  │  :8002       │  │   :8003              │   │
│  │              │  │              │  │                      │   │
│  │ Redis (online│  │ Versions     │  │ Real-time inference  │   │
│  │ PostgreSQL   │  │ Stages       │  │ Model cache          │   │
│  │ offline)     │  │ Metrics      │  │ Deployment mgmt      │   │
│  └──────┬───────┘  └──────┬───────┘  └──────────┬───────────┘   │
│         │                 │                     │               │
│  ┌──────▼───────┐  ┌──────▼───────────────────────────────────┐ │
│  │Drift Detect. │  │           Scheduler                      │ │
│  │  :8004       │  │           :8005                          │ │
│  │              │  │                                          │ │
│  │ KS test      │  │ APScheduler (cron)                       │ │
│  │ PSI scoring  │  │ Drift-triggered retraining               │ │
│  │ Kafka ingest │  │ Manual trigger API                       │ │
│  └──────────────┘  └──────────────────────────────────────────┘ │
│                                                                 │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │                   Shared Infrastructure                  │   │
│  │  Kafka · Redis · PostgreSQL · Prometheus · Grafana       │   │
│  └──────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
                              │
                    ┌─────────▼──────────┐
                    │    cortex-sdk      │
                    │  pip install .     │
                    │  CortexClient(...) │
                    └────────────────────┘
```

---

## Services

| Service           | Port | Description                                         |
| ----------------- | ---- | --------------------------------------------------- |
| `feature-store`   | 8001 | Online (Redis) + offline (PostgreSQL) feature store |
| `model-registry`  | 8002 | Versioned model registry with stage management      |
| `serving`         | 8003 | Real-time inference with in-memory model cache      |
| `drift-detection` | 8004 | KS test + PSI drift detection with Kafka ingestion  |
| `scheduler`       | 8005 | APScheduler cron + drift-triggered retraining jobs  |
| `prometheus`      | 9090 | Metrics collection                                  |
| `grafana`         | 3000 | Dashboards (admin / cortex_grafana)                 |
| `kafka`           | 9092 | Feature event streaming                             |
| `redis`           | 6379 | Online feature store cache                          |
| `postgres`        | 5432 | Offline store + registry + reports                  |

---

## Quick Start

### Prerequisites

- Docker ≥ 24 and Docker Compose v2
- Python ≥ 3.9 (for SDK)

### 1. Clone and configure

```bash
git clone https://github.com/quantsingularity/Cortex.git
cd Cortex
cp .env.example .env
# Edit .env if needed (defaults work out of the box)
```

### 2. Start all services

```bash
docker compose up --build -d
```

Wait ~30 seconds for all services to initialise, then verify:

```bash
curl http://localhost:8001/health   # feature-store
curl http://localhost:8002/health   # model-registry
curl http://localhost:8003/health   # serving
curl http://localhost:8004/health   # drift-detection
curl http://localhost:8005/health   # scheduler
```

### 3. Install the SDK

```bash
cd sdk
pip install -e .
```

### 4. End-to-end example

```python
from cortex_sdk import CortexClient
import random

client = CortexClient("http://localhost")

# Check all services are up
print(client.health_check())

# ── Feature Store ──────────────────────────────────────────────────
client.features.create_group("user_features", description="User-level features")
client.features.add_feature_definition("user_features", "amount",  dtype="float")
client.features.add_feature_definition("user_features", "age",     dtype="int")
client.features.add_feature_definition("user_features", "hour",    dtype="int")

client.features.push("user_features", entity_id="u_001", features={
    "amount": 250.0, "age": 34, "hour": 14
})

online = client.features.get("user_features", entity_ids=["u_001"])
print(online[0]["features"])    # {'amount': 250.0, 'age': 34, 'hour': 14}

# ── Model Registry ─────────────────────────────────────────────────
client.registry.create_model("fraud_model", description="XGBoost fraud detector")
client.registry.create_version(
    "fraud_model", version="1.0.0",
    artifact_uri="mock://models/fraud/v1",
    framework="mock",
    metrics={"auc": 0.97, "f1": 0.91, "precision": 0.89},
    params={"n_estimators": 300, "max_depth": 6},
)
client.registry.promote("fraud_model", "1.0.0")
prod = client.registry.get_production("fraud_model")
print(f"Production: {prod['model_name']} v{prod['version']} ({prod['stage']})")

# ── Serving ────────────────────────────────────────────────────────
client.serving.deploy("fraud_model", "1.0.0")

result = client.serving.predict("fraud_model", [
    {"amount": 500.0, "age": 25, "hour": 22},
    {"amount": 30.0,  "age": 45, "hour": 9},
])
print(f"Predictions: {result['predictions']}  latency: {result['latency_ms']}ms")

# ── Drift Detection ────────────────────────────────────────────────
ref_samples = [random.gauss(300, 80) for _ in range(1000)]
client.drift.upload_reference("fraud_model", "1.0.0", "amount", ref_samples)

# Simulate a distribution shift (higher mean → possible fraud spike)
current_samples = [random.gauss(700, 120) for _ in range(300)]
reports = client.drift.check("fraud_model", "1.0.0", "amount", current_samples)
for r in reports:
    status = "⚠️  DRIFT" if r["drift_detected"] else "✅  OK"
    print(f"{r['test_type'].upper():4s} {status}  score={r['statistic']:.4f}")

# ── Scheduler ──────────────────────────────────────────────────────
client.scheduler.schedule("fraud_model", cron_expr="0 2 * * *")  # daily 2am UTC
client.scheduler.trigger("fraud_model")                            # fire now
jobs = client.scheduler.list_jobs(model_name="fraud_model")
print(f"Latest job: {jobs[0]['status']}")
```

---

## API Reference

### Feature Store (`localhost:8001`)

| Method | Endpoint                          | Description                       |
| ------ | --------------------------------- | --------------------------------- |
| `POST` | `/feature-groups/`                | Create feature group              |
| `GET`  | `/feature-groups/`                | List all groups                   |
| `GET`  | `/feature-groups/{name}`          | Get group                         |
| `POST` | `/feature-groups/{name}/features` | Add feature definition            |
| `POST` | `/features/{group}/push`          | Push feature values               |
| `GET`  | `/features/{group}/history`       | Get offline history               |
| `POST` | `/online/{group}/get`             | Get online features (low-latency) |
| `GET`  | `/metrics`                        | Prometheus metrics                |

### Model Registry (`localhost:8002`)

| Method  | Endpoint                              | Description             |
| ------- | ------------------------------------- | ----------------------- |
| `POST`  | `/models/`                            | Register a model        |
| `GET`   | `/models/`                            | List models             |
| `POST`  | `/models/{name}/versions`             | Create version          |
| `GET`   | `/models/{name}/versions`             | List versions           |
| `PATCH` | `/models/{name}/versions/{v}`         | Update version metadata |
| `POST`  | `/models/{name}/versions/{v}/promote` | Promote to production   |
| `GET`   | `/models/{name}/production`           | Get production version  |
| `POST`  | `/models/{name}/versions/{v}/metrics` | Log a metric            |
| `GET`   | `/models/{name}/versions/{v}/metrics` | Get metric history      |

### Serving (`localhost:8003`)

| Method   | Endpoint                | Description            |
| -------- | ----------------------- | ---------------------- |
| `POST`   | `/predict/{model_name}` | Run inference          |
| `GET`    | `/predict/loaded`       | List cached models     |
| `POST`   | `/deployments/`         | Deploy a model version |
| `GET`    | `/deployments/`         | List deployments       |
| `DELETE` | `/deployments/{model}`  | Undeploy model         |

### Drift Detection (`localhost:8004`)

| Method | Endpoint                 | Description                   |
| ------ | ------------------------ | ----------------------------- |
| `POST` | `/reference/`            | Upload reference distribution |
| `GET`  | `/reference/`            | List reference distributions  |
| `POST` | `/drift/check`           | Run KS + PSI drift check      |
| `GET`  | `/drift/reports`         | List drift reports            |
| `GET`  | `/drift/reports/summary` | Per-feature summary           |

### Scheduler (`localhost:8005`)

| Method | Endpoint          | Description            |
| ------ | ----------------- | ---------------------- |
| `POST` | `/jobs/trigger`   | Trigger retraining now |
| `POST` | `/jobs/schedule`  | Register cron schedule |
| `GET`  | `/jobs/schedules` | List all schedules     |
| `GET`  | `/jobs/`          | List retraining jobs   |
| `GET`  | `/jobs/{id}`      | Get job details        |

---

## Kafka Topics

| Topic             | Producer          | Consumer                       | Schema                                                                                  |
| ----------------- | ----------------- | ------------------------------ | --------------------------------------------------------------------------------------- |
| `cortex.features` | Any service / SDK | Feature Store, Drift Detection | `{model_name, feature_group, entity_id, feature_name, value, version, event_timestamp}` |
| `cortex.drift`    | Drift Detection   | Scheduler                      | `{model_name, version, feature_name, drift_detected}`                                   |

---

## Prometheus Metrics

| Metric                              | Type      | Labels                                | Description              |
| ----------------------------------- | --------- | ------------------------------------- | ------------------------ |
| `cortex_predictions_total`          | Counter   | `model_name, version, status`         | Total inference requests |
| `cortex_inference_duration_seconds` | Histogram | `model_name, version`                 | Inference latency        |
| `cortex_drift_score`                | Gauge     | `model_name, feature_name, test_type` | Latest drift score       |
| `cortex_drift_alerts_total`         | Counter   | `model_name, feature_name`            | Total drift alerts       |
| `cortex_feature_writes_total`       | Counter   | `feature_group`                       | Feature write throughput |
| `cortex_retraining_jobs_total`      | Counter   | `status`                              | Retraining job outcomes  |
| `cortex_models_in_production`       | Gauge     | -                                     | Active production models |

Access Grafana at **http://localhost:3000** (admin / cortex_grafana) for pre-built dashboards.

---

## SDK Usage

### Install

```bash
# From source
cd sdk && pip install -e .

# Or after publishing to PyPI
pip install cortex-sdk
```

### Configuration

```python
from cortex_sdk import CortexClient, CortexConfig

# Simple - all services on localhost with default ports
client = CortexClient("http://localhost")

# Full config
client = CortexClient(config=CortexConfig(
    base_url="http://cortex-gateway",
    kafka_bootstrap_servers="kafka:9092",
    timeout=30.0,
))

# From environment variables
# CORTEX_BASE_URL, CORTEX_FEATURE_STORE_URL, CORTEX_KAFKA_BOOTSTRAP_SERVERS, etc.
client = CortexClient(config=CortexConfig.from_env())
```

### High-throughput Kafka publishing

```python
with client.kafka_publisher() as pub:
    pub.publish_batch("fraud_model", "user_features", [
        {"entity_id": f"u_{i}", "features": {"amount": i * 10.0, "hour": i % 24}}
        for i in range(10_000)
    ])
```

### Async support

```python
import asyncio

async def main():
    await client.features.apush("user_features", "u_001", {"amount": 100.0})
    result = await client.serving.apredict("fraud_model", [{"amount": 100.0}])
    print(result)

asyncio.run(main())
```

---

## Folder Structure

```
Cortex/
├── docker-compose.yml          # Full stack orchestration
├── .env.example                # Environment variable template
├── infra/
│   ├── init.sql                # PostgreSQL schema (auto-run on first start)
│   ├── prometheus/
│   │   └── prometheus.yml      # Scrape configs for all services
│   └── grafana/
│       └── provisioning/       # Auto-provisioned datasources + dashboards
├── feature-store/
│   ├── Dockerfile
│   ├── requirements.txt
│   └── src/
│       ├── main.py             # FastAPI app + lifespan
│       ├── database.py         # SQLAlchemy models
│       ├── redis_client.py     # Redis online store
│       ├── kafka_consumer.py   # Kafka ingestion consumer
│       ├── schemas.py          # Pydantic schemas
│       └── routers/
│           ├── feature_groups.py
│           ├── features.py
│           └── online_store.py
├── model-registry/
│   ├── Dockerfile
│   ├── requirements.txt
│   └── src/
│       ├── main.py
│       ├── database.py
│       ├── schemas.py
│       └── routers/
│           ├── models.py
│           ├── versions.py
│           └── metrics.py
├── serving/
│   ├── Dockerfile
│   ├── requirements.txt
│   └── src/
│       ├── main.py
│       ├── database.py
│       ├── model_cache.py      # In-memory model loader
│       └── routers/
│           ├── inference.py
│           └── deployments.py
├── drift-detection/
│   ├── Dockerfile
│   ├── requirements.txt
│   └── src/
│       ├── main.py
│       ├── database.py
│       ├── detector.py         # KS test + PSI implementation
│       ├── kafka_consumer.py   # Rolling window drift consumer
│       ├── schemas.py
│       └── routers/
│           ├── reference.py
│           └── drift.py
├── scheduler/
│   ├── Dockerfile
│   ├── requirements.txt
│   └── src/
│       ├── main.py
│       ├── database.py
│       ├── scheduler.py        # APScheduler setup + job executor
│       └── routers/
│           └── jobs.py
└── sdk/
    ├── setup.py
    ├── pyproject.toml
    ├── requirements.txt
    ├── tests/
    │   └── test_sdk.py
    └── src/
        └── cortex_sdk/
            ├── __init__.py
            ├── client.py           # CortexClient facade
            ├── config.py           # CortexConfig
            ├── exceptions.py       # CortexError hierarchy
            ├── feature_store.py    # FeatureStoreClient
            ├── model_registry.py   # ModelRegistryClient
            ├── clients.py          # ServingClient, DriftClient, SchedulerClient
            └── kafka_publisher.py  # High-throughput Kafka publisher
```

---

## Integration with Other Services

Cortex is designed to be consumed by all downstream services in the suite via the SDK:

```python
# In PayNext fraud detection service
from cortex_sdk import CortexClient

cortex = CortexClient(config=CortexConfig.from_env())

# Get real-time features for a transaction
features = cortex.features.get("transaction_features", [transaction.id])

# Score the transaction
score = cortex.serving.predict("fraud_model", features[0]["features"])

# If score is high, log the feature snapshot for future drift monitoring
if score["predictions"][0] > 0.8:
    cortex.features.push("fraud_alerts", transaction.id, features[0]["features"])
```

---

## Development

### Run a single service locally

```bash
cd feature-store
pip install -r requirements.txt
uvicorn src.main:app --reload --port 8001
```

### Run tests

```bash
# SDK tests (no services required)
cd sdk && pip install pytest anyio && pytest tests/

# Service tests (requires running stack)
docker compose up -d
cd feature-store && pytest tests/
```

### Rebuild a single service

```bash
docker compose up --build feature-store -d
```

### View logs

```bash
docker compose logs -f serving
docker compose logs -f drift-detection
```

---

## Stopping the Stack

```bash
docker compose down           # stop containers
docker compose down -v        # stop + wipe all volumes (full reset)
```

---
