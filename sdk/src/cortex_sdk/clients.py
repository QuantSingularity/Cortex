from __future__ import annotations

from typing import Any, Dict, List, Optional

import httpx

from .exceptions import _raise_for_status

# ─── Serving Client ────────────────────────────────────────────────────────────


class ServingClient:
    """
    Client for the Cortex Serving layer.

    Examples
    --------
        result = client.serving.predict("fraud_model", [{"amount": 500.0, "hour": 22}])
        result = client.serving.predict("fraud_model", features, return_proba=True)
        client.serving.deploy("fraud_model", "1.0.0")
        client.serving.list_deployments()
    """

    def __init__(self, base_url: str, timeout: float = 10.0):
        self._base = base_url.rstrip("/")
        self._timeout = timeout

    def predict(
        self,
        model_name: str,
        features: List[Dict[str, Any]],
        return_proba: bool = False,
    ) -> dict:
        """Run real-time inference. Returns predictions + latency_ms."""
        with httpx.Client(timeout=self._timeout) as c:
            r = c.post(
                f"{self._base}/predict/{model_name}",
                json={
                    "features": features,
                    "return_proba": return_proba,
                },
            )
            _raise_for_status(r)
            return r.json()

    async def apredict(
        self,
        model_name: str,
        features: List[Dict[str, Any]],
        return_proba: bool = False,
    ) -> dict:
        """Async inference."""
        async with httpx.AsyncClient(timeout=self._timeout) as c:
            r = await c.post(
                f"{self._base}/predict/{model_name}",
                json={
                    "features": features,
                    "return_proba": return_proba,
                },
            )
            _raise_for_status(r)
            return r.json()

    def deploy(self, model_name: str, version: str, config: Dict = {}) -> dict:
        with httpx.Client(timeout=self._timeout) as c:
            r = c.post(
                f"{self._base}/deployments/",
                json={"model_name": model_name, "version": version, "config": config},
            )
            _raise_for_status(r)
            return r.json()

    def undeploy(self, model_name: str) -> None:
        with httpx.Client(timeout=self._timeout) as c:
            r = c.delete(f"{self._base}/deployments/{model_name}")
            _raise_for_status(r)

    def list_deployments(self, active_only: bool = True) -> List[dict]:
        with httpx.Client(timeout=self._timeout) as c:
            r = c.get(f"{self._base}/deployments/", params={"active_only": active_only})
            _raise_for_status(r)
            return r.json()

    def list_loaded(self) -> List[dict]:
        """Models currently loaded in the serving cache."""
        with httpx.Client(timeout=self._timeout) as c:
            r = c.get(f"{self._base}/predict/loaded")
            _raise_for_status(r)
            return r.json()


# ─── Drift Detection Client ────────────────────────────────────────────────────


class DriftClient:
    """
    Client for Cortex Drift Detection.

    Examples
    --------
        client.drift.upload_reference("fraud_model", "1.0.0", "amount", samples=[...])
        reports = client.drift.check("fraud_model", "1.0.0", "amount", current_samples=[...])
        summary = client.drift.summary("fraud_model")
    """

    def __init__(self, base_url: str, timeout: float = 10.0):
        self._base = base_url.rstrip("/")
        self._timeout = timeout

    def upload_reference(
        self,
        model_name: str,
        version: str,
        feature_name: str,
        samples: List[float],
    ) -> dict:
        """Upload baseline (training-time) distribution for a feature."""
        with httpx.Client(timeout=self._timeout) as c:
            r = c.post(
                f"{self._base}/reference/",
                json={
                    "model_name": model_name,
                    "version": version,
                    "feature_name": feature_name,
                    "samples": samples,
                },
            )
            _raise_for_status(r)
            return r.json()

    def check(
        self,
        model_name: str,
        version: str,
        feature_name: str,
        current_samples: List[float],
        ks_threshold: float = 0.05,
        psi_threshold: float = 0.20,
    ) -> List[dict]:
        """Run KS + PSI drift check. Returns list of drift reports (one per test)."""
        with httpx.Client(timeout=self._timeout) as c:
            r = c.post(
                f"{self._base}/drift/check",
                json={
                    "model_name": model_name,
                    "version": version,
                    "feature_name": feature_name,
                    "current_samples": current_samples,
                    "ks_threshold": ks_threshold,
                    "psi_threshold": psi_threshold,
                },
            )
            _raise_for_status(r)
            return r.json()

    def list_reports(
        self,
        model_name: Optional[str] = None,
        feature_name: Optional[str] = None,
        drift_only: bool = False,
        limit: int = 100,
    ) -> List[dict]:
        params: Dict[str, Any] = {"limit": limit, "drift_only": drift_only}
        if model_name:
            params["model_name"] = model_name
        if feature_name:
            params["feature_name"] = feature_name
        with httpx.Client(timeout=self._timeout) as c:
            r = c.get(f"{self._base}/drift/reports", params=params)
            _raise_for_status(r)
            return r.json()

    def summary(self, model_name: str) -> List[dict]:
        """Per-feature drift summary for a model (latest result per feature)."""
        with httpx.Client(timeout=self._timeout) as c:
            r = c.get(
                f"{self._base}/drift/reports/summary", params={"model_name": model_name}
            )
            _raise_for_status(r)
            return r.json()


# ─── Scheduler Client ──────────────────────────────────────────────────────────


class SchedulerClient:
    """
    Client for Cortex Scheduler.

    Examples
    --------
        client.scheduler.trigger("fraud_model")
        client.scheduler.schedule("fraud_model", cron_expr="0 2 * * *")
        client.scheduler.list_jobs(model_name="fraud_model")
    """

    def __init__(self, base_url: str, timeout: float = 10.0):
        self._base = base_url.rstrip("/")
        self._timeout = timeout

    def trigger(
        self,
        model_name: str,
        trigger_type: str = "manual",
        metadata: Dict = {},
    ) -> dict:
        """Immediately trigger a retraining job (async, non-blocking)."""
        with httpx.Client(timeout=self._timeout) as c:
            r = c.post(
                f"{self._base}/jobs/trigger",
                json={
                    "model_name": model_name,
                    "trigger_type": trigger_type,
                    "metadata": metadata,
                },
            )
            _raise_for_status(r)
            return r.json()

    def schedule(self, model_name: str, cron_expr: str) -> dict:
        """Register a cron-based retraining schedule. e.g. '0 2 * * *' = daily 2am."""
        with httpx.Client(timeout=self._timeout) as c:
            r = c.post(
                f"{self._base}/jobs/schedule",
                json={"model_name": model_name, "cron_expr": cron_expr},
            )
            _raise_for_status(r)
            return r.json()

    def list_schedules(self) -> List[dict]:
        with httpx.Client(timeout=self._timeout) as c:
            r = c.get(f"{self._base}/jobs/schedules")
            _raise_for_status(r)
            return r.json()

    def list_jobs(
        self,
        model_name: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 50,
    ) -> List[dict]:
        params: Dict[str, Any] = {"limit": limit}
        if model_name:
            params["model_name"] = model_name
        if status:
            params["status"] = status
        with httpx.Client(timeout=self._timeout) as c:
            r = c.get(f"{self._base}/jobs/", params=params)
            _raise_for_status(r)
            return r.json()

    def get_job(self, job_id: int) -> dict:
        with httpx.Client(timeout=self._timeout) as c:
            r = c.get(f"{self._base}/jobs/{job_id}")
            _raise_for_status(r)
            return r.json()
