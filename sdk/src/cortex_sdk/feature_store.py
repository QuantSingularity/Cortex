"""
Feature Store client module.
Supports both synchronous (httpx) and asynchronous usage.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

import httpx

from .exceptions import _raise_for_status


class FeatureStoreClient:
    """
    Client for the Cortex Feature Store service.

    Examples
    --------
    Push features (sync):
        client.features.push("user_features", "u_123", {"age": 34, "balance": 1500.0})

    Get online features (sync):
        result = client.features.get("user_features", ["u_123", "u_456"])
    """

    def __init__(self, base_url: str, timeout: float = 10.0):
        self._base = base_url.rstrip("/")
        self._timeout = timeout

    # ── Feature Groups ────────────────────────────────────────────────────────

    def create_group(self, name: str, description: str = "", tags: Dict = {}) -> dict:
        """Create a new feature group."""
        with httpx.Client(timeout=self._timeout) as c:
            r = c.post(
                f"{self._base}/feature-groups/",
                json={"name": name, "description": description, "tags": tags},
            )
            _raise_for_status(r)
            return r.json()

    def list_groups(self) -> List[dict]:
        with httpx.Client(timeout=self._timeout) as c:
            r = c.get(f"{self._base}/feature-groups/")
            _raise_for_status(r)
            return r.json()

    def get_group(self, name: str) -> dict:
        with httpx.Client(timeout=self._timeout) as c:
            r = c.get(f"{self._base}/feature-groups/{name}")
            _raise_for_status(r)
            return r.json()

    def add_feature_definition(
        self,
        group_name: str,
        feature_name: str,
        dtype: str = "float",
        description: str = "",
    ) -> dict:
        with httpx.Client(timeout=self._timeout) as c:
            r = c.post(
                f"{self._base}/feature-groups/{group_name}/features",
                json={"name": feature_name, "dtype": dtype, "description": description},
            )
            _raise_for_status(r)
            return r.json()

    # ── Feature Values ─────────────────────────────────────────────────────────

    def push(
        self,
        group_name: str,
        entity_id: str,
        features: Dict[str, Any],
        event_timestamp: Optional[datetime] = None,
    ) -> dict:
        """Push feature values to the online + offline store."""
        payload: Dict[str, Any] = {"entity_id": entity_id, "features": features}
        if event_timestamp:
            payload["event_timestamp"] = event_timestamp.isoformat()

        with httpx.Client(timeout=self._timeout) as c:
            r = c.post(f"{self._base}/features/{group_name}/push", json=payload)
            _raise_for_status(r)
            return r.json()

    def get(
        self,
        group_name: str,
        entity_ids: List[str],
        feature_names: Optional[List[str]] = None,
    ) -> List[dict]:
        """Get latest feature values from the online store (Redis)."""
        payload: Dict[str, Any] = {"entity_ids": entity_ids}
        if feature_names:
            payload["feature_names"] = feature_names

        with httpx.Client(timeout=self._timeout) as c:
            r = c.post(f"{self._base}/online/{group_name}/get", json=payload)
            _raise_for_status(r)
            return r.json()

    def get_history(
        self,
        group_name: str,
        entity_id: str,
        feature_name: Optional[str] = None,
        limit: int = 100,
    ) -> List[dict]:
        """Get historical feature values from the offline store (PostgreSQL)."""
        params: Dict[str, Any] = {"entity_id": entity_id, "limit": limit}
        if feature_name:
            params["feature_name"] = feature_name

        with httpx.Client(timeout=self._timeout) as c:
            r = c.get(f"{self._base}/features/{group_name}/history", params=params)
            _raise_for_status(r)
            return r.json()

    # ── Async variants ─────────────────────────────────────────────────────────

    async def apush(
        self,
        group_name: str,
        entity_id: str,
        features: Dict[str, Any],
        event_timestamp: Optional[datetime] = None,
    ) -> dict:
        payload: Dict[str, Any] = {"entity_id": entity_id, "features": features}
        if event_timestamp:
            payload["event_timestamp"] = event_timestamp.isoformat()

        async with httpx.AsyncClient(timeout=self._timeout) as c:
            r = await c.post(f"{self._base}/features/{group_name}/push", json=payload)
            _raise_for_status(r)
            return r.json()

    async def aget(
        self,
        group_name: str,
        entity_ids: List[str],
        feature_names: Optional[List[str]] = None,
    ) -> List[dict]:
        payload: Dict[str, Any] = {"entity_ids": entity_ids}
        if feature_names:
            payload["feature_names"] = feature_names

        async with httpx.AsyncClient(timeout=self._timeout) as c:
            r = await c.post(f"{self._base}/online/{group_name}/get", json=payload)
            _raise_for_status(r)
            return r.json()
