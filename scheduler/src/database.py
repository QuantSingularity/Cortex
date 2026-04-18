import os
from datetime import datetime, timezone

from sqlalchemy import JSON, BigInteger, Column, DateTime, Integer, String, Text
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


class RetrainingJob(Base):
    __tablename__ = "retraining_jobs"
    id = Column(BigInteger, primary_key=True)
    model_name = Column(String(128), nullable=False)
    trigger_type = Column(String(32), nullable=False)  # scheduled | drift | manual
    status = Column(String(32), nullable=False, default="pending")
    triggered_at = Column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    started_at = Column(DateTime(timezone=True))
    completed_at = Column(DateTime(timezone=True))
    error_message = Column(Text)
    metadata_ = Column("metadata", JSON, default={})


class ScheduledTrigger(Base):
    """Cron-based retraining schedule per model."""

    __tablename__ = "scheduled_triggers"
    id = Column(Integer, primary_key=True)
    model_name = Column(String(128), unique=True, nullable=False)
    cron_expr = Column(String(64), nullable=False, default="0 2 * * *")  # daily 2am
    enabled = Column(String(8), default="true")
    created_at = Column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at = Column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )


async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def get_db():
    async with AsyncSessionLocal() as session:
        yield session
