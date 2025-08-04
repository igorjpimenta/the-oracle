import operator
from langgraph.graph import StateGraph as LangGraphStateGraph
from typing import (
    TypedDict, Annotated, Self, Callable,
    Awaitable, Union, Optional, Hashable, Any
)
from langchain_core.runnables import Runnable

from .models.enums import Intention
from .models.messages import Message
from .models.data import (
    CollectedData,
    TranscriptionData,
    TranscriptionAnalysis,
    ExtractedInsights,
)
from .utils import operators


class StateGraph(LangGraphStateGraph):
    def add_multiple_conditional_edges(
        self,
        source: list[str],
        path: Union[
            Callable[..., Union[Hashable, list[Hashable]]],
            Callable[..., Awaitable[Union[Hashable, list[Hashable]]]],
            Runnable[Any, Union[Hashable, list[Hashable]]],
        ],
        path_map: Optional[Union[dict[Hashable, str], list[str]]] = None,
        then: Optional[str] = None,
    ) -> Self:
        for s in source:
            super().add_conditional_edges(
                source=s,
                path=path,
                path_map=path_map,
                then=then,
            )

        return self


class BaseState(TypedDict):
    """Base state"""
    thread_id: str


class ConversationalState(BaseState):
    """Conversational state"""
    chat_history: Annotated[list[Message], operator.add]
    messages: Annotated[list[Message], operator.add]
    next: str


class State(ConversationalState):
    """State"""
    current_intention: Intention
    current_inquiry: str
    current_task: str
    unhandled_tasks: Annotated[list[str], operators.reset_when_empty]
    data_for_the_task: Annotated[
        list[CollectedData], operators.reset_when_empty
    ]
    transcription_data: TranscriptionData
    transcription_analysis: Optional[TranscriptionAnalysis]
    extracted_insights: Optional[ExtractedInsights]


class ProcessingState(BaseState):
    """State schema for background transcription processing workflow"""
    # Transcription data to process
    transcription_id: str
    transcription_data: TranscriptionData

    # Analysis results (built progressively)
    transcription_analysis: Optional[TranscriptionAnalysis]
    extracted_insights: Optional[ExtractedInsights]
