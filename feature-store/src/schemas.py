from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class FeatureGroupCreate(BaseModel):
    name: str
    description: Optional[str] = None
    tags: Dict[str, Any] = {}


class FeatureGroupResponse(BaseModel):
    id: int
    name: str
    description: Optional[str]
    tags: Dict[str, Any]
    created_at: datetime

    class Config:
        from_attributes = True


class FeatureDefinitionCreate(BaseModel):
    name: str
    dtype: str = Field(..., pattern="^(float|int|string|bool)$")
    description: Optional[str] = None
    default_value: Optional[str] = None
    tags: Dict[str, Any] = {}


class FeatureDefinitionResponse(BaseModel):
    id: int
    feature_group: str
    name: str
    dtype: str
    description: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True


class FeatureWriteRequest(BaseModel):
    entity_id: str
    features: Dict[str, Any]
    event_timestamp: Optional[datetime] = None


class FeatureReadRequest(BaseModel):
    entity_ids: List[str]
    feature_names: Optional[List[str]] = None


class FeatureReadResponse(BaseModel):
    entity_id: str
    features: Dict[str, Any]
    retrieved_at: datetime
