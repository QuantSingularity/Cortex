import json
from datetime import datetime, timezone

import redis.asyncio as aioredis
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import FeatureGroup, FeatureValue, get_db
from ..redis_client import get_redis, make_online_key
from ..schemas import FeatureWriteRequest

router = APIRouter()


@router.post("/{group_name}/push", status_code=201)
async def push_features(
    group_name: str,
    body: FeatureWriteRequest,
    db: AsyncSession = Depends(get_db),
    r: aioredis.Redis = Depends(get_redis),
):
    grp = await db.execute(select(FeatureGroup).where(FeatureGroup.name == group_name))
    if not grp.scalar_one_or_none():
        raise HTTPException(
            status_code=404, detail=f"Feature group '{group_name}' not found"
        )

    ts = body.event_timestamp or datetime.now(timezone.utc)

    # Write to offline (postgres)
    rows = [
        FeatureValue(
            feature_group=group_name,
            entity_id=body.entity_id,
            feature_name=k,
            feature_value=str(v),
            event_timestamp=ts,
        )
        for k, v in body.features.items()
    ]
    db.add_all(rows)
    await db.commit()

    # Write to online (redis) — latest values
    redis_key = make_online_key(group_name, body.entity_id)
    await r.hset(
        redis_key, mapping={k: json.dumps(v) for k, v in body.features.items()}
    )
    await r.expire(redis_key, 86400 * 7)  # 7-day TTL

    return {
        "status": "ok",
        "entity_id": body.entity_id,
        "features_written": len(body.features),
    }


@router.get("/{group_name}/history")
async def get_feature_history(
    group_name: str,
    entity_id: str,
    feature_name: str | None = None,
    limit: int = 100,
    db: AsyncSession = Depends(get_db),
):
    conditions = [
        FeatureValue.feature_group == group_name,
        FeatureValue.entity_id == entity_id,
    ]
    if feature_name:
        conditions.append(FeatureValue.feature_name == feature_name)

    result = await db.execute(
        select(FeatureValue)
        .where(and_(*conditions))
        .order_by(FeatureValue.event_timestamp.desc())
        .limit(limit)
    )
    rows = result.scalars().all()
    return [
        {
            "feature_name": r.feature_name,
            "feature_value": r.feature_value,
            "event_timestamp": r.event_timestamp,
        }
        for r in rows
    ]
