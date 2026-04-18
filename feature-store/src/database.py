import os
from datetime import datetime, timezone

from sqlalchemy import JSON, BigInteger, Column, DateTime, Integer, String, Text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

DATABASE_URL = os.getenv(
    "DATABASE_URL", "postgresql+asyncpg://cortex:cortex_secret@postgres:5432/cortex"
)
# Convert sync URL to async
ASYNC_DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://")

engine = create_async_engine(ASYNC_DATABASE_URL, echo=False, pool_pre_ping=True)
AsyncSessionLocal = async_sessionmaker(
    engine, expire_on_commit=False, class_=AsyncSession
)


class Base(DeclarativeBase):
    pass


class FeatureGroup(Base):
    __tablename__ = "feature_groups"
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


class FeatureDefinition(Base):
    __tablename__ = "feature_definitions"
    id = Column(Integer, primary_key=True)
    feature_group = Column(String(128), nullable=False)
    name = Column(String(128), nullable=False)
    dtype = Column(String(64), nullable=False)
    description = Column(Text)
    default_value = Column(Text)
    tags = Column(JSON, default={})
    created_at = Column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )


class FeatureValue(Base):
    __tablename__ = "feature_values"
    id = Column(BigInteger, primary_key=True)
    feature_group = Column(String(128), nullable=False)
    entity_id = Column(String(256), nullable=False)
    feature_name = Column(String(128), nullable=False)
    feature_value = Column(Text)
    event_timestamp = Column(DateTime(timezone=True), nullable=False)
    created_at = Column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )


async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def get_db():
    async with AsyncSessionLocal() as session:
        yield session
