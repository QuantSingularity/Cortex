import logging
import os
from datetime import datetime, timezone
from typing import Any, Dict, Optional

import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import ModelDeployment, get_db
from ..model_cache import load_model

logger = logging.getLogger("cortex.serving.deployments")
router = APIRouter()

MODEL_REGISTRY_URL = os.getenv("MODEL_REGISTRY_URL", "http://model-registry:8002")


class DeployRequest(BaseModel):
    model_name: str
    version: str
    config: Dict[str, Any] = {}


class DeployResponse(BaseModel):
    id: int
    model_name: str
    version: str
    artifact_uri: str
    framework: Optional[str]
    is_active: bool
    deployed_at: datetime

    class Config:
        from_attributes = True


@router.post("/", response_model=DeployResponse, status_code=201)
async def deploy_model(body: DeployRequest, db: AsyncSession = Depends(get_db)):
    """Deploy a model version from the registry into the serving layer."""
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get(
            f"{MODEL_REGISTRY_URL}/models/{body.model_name}/versions/{body.version}"
        )
        if resp.status_code == 404:
            raise HTTPException(
                404, f"Model '{body.model_name}' v{body.version} not in registry"
            )
        if resp.status_code != 200:
            raise HTTPException(502, "Model registry unavailable")
        version_info = resp.json()

    # Deactivate previous deployments
    prev = await db.execute(
        select(ModelDeployment).where(
            ModelDeployment.model_name == body.model_name,
            ModelDeployment.is_active == True,
        )
    )
    for old in prev.scalars().all():
        old.is_active = False
        old.updated_at = datetime.now(timezone.utc)

    deployment = ModelDeployment(
        model_name=body.model_name,
        version=body.version,
        artifact_uri=version_info["artifact_uri"],
        framework=version_info.get("framework", "mock"),
        is_active=True,
        config=body.config,
    )
    db.add(deployment)
    await db.commit()
    await db.refresh(deployment)

    # Load into memory
    await load_model(body.model_name, version_info)
    logger.info(f"Deployed {body.model_name} v{body.version}")

    return deployment


@router.get("/", response_model=list[DeployResponse])
async def list_deployments(
    active_only: bool = True, db: AsyncSession = Depends(get_db)
):
    q = select(ModelDeployment)
    if active_only:
        q = q.where(ModelDeployment.is_active == True)
    result = await db.execute(q.order_by(ModelDeployment.deployed_at.desc()))
    return result.scalars().all()


@router.delete("/{model_name}", status_code=204)
async def undeploy_model(model_name: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(ModelDeployment).where(
            ModelDeployment.model_name == model_name,
            ModelDeployment.is_active == True,
        )
    )
    dep = result.scalar_one_or_none()
    if not dep:
        raise HTTPException(404, f"No active deployment found for '{model_name}'")
    dep.is_active = False
    dep.updated_at = datetime.now(timezone.utc)
    await db.commit()
