"""
Kafka consumer for real-time drift monitoring.
Listens on cortex.features topic, accumulates a rolling window of values
per (model_name, feature_name), and triggers drift checks periodically.
"""

import asyncio
import json
import logging
import os
from collections import defaultdict

from aiokafka import AIOKafkaConsumer

logger = logging.getLogger("cortex.drift-detection.kafka")

KAFKA_BOOTSTRAP = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "kafka:29092")
KAFKA_TOPIC = os.getenv("KAFKA_FEATURE_TOPIC", "cortex.features")
WINDOW_SIZE = int(os.getenv("DRIFT_WINDOW_SIZE", "500"))  # samples before auto-check
KS_THRESHOLD = float(os.getenv("KS_THRESHOLD", "0.05"))
PSI_THRESHOLD = float(os.getenv("PSI_THRESHOLD", "0.20"))

# Rolling buffer: {(model_name, feature_name): [values]}
_window: dict = defaultdict(list)


async def _consume():
    consumer = AIOKafkaConsumer(
        KAFKA_TOPIC,
        bootstrap_servers=KAFKA_BOOTSTRAP,
        group_id="cortex-drift-detection",
        value_deserializer=lambda m: json.loads(m.decode("utf-8")),
        auto_offset_reset="latest",
    )
    await consumer.start()
    logger.info(f"Drift Kafka consumer started — topic: {KAFKA_TOPIC}")

    try:
        async for msg in consumer:
            try:
                event = msg.value
                model_name = event.get("model_name")
                feature_name = event.get("feature_name")
                value = event.get("value")

                if not all([model_name, feature_name, value is not None]):
                    continue

                key = (model_name, feature_name)
                _window[key].append(float(value))

                # Once window is full, trigger a drift check
                if len(_window[key]) >= WINDOW_SIZE:
                    current_samples = _window[key][:WINDOW_SIZE]
                    _window[key] = _window[key][WINDOW_SIZE:]  # slide window

                    version = event.get("version", "latest")
                    asyncio.create_task(
                        _auto_check(model_name, version, feature_name, current_samples)
                    )

            except Exception as e:
                logger.error(f"Kafka consumer error: {e}")
    finally:
        await consumer.stop()


async def _auto_check(
    model_name: str,
    version: str,
    feature_name: str,
    current_samples: list,
):
    """Auto-trigger drift check against stored reference via internal HTTP call."""
    import httpx

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            await client.post(
                "http://localhost:8004/drift/check",
                json={
                    "model_name": model_name,
                    "version": version,
                    "feature_name": feature_name,
                    "current_samples": current_samples,
                    "ks_threshold": KS_THRESHOLD,
                    "psi_threshold": PSI_THRESHOLD,
                },
            )
        logger.info(
            f"Auto drift check: {model_name}/{feature_name} ({len(current_samples)} samples)"
        )
    except Exception as e:
        logger.warning(f"Auto drift check failed: {e}")


async def _run_guarded():
    """Keep the consumer alive across broker outages instead of dying with an
    unretrieved background-task exception when Kafka is unreachable."""
    while True:
        try:
            await _consume()
        except asyncio.CancelledError:
            raise
        except Exception as e:
            logger.warning(f"Drift Kafka consumer unavailable, retrying in 10s: {e}")
            await asyncio.sleep(10)


async def start_kafka_consumer():
    asyncio.create_task(_run_guarded())
