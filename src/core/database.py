"""Database connection and session management."""

from contextlib import asynccontextmanager, contextmanager
from typing import AsyncGenerator, Generator

from sqlalchemy import create_engine
from sqlalchemy.exc import DataError, IntegrityError, SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.orm.session import close_all_sessions

from src.config import get_settings
from src.models.base import Base

settings = get_settings()

# Check if we're using SQLite (for testing)
is_sqlite = "sqlite" in settings.database_url

# Create engine with appropriate settings
if is_sqlite:
    # SQLite doesn't support these pool settings
    sync_engine = create_engine(
        settings.database_url,
        echo=settings.environment == "development",
    )
else:
    # PostgreSQL settings
    sync_engine = create_engine(
        settings.database_url.replace("postgresql+asyncpg://", "postgresql://"),
        pool_size=20,
        max_overflow=40,
        pool_pre_ping=True,
        pool_recycle=3600,
        echo=settings.environment == "development",
    )

# Async engine for application use
if is_sqlite:
    # SQLite with aiosqlite
    async_db_url = settings.database_url.replace("sqlite://", "sqlite+aiosqlite://")
    async_engine = create_async_engine(
        async_db_url,
        echo=settings.environment == "development",
    )
else:
    # Convert postgresql:// to postgresql+asyncpg:// for async driver
    async_db_url = settings.database_url.replace(
        "postgresql://", "postgresql+asyncpg://"
    )
    async_engine = create_async_engine(
        async_db_url,
        pool_size=20,
        max_overflow=40,
        pool_pre_ping=True,
        pool_recycle=3600,
        echo=settings.environment == "development",
    )

# Session factories
SyncSessionLocal = sessionmaker(
    bind=sync_engine,
    class_=Session,
    autocommit=False,
    autoflush=False,
    expire_on_commit=False,
)

AsyncSessionLocal = async_sessionmaker(
    bind=async_engine,
    class_=AsyncSession,
    autocommit=False,
    autoflush=False,
    expire_on_commit=False,
)


@contextmanager
def get_db() -> Generator[Session, None, None]:
    """Get synchronous database session."""
    db = SyncSessionLocal()
    try:
        yield db
        db.commit()
    except (DataError, IntegrityError, SQLAlchemyError):
        db.rollback()
        raise
    finally:
        db.close()


@asynccontextmanager
async def get_async_db() -> AsyncGenerator[AsyncSession, None]:
    """Get asynchronous database session."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except (DataError, IntegrityError, SQLAlchemyError, TypeError, ValueError):
            await session.rollback()
            raise
        finally:
            await session.close()


def init_db() -> None:
    """Initialize database with tables."""
    Base.metadata.create_all(bind=sync_engine)


async def init_async_db() -> None:
    """Initialize database with tables asynchronously."""
    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


def drop_db() -> None:
    """Drop all database tables (use with caution)."""
    close_all_sessions()
    Base.metadata.drop_all(bind=sync_engine)


async def drop_async_db() -> None:
    """Drop all database tables asynchronously (use with caution)."""
    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
