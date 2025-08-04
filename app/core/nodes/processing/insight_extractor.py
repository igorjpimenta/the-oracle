"""
Insight extractor node - extracts insights for background processing.
"""

import logging

from ...config.instructor import instructor_client, llm_name
from ...models.nodes import InsightExtractor
from ...prompts.processing import INSIGHT_EXTRACTOR_PROMPT
from ...models.messages import SMessage
from ...states import ProcessingState

logger = logging.getLogger(__name__)


async def insight_extractor_node(state: ProcessingState):
    """Extract insights from transcription analysis in background processing"""

    agent_name = "ProcessingInsightExtractor"
    transcription_data = state["transcription_data"]

    if not state["transcription_analysis"]:
        error_message = (
            "No transcription analysis available for insight extraction"
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

    try:
        logger.info(
            "Starting insight extraction for transcription "
            f"{transcription_data['transcription_id']}"
        )

        response = instructor_client.chat.completions.create(
            model=str(llm_name),
            response_model=InsightExtractor,
            messages=[
                SMessage(
                    name=agent_name,
                    content=_get_insight_extractor_prompt(state)
                ).to_instructor_message(),
            ]
        )

        logger.info(
            "Completed insight extraction for transcription "
            f"{transcription_data['transcription_id']}"
        )

        return {
            "extracted_insights": response.model_dump(),
            "messages": [
                SMessage(
                    name=agent_name,
                    content="Insights extracted for transcription "
                    f"{transcription_data['transcription_id']}"
                )
            ],
        }

    except Exception as e:
        error_message = (
            "Error extracting insights for transcription "
            f"{transcription_data['transcription_id']}: {str(e)}"
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


def _get_insight_extractor_prompt(state: ProcessingState):
    """Get processing insight extractor prompt"""

    analysis = state["transcription_analysis"]
    assert analysis is not None, "Transcription analysis is required"
    transcription_data = state["transcription_data"]

    return INSIGHT_EXTRACTOR_PROMPT.format(
        summary=analysis["summary"],
        key_topics=", ".join(analysis["key_topics"]),
        sentiment=analysis["sentiment"],
        main_themes=", ".join(analysis["main_themes"]),
        important_quotes="\n".join(analysis["important_quotes"]),
        technical_terms=", ".join(analysis["technical_terms"]),
        duration=transcription_data.get("duration", "unknown"),
    )
