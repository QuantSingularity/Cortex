import os
from datetime import datetime, timezone

from sqlalchemy import (
    JSON,
    BigInteger,
    Column,
    DateTime,
    Float,
    Integer,
    String,
    Text,
    UniqueConstraint,
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


class RegisteredModel(Base):
    __tablename__ = "registered_models"
    id = Column(Integer, primary_key=True)
    name = Column(String(128), unique=True, nullable=False)
    description = Column(Text)
    tags = Column(JSON, default={})
    created_at = Column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at = Column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )


class ModelVersion(Base):
    __tablename__ = "model_versions"
    __table_args__ = (UniqueConstraint("model_name", "version"),)
    id = Column(Integer, primary_key=True)
    model_name = Column(String(128), nullable=False)
    version = Column(String(64), nullable=False)
    stage = Column(String(32), nullable=False, default="staging")
    artifact_uri = Column(Text, nullable=False)
    framework = Column(String(64))
    python_version = Column(String(16))
    description = Column(Text)
    tags = Column(JSON, default={})
    metrics = Column(JSON, default={})
    params = Column(JSON, default={})
    created_at = Column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at = Column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )


class ModelMetricsHistory(Base):
    __tablename__ = "model_metrics_history"
    id = Column(BigInteger, primary_key=True)
    model_name = Column(String(128), nullable=False)
    version = Column(String(64), nullable=False)
    metric_name = Column(String(128), nullable=False)
    metric_value = Column(Float, nullable=False)
    step = Column(Integer, default=0)
    timestamp = Column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )


async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def get_db():
    async with AsyncSessionLocal() as session:
        yield session
