"""
Cortex Model Registry Service
Stores model versions, metadata, performance metrics, and manages stage transitions.
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from prometheus_client import Gauge
from prometheus_fastapi_instrumentator import Instrumentator

from .database import init_db
from .routers import metrics, models, versions

logging.basicConfig(level="INFO")
logger = logging.getLogger("cortex.model-registry")

MODELS_IN_PRODUCTION = Gauge(
    "cortex_models_in_production",
    "Number of model versions currently in production stage",
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting Cortex Model Registry...")
    await init_db()
    yield
    logger.info("Shutting down Cortex Model Registry...")


app = FastAPI(
    title="Cortex Model Registry",
    description="Versioned model registry with metadata and metrics tracking",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"]
)
Instrumentator().instrument(app).expose(app)

app.include_router(models.router, prefix="/models", tags=["Models"])
app.include_router(versions.router, prefix="/models", tags=["Versions"])
app.include_router(metrics.router, prefix="/models", tags=["Metrics"])


@app.get("/health")
async def health():
    return {"status": "ok", "service": "cortex-model-registry"}
