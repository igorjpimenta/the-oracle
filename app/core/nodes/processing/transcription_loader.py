"""
Processing transcription loader node - loads transcription for background
analysis.
"""

import logging
from sqlalchemy import select
from typing import TypedDict, Optional

from ...config.instructor import instructor_client, llm_name
from ...models.nodes import TranscriptionLoader
from ...prompts.processing import TRANSCRIPTION_LOADER_PROMPT
from ...models.messages import SMessage
from ...states import ProcessingState
from ...database.db import get_db
from ...database.schema import Transcription

logger = logging.getLogger(__name__)


class TranscriptionMetadata(TypedDict):
    original_filename: str
    model: str
    confidence_score: Optional[float]
    processing_time: Optional[float]


class TranscriptionData(TypedDict):
    transcription_id: str
    text: str
    duration: Optional[float]
    language: Optional[str]
    metadata: Optional[TranscriptionMetadata]


async def transcription_loader_node(state: ProcessingState):
    """Load transcription data for background processing"""

    agent_name = "ProcessingTranscriptionLoader"
    transcription_id = state["transcription_id"]

    try:
        async for db in get_db():
            transcription_result = await db.execute(
                select(Transcription).where(
                    Transcription.id == transcription_id
                )
            )
            transcription = transcription_result.scalar_one_or_none()

            if not transcription:
                raise ValueError(
                    f"Transcription {transcription_id} not found"
                )

            transcription_data: TranscriptionData = {
                "transcription_id": transcription.id,
                "text": transcription.transcription_text,
                "duration": transcription.duration_seconds,
                "language": transcription.language,
                "metadata": {
                    "original_filename": transcription.original_filename,
                    "model": transcription.model,
                    "confidence_score": transcription.confidence_score,
                    "processing_time": transcription.processing_time_seconds
                },
            }

            response = instructor_client.chat.completions.create(
                model=str(llm_name),
                response_model=TranscriptionLoader,
                messages=[
                    SMessage(
                        name=agent_name,
                        content=_get_loader_prompt(
                            transcription_data
                        )
                    ).to_instructor_message(),
                ]
            )

            logger.info(
                "Successfully loaded transcription "
                f"{transcription_id} for processing"
            )

            return {
                "transcription_data": transcription_data,
                "messages": [
                    SMessage(
                        name=agent_name,
                        content=(
                            "Loaded transcription for processing: "
                            f"{response.text_preview}"
                        )
                    )
                ],
            }

    except Exception as e:
        error_message = (
            f"Error loading transcription {transcription_id}: {str(e)}"
        )
        logger.error(error_message)
        return {
            "messages": [
                SMessage(
                    name=agent_name,
                    content=error_message
                )
            ]
        }


def _get_loader_prompt(transcription_data: TranscriptionData):
    """Get processing transcription loader prompt"""

    return TRANSCRIPTION_LOADER_PROMPT.format(
        transcription_id=transcription_data["transcription_id"],
        text=transcription_data["text"],
        metadata=transcription_data["metadata"]
    )
