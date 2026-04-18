"""
Cortex Scheduler Service
Manages model retraining jobs triggered by:
  - Scheduled cron intervals (APScheduler)
  - Drift alerts from the drift-detection service
  - Manual triggers via REST API
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from prometheus_client import Counter, Gauge
from prometheus_fastapi_instrumentator import Instrumentator

from .database import init_db
from .routers import jobs
from .scheduler import shutdown_scheduler, start_scheduler

logging.basicConfig(level="INFO")
logger = logging.getLogger("cortex.scheduler")

RETRAINING_JOBS_TOTAL = Counter(
    "cortex_retraining_jobs_total",
    "Total retraining jobs by status",
    ["status"],
)
JOBS_RUNNING = Gauge(
    "cortex_retraining_jobs_running",
    "Currently running retraining jobs",
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting Cortex Scheduler...")
    await init_db()
    await start_scheduler()
    yield
    logger.info("Shutting down Cortex Scheduler...")
    await shutdown_scheduler()


app = FastAPI(
    title="Cortex Scheduler",
    description="Retraining job scheduler with drift-triggered and cron-based execution",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"]
)
Instrumentator().instrument(app).expose(app)

app.include_router(jobs.router, prefix="/jobs", tags=["Jobs"])


@app.get("/health")
async def health():
    return {"status": "ok", "service": "cortex-scheduler"}
