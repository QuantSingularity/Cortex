"""
Cortex Feature Store Service
Lightweight custom feature store backed by Redis (online) and PostgreSQL (offline).
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from prometheus_client import Counter, Histogram
from prometheus_fastapi_instrumentator import Instrumentator

from .database import init_db
from .kafka_consumer import start_kafka_consumer
from .routers import feature_groups, features, online_store

logging.basicConfig(level="INFO")
logger = logging.getLogger("cortex.feature-store")

# ─── Prometheus Metrics ────────────────────────────────────────────────────────
FEATURE_WRITES = Counter(
    "cortex_feature_writes_total", "Total feature writes", ["feature_group"]
)
FEATURE_READS = Counter(
    "cortex_feature_reads_total", "Total feature reads", ["feature_group"]
)
WRITE_LATENCY = Histogram(
    "cortex_feature_write_duration_seconds", "Feature write latency"
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting Cortex Feature Store...")
    await init_db()
    await start_kafka_consumer()
    yield
    logger.info("Shutting down Cortex Feature Store...")


app = FastAPI(
    title="Cortex Feature Store",
    description="Online + offline feature store for Cortex MLOps Backbone",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

Instrumentator().instrument(app).expose(app)

app.include_router(
    feature_groups.router, prefix="/feature-groups", tags=["Feature Groups"]
)
app.include_router(features.router, prefix="/features", tags=["Features"])
app.include_router(online_store.router, prefix="/online", tags=["Online Store"])


@app.get("/health")
async def health():
    return {"status": "ok", "service": "cortex-feature-store"}
