"""
Conversation handler node - handles user Q&A about processed transcriptions.
"""

import logging

from ...config.instructor import instructor_client, llm_name
from ...models.nodes import TranscriptionDigger
from ...prompts.conversation import get_transcription_digger_prompt
from ...models.messages import SMessage
from ...models.data import CollectedData
from ...states import WorkerState

logger = logging.getLogger(__name__)


def transcription_digger_node(state: WorkerState):
    """Handle user conversation about processed transcription"""

    agent_name = "TranscriptionDigger"

    response = instructor_client.chat.completions.create(
        model=str(llm_name),
        response_model=TranscriptionDigger,
        messages=[
            SMessage(
                name=agent_name,
                content=_get_transcription_digger_prompt(state)
            ).to_instructor_message(),
            *(
                [
                    state["orientations_for_the_task"]
                    .to_instructor_message()
                ]
                if state["orientations_for_the_task"]
                else []
            ),
        ]
    )

    return {
        "data_for_the_task": [
            CollectedData(
                data=response.data_collected,
                notes=response.notes,
            )
        ]
    }


def _get_transcription_digger_prompt(state: WorkerState):
    """Get transcription digger prompt"""

    analysis = state["analysis"]
    insights = state["insights"]

    return get_transcription_digger_prompt(
        analysis=analysis,
        insights=insights
    ).format(
        task=state["current_task"],
        previous_messages=(
            "\n".join(
                [
                    x.to_string()
                    for x in state["chat_history"][-5:]
                ]
            )
        ),
    )
