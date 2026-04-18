import os
from dataclasses import dataclass
from typing import Optional


@dataclass
class CortexConfig:
    """
    Configuration for the Cortex SDK.

    Parameters
    ----------
    base_url : str
        Base URL of the Cortex gateway (or feature-store host).
        If all services are on separate ports, override each URL individually.
    feature_store_url : str, optional
        Defaults to base_url:8001
    model_registry_url : str, optional
        Defaults to base_url:8002
    serving_url : str, optional
        Defaults to base_url:8003
    drift_detection_url : str, optional
        Defaults to base_url:8004
    scheduler_url : str, optional
        Defaults to base_url:8005
    kafka_bootstrap_servers : str, optional
        For direct Kafka feature publishing (bypasses HTTP).
    timeout : float
        HTTP request timeout in seconds (default 10).
    """

    base_url: str = "http://localhost"
    feature_store_url: Optional[str] = None
    model_registry_url: Optional[str] = None
    serving_url: Optional[str] = None
    drift_detection_url: Optional[str] = None
    scheduler_url: Optional[str] = None
    kafka_bootstrap_servers: Optional[str] = None
    timeout: float = 10.0

    def __post_init__(self):
        self.feature_store_url = self.feature_store_url or f"{self.base_url}:8001"
        self.model_registry_url = self.model_registry_url or f"{self.base_url}:8002"
        self.serving_url = self.serving_url or f"{self.base_url}:8003"
        self.drift_detection_url = self.drift_detection_url or f"{self.base_url}:8004"
        self.scheduler_url = self.scheduler_url or f"{self.base_url}:8005"

    @classmethod
    def from_env(cls) -> "CortexConfig":
        """Load config from environment variables."""
        return cls(
            base_url=os.getenv("CORTEX_BASE_URL", "http://localhost"),
            feature_store_url=os.getenv("CORTEX_FEATURE_STORE_URL"),
            model_registry_url=os.getenv("CORTEX_MODEL_REGISTRY_URL"),
            serving_url=os.getenv("CORTEX_SERVING_URL"),
            drift_detection_url=os.getenv("CORTEX_DRIFT_DETECTION_URL"),
            scheduler_url=os.getenv("CORTEX_SCHEDULER_URL"),
            kafka_bootstrap_servers=os.getenv("CORTEX_KAFKA_BOOTSTRAP_SERVERS"),
            timeout=float(os.getenv("CORTEX_TIMEOUT", "10")),
        )
