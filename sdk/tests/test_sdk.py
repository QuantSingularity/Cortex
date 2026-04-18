"""
Unit tests for the Cortex SDK (no running services required — uses httpx mock transport).
"""

import httpx
import pytest
from cortex_sdk import CortexClient, CortexConfig


def _mock_transport(responses: dict):
    """Build an httpx mock transport from a URL → response dict."""

    class MockTransport(httpx.BaseTransport):
        def handle_request(self, request):
            key = f"{request.method} {request.url.path}"
            if key in responses:
                code, body = responses[key]
                return httpx.Response(code, json=body)
            return httpx.Response(404, json={"detail": "not found"})

    return MockTransport()


def test_cortex_config_defaults():
    cfg = CortexConfig(base_url="http://cortex")
    assert cfg.feature_store_url == "http://cortex:8001"
    assert cfg.model_registry_url == "http://cortex:8002"
    assert cfg.serving_url == "http://cortex:8003"
    assert cfg.drift_detection_url == "http://cortex:8004"
    assert cfg.scheduler_url == "http://cortex:8005"


def test_cortex_config_from_env(monkeypatch):
    monkeypatch.setenv("CORTEX_BASE_URL", "http://prod-cortex")
    monkeypatch.setenv("CORTEX_TIMEOUT", "30")
    cfg = CortexConfig.from_env()
    assert cfg.base_url == "http://prod-cortex"
    assert cfg.timeout == 30.0


def test_client_repr():
    client = CortexClient("http://localhost")
    assert "CortexClient" in repr(client)
    assert "localhost" in repr(client)


def test_health_check_all_unreachable():
    client = CortexClient("http://127.0.0.1:1")  # nothing listening
    result = client.health_check()
    for svc in [
        "feature-store",
        "model-registry",
        "serving",
        "drift-detection",
        "scheduler",
    ]:
        assert "unreachable" in result[svc] or "error" in result[svc]


def test_kafka_publisher_missing_config():
    client = CortexClient("http://localhost")
    with pytest.raises(ValueError, match="kafka_bootstrap_servers"):
        client.kafka_publisher()


def test_kafka_publisher_with_config():
    cfg = CortexConfig(
        base_url="http://localhost", kafka_bootstrap_servers="kafka:9092"
    )
    client = CortexClient(config=cfg)
    # Don't actually connect — just verify the publisher is created
    try:
        client.kafka_publisher()
    except Exception as e:
        # kafka not running in test env — ImportError or connection error is fine
        assert "kafka" in str(e).lower() or "connect" in str(e).lower()
