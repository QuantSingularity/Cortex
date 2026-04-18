import hashlib
import json
import logging
import time
from typing import Any, Dict, List

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import PredictionLog, get_db
from ..main import INFERENCE_LATENCY, PREDICTIONS_TOTAL
from ..model_cache import get_model

logger = logging.getLogger("cortex.serving.inference")
router = APIRouter()


class PredictRequest(BaseModel):
    features: List[Dict[str, Any]]
    return_proba: bool = False


class PredictResponse(BaseModel):
    model_name: str
    version: str
    predictions: List[Any]
    latency_ms: float


@router.post("/{model_name}", response_model=PredictResponse)
async def predict(
    model_name: str,
    body: PredictRequest,
    db: AsyncSession = Depends(get_db),
):
    cached = get_model(model_name)
    if not cached:
        raise HTTPException(404, f"Model '{model_name}' not loaded. Deploy it first.")

    model = cached["model"]
    version = cached["version"]

    input_hash = hashlib.sha256(
        json.dumps(body.features, sort_keys=True).encode()
    ).hexdigest()[:16]

    start = time.perf_counter()
    status = "success"
    try:
        feature_arrays = [list(f.values()) for f in body.features]
        if body.return_proba and hasattr(model, "predict_proba"):
            predictions = model.predict_proba(feature_arrays)
        else:
            predictions = model.predict(feature_arrays)
    except Exception as e:
        status = "error"
        logger.error(f"Inference error for {model_name}: {e}")
        raise HTTPException(500, f"Inference failed: {e}")
    finally:
        elapsed_ms = (time.perf_counter() - start) * 1000
        PREDICTIONS_TOTAL.labels(
            model_name=model_name, version=version, status=status
        ).inc()
        INFERENCE_LATENCY.labels(model_name=model_name, version=version).observe(
            elapsed_ms / 1000
        )

        log = PredictionLog(
            model_name=model_name,
            version=version,
            input_hash=input_hash,
            latency_ms=int(elapsed_ms),
            status=status,
        )
        db.add(log)
        await db.commit()

    return PredictResponse(
        model_name=model_name,
        version=version,
        predictions=(
            predictions if isinstance(predictions, list) else predictions.tolist()
        ),
        latency_ms=round(elapsed_ms, 2),
    )


@router.get("/loaded", summary="List all models currently loaded in cache")
async def list_loaded():
    from ..model_cache import list_loaded_models

    return list_loaded_models()
