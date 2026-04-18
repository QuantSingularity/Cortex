"""
Kafka-based feature publisher.
Use this for high-throughput, low-latency feature streaming
instead of the HTTP push endpoint.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional

logger = logging.getLogger("cortex.sdk.kafka")


class KafkaFeaturePublisher:
    """
    Publishes feature events directly to Kafka.

    Use when you need:
    - Sub-millisecond publishing latency
    - Very high throughput (>10k events/sec)
    - Decoupled, fire-and-forget feature ingestion

    Examples
    --------
        publisher = KafkaFeaturePublisher("kafka:9092")
        publisher.publish(
            model_name="fraud_model",
            feature_group="user_features",
            entity_id="u_123",
            features={"amount": 250.0, "hour": 14},
        )
        publisher.close()
    """

    def __init__(
        self,
        bootstrap_servers: str,
        topic: str = "cortex.features",
    ):
        try:
            from kafka import KafkaProducer

            self._producer = KafkaProducer(
                bootstrap_servers=bootstrap_servers,
                value_serializer=lambda v: json.dumps(v).encode("utf-8"),
                acks="all",
                retries=3,
            )
            self._topic = topic
            logger.info(f"Kafka producer connected to {bootstrap_servers}")
        except ImportError:
            raise ImportError(
                "kafka-python is required for KafkaFeaturePublisher. "
                "Install it: pip install kafka-python"
            )

    def publish(
        self,
        model_name: str,
        feature_group: str,
        entity_id: str,
        features: Dict[str, Any],
        version: str = "latest",
        event_timestamp: Optional[datetime] = None,
    ) -> None:
        ts = (event_timestamp or datetime.now(timezone.utc)).isoformat()
        for feature_name, value in features.items():
            event = {
                "model_name": model_name,
                "feature_group": feature_group,
                "entity_id": entity_id,
                "feature_name": feature_name,
                "value": value,
                "version": version,
                "event_timestamp": ts,
            }
            self._producer.send(self._topic, value=event)

    def publish_batch(
        self,
        model_name: str,
        feature_group: str,
        records: list[Dict[str, Any]],
        version: str = "latest",
    ) -> int:
        """
        Publish multiple feature records at once.
        Each record must have: entity_id, features (dict).
        Returns number of events published.
        """
        count = 0
        for record in records:
            self.publish(
                model_name=model_name,
                feature_group=feature_group,
                entity_id=record["entity_id"],
                features=record["features"],
                version=version,
            )
            count += len(record["features"])
        self._producer.flush()
        return count

    def close(self) -> None:
        self._producer.flush()
        self._producer.close()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()
