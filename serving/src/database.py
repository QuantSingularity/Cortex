import os
from datetime import datetime, timezone

from sqlalchemy import JSON, Boolean, Column, DateTime, Integer, String, Text
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


class ModelDeployment(Base):
    __tablename__ = "model_deployments"
    id = Column(Integer, primary_key=True)
    model_name = Column(String(128), nullable=False)
    version = Column(String(64), nullable=False)
    artifact_uri = Column(Text, nullable=False)
    framework = Column(String(64), default="sklearn")
    is_active = Column(Boolean, default=True)
    config = Column(JSON, default={})
    deployed_at = Column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at = Column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )


class PredictionLog(Base):
    __tablename__ = "prediction_logs"
    id = Column(Integer, primary_key=True)
    model_name = Column(String(128), nullable=False)
    version = Column(String(64), nullable=False)
    input_hash = Column(String(64))
    latency_ms = Column(Integer)
    status = Column(String(16), default="success")
    predicted_at = Column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )


async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def get_db():
    async with AsyncSessionLocal() as session:
        yield session
