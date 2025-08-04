"""
Whisper transcription tool for LangGraph that handles audio file transcription.
Supports English and Spanish languages with graceful error handling.
"""

import os
import uuid
import logging
import tempfile
import time
import whisper  # type: ignore
import torch
import numpy as np
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from datetime import datetime
from typing import Optional, Any, cast, TypedDict, Literal
from dataclasses import dataclass

from ..clients.media import NyxenAPIClient, NyxenAPIException
from ..database.schema import Transcription
from ..database import get_db
from ..models.messages import SMessage

logger = logging.getLogger(__name__)


WhisperAvailableModels = Literal["base", "small", "medium", "large"]


class Segment(TypedDict):
    """Segment of transcription"""
    start: float
    end: float
    text: str
    tokens: torch.Tensor
    temperature: float
    avg_logprob: float
    compression_ratio: float
    no_speech_prob: float


@dataclass
class TranscriptionResult:
    """Result of audio transcription"""
    id: str
    session_id: str
    transcription_text: str
    language: str
    confidence_score: Optional[float]
    duration_seconds: Optional[float]
    audio_file_id: str
    original_filename: str
    model: str
    processing_time_seconds: Optional[float]
    created_at: datetime
    metadata: Optional[dict[str, Any]] = None

    def to_message(self) -> SMessage:
        """Convert transcription result to a system message"""
        duration_str = (
            f"{self.duration_seconds:.2f} seconds"
            if self.duration_seconds else "N/A"
        )
        confidence_str = (
            f"{self.confidence_score:.2f}"
            if self.confidence_score else "N/A"
        )

        return SMessage(
            name="WhisperTranscription",
            content=(
                f"Audio transcription completed:\n\n"
                f"Original file: {self.original_filename}\n"
                f"Language: {self.language}\n"
                f"Duration: {duration_str}\n"
                f"Model: {self.model}\n"
                f"Confidence: {confidence_str}\n\n"
                f"Transcription:\n{self.transcription_text}"
            )
        )


