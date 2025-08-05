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
from ..core.database import get_db
from ..core.database.schema import (
    Session, Message, TranscriptionProcessing, Transcription,
    TranscriptionAnalysis, TranscriptionInsights
)
from ..core.models.data import (
    TranscriptionData,
    TranscriptionAnalysis as TranscriptionAnalysisModel,
    ExtractedInsights as ExtractedInsightsModel,
    TranscriptionProcessingData
)

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
        session_id = request.session_id

        # Check if session exists
        existing_session = await db.execute(
            select(Session).where(Session.id == session_id)
        )
        session_record = existing_session.scalar_one_or_none()

        if session_record:
            session_record.status = "active"
        else:
            raise HTTPException(
                status_code=404, detail="Session not found"
            )

        # Get transcription
        existing_transcription = await db.execute(
            select(Transcription).where(
                Transcription.session_id == session_id
            )
        )
        transcription_record = existing_transcription.scalar_one_or_none()

        if not transcription_record:
            raise HTTPException(
                status_code=404, detail=(
                    "Transcription not found. "
                    "Create a transcription first."
                )
            )

        transcription_data = TranscriptionData(
            transcription_id=transcription_record.id,
            text=transcription_record.transcription_text,
            duration=transcription_record.duration_seconds,
            language=transcription_record.language,
            metadata=transcription_record.meta_data
        )

        # Get transcription processing
        existing_transcription_processing = await db.execute(
            select(TranscriptionProcessing).where(
                TranscriptionProcessing.transcription_id
                == transcription_record.id
            )
        )
        transcription_processing_record = existing_transcription_processing \
            .scalar_one_or_none()

        if not transcription_processing_record:
            raise HTTPException(
                status_code=404, detail=(
                    "Transcription processing not found. "
                    "Process the transcription first."
                )
            )

        # Get transcription analysis
        existing_transcription_analysis = await db.execute(
            select(TranscriptionAnalysis).where(
                TranscriptionAnalysis.id
                == transcription_processing_record.analysis_id
            )
        )
        transcription_analysis_record = existing_transcription_analysis \
            .scalar_one_or_none()

        transcription_analysis = None
        if transcription_analysis_record:
            transcription_analysis = TranscriptionAnalysisModel(
                summary=transcription_analysis_record.summary,
                key_topics=transcription_analysis_record.key_topics,
                sentiment=transcription_analysis_record.sentiment,
                main_themes=transcription_analysis_record.main_themes,
                important_quotes=(
                    transcription_analysis_record.important_quotes
                ),
                technical_terms=transcription_analysis_record.technical_terms
            )

        # Get transcription insights
        existing_transcription_insights = await db.execute(
            select(TranscriptionInsights).where(
                TranscriptionInsights.id
                == transcription_processing_record.insights_id
            )
        )
        transcription_insights_record = existing_transcription_insights \
            .scalar_one_or_none()

        transcription_insights = None
        if transcription_insights_record:
            transcription_insights = ExtractedInsightsModel(
                key_insights=transcription_insights_record.key_insights,
                action_items=transcription_insights_record.action_items,
                recommendations=transcription_insights_record.recommendations,
                opportunities=transcription_insights_record.opportunities,
                concerns=transcription_insights_record.concerns,
                next_steps=transcription_insights_record.next_steps
            )

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
            transcription_data=TranscriptionProcessingData(
                data=transcription_data,
                analysis=transcription_analysis,
                insights=transcription_insights
            )
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
