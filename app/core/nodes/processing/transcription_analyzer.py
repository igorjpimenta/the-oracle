"""
Transcription analyzer node - deep analysis for background processing.
"""

import logging

from ...config.instructor import instructor_client, llm_name
from ...models.nodes import TranscriptionAnalyzer
from ...prompts.processing import TRANSCRIPTION_ANALYZER_PROMPT
from ...models.messages import SMessage
from ...states import ProcessingState

logger = logging.getLogger(__name__)


async def transcription_analyzer_node(state: ProcessingState):
    """Analyze transcription content in background processing"""

    agent_name = "ProcessingTranscriptionAnalyzer"

    try:
        logger.info(
            "Starting analysis for transcription "
            f"{state['transcription_data']['transcription_id']}"
        )

        response = instructor_client.chat.completions.create(
            model=str(llm_name),
            response_model=TranscriptionAnalyzer,
            messages=[
                SMessage(
                    name=agent_name,
                    content=_get_analyzer_prompt(state)
                ).to_instructor_message(),
            ]
        )

        logger.info(
            "Completed analysis for transcription "
            f"{state['transcription_data']['transcription_id']}"
        )

        return {
            "transcription_analysis": response.model_dump(),
            "messages": [
                SMessage(
                    name=agent_name,
                    content=(
                        "Analysis results completed for transcription "
                        f"{state['transcription_data']['transcription_id']}"
                    )
                )
            ],
        }

    except Exception as e:
        error_message = (
            "Error analyzing transcription "
            f"{state['transcription_data']['transcription_id']}: {str(e)}"
        )
        logger.error(error_message)
        return {
            "messages": [
                SMessage(
                    name=agent_name,
                    content=error_message
                )
            ],
        }


def _get_analyzer_prompt(state: ProcessingState):
    """Get processing transcription analyzer prompt"""

    transcription_data = state["transcription_data"]

    return TRANSCRIPTION_ANALYZER_PROMPT.format(
        transcription_text=transcription_data["text"],
        duration=transcription_data.get("duration", "unknown"),
        language=transcription_data.get("language", "unknown"),
    )
