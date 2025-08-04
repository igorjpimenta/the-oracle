"""
Audio transcription endpoints.
"""

import logging
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import Optional

from ..models.schemas import (
    TranscriptionResponse, TranscriptionListResponse
)
from ..core.tools.whisper_transcription import (
    WhisperTranscriptionTool, WhisperAvailableModels
)
from ..core.database.schema import Session, Transcription
from ..core.database import get_db

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/", response_model=TranscriptionResponse)
async def transcribe_audio(
    file: UploadFile = File(..., description="Audio file to transcribe"),
    session_id: str = Form(
        ..., description="Session ID to associate transcription with"
    ),
    language: Optional[str] = Form(
        None, description=(
            "Language for transcription (en, es, or auto detection)"
        )
    ),
    whisper_model: Optional[WhisperAvailableModels] = Form(
        "small", description=(
            "Whisper model to use (base, small, medium, large)"
        )
    ),
    db: AsyncSession = Depends(get_db)
):
    """
    Transcribe an uploaded audio file using Whisper.

    Supports various audio formats including MP3, WAV, M4A, MP4, OPUS,
    OGG, FLAC, and WEBM. The transcription result is persisted to the
    database and associated with the provided session.
    """
    try:
        # Validate session exists
        session_result = await db.execute(
            select(Session).where(Session.id == session_id)
        )
        session_record = session_result.scalar_one_or_none()

        if not session_record:
            raise HTTPException(
                status_code=404,
                detail=f"Session {session_id} not found"
            )

        # Validate whisper model
        valid_models: list[WhisperAvailableModels] = [
            "base", "small", "medium", "large"
        ]
        if whisper_model not in valid_models:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid whisper model. Must be one of: "
                f"{', '.join(valid_models)}"
            )

        # Read file content
        audio_content = await file.read()

        if not audio_content:
            raise HTTPException(
                status_code=400,
                detail="Empty audio file provided"
            )

        # Create transcription tool
        transcription_tool = WhisperTranscriptionTool(
            whisper_model=whisper_model
        )

        # Perform transcription
        result = await transcription_tool.transcribe_audio(
            session_id=session_id,
            audio_content=audio_content,
            filename=file.filename or "audio_file",
            language=language,
            mimetype=file.content_type or "audio/mpeg"
        )

        # Return transcription response
        return TranscriptionResponse(
            id=result.id,
            session_id=result.session_id,
            transcription_text=result.transcription_text,
            language=result.language,
            confidence_score=result.confidence_score,
            duration_seconds=result.duration_seconds,
            audio_file_id=result.audio_file_id,
            original_filename=result.original_filename,
            model=result.model,
            processing_time_seconds=result.processing_time_seconds,
            created_at=result.created_at,
            metadata=result.metadata
        )

    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except Exception as e:
        logger.error(f"Error transcribing audio file: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Error processing audio transcription: {str(e)}"
        )


@router.get("/{session_id}", response_model=TranscriptionListResponse)
async def get_session_transcriptions(
    session_id: str,
    limit: int = 50,
    db: AsyncSession = Depends(get_db)
):
    """
    Get all transcriptions for a session.

    Args:
        session_id: Session ID to get transcriptions for
        limit: Maximum number of transcriptions to return (default: 50)
    """
    try:
        # Validate session exists
        session_result = await db.execute(
            select(Session).where(Session.id == session_id)
        )
        session_record = session_result.scalar_one_or_none()

        if not session_record:
            raise HTTPException(
                status_code=404,
                detail=f"Session {session_id} not found"
            )

        # Get transcriptions using the tool
        transcription_tool = WhisperTranscriptionTool()
        transcription_results = (
            await transcription_tool.get_session_transcriptions(
                session_id=session_id, limit=limit
            )
        )

        # Convert to response format
        transcriptions = [
            TranscriptionResponse(
                id=result.id,
                session_id=result.session_id,
                transcription_text=result.transcription_text,
                language=result.language,
                confidence_score=result.confidence_score,
                duration_seconds=result.duration_seconds,
                audio_file_id=result.audio_file_id,
                original_filename=result.original_filename,
                model=result.model,
                processing_time_seconds=result.processing_time_seconds,
                created_at=result.created_at,
                metadata=result.metadata
            )
            for result in transcription_results
        ]

        return TranscriptionListResponse(
            transcriptions=transcriptions,
            session_id=session_id,
            total_count=len(transcriptions)
        )

    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except Exception as e:
        logger.error(f"Error getting session transcriptions: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Error retrieving transcriptions: {str(e)}"
        )


