"""
In-memory model cache.
Loads model artifacts on startup so inference is fast.
For production use this would load actual sklearn / xgboost / torch objects.
Here we implement a pluggable loader pattern with a mock fallback.
"""

import logging
import os
import pickle
from typing import Dict, Optional

import httpx

logger = logging.getLogger("cortex.serving.cache")

MODEL_REGISTRY_URL = os.getenv("MODEL_REGISTRY_URL", "http://model-registry:8002")

# model_name -> {version, model_object, framework, meta}
_model_cache: Dict[str, Dict] = {}


async def warm_cache():
    """Load all production models from the registry on startup."""
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(f"{MODEL_REGISTRY_URL}/models/")
            if resp.status_code != 200:
                logger.warning(
                    "Could not reach model registry - starting with empty cache"
                )
                return

            models = resp.json()
            for model in models:
                name = model["name"]
                prod_resp = await client.get(
                    f"{MODEL_REGISTRY_URL}/models/{name}/production"
                )
                if prod_resp.status_code == 200:
                    version_info = prod_resp.json()
                    await load_model(name, version_info)

        logger.info(f"Model cache warmed: {list(_model_cache.keys())}")
    except Exception as e:
        logger.warning(f"Cache warm-up skipped: {e}")


async def load_model(model_name: str, version_info: dict):
    """
    Load a model into the in-memory cache.
    Supports: sklearn (pickle), xgboost (json), mock/passthrough.
    """
    framework = version_info.get("framework", "mock")
    artifact_uri = version_info.get("artifact_uri", "")
    version = version_info.get("version", "unknown")

    model_obj = None

    if framework == "mock" or not artifact_uri or artifact_uri.startswith("mock://"):
        # Mock predictor - returns zeros; used in dev/testing
        model_obj = MockModel(model_name)
        logger.info(f"Loaded MOCK model: {model_name} v{version}")

    elif framework == "sklearn" and os.path.exists(artifact_uri):
        with open(artifact_uri, "rb") as f:
            model_obj = pickle.load(f)
        logger.info(
            f"Loaded sklearn model: {model_name} v{version} from {artifact_uri}"
        )

    else:
        model_obj = MockModel(model_name)
        logger.warning(f"Unknown framework '{framework}' for {model_name} - using mock")

    _model_cache[model_name] = {
        "version": version,
        "model": model_obj,
        "framework": framework,
        "artifact_uri": artifact_uri,
    }


def get_model(model_name: str) -> Optional[Dict]:
    return _model_cache.get(model_name)


def list_loaded_models() -> list:
    return [
        {"model_name": k, "version": v["version"], "framework": v["framework"]}
        for k, v in _model_cache.items()
    ]


class MockModel:
    """Passthrough mock model for dev/testing - returns dummy predictions."""

    def __init__(self, name: str):
        self.name = name

    def predict(self, features: list) -> list:
        return [0.5 for _ in features]

    def predict_proba(self, features: list) -> list:
        return [[0.5, 0.5] for _ in features]
