from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import RegisteredModel, get_db
from ..schemas import RegisteredModelCreate, RegisteredModelResponse

router = APIRouter()


@router.post("/", response_model=RegisteredModelResponse, status_code=201)
async def create_model(body: RegisteredModelCreate, db: AsyncSession = Depends(get_db)):
    existing = await db.execute(
        select(RegisteredModel).where(RegisteredModel.name == body.name)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(409, f"Model '{body.name}' already registered")
    model = RegisteredModel(**body.model_dump())
    db.add(model)
    await db.commit()
    await db.refresh(model)
    return model


@router.get("/", response_model=list[RegisteredModelResponse])
async def list_models(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(RegisteredModel).order_by(RegisteredModel.name))
    return result.scalars().all()


@router.get("/{model_name}", response_model=RegisteredModelResponse)
async def get_model(model_name: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(RegisteredModel).where(RegisteredModel.name == model_name)
    )
    m = result.scalar_one_or_none()
    if not m:
        raise HTTPException(404, f"Model '{model_name}' not found")
    return m


@router.delete("/{model_name}", status_code=204)
async def delete_model(model_name: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(RegisteredModel).where(RegisteredModel.name == model_name)
    )
    m = result.scalar_one_or_none()
    if not m:
        raise HTTPException(404, f"Model '{model_name}' not found")
    await db.delete(m)
    await db.commit()
