from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field


class ReferenceUploadRequest(BaseModel):
    model_name: str
    version: str
    feature_name: str
    samples: List[float] = Field(..., min_length=10, max_length=100_000)


class ReferenceResponse(BaseModel):
    id: int
    model_name: str
    version: str
    feature_name: str
    sample_count: int
    created_at: datetime

    class Config:
        from_attributes = True


class DriftCheckRequest(BaseModel):
    model_name: str
    version: str
    feature_name: str
    current_samples: List[float] = Field(..., min_length=10)
    ks_threshold: float = 0.05
    psi_threshold: float = 0.20


class DriftReportResponse(BaseModel):
    id: int
    model_name: str
    version: str
    feature_name: str
    test_type: str
    statistic: float
    p_value: Optional[float]
    psi_score: Optional[float]
    drift_detected: bool
    threshold: float
    sample_size: Optional[int]
    reported_at: datetime

    class Config:
        from_attributes = True