@router.get("/transcriptions", response_model=TranscriptionListResponse)
async def get_all_transcriptions(limit: int = 50):
    """
    Get all transcriptions.
    """
    try:
        # Get transcriptions using the tool
        transcription_tool = WhisperTranscriptionTool()
        transcription_results = (
            await transcription_tool.get_session_transcriptions(
                limit=limit
            )
        )

        # Convert to response format
        transcriptions = [
            TranscriptionResponse(
                id=result.id,
                session_id=result.session_id,
                transcription_text=result.transcription_text,
                language=result.language,
                confidence_score=result.confidence_score,
                duration_seconds=result.duration_seconds,
                audio_file_id=result.audio_file_id,
                original_filename=result.original_filename,
                model=result.model,
                processing_time_seconds=result.processing_time_seconds,
                created_at=result.created_at,
                metadata=result.metadata
            )
            for result in transcription_results
        ]

        return TranscriptionListResponse(
            transcriptions=transcriptions,
            session_id="all",
            total_count=len(transcriptions)
        )
    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except Exception as e:
        logger.error(f"Error getting all transcriptions: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Error retrieving transcriptions: {str(e)}"
        )


@router.get(
    "/transcription/{transcription_id}", response_model=TranscriptionResponse
)
async def get_transcription(
    transcription_id: str,
    db: AsyncSession = Depends(get_db)
):
    """
    Get a specific transcription by ID.
    """
    try:
        # Query transcription from database
        result = await db.execute(
            select(Transcription).where(Transcription.id == transcription_id)
        )
        transcription = result.scalar_one_or_none()

        if not transcription:
            raise HTTPException(
                status_code=404,
                detail=f"Transcription {transcription_id} not found"
            )

        return TranscriptionResponse(
            id=transcription.id,
            session_id=transcription.session_id,
            transcription_text=transcription.transcription_text,
            language=transcription.language,
            confidence_score=transcription.confidence_score,
            duration_seconds=transcription.duration_seconds,
            audio_file_id=transcription.audio_file_id,
            original_filename=transcription.original_filename,
            model=transcription.model,
            processing_time_seconds=(
                transcription.processing_time_seconds or 0.0
            ),
            created_at=transcription.created_at,
            metadata=transcription.meta_data
        )

    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except Exception as e:
        logger.error(f"Error getting transcription {transcription_id}: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Error retrieving transcription: {str(e)}"
        )


@router.delete("/transcription/{transcription_id}")
async def delete_transcription(
    transcription_id: str,
    db: AsyncSession = Depends(get_db)
):
    """
    Delete a specific transcription by ID.
    """
    try:
        # Find and delete transcription
        result = await db.execute(
            select(Transcription).where(Transcription.id == transcription_id)
        )
        transcription = result.scalar_one_or_none()

        if not transcription:
            raise HTTPException(
                status_code=404,
                detail=f"Transcription {transcription_id} not found"
            )

        await db.delete(transcription)
        await db.commit()

        return JSONResponse(
            content={
                "message": f"Transcription {transcription_id} deleted "
                "successfully"
            },
            status_code=200
        )

    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except Exception as e:
        await db.rollback()
        logger.error(f"Error deleting transcription {transcription_id}: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Error deleting transcription: {str(e)}"
        )
