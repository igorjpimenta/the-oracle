"""Task orchestrator node implementation."""

import logging

from ...config.instructor import instructor_client, llm_name
from ...models.nodes import TaskOrchestrator
from ...prompts.conversation import (
    TASK_ORCHESTRATOR_PROMPT,
    ORIENTATIONS_PROMPT
)
from ...models.messages import SMessage
from ...states import WorkerState

logger = logging.getLogger(__name__)


def task_orchestrator_node(state: WorkerState):
    """Task orchestrator node logic"""

    agent_name = "TaskOrchestrator"

    response = instructor_client.chat.completions.create(
        model=str(llm_name),
        response_model=TaskOrchestrator,
        messages=[
            SMessage(
                name=agent_name,
                content=_get_task_orchestrator_prompt(state)
            ).to_instructor_message(),
            *[
                x.to_instructor_message()
                for x in state["chat_history"][-5:]
            ],
        ]
    )

    message = SMessage(
        name=agent_name,
        content=_get_orientations_prompt(response),
    )

    return {
        "orientations_for_the_task": message,
        "next": response.chosen_agent.value,
    }


def _get_task_orchestrator_prompt(state: WorkerState) -> str:
    """Get task orchestrator prompt"""

    return TASK_ORCHESTRATOR_PROMPT.format(
        task=state["current_task"],
    )


def _get_orientations_prompt(response: TaskOrchestrator) -> str:
    """Get orientations prompt"""

    return ORIENTATIONS_PROMPT.format(
        objective=response.objective,
        orientations="\n".join(response.orientations),
        task=response.task,
    )
