"""
Cortex Drift Detection Service
Detects feature distribution drift using KS test and PSI.
Consumes live feature events from Kafka and compares against reference distributions.
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from prometheus_client import Counter, Gauge
from prometheus_fastapi_instrumentator import Instrumentator

from .database import init_db
from .kafka_consumer import start_kafka_consumer
from .routers import drift, reference

logging.basicConfig(level="INFO")
logger = logging.getLogger("cortex.drift-detection")

DRIFT_SCORE_GAUGE = Gauge(
    "cortex_drift_score",
    "Latest drift score per feature",
    ["model_name", "feature_name", "test_type"],
)
DRIFT_ALERTS_TOTAL = Counter(
    "cortex_drift_alerts_total",
    "Total drift alerts triggered",
    ["model_name", "feature_name"],
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting Cortex Drift Detection...")
    await init_db()
    await start_kafka_consumer()
    yield
    logger.info("Shutting down Cortex Drift Detection...")


app = FastAPI(
    title="Cortex Drift Detection",
    description="Statistical drift detection via KS test and PSI on incoming feature distributions",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"]
)
Instrumentator().instrument(app).expose(app)

app.include_router(
    reference.router, prefix="/reference", tags=["Reference Distributions"]
)
app.include_router(drift.router, prefix="/drift", tags=["Drift Reports"])


@app.get("/health")
async def health():
    return {"status": "ok", "service": "cortex-drift-detection"}
