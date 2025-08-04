"""Intent seeker node implementation."""

from ...config.instructor import instructor_client, llm_name
from ...models.nodes import IntentionSeeker
from ...prompts.conversation import INTENT_SEEKER_PROMPT
from ...models.messages import SMessage
from ...states import State


def intent_seeker_node(state: State):
    """Intent seeker node logic"""

    agent_name = "IntentionSeeker"

    response = instructor_client.chat.completions.create(
        model=str(llm_name),
        response_model=IntentionSeeker,
        messages=[
            SMessage(
                name=agent_name,
                content=_get_intent_seeker_prompt(state)
            ).to_instructor_message(),
        ]
    )

    return {
        "current_intention": response.intention,
        "current_inquiry": response.inquiry,
    }


def _get_intent_seeker_prompt(state: State):
    """Get intent seeker prompt"""

    return INTENT_SEEKER_PROMPT.format(
        previous_messages=(
            "\n".join(
                [x.to_string() for x in state["chat_history"][-10:]]
            )
        ),
    )