class WhisperTranscriptionTool:
    """
    Tool for transcribing audio files using OpenAI Whisper.

    Features:
    - Supports English and Spanish audio transcription
    - Uploads audio files to Nyxen media service
    - Stores transcription results in database
    - Graceful error handling and retries
    - Multiple Whisper model support (base, small, medium, large)
    """

    def __init__(self, whisper_model: WhisperAvailableModels = "base"):
        """
        Initialize the transcription tool.

        Args:
            whisper_model: Whisper model to use (base, small, medium, large)
        """
        self.whisper_model = whisper_model
        self.model = f"whisper-{whisper_model}"
        self._model: Optional[whisper.Whisper] = None
        self.supported_languages = ["en", "es", "auto"]
        self.supported_formats = [
            ".mp3", ".wav", ".m4a", ".mp4", ".opus", ".ogg", ".flac", ".webm"
        ]
        self._load_whisper_model()

    def _load_whisper_model(self) -> None:
        """Load Whisper model if not already loaded"""
        if self._model is None:
            logger.info(f"Loading Whisper model: {self.whisper_model}")
            try:
                self._model = whisper.load_model(self.whisper_model)
                logger.info(
                    f"Successfully loaded Whisper model: {self.whisper_model}"
                )
            except Exception as e:
                logger.error(
                    f"Failed to load Whisper model {self.whisper_model}: "
                    f"{str(e)}"
                )
                raise

    def _get_file_extension(self, filename: str) -> str:
        """Get file extension from filename"""
        return os.path.splitext(filename.lower())[1]

    def _is_supported_format(self, filename: str) -> bool:
        """Check if the file format is supported"""
        extension = self._get_file_extension(filename)
        return extension in self.supported_formats

    def _validate_language(self, language: Optional[str]) -> str:
        """Validate and normalize language parameter"""
        if language is None:
            return "auto"

        language = language.lower()
        if language in self.supported_languages:
            return language

        # Try to map common language codes
        language_map = {
            "english": "en",
            "spanish": "es",
        }

        return language_map.get(language, "auto")

    async def _save_transcription_to_db(
        self,
        db: AsyncSession,
        session_id: str,
        audio_file_id: str,
        original_filename: str,
        transcription_text: str,
        language: str,
        confidence_score: Optional[float],
        duration_seconds: Optional[float],
        audio_size_bytes: Optional[int],
        processing_time_seconds: float,
        metadata: Optional[dict[str, Any]] = None
    ) -> Transcription:
        """Save transcription result to database"""

        transcription = Transcription(
            id=str(uuid.uuid4()),
            session_id=session_id,
            audio_file_id=audio_file_id,
            original_filename=original_filename,
            transcription_text=transcription_text,
            language=language,
            confidence_score=confidence_score,
            duration_seconds=duration_seconds,
            audio_size_bytes=audio_size_bytes,
            model=self.model,
            processing_time_seconds=processing_time_seconds,
            meta_data=metadata
        )

        db.add(transcription)
        await db.commit()
        await db.refresh(transcription)

        logger.info(
            f"Saved transcription to database with ID: {transcription.id}")
        return transcription

    def _transcribe_audio_file(
        self,
        audio_file_path: str,
        language: Optional[str] = None
    ) -> dict[str, Any]:
        """
        Transcribe audio file using Whisper.

        Args:
            audio_file_path: Path to the audio file
            language: Language code (en, es, or auto for detection)

        Returns:
            Dictionary with transcription results
        """
        self._load_whisper_model()

        start_time = time.time()

        try:
            if self._model is None:
                raise ValueError(
                    "Whisper model not loaded. It should be loaded "
                    "in the constructor."
                )

            # Prepare options for Whisper
            options: dict[str, Any] = {}

            if language and language != "auto":
                options["language"] = language

            logger.info(
                f"Starting transcription of audio file: {audio_file_path}"
            )
            logger.info(f"Using language: {language or 'auto-detect'}")

            # Perform transcription
            result = self._model.transcribe(audio_file_path, **options)

            processing_time = time.time() - start_time

            # Extract results
            transcription_text = cast(str, result["text"]).strip()
            detected_language = result.get("language", language or "unknown")

            # Calculate average confidence if segments are available
            confidence_score = None
            if "segments" in result and \
                    (segments := cast(list[Segment], result["segments"])):
                # Average confidence from all segments
                confidences = [
                    segment["avg_logprob"]
                    for segment in segments
                    if segment["avg_logprob"] is not np.nan
                ]
                if confidences:
                    confidence_score = sum(confidences) / len(confidences)
                    # Convert log probability to confidence score (0-1)
                    confidence_score = max(0, min(1, (confidence_score + 1)))

            logger.info(
                f"Transcription completed in {processing_time:.2f} seconds"
            )
            logger.info(f"Detected language: {detected_language}")
            logger.info(
                f"Transcription length: {len(transcription_text)} characters"
            )

            return {
                "text": transcription_text,
                "language": detected_language,
                "confidence_score": confidence_score,
                "processing_time_seconds": processing_time,
                "segments": result.get("segments", []),
                "full_result": result
            }

        except Exception as e:
            processing_time = time.time() - start_time
            logger.error(
                f"Transcription failed after {processing_time:.2f} seconds: "
                f"{str(e)}"
            )
            raise

    async def transcribe_audio(
        self,
        session_id: str,
        audio_content: bytes,
        filename: str,
        language: Optional[str] = None,
        mimetype: str = "audio/mpeg"
    ) -> TranscriptionResult:
        """
        Transcribe audio content and store results.

        Args:
            session_id: Session ID to associate the transcription with
            audio_content: Audio file content as bytes
            filename: Original filename
            language: Language for transcription (en, es, or auto)
            mimetype: MIME type of the audio file

        Returns:
            TranscriptionResult with all transcription details

        Raises:
            ValueError: If file format is not supported
            NyxenAPIException: If media upload fails
            Exception: If transcription or database operations fail
        """

        # Validate inputs
        if not self._is_supported_format(filename):
            supported_str = ', '.join(self.supported_formats)
            raise ValueError(
                f"Unsupported audio format. File: {filename}. "
                f"Supported formats: {supported_str}"
            )

        language = self._validate_language(language)

        logger.info(f"Starting audio transcription for session {session_id}")
        logger.info(
            f"File: {filename}, Size: {len(audio_content)} bytes, "
            f"Language: {language}"
        )

        # Upload audio file to Nyxen media service
        async with NyxenAPIClient() as nyxen_client:
            try:
                upload_response = await nyxen_client.upload_audio_file(
                    file_content=audio_content,
                    filename=filename,
                    mimetype=mimetype
                )
                logger.info(
                    f"Audio file uploaded to Nyxen with ID: "
                    f"{upload_response['id']}"
                )

                # Get the file URL
                audio_file_url = await nyxen_client.get_media_file_url(
                    upload_response["id"]
                )
                logger.info(
                    f"Audio file URL: {audio_file_url}"
                )

            except Exception as e:
                logger.error(f"Failed to upload audio file: {str(e)}")
                raise NyxenAPIException(f"Audio upload failed: {str(e)}")

        # Create temporary file for Whisper processing
        transcription_result = None
        with tempfile.NamedTemporaryFile(
            delete=False, suffix=self._get_file_extension(filename)
        ) as temp_file:
            try:
                # Write audio content to temporary file
                temp_file.write(audio_content)
                temp_file.flush()
                temp_file_path = temp_file.name

                logger.info(
                    "Created temporary file for transcription: "
                    f"{temp_file_path}"
                )

                # Perform transcription
                transcription_result = self._transcribe_audio_file(
                    audio_file_path=temp_file_path,
                    language=language if language != "auto" else None
                )

            finally:
                # Clean up temporary file
                try:
                    os.unlink(temp_file_path)
                    logger.debug(
                        f"Cleaned up temporary file: {temp_file_path}"
                    )
                except Exception as e:
                    logger.warning(
                        f"Failed to clean up temporary file {temp_file_path}: "
                        f"{str(e)}"
                    )

        if not transcription_result:
            raise Exception("Transcription failed - no result returned")

        # Save to database
        async for db in get_db():
            try:
                transcription = await self._save_transcription_to_db(
                    db=db,
                    session_id=session_id,
                    audio_file_id=upload_response["id"],
                    original_filename=upload_response["originalname"],
                    transcription_text=transcription_result["text"],
                    language=transcription_result["language"],
                    confidence_score=transcription_result["confidence_score"],
                    duration_seconds=transcription_result.get("duration"),
                    audio_size_bytes=upload_response["size"],
                    processing_time_seconds=transcription_result.get(
                        "processing_time_seconds", 0.0
                    ),
                    metadata={
                        "segments": transcription_result.get("segments", []),
                        "model": self.model,
                        "upload_info": {
                            "bucket": upload_response["bucket"],
                            "public": upload_response["public"],
                            "mimetype": upload_response["mimetype"]
                        }
                    }
                )

                # Create result object
                result = TranscriptionResult(
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
                        transcription.processing_time_seconds
                    ),
                    created_at=transcription.created_at,
                    metadata=transcription.meta_data
                )

                logger.info(
                    f"Audio transcription completed successfully. "
                    f"Transcription ID: {result.id}"
                )
                return result

            except Exception as e:
                logger.error(
                    f"Failed to save transcription to database: {str(e)}"
                )
                raise

        raise Exception("Database operation failed")

    async def get_session_transcriptions(
        self,
        session_id: Optional[str] = None,
        limit: int = 50
    ) -> list[TranscriptionResult]:
        """
        Get all transcriptions for a session.

        Args:
            session_id: Session ID
            limit: Maximum number of transcriptions to return

        Returns:
            List of TranscriptionResult objects
        """
        transcription_results: list[TranscriptionResult] = []

        async for db in get_db():
            # Query transcriptions for the session
            stmt = (
                select(Transcription)
                .order_by(Transcription.created_at.desc())
                .limit(limit)
            )

            if session_id:
                stmt = stmt \
                    .where(Transcription.session_id == session_id)

            result = await db.execute(stmt)
            transcriptions = result.scalars().all()

            # Convert to TranscriptionResult objects
            transcription_results = [
                TranscriptionResult(
                    id=t.id,
                    session_id=t.session_id,
                    transcription_text=t.transcription_text,
                    language=t.language,
                    confidence_score=t.confidence_score,
                    duration_seconds=t.duration_seconds,
                    audio_file_id=t.audio_file_id,
                    original_filename=t.original_filename,
                    model=t.model,
                    processing_time_seconds=t.processing_time_seconds or 0.0,
                    created_at=t.created_at,
                    metadata=t.meta_data
                )
                for t in transcriptions
            ]

        return transcription_results


