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


class Touchpoint(BaseModel):
    """Touchpoint model"""

    answer: str = Field(
        ...,
        description="The answer for the user's inquiry"
    )


# Transcription-specific node models

class TranscriptionLoader(BaseModel):
    """Transcription loader model"""

    text_preview: str = Field(
        ...,
        description=(
            "Short summary of the transcription with the most "
            "important information. The core of the transcription content"
        )
    )


class TranscriptionAnalyzer(BaseModel):
    """Transcription analyzer model"""

    summary: str = Field(
        ...,
        description="Comprehensive summary of the transcription content"
    )
    key_topics: list[str] = Field(
        ...,
        description="Main topics discussed in the transcription"
    )
    sentiment: str = Field(
        ...,
        description=(
            "Overall sentiment of the transcription (positive, negative, "
            "neutral, mixed)"
        )
    )
    main_themes: list[str] = Field(
        ...,
        description="Core themes and concepts from the transcription"
    )
    important_quotes: list[str] = Field(
        ...,
        description="Key quotes or important statements from the transcription"
    )
    technical_terms: list[str] = Field(
        ...,
        description="Technical terms, jargon, or specialized vocabulary used"
    )


class InsightExtractor(BaseModel):
    """Insight extractor model"""

    key_insights: list[str] = Field(
        ...,
        description="Most important insights derived from the transcription"
    )
    action_items: list[str] = Field(
        ...,
        description="Specific actionable items mentioned or implied"
    )
    recommendations: list[str] = Field(
        ...,
        description="Strategic recommendations based on the content"
    )
    opportunities: list[str] = Field(
        ...,
        description="Opportunities identified from the discussion"
    )
    concerns: list[str] = Field(
        ...,
        description="Concerns, risks, or issues highlighted"
    )
    next_steps: list[str] = Field(
        ...,
        description="Suggested next steps or follow-up actions"
    )


class TranscriptionDigger(BaseModel):
    """Transcription digger model"""

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
