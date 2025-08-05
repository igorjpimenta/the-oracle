import logging
from fastapi import APIRouter, HTTPException

from ..core.memory.memory_manager import MemoryManager

router = APIRouter()

logger = logging.getLogger(__name__)


@router.get("/{thread_id}")
async def get_thread_state(
    thread_id: str
):
    """Reset the state of a thread."""
    try:
        memory_manager = MemoryManager(checkpointer_kind="redis")

        config = memory_manager.create_thread_config(thread_id=thread_id)
        state = await memory_manager.get_thread_state(config)

        return {"state": state}
    except Exception as e:
        logger.error(f"Error getting thread state: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{thread_id}")
async def reset_thread_state(
    thread_id: str
):
    """Reset the state of a thread."""
    try:
        memory_manager = MemoryManager(checkpointer_kind="redis")

        config = memory_manager.create_thread_config(thread_id=thread_id)
        await memory_manager.reset_thread_state(config)

        return {"message": "Thread state reset successfully"}
    except Exception as e:
        logger.error(f"Error resetting thread state: {e}")
        raise HTTPException(status_code=500, detail=str(e))
