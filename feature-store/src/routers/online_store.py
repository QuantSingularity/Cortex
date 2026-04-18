import json
from datetime import datetime, timezone

import redis.asyncio as aioredis
from fastapi import APIRouter, Depends

from ..redis_client import get_redis, make_online_key
from ..schemas import FeatureReadRequest, FeatureReadResponse

router = APIRouter()


@router.post("/{group_name}/get", response_model=list[FeatureReadResponse])
async def get_online_features(
    group_name: str,
    body: FeatureReadRequest,
    r: aioredis.Redis = Depends(get_redis),
):
    """
    Low-latency online feature retrieval from Redis.
    Returns latest feature values for each requested entity_id.
    """
    results = []
    for entity_id in body.entity_ids:
        redis_key = make_online_key(group_name, entity_id)
        raw = await r.hgetall(redis_key)
        if not raw:
            features = {}
        else:
            if body.feature_names:
                features = {
                    k: json.loads(v) for k, v in raw.items() if k in body.feature_names
                }
            else:
                features = {k: json.loads(v) for k, v in raw.items()}

        results.append(
            FeatureReadResponse(
                entity_id=entity_id,
                features=features,
                retrieved_at=datetime.now(timezone.utc),
            )
        )
    return results
