import operator
from langgraph.graph import StateGraph as LangGraphStateGraph
from typing import (
    TypedDict, Annotated, Self, Callable,
    Awaitable, Union, Optional, Hashable, Any
)
from langchain_core.runnables import Runnable

from .models.enums import Intention
from .models.messages import Message
from .models.data import CollectedData
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
    chat_history: Annotated[list[Message], operator.add]
    messages: Annotated[list[Message], operator.add]
    next: str


class State(BaseState):
    """State"""
    current_intention: Intention
    current_inquiry: str
    unhandled_tasks: Annotated[list[str], operators.reset_when_empty]
    data_for_the_task: Annotated[
        list[CollectedData], operators.reset_when_empty
    ]
