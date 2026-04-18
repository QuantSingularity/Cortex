"""
Cortex Serving Service
Real-time model inference with latency tracking, caching, and Prometheus metrics.
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from prometheus_client import Counter, Gauge, Histogram
from prometheus_fastapi_instrumentator import Instrumentator

from .database import init_db
from .model_cache import warm_cache
from .routers import deployments, inference

logging.basicConfig(level="INFO")
logger = logging.getLogger("cortex.serving")

# ─── Prometheus Metrics ────────────────────────────────────────────────────────
PREDICTIONS_TOTAL = Counter(
    "cortex_predictions_total",
    "Total prediction requests",
    ["model_name", "version", "status"],
)
INFERENCE_LATENCY = Histogram(
    "cortex_inference_duration_seconds",
    "Inference request latency in seconds",
    ["model_name", "version"],
    buckets=[0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5],
)
ACTIVE_MODELS = Gauge(
    "cortex_active_deployed_models", "Number of currently deployed models"
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting Cortex Serving Layer...")
    await init_db()
    await warm_cache()
    yield
    logger.info("Shutting down Cortex Serving Layer...")


app = FastAPI(
    title="Cortex Serving",
    description="Real-time model inference and deployment management",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"]
)
Instrumentator().instrument(app).expose(app)

app.include_router(inference.router, prefix="/predict", tags=["Inference"])
app.include_router(deployments.router, prefix="/deployments", tags=["Deployments"])


@app.get("/health")
async def health():
    return {"status": "ok", "service": "cortex-serving"}
