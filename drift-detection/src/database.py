import os
from datetime import datetime, timezone

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    Column,
    DateTime,
    Float,
    Integer,
    String,
)
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

DATABASE_URL = os.getenv(
    "DATABASE_URL", "postgresql://cortex:cortex_secret@postgres:5432/cortex"
)
ASYNC_URL = DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://")

engine = create_async_engine(ASYNC_URL, echo=False, pool_pre_ping=True)
AsyncSessionLocal = async_sessionmaker(
    engine, expire_on_commit=False, class_=AsyncSession
)


class Base(DeclarativeBase):
    pass


class ReferenceDistribution(Base):
    """Baseline (training-time) feature distribution stored as histogram bins."""

    __tablename__ = "reference_distributions"
    id = Column(Integer, primary_key=True)
    model_name = Column(String(128), nullable=False)
    version = Column(String(64), nullable=False)
    feature_name = Column(String(128), nullable=False)
    samples = Column(JSON, nullable=False)  # list of float values (capped at 10k)
    bin_edges = Column(JSON)  # for PSI histogram
    bin_counts = Column(JSON)
    sample_count = Column(Integer, default=0)
    created_at = Column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at = Column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )


class DriftReport(Base):
    __tablename__ = "drift_reports"
    id = Column(BigInteger, primary_key=True)
    model_name = Column(String(128), nullable=False)
    version = Column(String(64), nullable=False)
    feature_name = Column(String(128), nullable=False)
    test_type = Column(String(32), nullable=False)
    statistic = Column(Float, nullable=False)
    p_value = Column(Float)
    psi_score = Column(Float)
    drift_detected = Column(Boolean, nullable=False, default=False)
    threshold = Column(Float, nullable=False)
    sample_size = Column(Integer)
    reported_at = Column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )


async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def get_db():
    async with AsyncSessionLocal() as session:
        yield session
