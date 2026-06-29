"""
Kafka consumer that ingests real-time feature events and writes them
to both the online (Redis) and offline (PostgreSQL) stores.
"""

import asyncio
import json
import logging
import os
from datetime import datetime, timezone

from aiokafka import AIOKafkaConsumer

logger = logging.getLogger("cortex.feature-store.kafka")

KAFKA_BOOTSTRAP = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "kafka:29092")
KAFKA_TOPIC = os.getenv("KAFKA_FEATURE_TOPIC", "cortex.features")


async def _consume():
    consumer = AIOKafkaConsumer(
        KAFKA_TOPIC,
        bootstrap_servers=KAFKA_BOOTSTRAP,
        group_id="cortex-feature-store",
        value_deserializer=lambda m: json.loads(m.decode("utf-8")),
        auto_offset_reset="latest",
    )
    await consumer.start()
    logger.info(f"Kafka consumer started — topic: {KAFKA_TOPIC}")

    try:
        async for msg in consumer:
            try:
                event = msg.value
                # Expected schema:
                # {
                #   "feature_group": "user_features",
                #   "entity_id": "user_123",
                #   "features": {"age": 34, "balance": 1500.0},
                #   "event_timestamp": "2024-01-01T00:00:00Z"  (optional)
                # }
                feature_group = event.get("feature_group")
                entity_id = event.get("entity_id")
                features = event.get("features", {})
                ts_raw = event.get("event_timestamp")
                ts = (
                    datetime.fromisoformat(ts_raw)
                    if ts_raw
                    else datetime.now(timezone.utc)
                )

                if not feature_group or not entity_id:
                    logger.warning(f"Skipping malformed event: {event}")
                    continue

                # Lazy import to avoid circular deps
                from .database import AsyncSessionLocal, FeatureValue
                from .redis_client import get_redis, make_online_key

                # Write to Redis
                r = await get_redis()
                redis_key = make_online_key(feature_group, entity_id)
                await r.hset(
                    redis_key, mapping={k: json.dumps(v) for k, v in features.items()}
                )
                await r.expire(redis_key, 86400 * 7)

                # Write to Postgres
                async with AsyncSessionLocal() as session:
                    rows = [
                        FeatureValue(
                            feature_group=feature_group,
                            entity_id=entity_id,
                            feature_name=k,
                            feature_value=str(v),
                            event_timestamp=ts,
                        )
                        for k, v in features.items()
                    ]
                    session.add_all(rows)
                    await session.commit()

                logger.debug(f"Ingested {len(features)} features for {entity_id}")

            except Exception as e:
                logger.error(f"Error processing Kafka message: {e}")

    finally:
        await consumer.stop()


async def _run_guarded():
    """Keep the consumer alive across broker outages instead of dying with an
    unretrieved background-task exception when Kafka is unreachable."""
    while True:
        try:
            await _consume()
        except asyncio.CancelledError:
            raise
        except Exception as e:
            logger.warning(
                f"Feature-store Kafka consumer unavailable, retrying in 10s: {e}"
            )
            await asyncio.sleep(10)


async def start_kafka_consumer():
    asyncio.create_task(_run_guarded())
