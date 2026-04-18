"""
Cortex SDK
=========
The single-import client for the Cortex MLOps Backbone.

Usage
-----
    from cortex_sdk import CortexClient

    client = CortexClient(base_url="http://localhost")

    # Push features
    client.features.push("user_features", entity_id="u_123", features={"age": 34, "balance": 1500.0})

    # Get online features
    result = client.features.get("user_features", entity_ids=["u_123"])

    # Run inference
    pred = client.serving.predict("fraud_model", features=[{"amount": 250.0, "hour": 14}])

    # Register a model
    client.registry.create_model("fraud_model", description="XGBoost fraud detector")
    client.registry.create_version("fraud_model", version="1.0.0", artifact_uri="s3://models/fraud/v1")

    # Check drift
    client.drift.upload_reference("fraud_model", "1.0.0", "amount", samples=[...])
    report = client.drift.check("fraud_model", "1.0.0", "amount", current_samples=[...])

    # Trigger retraining
    client.scheduler.trigger("fraud_model")
"""

from .client import CortexClient
from .config import CortexConfig
from .exceptions import CortexConflictError, CortexError, CortexNotFoundError

__all__ = [
    "CortexClient",
    "CortexConfig",
    "CortexError",
    "CortexNotFoundError",
    "CortexConflictError",
]
__version__ = "0.1.0"
