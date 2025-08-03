"""
Database configuration and session management with PostgreSQL.
"""

from sqlalchemy.ext.asyncio import (
    create_async_engine,
    AsyncSession,
    async_sessionmaker
)
from sqlalchemy.engine.url import URL
from sqlalchemy import text
from typing import AsyncGenerator
import logging

from ..config.settings import get_settings, get_database_settings
from .schema import Base

logger = logging.getLogger(__name__)


class DatabaseManager:
    def __init__(self):
        self.engine = None
        self.async_session_maker = None

    async def initialize(self):
        if self.async_session_maker is not None:
            return

        settings = get_database_settings()
        general_settings = get_settings()
        database_url = settings.database_url_obj_async

        db_host = database_url.host
        logger.info(f"Initializing database connection to: {db_host}")

        # Create async engine (SSL is already configured in the URL)
        self.engine = create_async_engine(
            url=database_url,
            echo=general_settings.DEBUG,
            pool_size=20,
            max_overflow=0,
            pool_pre_ping=True,  # Verify connections before use
            pool_recycle=3600,   # Recycle connections every hour
        )

        # Create session maker
        self.async_session_maker = async_sessionmaker(
            self.engine,
            class_=AsyncSession,
            expire_on_commit=False
        )

        # Create tables
        try:
            async with self.engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
            logger.info("✅ Database tables created successfully")
        except Exception as e:
            logger.error(f"❌ Failed to create database tables: {e}")
            raise

    async def get_session(self) -> AsyncSession:
        await self.initialize()
        if self.async_session_maker is None:
            raise RuntimeError("Database not initialized")
        return self.async_session_maker()


db_manager = DatabaseManager()


def get_database_url() -> URL:
    """Get database URL from settings"""
    settings = get_database_settings()
    return settings.database_url_obj


async def init_database():
    """Initialize the database with required tables"""
    await db_manager.initialize()


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Get database session"""
    async with await db_manager.get_session() as session:
        try:
            yield session
        except Exception as e:
            await session.rollback()
            logger.error(f"Database session error: {e}")
            raise
        finally:
            await session.close()


async def close_database():
    """Close database connections"""
    global engine
    if db_manager.engine:
        await db_manager.engine.dispose()
        logger.info("Database connections closed")


async def check_database_health() -> bool:
    """Check if database is healthy"""
    try:
        if db_manager.async_session_maker is None:
            return False

        async with db_manager.async_session_maker() as session:
            # Simple query to test connection
            result = await session.execute(text("SELECT 1"))
            return result.scalar() == 1
    except Exception as e:
        logger.error(f"Database health check failed: {e}")
        return False
