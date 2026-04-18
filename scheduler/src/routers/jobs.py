from datetime import datetime
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import RetrainingJob, ScheduledTrigger, get_db
from ..scheduler import register_schedule, trigger_now

router = APIRouter()


class TriggerRequest(BaseModel):
    model_name: str
    trigger_type: str = "manual"
    metadata: Dict[str, Any] = {}


class ScheduleRequest(BaseModel):
    model_name: str
    cron_expr: str  # e.g. "0 2 * * *"  (daily at 2am)


class JobResponse(BaseModel):
    id: int
    model_name: str
    trigger_type: str
    status: str
    triggered_at: datetime
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    error_message: Optional[str]

    class Config:
        from_attributes = True


@router.post("/trigger", status_code=202)
async def trigger_retraining(body: TriggerRequest):
    """Immediately trigger a retraining job (async, non-blocking)."""
    await trigger_now(body.model_name, body.trigger_type, body.metadata)
    return {
        "status": "accepted",
        "message": f"Retraining job queued for '{body.model_name}'",
    }


@router.post("/schedule", status_code=201)
async def create_schedule(body: ScheduleRequest):
    """Register a cron-based retraining schedule for a model."""
    await register_schedule(body.model_name, body.cron_expr)
    return {
        "status": "scheduled",
        "model_name": body.model_name,
        "cron_expr": body.cron_expr,
    }


@router.get("/schedules")
async def list_schedules(db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(ScheduledTrigger).order_by(ScheduledTrigger.model_name)
    )
    rows = result.scalars().all()
    return [
        {
            "model_name": r.model_name,
            "cron_expr": r.cron_expr,
            "enabled": r.enabled,
            "created_at": r.created_at,
        }
        for r in rows
    ]


@router.get("/", response_model=list[JobResponse])
async def list_jobs(
    model_name: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = 50,
    db: AsyncSession = Depends(get_db),
):
    q = select(RetrainingJob)
    if model_name:
        q = q.where(RetrainingJob.model_name == model_name)
    if status:
        q = q.where(RetrainingJob.status == status)
    result = await db.execute(
        q.order_by(RetrainingJob.triggered_at.desc()).limit(limit)
    )
    return result.scalars().all()


@router.get("/{job_id}", response_model=JobResponse)
async def get_job(job_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(RetrainingJob).where(RetrainingJob.id == job_id))
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(404, f"Job #{job_id} not found")
    return job
