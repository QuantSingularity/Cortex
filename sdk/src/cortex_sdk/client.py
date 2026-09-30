"""
CortexClient - single entry point for the entire Cortex MLOps Backbone SDK.
"""

from __future__ import annotations

from typing import Optional

from .clients import DriftClient, SchedulerClient, ServingClient
from .config import CortexConfig
from .feature_store import FeatureStoreClient
from .model_registry import ModelRegistryClient


class CortexClient:
    """
    Unified client for all Cortex MLOps Backbone services.

    Parameters
    ----------
    base_url : str
        Root URL where Cortex services are running.
        If all on localhost with default ports, pass "http://localhost".
    config : CortexConfig, optional
        Full config object. Overrides base_url if provided.

    Attributes
    ----------
    features  : FeatureStoreClient
    registry  : ModelRegistryClient
    serving   : ServingClient
    drift     : DriftClient
    scheduler : SchedulerClient

    Examples
    --------
    Quick start with localhost defaults:

        from cortex_sdk import CortexClient

        client = CortexClient("http://localhost")

        # 1. Create a feature group and push features
        client.features.create_group("user_features", description="User-level features")
        client.features.push("user_features", entity_id="u_123", features={
            "age": 34, "balance": 1500.0, "transactions_7d": 12
        })

        # 2. Register a model
        client.registry.create_model("fraud_model", description="XGBoost fraud detector")
        client.registry.create_version(
            "fraud_model", version="1.0.0",
            artifact_uri="s3://cortex-models/fraud/v1.pkl",
            framework="xgboost",
            metrics={"auc": 0.97, "f1": 0.91},
        )
        client.registry.promote("fraud_model", "1.0.0")

        # 3. Deploy and predict
        client.serving.deploy("fraud_model", "1.0.0")
        result = client.serving.predict("fraud_model", [{"amount": 500.0, "hour": 22}])
        print(result["predictions"])

        # 4. Upload reference distribution and check drift
        import random
        ref_samples = [random.gauss(500, 100) for _ in range(1000)]
        client.drift.upload_reference("fraud_model", "1.0.0", "amount", ref_samples)

        current = [random.gauss(800, 150) for _ in range(300)]   # shifted distribution
        reports = client.drift.check("fraud_model", "1.0.0", "amount", current)
        for r in reports:
            print(f"{r['test_type']}: drift={r['drift_detected']} score={r['statistic']:.4f}")

        # 5. Schedule retraining
        client.scheduler.schedule("fraud_model", cron_expr="0 2 * * *")   # daily at 2am
        client.scheduler.trigger("fraud_model")                             # manual trigger now

    Load config from environment variables:

        from cortex_sdk import CortexClient, CortexConfig
        client = CortexClient(config=CortexConfig.from_env())
    """

    def __init__(
        self,
        base_url: str = "http://localhost",
        config: Optional[CortexConfig] = None,
    ):
        cfg = config or CortexConfig(base_url=base_url)

        self.features = FeatureStoreClient(cfg.feature_store_url, cfg.timeout)
        self.registry = ModelRegistryClient(cfg.model_registry_url, cfg.timeout)
        self.serving = ServingClient(cfg.serving_url, cfg.timeout)
        self.drift = DriftClient(cfg.drift_detection_url, cfg.timeout)
        self.scheduler = SchedulerClient(cfg.scheduler_url, cfg.timeout)

        self._config = cfg

    def kafka_publisher(self, topic: str = "cortex.features"):
        """
        Create a Kafka-based feature publisher for high-throughput ingestion.
        Requires CORTEX_KAFKA_BOOTSTRAP_SERVERS env var or config.kafka_bootstrap_servers.
        """
        if not self._config.kafka_bootstrap_servers:
            raise ValueError(
                "Set kafka_bootstrap_servers in CortexConfig or "
                "CORTEX_KAFKA_BOOTSTRAP_SERVERS env var."
            )
        from .kafka_publisher import KafkaFeaturePublisher

        return KafkaFeaturePublisher(self._config.kafka_bootstrap_servers, topic=topic)

    def health_check(self) -> dict:
        """Ping all services and return their health status."""
        import httpx

        results = {}
        services = {
            "feature-store": self._config.feature_store_url,
            "model-registry": self._config.model_registry_url,
            "serving": self._config.serving_url,
            "drift-detection": self._config.drift_detection_url,
            "scheduler": self._config.scheduler_url,
        }
        for name, url in services.items():
            try:
                r = httpx.get(f"{url}/health", timeout=5)
                results[name] = (
                    "ok" if r.status_code == 200 else f"error ({r.status_code})"
                )
            except Exception as e:
                results[name] = f"unreachable ({e})"
        return results

    def __repr__(self) -> str:
        return f"CortexClient(base_url={self._config.base_url!r})"