# Factory function for creating transcription tool instances
def _create_whisper_tool(model: WhisperAvailableModels = "base") \
        -> WhisperTranscriptionTool:
    """
    Create a Whisper transcription tool instance.

    Args:
        model: Whisper model to use (base, small, medium, large)

    Returns:
        WhisperTranscriptionTool instance
    """
    return WhisperTranscriptionTool(whisper_model=model)


# Tool function for LangGraph integration
async def transcribe_audio_tool(
    _: dict[str, Any],
    session_id: str,
    audio_content: bytes,
    filename: str,
    language: Optional[str] = None,
    whisper_model: WhisperAvailableModels = "base"
) -> dict[str, Any]:
    """
    LangGraph-compatible tool function for audio transcription.

    Args:
        state: LangGraph state (not used but required for compatibility)
        session_id: Session ID to associate the transcription with
        audio_content: Audio file content as bytes
        filename: Original filename
        language: Language for transcription (en, es, or auto)
        whisper_model: Whisper model to use

    Returns:
        Updated state with transcription message
    """

    tool = _create_whisper_tool(whisper_model)

    try:
        result = await tool.transcribe_audio(
            session_id=session_id,
            audio_content=audio_content,
            filename=filename,
            language=language
        )

        # Create message from result
        message = result.to_message()

        # Update state with transcription result
        return {
            "messages": [message],
            "transcription_result": {
                "id": result.id,
                "text": result.transcription_text,
                "language": result.language,
                "confidence": result.confidence_score,
                "duration": result.duration_seconds,
                "file_id": result.audio_file_id,
                "filename": result.original_filename
            }
        }

    except Exception as e:
        logger.error(f"Transcription tool failed: {str(e)}")

        # Return error message
        error_message = SMessage(
            name="WhisperTranscription",
            content=f"Audio transcription failed: {str(e)}"
        )

        return {
            "messages": [error_message],
            "transcription_error": str(e)
        }
