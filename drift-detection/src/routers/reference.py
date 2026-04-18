from datetime import datetime, timezone

import numpy as np
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import ReferenceDistribution, get_db
from ..schemas import ReferenceResponse, ReferenceUploadRequest

router = APIRouter()

MAX_STORED_SAMPLES = 10_000


@router.post("/", response_model=ReferenceResponse, status_code=201)
async def upload_reference(
    body: ReferenceUploadRequest, db: AsyncSession = Depends(get_db)
):
    """Upload reference (baseline) feature distribution for a model version."""
    existing = await db.execute(
        select(ReferenceDistribution).where(
            and_(
                ReferenceDistribution.model_name == body.model_name,
                ReferenceDistribution.version == body.version,
                ReferenceDistribution.feature_name == body.feature_name,
            )
        )
    )
    ref = existing.scalar_one_or_none()

    samples = body.samples[:MAX_STORED_SAMPLES]
    arr = np.array(samples)
    bin_edges = list(np.percentile(arr, np.linspace(0, 100, 11)))

    if ref:
        ref.samples = samples
        ref.bin_edges = [round(float(e), 6) for e in bin_edges]
        ref.bin_counts = []
        ref.sample_count = len(samples)
        ref.updated_at = datetime.now(timezone.utc)
    else:
        ref = ReferenceDistribution(
            model_name=body.model_name,
            version=body.version,
            feature_name=body.feature_name,
            samples=samples,
            bin_edges=[round(float(e), 6) for e in bin_edges],
            bin_counts=[],
            sample_count=len(samples),
        )
        db.add(ref)

    await db.commit()
    await db.refresh(ref)
    return ref


@router.get("/", response_model=list[ReferenceResponse])
async def list_references(
    model_name: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    q = select(ReferenceDistribution)
    if model_name:
        q = q.where(ReferenceDistribution.model_name == model_name)
    result = await db.execute(q.order_by(ReferenceDistribution.created_at.desc()))
    return result.scalars().all()


@router.delete("/{model_name}/{version}/{feature_name}", status_code=204)
async def delete_reference(
    model_name: str,
    version: str,
    feature_name: str,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(ReferenceDistribution).where(
            and_(
                ReferenceDistribution.model_name == model_name,
                ReferenceDistribution.version == version,
                ReferenceDistribution.feature_name == feature_name,
            )
        )
    )
    ref = result.scalar_one_or_none()
    if not ref:
        raise HTTPException(404, "Reference distribution not found")
    await db.delete(ref)
    await db.commit()
