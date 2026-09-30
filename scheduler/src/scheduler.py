"""
APScheduler integration.
- Loads scheduled triggers from DB on startup
- Executes retraining jobs (mock executor - plug in your training code here)
- Exposes add/remove schedule APIs
"""

import logging
import os
from datetime import datetime, timezone

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from .database import AsyncSessionLocal, RetrainingJob, ScheduledTrigger

logger = logging.getLogger("cortex.scheduler.apscheduler")

_scheduler = AsyncIOScheduler()

MODEL_REGISTRY_URL = os.getenv("MODEL_REGISTRY_URL", "http://model-registry:8002")


async def _execute_retraining(model_name: str, trigger_type: str, metadata: dict = {}):
    """
    Execute a retraining job.
    In production: call your training pipeline, update model registry with new version.
    Here we implement the job lifecycle management and a mock training step.
    """
    async with AsyncSessionLocal() as db:
        job = RetrainingJob(
            model_name=model_name,
            trigger_type=trigger_type,
            status="running",
            started_at=datetime.now(timezone.utc),
            metadata_=metadata,
        )
        db.add(job)
        await db.commit()
        await db.refresh(job)
        job_id = job.id

    logger.info(
        f"Retraining job #{job_id} started: {model_name} (trigger={trigger_type})"
    )

    try:
        # ── PLUG YOUR TRAINING PIPELINE HERE ──────────────────────────────────
        # Example: call a training script, update model artifact, register new version
        #
        # import subprocess
        # result = subprocess.run(
        #     ["python", "train.py", "--model", model_name],
        #     capture_output=True, check=True
        # )
        #
        # For now: simulate training with a 2-second sleep
        import asyncio

        await asyncio.sleep(2)

        new_version = f"auto-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}"
        logger.info(f"Retraining job #{job_id} completed. New version: {new_version}")

        # Register new version with model registry
        import httpx

        try:
            async with httpx.AsyncClient(timeout=10) as client:
                await client.post(
                    f"{MODEL_REGISTRY_URL}/models/{model_name}/versions",
                    json={
                        "version": new_version,
                        "artifact_uri": f"mock://models/{model_name}/{new_version}",
                        "framework": "mock",
                        "description": f"Auto-retrained ({trigger_type})",
                        "tags": {"trigger": trigger_type, **metadata},
                    },
                )
        except Exception as e:
            logger.warning(f"Could not register new version in registry: {e}")

        async with AsyncSessionLocal() as db:
            from sqlalchemy import select

            result = await db.execute(
                select(RetrainingJob).where(RetrainingJob.id == job_id)
            )
            j = result.scalar_one()
            j.status = "success"
            j.completed_at = datetime.now(timezone.utc)
            j.metadata_ = {**(j.metadata_ or {}), "new_version": new_version}
            await db.commit()

        from .main import RETRAINING_JOBS_TOTAL

        RETRAINING_JOBS_TOTAL.labels(status="success").inc()

    except Exception as e:
        logger.error(f"Retraining job #{job_id} failed: {e}")
        async with AsyncSessionLocal() as db:
            from sqlalchemy import select

            result = await db.execute(
                select(RetrainingJob).where(RetrainingJob.id == job_id)
            )
            j = result.scalar_one()
            j.status = "failed"
            j.completed_at = datetime.now(timezone.utc)
            j.error_message = str(e)
            await db.commit()

        from .main import RETRAINING_JOBS_TOTAL

        RETRAINING_JOBS_TOTAL.labels(status="failed").inc()


async def start_scheduler():
    """Load schedules from DB and start APScheduler."""
    async with AsyncSessionLocal() as db:
        from sqlalchemy import select

        result = await db.execute(
            select(ScheduledTrigger).where(ScheduledTrigger.enabled == "true")
        )
        triggers = result.scalars().all()

    for t in triggers:
        _add_cron_job(t.model_name, t.cron_expr)
        logger.info(f"Loaded schedule for {t.model_name}: {t.cron_expr}")

    _scheduler.start()
    logger.info("APScheduler started")


async def shutdown_scheduler():
    if _scheduler.running:
        _scheduler.shutdown(wait=False)


def _add_cron_job(model_name: str, cron_expr: str):
    parts = cron_expr.split()
    if len(parts) != 5:
        logger.warning(
            f"Invalid cron expression '{cron_expr}' for {model_name} - skipping"
        )
        return

    minute, hour, day, month, day_of_week = parts
    _scheduler.add_job(
        _execute_retraining,
        CronTrigger(
            minute=minute,
            hour=hour,
            day=day,
            month=month,
            day_of_week=day_of_week,
        ),
        args=[model_name, "scheduled", {}],
        id=f"retrain_{model_name}",
        replace_existing=True,
    )


async def register_schedule(model_name: str, cron_expr: str):
    """Register or update a cron schedule for a model."""
    _add_cron_job(model_name, cron_expr)

    async with AsyncSessionLocal() as db:
        from sqlalchemy import select

        result = await db.execute(
            select(ScheduledTrigger).where(ScheduledTrigger.model_name == model_name)
        )
        existing = result.scalar_one_or_none()
        if existing:
            existing.cron_expr = cron_expr
            existing.enabled = "true"
            existing.updated_at = datetime.now(timezone.utc)
        else:
            db.add(ScheduledTrigger(model_name=model_name, cron_expr=cron_expr))
        await db.commit()


async def trigger_now(
    model_name: str, trigger_type: str = "manual", metadata: dict = {}
):
    """Immediately enqueue a retraining job (non-blocking)."""
    import asyncio

    asyncio.create_task(_execute_retraining(model_name, trigger_type, metadata))
