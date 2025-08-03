"""
Redis-based checkpointer for LangGraph agent memory with async support.
"""

import logging
from typing import AsyncGenerator, Optional, Any
from contextlib import asynccontextmanager

try:
    from langgraph.checkpoint.redis import AsyncRedisSaver
    import redis.asyncio as redis
except ImportError as e:
    raise ImportError(
        "Redis checkpoint dependencies not found. "
        "Install with: pip install langgraph-checkpoint-redis redis"
    ) from e

from ..config.settings import get_redis_settings

logger = logging.getLogger(__name__)


def _get_redis_url() -> str:
    """Get the Redis URL for the database"""
    settings = get_redis_settings()

    return settings.redis_url


class RedisCheckpointer:
    """
    Redis checkpointer with connection management for LangGraph agent memory.
    """

    def __init__(self):
        self._initialized = False

    async def initialize(self) -> None:
        """Initialize the Redis checkpointer and verify connection"""
        if self._initialized:
            return

        try:
            redis_url = _get_redis_url()

            # Test connection to Redis
            redis_client = redis.from_url(redis_url)
            await redis_client.ping()
            await redis_client.aclose()

            async with AsyncRedisSaver.from_conn_string(redis_url) \
                    as checkpointer:
                from langchain_core.runnables import RunnableConfig
                test_config: RunnableConfig = {
                    "configurable": {"thread_id": "health_check_init"}
                }
                await checkpointer.aget(test_config)
                logger.info(
                    "✅ LangGraph Redis checkpointer initialized successfully"
                )

            self._initialized = True

        except Exception as e:
            logger.error(
                f"❌ Failed to initialize Redis checkpointer: {e}"
            )
            raise

    @asynccontextmanager
    async def get_checkpointer(self) -> AsyncGenerator[AsyncRedisSaver, None]:
        """
        Get an async Redis checkpointer with proper connection management.

        Returns:
            AsyncRedisSaver: Configured checkpointer instance
        """
        await self.initialize()

        redis_url = _get_redis_url()

        try:
            async with AsyncRedisSaver.from_conn_string(redis_url) \
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
        """Clean up resources"""
        if self._initialized:
            self._initialized = False
            logger.info("Redis checkpointer closed")


# Global checkpointer instance
_checkpointer_instance: Optional[RedisCheckpointer] = None


def get_redis_checkpointer() -> RedisCheckpointer:
    """
    Get the global Redis checkpointer instance.

    Returns:
        RedisCheckpointer: Global checkpointer instance
    """
    global _checkpointer_instance
    if _checkpointer_instance is None:
        _checkpointer_instance = RedisCheckpointer()
    return _checkpointer_instance


async def health_check() -> dict[str, Any]:
    """
    Perform health check on Redis checkpointer.

    Returns:
        dict containing health status information
    """
    checkpointer = get_redis_checkpointer()

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
                "database": "redis",
                "checkpointer": "async",
                "connection": checkpointer._initialized
            }
    except Exception as e:
        logger.error(f"Redis checkpointer health check failed: {e}")
        return {
            "status": "unhealthy",
            "error": str(e),
            "database": "redis",
            "checkpointer": "async"
        }


async def test_redis_connection() -> bool:
    """
    Test Redis connection without using checkpointer.

    Returns:
        bool: True if connection successful, False otherwise
    """
    try:
        redis_url = _get_redis_url()
        redis_client = redis.from_url(redis_url)
        await redis_client.ping()
        await redis_client.aclose()
        return True
    except Exception as e:
        logger.error(f"Redis connection test failed: {e}")
        return False
