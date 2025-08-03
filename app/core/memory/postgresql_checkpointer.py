"""
PostgreSQL-based checkpointer for LangGraph agent memory with async support.
"""

import logging
from typing import AsyncGenerator, Optional, Any
from contextlib import asynccontextmanager

try:
    from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
    from psycopg import AsyncConnection
    from psycopg_pool import AsyncConnectionPool
except ImportError as e:
    raise ImportError(
        "PostgreSQL checkpoint dependencies not found. "
        "Install with: pip install langgraph-checkpoint-postgres psycopg[pool]"
    ) from e

from ..config.settings import get_database_settings

logger = logging.getLogger(__name__)


def _get_psycopg_url() -> str:
    """Get the psycopg URL for the database"""
    settings = get_database_settings()
    sync_url_obj = settings.database_url_obj

    return sync_url_obj.set(drivername="postgresql").render_as_string(
        hide_password=False
    )


class PostgreSQLCheckpointer:
    """
    PostgreSQL checkpointer with connection pooling for LangGraph agent memory.
    """
    pool: Optional[AsyncConnectionPool]

    def __init__(self):
        self.pool = None
        self._initialized = False

    async def initialize(self) -> None:
        """Initialize the PostgreSQL connection pool"""
        if self._initialized:
            return

        try:
            psycopg_url = _get_psycopg_url()

            # Create async connection pool with optimal settings
            self.pool = AsyncConnectionPool(
                conninfo=psycopg_url,
                min_size=5,
                max_size=20,
                max_idle=180,
                max_lifetime=1800,
                configure=self._configure_connection
            )

            # Open the pool using the recommended method
            await self.pool.open()

            # Setup checkpoint tables using the correct API
            if self.pool:
                async with AsyncPostgresSaver.from_conn_string(psycopg_url) \
                        as checkpointer:
                    # Ensure all required tables are created
                    await checkpointer.setup()
                    logger.info(
                        "✅ LangGraph checkpoint tables created successfully"
                    )

            self._initialized = True
            logger.info("✅ PostgreSQL checkpointer initialized successfully")

        except Exception as e:
            logger.error(
                f"❌ Failed to initialize PostgreSQL checkpointer: {e}"
            )
            raise

    @staticmethod
    async def _configure_connection(conn: AsyncConnection) -> None:
        """Configure connection settings for optimal performance"""
        await conn.set_autocommit(True)

        # Set optimal PostgreSQL settings for LangGraph workloads
        await conn.execute("SET statement_timeout = '300s'")
        await conn.execute(
            "SET idle_in_transaction_session_timeout = '60s'"
        )
        await conn.execute("SET lock_timeout = '30s'")

    @asynccontextmanager
    async def get_checkpointer(
        self
    ) -> AsyncGenerator[AsyncPostgresSaver, None]:
        """
        Get an async PostgreSQL checkpointer with proper connection management.

        Returns:
            AsyncPostgresSaver: Configured checkpointer instance
        """
        await self.initialize()

        if not self.pool:
            raise RuntimeError("PostgreSQL pool not initialized")

        try:
            psycopg_url = _get_psycopg_url()

            async with AsyncPostgresSaver.from_conn_string(psycopg_url) \
                    as checkpointer:
                yield checkpointer

        except AttributeError as e:
            if "'dict' object has no attribute 'to_dict'" in str(e):
                logger.error(
                    "to_dict error detected: This likely means messages "
                    "from database are already in dict format but code "
                    "is trying to call to_dict() on them again. "
                    f"Full error: {e}"
                )
            raise
        except Exception as e:
            logger.error(f"Error in checkpointer context: {e}")
            raise

    async def close(self) -> None:
        """Close the connection pool"""
        if self.pool:
            await self.pool.close()
            self._initialized = False
            logger.info("PostgreSQL checkpointer closed")


# Global checkpointer instance
_checkpointer_instance: Optional[PostgreSQLCheckpointer] = None


def get_postgresql_checkpointer() -> PostgreSQLCheckpointer:
    """
    Get the global PostgreSQL checkpointer instance.

    Returns:
        PostgreSQLCheckpointer: Global checkpointer instance
    """
    global _checkpointer_instance
    if _checkpointer_instance is None:
        _checkpointer_instance = PostgreSQLCheckpointer()
    return _checkpointer_instance


async def health_check() -> dict[str, Any]:
    """
    Perform health check on PostgreSQL checkpointer.

    Returns:
        dict containing health status information
    """
    checkpointer = get_postgresql_checkpointer()

    try:
        async with checkpointer.get_checkpointer() as saver:
            # Simple connection test using the correct config format
            from langchain_core.runnables import RunnableConfig
            test_config: RunnableConfig = {
                "configurable": {"thread_id": "health_check"}
            }
            await saver.aget(test_config)

            return {
                "status": "healthy",
                "database": "postgresql",
                "checkpointer": "async",
                "connection_pool": checkpointer._initialized
            }
    except Exception as e:
        logger.error(f"PostgreSQL checkpointer health check failed: {e}")
        return {
            "status": "unhealthy",
            "error": str(e),
            "database": "postgresql",
            "checkpointer": "async"
        }


# Utility function for creating direct checkpointer (for advanced use cases)
@asynccontextmanager
async def create_direct_checkpointer(
    database_url: Optional[str] = None
) -> AsyncGenerator[AsyncPostgresSaver, None]:
    """
    Create a direct PostgreSQL checkpointer connection.

    Args:
        database_url: Optional database URL, uses settings if not provided

    Yields:
        AsyncPostgresSaver: Direct checkpointer connection
    """
    if database_url:
        db_url = database_url
    else:
        db_url = _get_psycopg_url()

    # Use the correct API for creating checkpointer
    async with AsyncPostgresSaver.from_conn_string(db_url) as checkpointer:
        # Ensure tables exist
        await checkpointer.setup()
        yield checkpointer
