from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import ModelMetricsHistory, ModelVersion, get_db
from ..schemas import MetricHistoryResponse, MetricLogRequest

router = APIRouter()


@router.post("/{model_name}/versions/{version}/metrics", status_code=201)
async def log_metric(
    model_name: str,
    version: str,
    body: MetricLogRequest,
    db: AsyncSession = Depends(get_db),
):
    mv_result = await db.execute(
        select(ModelVersion).where(
            ModelVersion.model_name == model_name,
            ModelVersion.version == version,
        )
    )
    mv = mv_result.scalar_one_or_none()
    if not mv:
        raise HTTPException(
            404, f"Version '{version}' not found for model '{model_name}'"
        )

    # Update summary metrics on version
    current_metrics = dict(mv.metrics or {})
    current_metrics[body.metric_name] = body.metric_value
    mv.metrics = current_metrics

    # Append to history
    record = ModelMetricsHistory(
        model_name=model_name,
        version=version,
        metric_name=body.metric_name,
        metric_value=body.metric_value,
        step=body.step,
    )
    db.add(record)
    await db.commit()
    return {"status": "logged", "metric": body.metric_name, "value": body.metric_value}


@router.get(
    "/{model_name}/versions/{version}/metrics",
    response_model=list[MetricHistoryResponse],
)
async def get_metric_history(
    model_name: str,
    version: str,
    metric_name: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    q = select(ModelMetricsHistory).where(
        ModelMetricsHistory.model_name == model_name,
        ModelMetricsHistory.version == version,
    )
    if metric_name:
        q = q.where(ModelMetricsHistory.metric_name == metric_name)
    result = await db.execute(q.order_by(ModelMetricsHistory.step))
    return result.scalars().all()
