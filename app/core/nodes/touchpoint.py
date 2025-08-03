"""Touchpoint node implementation."""

import logging

from ..utils import get_current_date
from ..models.nodes import Touchpoint
from ..models.messages import SMessage
from ..states import State
from ..config.instructor import instructor_client, llm_name
from ..prompts import TOUCHPOINT_PROMPT

logger = logging.getLogger(__name__)


def touchpoint_node(state: State):
    """Touchpoint node logic"""

    agent_name = "Touchpoint"

    response = instructor_client.chat.completions.create(
        model=str(llm_name),
        response_model=Touchpoint,
        messages=[
            SMessage(
                name=agent_name,
                content=_get_touchpoint_prompt(state)
            ).to_instructor_message(),
            *[
                x.to_instructor_message()
                for x in state["messages"][-5:]
            ],
        ]
    )

    message = SMessage(
        name=agent_name,
        content=response.answer
    )

    return {
        "chat_history": [message],
    }


def _get_touchpoint_prompt(state: State) -> str:
    """Get touchpoint prompt"""

    return TOUCHPOINT_PROMPT.format(
        inquiry=state["current_inquiry"],
        current_date=get_current_date(),
        collected_data=(
            "\n\n".join(
                [
                    f"Data: {x['data']}\nNotes: {x['notes']}"
                    for x in state["data_for_the_task"]
                ]
            )
        ),
        previous_messages=(
            "\n".join(
                [
                    x.to_string()
                    for x in state["chat_history"][-5:]
                ]
            )
        ),
    )
