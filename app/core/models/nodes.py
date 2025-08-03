from pydantic import BaseModel, Field

from .enums import Intention, WorkerAgent


class IntentionSeeker(BaseModel):
    """Intention seeker model"""

    intention: Intention = Field(
        ...,
        description="The intention of the user for the current iteration"
    )
    inquiry: str = Field(
        ...,
        description=(
            "The interpretation of the user's inquiry for the current "
            "iteration. This is the user's inquiry in your own words based "
            "on the context of the conversation"
        )
    )


class Manager(BaseModel):
    """Manager model"""

    tasks: list[str] = Field(
        ...,
        description=(
            "The list of tasks to be executed for accomplishing the "
            "given inquiry"
        )
    )


class TaskOrchestrator(BaseModel):
    """Task orchestrator model"""

    task: str = Field(
        ...,
        description=(
            "The task to be executed for accomplishing the given inquiry"
        )
    )
    objective: str = Field(
        ...,
        description="The objective for the chosen agent to accomplish the task"
    )
    orientations: list[str] = Field(
        ...,
        description=(
            "The orientations for the chosen agent to accomplish the task"
        )
    )
    chosen_agent: WorkerAgent = Field(
        ...,
        description=(
            "The agent that will be accountable for executing the task"
        )
    )


class DataCollector(BaseModel):
    """Data collector model"""

    data_collected: str = Field(
        ...,
        description="The data collected for the given task"
    )
    notes: str = Field(
        ...,
        description=(
            "The notes about the given task about the data output"
        )
    )


class Touchpoint(BaseModel):
    """Touchpoint model"""

    answer: str = Field(
        ...,
        description="The answer for the user's inquiry"
    )
