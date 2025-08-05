"""
Memory manager for LangGraph Agent with PostgreSQL
persistence and optimizations.
"""

import logging
import importlib
from typing import Optional, Any, Literal, cast, Union
from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.base import CheckpointTuple
from datetime import datetime

from ..states import BaseState
from .postgresql_checkpointer import PostgreSQLCheckpointer
from .redis_checkpointer import RedisCheckpointer

logger = logging.getLogger(__name__)


BaseCheckpointSaver = Union[
    PostgreSQLCheckpointer,
    RedisCheckpointer
]


class MemoryManager:
    """
    Manages conversation memory and state using PostgreSQL or Redis
    checkpointer.
    Provides optimized memory operations to reduce response time.
    """
    _cache: dict[str, Any]
    checkpointer: BaseCheckpointSaver

    def __init__(self, checkpointer_kind: Literal["postgresql", "redis"]):
        match checkpointer_kind:
            case "postgresql":
                from .postgresql_checkpointer import (
                    get_postgresql_checkpointer, health_check
                )
                self.checkpointer = get_postgresql_checkpointer()
                self.health_check = health_check
            case "redis":
                from .redis_checkpointer import (
                    get_redis_checkpointer, health_check
                )
                self.checkpointer = get_redis_checkpointer()
                self.health_check = health_check
            case _:
                raise ValueError(f"Invalid checkpointer: {checkpointer_kind}")

        self.checkpointer_kind = checkpointer_kind
        # In-memory cache for recent conversations
        self._cache = {}
        self._cache_ttl = 60 * 5

    async def initialize(self) -> None:
        """Initialize the memory manager"""
        await self.checkpointer.initialize()
        logger.info(
            f"Memory manager initialized with {self.checkpointer_kind} "
            "persistence"
        )

    def _transform_constructor_items(self, data: Any) -> Any:
        """
        Recursively transform constructor items back to their original form.

        This function traverses nested data structures (lists, dicts) and
        converts constructor representations back to actual instances.

        Args:
            data: The data structure to transform (can be dict, list, or
                any other type)

        Returns:
            The transformed data with constructor items replaced by actual
            instances

        Example:
            Input constructor object:
            {
                "lc": 2,
                "type": "constructor",
                "id": ["app", "core", "models", "messages", "HMessage"],
                "method": [null, "model_construct"],
                "kwargs": {"content": "Hello", "name": "Human"}
            }

            Output: HMessage(content="Hello", name="Human")

            Also handles nested structures like:
            {
                "chat_history": [
                    { ... constructor object ... },
                    { ... another constructor object ... }
                ],
                "other_data": "normal_value"
            }
        """
        if isinstance(data, dict):
            # Check if this dict represents a constructor
            if (
                data.get("lc") == 2 and
                data.get("type") == "constructor" and
                "id" in data and
                "method" in data and
                "kwargs" in data
            ):

                try:
                    # Extract constructor information
                    module_path = data["id"]
                    method_info = data["method"]
                    kwargs = data["kwargs"]

                    # Build the module path
                    if len(module_path) < 2:
                        logger.warning(f"Invalid module path: {module_path}")
                        return data

                    # Import the module and get the class
                    module_name = ".".join(module_path[:-1])
                    class_name = module_path[-1]

                    try:
                        module = importlib.import_module(module_name)
                        cls = getattr(module, class_name)
                    except (ImportError, AttributeError) as e:
                        msg = (
                            f"Could not import {module_name}."
                            f"{class_name}: {e}"
                        )
                        logger.warning(msg)
                        return data

                    # Recursively transform kwargs
                    transformed_kwargs = self._transform_constructor_items(
                        kwargs
                    )

                    # Create the instance based on method
                    method_name = (
                        method_info[1] if method_info[1] else "__init__"
                    )

                    if (
                        method_name == "model_construct" and
                            hasattr(cls, "model_construct")
                    ):
                        # Use Pydantic's model_construct method
                        return cls.model_construct(**transformed_kwargs)
                    elif method_name == "__init__":
                        # Use regular constructor
                        return cls(**transformed_kwargs)
                    else:
                        # Use specified method
                        if hasattr(cls, method_name):
                            method = getattr(cls, method_name)
                            return method(**transformed_kwargs)
                        else:
                            msg = f"Method {method_name} not found on {cls}"
                            logger.warning(msg)
                            return data

                except Exception as e:
                    logger.warning(f"Error constructing object: {e}")
                    return data
            else:
                # Regular dict - recursively transform values
                return {
                    key: self._transform_constructor_items(value)
                    for key, value in data.items()
                }

        elif isinstance(data, list):
            # Recursively transform list items
            return [self._transform_constructor_items(item) for item in data]
        else:
            # Return as-is for primitive types
            return data

    def create_thread_config(
        self,
        thread_id: str,
        checkpoint_ns: str = "",  # default namespace
        checkpoint_id: Optional[str] = None
    ) -> RunnableConfig:
        """
        Create a thread configuration for LangGraph checkpointing.

        Args:
            thread_id: Unique thread identifier
            checkpoint_id: Optional checkpoint ID for time travel

        Returns:
            RunnableConfig: Configuration for thread persistence
        """
        config: RunnableConfig = {
            "configurable": {
                "thread_id": thread_id,
                "checkpoint_ns": checkpoint_ns,
            }
        }

        if checkpoint_id:
            config["configurable"]["checkpoint_id"] = checkpoint_id

        return config

    async def get_thread_state(
        self,
        config: RunnableConfig,
        checkpoint_id: Optional[str] = None
    ) -> BaseState:
        """
        Get the current state of a thread.

        Args:
            config: Thread configuration
            checkpoint_id: Optional specific checkpoint to retrieve

        Returns:
            Thread state dictionary or empty dict if not found.
            Use cast() to get proper typing: cast(State, result)
        """
        try:
            async with self.checkpointer.get_checkpointer() as saver:
                if "configurable" not in config:
                    config["configurable"] = {}

                if not (config["configurable"].get("thread_id", None)):
                    raise ValueError(
                        "Thread ID not found in config. "
                        "It is required to retrieve thread state"
                    )

                if checkpoint_id:
                    config["configurable"]["checkpoint_id"] = checkpoint_id

                tuple_snapshot = await saver.aget_tuple(config)
                if tuple_snapshot:
                    checkpoint = tuple_snapshot.checkpoint

                    transformed_values = self._transform_constructor_items(
                        checkpoint["channel_values"]
                    )

                    checkpoint_data = {
                        "values": transformed_values,
                        "metadata": tuple_snapshot.metadata,
                        "created_at": checkpoint["ts"],
                        "config": tuple_snapshot.config
                    }

                    return cast(BaseState, checkpoint_data["values"])

        except Exception as e:
            logger.error(f"Error retrieving thread state: {e}")

        return cast(BaseState, {})

    async def reset_thread_state(
        self,
        config: RunnableConfig
    ) -> None:
        """Reset the state of a thread."""
        async with self.checkpointer.get_checkpointer() as saver:
            if "configurable" not in config:
                config["configurable"] = {}

            if not (thread_id := config["configurable"].get("thread_id")):
                raise ValueError(
                    "Thread ID not found in config. "
                    "It is required to reset thread state"
                )
            await saver.adelete_thread(thread_id)

    async def get_thread_checkpoints(
        self,
        config: RunnableConfig,
        limit: int = 20
    ) -> list[dict[str, Any]]:
        """
        Get checkpoint history for a thread.

        Args:
            config: Thread configuration
            limit: Maximum number of checkpoints to retrieve

        Returns:
            List of checkpoint summaries
        """
        result = []

        if "configurable" not in config:
            config["configurable"] = {}

        if not (thread_id := config["configurable"].get("thread_id")):
            raise ValueError(
                "Thread ID not found in config. "
                "It is required to retrieve checkpoints"
            )

        try:
            async with self.checkpointer.get_checkpointer() as saver:
                count = 0
                async for checkpoint in saver.alist(config):
                    if count >= limit:
                        break

                    checkpoint_id = checkpoint.config \
                        .get("configurable", {}) \
                        .get("checkpoint_id", "")

                    created_at = self._extract_created_at_from_checkpoint(
                        checkpoint
                    )

                    transformed_metadata = self._transform_constructor_items(
                        checkpoint.metadata
                    )

                    result.append({
                        "checkpoint_id": checkpoint_id,
                        "thread_id": thread_id,
                        "created_at": created_at,
                        "metadata": transformed_metadata
                    })
                    count += 1

        except Exception as e:
            logger.error(f"Error retrieving thread checkpoints: {e}")

        return result

    def _extract_created_at_from_checkpoint(
        self,
        checkpoint: CheckpointTuple
    ) -> Optional[datetime]:
        """Extract created_at from a checkpoint."""
        created_at = None
        has_checkpoint = checkpoint.checkpoint is not None
        has_ts = (
            has_checkpoint and "ts" in checkpoint.checkpoint
        )
        if has_ts:
            ts = checkpoint.checkpoint["ts"]
            if isinstance(ts, str):
                try:
                    ts_clean = ts.replace("Z", "+00:00")
                    created_at = datetime.fromisoformat(ts_clean)
                except ValueError:
                    created_at = None
        return created_at

    def clear_thread_cache(self, thread_id: str) -> None:
        """Clear cache entries for a specific thread"""
        keys_to_remove = [
            key for key in self._cache.keys()
            if key.startswith(f"history_{thread_id}_")
        ]
        for key in keys_to_remove:
            del self._cache[key]
