from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import FeatureDefinition, FeatureGroup, get_db
from ..schemas import (
    FeatureDefinitionCreate,
    FeatureDefinitionResponse,
    FeatureGroupCreate,
    FeatureGroupResponse,
)

router = APIRouter()


@router.post("/", response_model=FeatureGroupResponse, status_code=201)
async def create_feature_group(
    body: FeatureGroupCreate, db: AsyncSession = Depends(get_db)
):
    existing = await db.execute(
        select(FeatureGroup).where(FeatureGroup.name == body.name)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=409, detail=f"Feature group '{body.name}' already exists"
        )
    fg = FeatureGroup(**body.model_dump())
    db.add(fg)
    await db.commit()
    await db.refresh(fg)
    return fg


@router.get("/", response_model=list[FeatureGroupResponse])
async def list_feature_groups(db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(FeatureGroup).order_by(FeatureGroup.created_at.desc())
    )
    return result.scalars().all()


@router.get("/{name}", response_model=FeatureGroupResponse)
async def get_feature_group(name: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(FeatureGroup).where(FeatureGroup.name == name))
    fg = result.scalar_one_or_none()
    if not fg:
        raise HTTPException(status_code=404, detail=f"Feature group '{name}' not found")
    return fg


@router.delete("/{name}", status_code=204)
async def delete_feature_group(name: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(FeatureGroup).where(FeatureGroup.name == name))
    fg = result.scalar_one_or_none()
    if not fg:
        raise HTTPException(status_code=404, detail=f"Feature group '{name}' not found")
    await db.delete(fg)
    await db.commit()


@router.post(
    "/{group_name}/features", response_model=FeatureDefinitionResponse, status_code=201
)
async def add_feature_definition(
    group_name: str, body: FeatureDefinitionCreate, db: AsyncSession = Depends(get_db)
):
    grp_result = await db.execute(
        select(FeatureGroup).where(FeatureGroup.name == group_name)
    )
    if not grp_result.scalar_one_or_none():
        raise HTTPException(
            status_code=404, detail=f"Feature group '{group_name}' not found"
        )

    fd = FeatureDefinition(feature_group=group_name, **body.model_dump())
    db.add(fd)
    await db.commit()
    await db.refresh(fd)
    return fd


@router.get("/{group_name}/features", response_model=list[FeatureDefinitionResponse])
async def list_feature_definitions(group_name: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(FeatureDefinition).where(FeatureDefinition.feature_group == group_name)
    )
    return result.scalars().all()
