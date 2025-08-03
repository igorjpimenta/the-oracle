"""
Session management endpoints.
"""

import logging
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
import uuid

from ..models.schemas import (
    SessionCreate, SessionResponse, SessionMessagesResponse,
    SessionCheckpointResponse
)
from ..core.memory import MemoryManager
from ..core.database import get_db
from ..core.database.schema import Session, Message


logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/", response_model=list[SessionResponse])
async def get_sessions(
    db: AsyncSession = Depends(get_db)
):
    """Get all sessions"""
    result = await db.execute(select(Session))
    sessions = result.scalars().all()

    return [
        SessionResponse(
            id=session.id,
            created_at=session.created_at,
            updated_at=session.updated_at,
            status=session.status,
            metadata=session.meta_data
        )
        for session in sessions
    ]


@router.post("/", response_model=SessionResponse)
async def create_session(
    session_data: SessionCreate,
    db: AsyncSession = Depends(get_db)
):
    """Create a new session"""
    session_id = str(uuid.uuid4())

    session = Session(
        id=session_id,
        meta_data=session_data.metadata
    )

    db.add(session)
    await db.commit()
    await db.refresh(session)

    return SessionResponse(
        id=session.id,
        created_at=session.created_at,
        updated_at=session.updated_at,
        status=session.status,
        metadata=session.meta_data
    )


@router.get("/{session_id}", response_model=SessionResponse)
async def get_session(
    session_id: str,
    db: AsyncSession = Depends(get_db)
):
    """Get session by ID"""
    result = await db.execute(
        select(Session).where(Session.id == session_id)
    )
    session = result.scalar_one_or_none()

    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    return SessionResponse(
        id=session.id,
        created_at=session.created_at,
        updated_at=session.updated_at,
        status=session.status,
        metadata=session.meta_data
    )


@router.get(
    "/{session_id}/messages",
    response_model=list[SessionMessagesResponse]
)
async def get_session_messages(
    session_id: str,
    db: AsyncSession = Depends(get_db)
):
    """Get all messages for a session"""
    result = await db.execute(
        select(Message)
        .where(Message.session_id == session_id)
        .order_by(Message.timestamp)
    )
    messages = result.scalars().all()

    return [
        SessionMessagesResponse(
            id=message.id,
            session_id=message.session_id,
            role=message.role,
            content=message.content,
            timestamp=message.timestamp,
            metadata=message.meta_data
        )
        for message in messages
    ]


@router.delete("/{session_id}")
async def delete_session(
    session_id: str,
    db: AsyncSession = Depends(get_db)
):
    """Delete a session and its messages"""
    # Delete messages first (handled by cascade)
    # Delete session
    result = await db.execute(
        delete(Session).where(Session.id == session_id)
    )

    if result.rowcount == 0:
        raise HTTPException(status_code=404, detail="Session not found")

    await db.commit()
    return {"message": "Session deleted successfully"}


@router.get("/{session_id}/checkpoints")
async def get_session_checkpoints(
    session_id: str,
    limit: int = 10
) -> SessionCheckpointResponse:
    """
    Get checkpoint history for a session.
    """
    try:
        memory_manager = MemoryManager(checkpointer_kind="redis")
        await memory_manager.initialize()

        config = memory_manager.create_thread_config(
            thread_id=session_id
        )

        checkpoints = await memory_manager.get_thread_checkpoints(
            config, limit=limit
        )

        return SessionCheckpointResponse(
            session_id=session_id,
            checkpoint_count=len(checkpoints),
            checkpoints=checkpoints,
            limit=limit
        )

    except Exception as e:
        logger.error(f"Error getting session checkpoints: {e}")
        raise HTTPException(status_code=500, detail=str(e))
