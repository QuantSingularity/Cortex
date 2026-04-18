from __future__ import annotations

from typing import Any, Dict, List, Optional

import httpx

from .exceptions import _raise_for_status


class ModelRegistryClient:
    """
    Client for the Cortex Model Registry.

    Examples
    --------
        client.registry.create_model("fraud_model", description="XGBoost fraud detector")
        client.registry.create_version(
            "fraud_model", version="1.0.0",
            artifact_uri="s3://models/fraud/v1",
            framework="xgboost",
            metrics={"auc": 0.97, "f1": 0.91},
        )
        client.registry.promote("fraud_model", "1.0.0")
        prod = client.registry.get_production("fraud_model")
    """

    def __init__(self, base_url: str, timeout: float = 10.0):
        self._base = base_url.rstrip("/")
        self._timeout = timeout

    # ── Models ────────────────────────────────────────────────────────────────

    def create_model(self, name: str, description: str = "", tags: Dict = {}) -> dict:
        with httpx.Client(timeout=self._timeout) as c:
            r = c.post(
                f"{self._base}/models/",
                json={"name": name, "description": description, "tags": tags},
            )
            _raise_for_status(r)
            return r.json()

    def list_models(self) -> List[dict]:
        with httpx.Client(timeout=self._timeout) as c:
            r = c.get(f"{self._base}/models/")
            _raise_for_status(r)
            return r.json()

    def get_model(self, name: str) -> dict:
        with httpx.Client(timeout=self._timeout) as c:
            r = c.get(f"{self._base}/models/{name}")
            _raise_for_status(r)
            return r.json()

    def delete_model(self, name: str) -> None:
        with httpx.Client(timeout=self._timeout) as c:
            r = c.delete(f"{self._base}/models/{name}")
            _raise_for_status(r)

    # ── Versions ──────────────────────────────────────────────────────────────

    def create_version(
        self,
        model_name: str,
        version: str,
        artifact_uri: str,
        framework: Optional[str] = None,
        python_version: Optional[str] = None,
        description: Optional[str] = None,
        tags: Dict[str, Any] = {},
        metrics: Dict[str, float] = {},
        params: Dict[str, Any] = {},
    ) -> dict:
        with httpx.Client(timeout=self._timeout) as c:
            r = c.post(
                f"{self._base}/models/{model_name}/versions",
                json={
                    "version": version,
                    "artifact_uri": artifact_uri,
                    "framework": framework,
                    "python_version": python_version,
                    "description": description,
                    "tags": tags,
                    "metrics": metrics,
                    "params": params,
                },
            )
            _raise_for_status(r)
            return r.json()

    def list_versions(self, model_name: str, stage: Optional[str] = None) -> List[dict]:
        params = {"stage": stage} if stage else {}
        with httpx.Client(timeout=self._timeout) as c:
            r = c.get(f"{self._base}/models/{model_name}/versions", params=params)
            _raise_for_status(r)
            return r.json()

    def get_version(self, model_name: str, version: str) -> dict:
        with httpx.Client(timeout=self._timeout) as c:
            r = c.get(f"{self._base}/models/{model_name}/versions/{version}")
            _raise_for_status(r)
            return r.json()

    def promote(self, model_name: str, version: str) -> dict:
        """Promote a version to production (archives existing production)."""
        with httpx.Client(timeout=self._timeout) as c:
            r = c.post(f"{self._base}/models/{model_name}/versions/{version}/promote")
            _raise_for_status(r)
            return r.json()

    def get_production(self, model_name: str) -> dict:
        """Get the current production version."""
        with httpx.Client(timeout=self._timeout) as c:
            r = c.get(f"{self._base}/models/{model_name}/production")
            _raise_for_status(r)
            return r.json()

    def update_version(
        self,
        model_name: str,
        version: str,
        stage: Optional[str] = None,
        description: Optional[str] = None,
        metrics: Optional[Dict] = None,
    ) -> dict:
        payload = {
            k: v
            for k, v in {
                "stage": stage,
                "description": description,
                "metrics": metrics,
            }.items()
            if v is not None
        }
        with httpx.Client(timeout=self._timeout) as c:
            r = c.patch(
                f"{self._base}/models/{model_name}/versions/{version}", json=payload
            )
            _raise_for_status(r)
            return r.json()

    # ── Metrics ───────────────────────────────────────────────────────────────

    def log_metric(
        self,
        model_name: str,
        version: str,
        metric_name: str,
        metric_value: float,
        step: int = 0,
    ) -> dict:
        with httpx.Client(timeout=self._timeout) as c:
            r = c.post(
                f"{self._base}/models/{model_name}/versions/{version}/metrics",
                json={
                    "metric_name": metric_name,
                    "metric_value": metric_value,
                    "step": step,
                },
            )
            _raise_for_status(r)
            return r.json()

    def get_metric_history(
        self,
        model_name: str,
        version: str,
        metric_name: Optional[str] = None,
    ) -> List[dict]:
        params = {"metric_name": metric_name} if metric_name else {}
        with httpx.Client(timeout=self._timeout) as c:
            r = c.get(
                f"{self._base}/models/{model_name}/versions/{version}/metrics",
                params=params,
            )
            _raise_for_status(r)
            return r.json()
