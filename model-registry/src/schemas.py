from datetime import datetime
from typing import Any, Dict, Optional

from pydantic import BaseModel, Field


class RegisteredModelCreate(BaseModel):
    name: str
    description: Optional[str] = None
    tags: Dict[str, Any] = {}


class RegisteredModelResponse(BaseModel):
    id: int
    name: str
    description: Optional[str]
    tags: Dict[str, Any]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ModelVersionCreate(BaseModel):
    version: str
    artifact_uri: str
    framework: Optional[str] = None
    python_version: Optional[str] = None
    description: Optional[str] = None
    tags: Dict[str, Any] = {}
    metrics: Dict[str, float] = {}
    params: Dict[str, Any] = {}


class ModelVersionUpdate(BaseModel):
    stage: Optional[str] = Field(None, pattern="^(staging|production|archived)$")
    description: Optional[str] = None
    tags: Optional[Dict[str, Any]] = None
    metrics: Optional[Dict[str, float]] = None


class ModelVersionResponse(BaseModel):
    id: int
    model_name: str
    version: str
    stage: str
    artifact_uri: str
    framework: Optional[str]
    python_version: Optional[str]
    description: Optional[str]
    tags: Dict[str, Any]
    metrics: Dict[str, Any]
    params: Dict[str, Any]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class MetricLogRequest(BaseModel):
    metric_name: str
    metric_value: float
    step: int = 0


class MetricHistoryResponse(BaseModel):
    metric_name: str
    metric_value: float
    step: int
    timestamp: datetime

    class Config:
        from_attributes = True
