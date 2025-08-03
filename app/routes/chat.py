# flake8: noqa: E501
"""
Chat endpoints for the car assistant.
"""

import uuid
import logging
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from ..models.schemas import ChatRequest, ChatResponse
from ..core.agent import get_assistant
from ..core.database.schema import Session, Message
from ..core.database import get_db

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/", response_model=ChatResponse)
async def chat(
    request: ChatRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Process chat message with memory persistence.

    This endpoint now uses the memory-enabled assistant by default.
    For streaming responses, use /chat/stream.
    """
    user_message_timestamp = datetime.now(timezone.utc).replace(tzinfo=None)

    try:
        # Get assistant
        assistant = await get_assistant()

        session_id = request.session_id or str(uuid.uuid4())

        # Check if session exists, create or update
        existing_session = await db.execute(
            select(Session).where(Session.id == session_id)
        )
        session_record = existing_session.scalar_one_or_none()

        if session_record:
            # Update existing session
            session_record.status = "active"
        else:
            # Create new session
            session_record = Session(
                id=session_id,
                created_at=user_message_timestamp,
                status="active"
            )
            db.add(session_record)

        # Create user message
        user_message_id = str(uuid.uuid4())

        user_message = Message(
            id=user_message_id,
            session_id=session_id,
            role="user",
            content=request.message,
            timestamp=user_message_timestamp
        )
        db.add(user_message)

        await db.commit()

        # Process message with memory
        result = await assistant.process_message(
            user_input=request.message,
            thread_id=session_id,
        )

        assistant_message_id = str(uuid.uuid4())

        # Create assistant message
        assistant_message = Message(
            id=assistant_message_id,
            session_id=session_id,
            role="assistant",
            content=result.response,
        )
        db.add(assistant_message)

        await db.commit()

        return ChatResponse(
            response=result.response,
            session_id=session_id,
            memory_enabled=result.memory_enabled,
            fallback_used=result.fallback_used,
            message_count=result.message_count,
            performance=result.performance
        )

    except Exception as e:
        await db.rollback()
        logger.error(f"Error processing chat message: {e}")
        raise HTTPException(
            status_code=500, detail=f"Error processing message: {str(e)}"
        )
