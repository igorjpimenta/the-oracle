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
    TranscriptionResponse, TranscriptionListResponse,
    ProcessingResponse, ProcessingStatusResponse
)
from ..core.tools.whisper_transcription import (
    WhisperTranscriptionTool, WhisperAvailableModels
)
from ..core.database import get_db
from ..core.database.schema import (
    Session, Transcription, TranscriptionProcessing,
    TranscriptionAnalysis, TranscriptionInsights
)
from ..core.database.queries import handle_persistence
from ..core.agent import get_processing_agent
from ..core.models.data import (
    TranscriptionData,
    TranscriptionAnalysis as TranscriptionAnalysisModel,
    ExtractedInsights as ExtractedInsightsModel
)

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


@router.get("/", response_model=TranscriptionListResponse)
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
    "/{transcription_id}", response_model=TranscriptionResponse
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


@router.delete("/{transcription_id}")
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


@router.post("/{transcription_id}/process", response_model=ProcessingResponse)
async def process_transcription(
    transcription_id: str,
    db: AsyncSession = Depends(get_db)
):
    """
    Start processing a transcription using the ProcessingWorkflow.

    This endpoint initiates background processing that includes:
    - Loading transcription data
    - Analyzing transcription content
    - Extracting insights
    - Storing results to database
    """
    try:
        # Check if transcription exists
        existing_transcription = await db.execute(
            select(Transcription).where(
                Transcription.id == transcription_id
            )
        )
        transcription_record = existing_transcription.scalar_one_or_none()

        if not transcription_record:
            raise HTTPException(
                status_code=404,
                detail=f"Transcription {transcription_id} not found"
            )

        # Check if processing already exists
        existing_processing = await db.execute(
            select(TranscriptionProcessing).where(
                TranscriptionProcessing.transcription_id ==
                transcription_id
            )
        )
        processing_record = existing_processing.scalar_one_or_none()

        if processing_record and processing_record.status in [
            "processing", "completed"
        ]:
            raise HTTPException(
                status_code=409,
                detail="Transcription is already being processed or completed"
            )

        if not processing_record:
            processing_record = TranscriptionProcessing(
                transcription_id=transcription_id,
                status="processing",
                meta_data={"thread_id": transcription_record.session_id}
            )
            db.add(processing_record)
            await db.commit()
        else:
            processing_record.status = "processing"
            await db.commit()

        # Get processing agent
        processing_agent = await get_processing_agent()

        # Use session ID as thread ID for processing
        thread_id = transcription_record.session_id

        # Create TranscriptionData for the workflow
        transcription_data = TranscriptionData(
            transcription_id=transcription_record.id,
            text=transcription_record.transcription_text,
            duration=transcription_record.duration_seconds,
            language=transcription_record.language,
            metadata=transcription_record.meta_data or {}
        )

        # Process transcription with memory
        result = await processing_agent.process_transcription(
            thread_id=thread_id,
            transcription_id=transcription_id,
            transcription_data=transcription_data
        )

        if result.analysis:
            result_analysis = await handle_persistence(
                db=db,
                table_model=TranscriptionAnalysis,
                record=dict(result.analysis),
                record_id=processing_record.analysis_id
            )
            processing_record.analysis_id = result_analysis["id"]

        if result.insights:
            result_insights = await handle_persistence(
                db=db,
                table_model=TranscriptionInsights,
                record=dict(result.insights),
                record_id=processing_record.insights_id
            )
            processing_record.insights_id = result_insights["id"]

        await db.commit()

        # Return processing response
        return ProcessingResponse(
            transcription_id=transcription_id,
            status=result.status,
            thread_id=thread_id,
            analysis=result.analysis,
            insights=result.insights,
            processing_time=result.processing_time,
            created_at=processing_record.created_at
        )
    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except Exception as e:
        logger.error(f"Error processing transcription: {e}")

        if processing_record:
            processing_record.status = "failed"
            processing_record.meta_data = {
                **(processing_record.meta_data or {}),
                "error": str(e)
            }
            await db.commit()

        raise HTTPException(
            status_code=500,
            detail=f"Error processing transcription: {str(e)}"
        )


@router.get(
    "/{transcription_id}/process",
    response_model=ProcessingStatusResponse
)
async def get_processing_transcription(
    transcription_id: str,
    db: AsyncSession = Depends(get_db)
):
    """
    Get the current processing results for a transcription.
    """
    try:
        # Fetch transcription to ensure it exists
        existing_transcription = await db.execute(
            select(Transcription).where(
                Transcription.id == transcription_id
            )
        )
        transcription_record = existing_transcription.scalar_one_or_none()

        if not transcription_record:
            raise HTTPException(
                status_code=404,
                detail=f"Transcription {transcription_id} not found"
            )

        # Fetch processing record
        existing_processing = await db.execute(
            select(TranscriptionProcessing).where(
                TranscriptionProcessing.transcription_id == transcription_id
            )
        )
        processing_record = existing_processing.scalar_one_or_none()

        if not processing_record:
            raise HTTPException(
                status_code=404,
                detail=f"Processing record for transcription "
                f"{transcription_id} not found"
            )

        analysis = None
        if processing_record.analysis_id:
            existing_analysis = await db.execute(
                select(TranscriptionAnalysis).where(
                    TranscriptionAnalysis.id == processing_record.analysis_id
                )
            )
            analysis_record = existing_analysis.scalar_one_or_none()
            if analysis_record:
                analysis = TranscriptionAnalysisModel(
                    summary=analysis_record.summary,
                    key_topics=analysis_record.key_topics,
                    sentiment=analysis_record.sentiment,
                    main_themes=analysis_record.main_themes,
                    important_quotes=analysis_record.important_quotes,
                    technical_terms=analysis_record.technical_terms
                )

        insights = None
        if processing_record.insights_id:
            existing_insights = await db.execute(
                select(TranscriptionInsights).where(
                    TranscriptionInsights.id == processing_record.insights_id
                )
            )
            insights_record = existing_insights.scalar_one_or_none()
            if insights_record:
                insights = ExtractedInsightsModel(
                    key_insights=insights_record.key_insights,
                    action_items=insights_record.action_items,
                    recommendations=insights_record.recommendations,
                    opportunities=insights_record.opportunities,
                    concerns=insights_record.concerns,
                    next_steps=insights_record.next_steps
                )

        return ProcessingStatusResponse(
            transcription_id=transcription_id,
            session_id=transcription_record.session_id,
            analysis=analysis,
            insights=insights,
            status=processing_record.status,
            created_at=processing_record.created_at,
            updated_at=processing_record.updated_at
        )

    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except Exception as e:
        logger.error(f"Error getting processing status: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Error retrieving processing status: {str(e)}"
        )
