from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import ModelVersion, RegisteredModel, get_db
from ..schemas import ModelVersionCreate, ModelVersionResponse, ModelVersionUpdate

router = APIRouter()

VALID_STAGES = {"staging", "production", "archived"}


@router.post(
    "/{model_name}/versions", response_model=ModelVersionResponse, status_code=201
)
async def create_version(
    model_name: str,
    body: ModelVersionCreate,
    db: AsyncSession = Depends(get_db),
):
    m = await db.execute(
        select(RegisteredModel).where(RegisteredModel.name == model_name)
    )
    if not m.scalar_one_or_none():
        raise HTTPException(404, f"Model '{model_name}' not found")

    existing = await db.execute(
        select(ModelVersion).where(
            ModelVersion.model_name == model_name,
            ModelVersion.version == body.version,
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            409, f"Version '{body.version}' already exists for '{model_name}'"
        )

    mv = ModelVersion(model_name=model_name, **body.model_dump())
    db.add(mv)
    await db.commit()
    await db.refresh(mv)
    return mv


@router.get("/{model_name}/versions", response_model=list[ModelVersionResponse])
async def list_versions(
    model_name: str,
    stage: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    q = select(ModelVersion).where(ModelVersion.model_name == model_name)
    if stage:
        q = q.where(ModelVersion.stage == stage)
    result = await db.execute(q.order_by(ModelVersion.created_at.desc()))
    return result.scalars().all()


@router.get("/{model_name}/versions/{version}", response_model=ModelVersionResponse)
async def get_version(
    model_name: str, version: str, db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(ModelVersion).where(
            ModelVersion.model_name == model_name,
            ModelVersion.version == version,
        )
    )
    mv = result.scalar_one_or_none()
    if not mv:
        raise HTTPException(
            404, f"Version '{version}' not found for model '{model_name}'"
        )
    return mv


@router.patch("/{model_name}/versions/{version}", response_model=ModelVersionResponse)
async def update_version(
    model_name: str,
    version: str,
    body: ModelVersionUpdate,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(ModelVersion).where(
            ModelVersion.model_name == model_name,
            ModelVersion.version == version,
        )
    )
    mv = result.scalar_one_or_none()
    if not mv:
        raise HTTPException(
            404, f"Version '{version}' not found for model '{model_name}'"
        )

    updates = body.model_dump(exclude_none=True)
    for k, v in updates.items():
        setattr(mv, k, v)
    mv.updated_at = datetime.now(timezone.utc)

    await db.commit()
    await db.refresh(mv)
    return mv


@router.post(
    "/{model_name}/versions/{version}/promote", response_model=ModelVersionResponse
)
async def promote_to_production(
    model_name: str,
    version: str,
    db: AsyncSession = Depends(get_db),
):
    """Promote a version to production, archiving any existing production version."""
    # Archive existing production
    prod_result = await db.execute(
        select(ModelVersion).where(
            ModelVersion.model_name == model_name,
            ModelVersion.stage == "production",
        )
    )
    for existing_prod in prod_result.scalars().all():
        existing_prod.stage = "archived"
        existing_prod.updated_at = datetime.now(timezone.utc)

    # Promote target
    target_result = await db.execute(
        select(ModelVersion).where(
            ModelVersion.model_name == model_name,
            ModelVersion.version == version,
        )
    )
    mv = target_result.scalar_one_or_none()
    if not mv:
        raise HTTPException(404, f"Version '{version}' not found")

    mv.stage = "production"
    mv.updated_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(mv)
    return mv


@router.get("/{model_name}/production", response_model=ModelVersionResponse)
async def get_production_version(model_name: str, db: AsyncSession = Depends(get_db)):
    """Get the current production version of a model."""
    result = await db.execute(
        select(ModelVersion).where(
            ModelVersion.model_name == model_name,
            ModelVersion.stage == "production",
        )
    )
    mv = result.scalar_one_or_none()
    if not mv:
        raise HTTPException(
            404, f"No production version found for model '{model_name}'"
        )
    return mv
