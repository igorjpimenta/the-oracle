"""Data collector node implementation."""

import logging

from ..config.instructor import instructor_client, llm_name
from ..models.nodes import DataCollector
from ..prompts import DATA_COLLECTOR_PROMPT
from ..models.messages import SMessage
from ..models.data import CollectedData
from ..states import State

logger = logging.getLogger(__name__)


def data_collector_node(state: State):
    """Data collector node logic"""

    agent_name = "DataCollector"

    response = instructor_client.chat.completions.create(
        model=str(llm_name),
        response_model=DataCollector,
        messages=[
            SMessage(
                name=agent_name,
                content=_get_data_collector_prompt(state)
            ).to_instructor_message(),
            *[
                x.to_instructor_message()
                for x in state["messages"][-1:]
            ],
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


def _get_data_collector_prompt(state: State) -> str:
    """Get data collector prompt"""

    return DATA_COLLECTOR_PROMPT.format(
        previous_messages=(
            "\n".join(
                [
                    x.to_string()
                    for x in state["chat_history"][-5:]
                ]
            )
        ),
    )
