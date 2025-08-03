"""Manager node implementation."""

import logging

from ..config.instructor import instructor_client, llm_name
from ..models.nodes import Manager
from ..prompts import MANAGER_PROMPT
from ..models.messages import SMessage
from ..states import State

logger = logging.getLogger(__name__)


def manager_node(state: State):
    """Manager node logic"""

    agent_name = "Manager"

    response = instructor_client.chat.completions.create(
        model=str(llm_name),
        response_model=Manager,
        messages=[
            SMessage(
                name=agent_name,
                content=_get_manager_prompt(state)
            ).to_instructor_message(),
        ]
    )

    return {
        "unhandled_tasks": response.tasks,
    }


def _get_manager_prompt(state: State) -> str:
    """Get manager prompt"""

    return MANAGER_PROMPT.format(
        inquiry=state["current_inquiry"],
        previous_messages=(
            "\n".join(
                [x.to_string() for x in state["chat_history"][-5:]]
            )
        ),
    )
