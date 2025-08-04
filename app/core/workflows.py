from abc import ABC, abstractmethod
from typing import cast
from langgraph.graph import START, END

from .nodes.conversation import (
    intent_seeker_node,
    manager_node,
    task_orchestrator_node,
    transcription_digger_node,
    touchpoint_node,
)
from .nodes.processing import (
    # Processing workflow nodes
    transcription_loader_node,
    transcription_analyzer_node,
    insight_extractor_node,
    results_storage_node,
)
from .states import (
    BaseState, State, ProcessingState, StateGraph
)
from .models.enums import Agent, Intention
from .models.data import TranscriptionData


class BaseWorkflow(ABC):
    _graph: StateGraph
    _setted_up: bool

    @property
    @abstractmethod
    def state_schema(self) -> type[BaseState]:
        raise NotImplementedError("Subclass must implement this property")

    def __init__(self):
        self._setted_up = False

    def get_graph(self) -> StateGraph:
        if not self._setted_up:
            graph = StateGraph(self.state_schema)
            self._graph = self._setup_graph(graph)
            self._setted_up = True

        return self._graph

    @abstractmethod
    def _setup_graph(self, graph: StateGraph) -> StateGraph:
        raise NotImplementedError("Subclass must implement this method")


class DefaultWorkflow(BaseWorkflow):
    """User-facing workflow for Q&A about processed transcriptions"""

    @property
    def state_schema(self) -> type[BaseState]:
        return State

    def _setup_graph(self, graph: StateGraph) -> StateGraph:
        graph.add_node("intent_seeker", intent_seeker_node)
        graph.add_node("manager", manager_node)
        graph.add_node("task_orchestrator", task_orchestrator_node)
        graph.add_node("transcription_digger", transcription_digger_node)
        graph.add_node("touchpoint", touchpoint_node)

        graph.add_edge(START, "intent_seeker")
        graph.add_edge("intent_seeker", "manager")

        graph.add_conditional_edges(
            "manager",
            self._next_after_manager,
            {
                "task_orchestrator": "task_orchestrator",
                "touchpoint": "touchpoint",
            }
        )

        graph.add_conditional_edges(
            "task_orchestrator",
            self._next_worker,
            {
                "transcription_digger": "transcription_digger",
            }
        )

        graph.add_conditional_edges(
            "transcription_digger",
            self._next_after_task,
            {
                "task_orchestrator": "task_orchestrator",
                "touchpoint": "touchpoint",
            }
        )
        graph.add_edge("touchpoint", END)

        return graph

    def _next_worker(self, state: State) -> str:
        return state["next"]

    def _next_after_task(self, state: State) -> str:
        if len(state["unhandled_tasks"]) > 0:
            return Agent.TASK_ORCHESTRATOR.value
        return Agent.TOUCHPOINT.value

    def _next_after_manager(self, state: State) -> str:
        if state["current_intention"] == Intention.GREET:
            return Agent.TOUCHPOINT.value
        return Agent.TASK_ORCHESTRATOR.value

    def get_initial_state(self, *_, **kwargs) -> State:
        thread_id: str = kwargs.get("thread_id", None)
        if not thread_id:
            raise ValueError("Thread ID is required.")

        transcription_data = kwargs.get("transcription_data", None)
        if not transcription_data:
            raise ValueError("Transcription data is required.")

        chat_history = kwargs.get("chat_history", [])
        if not chat_history or not isinstance(chat_history, list):
            raise ValueError("Chat history must be a non-empty list.")

        transcription_analysis = kwargs.get("transcription_analysis", None)
        extracted_insights = kwargs.get("extracted_insights", None)

        return State(
            thread_id=cast(str, thread_id),
            chat_history=chat_history,
            messages=[],
            current_intention=Intention.GREET,
            current_inquiry="",
            current_task="",
            unhandled_tasks=[],
            data_for_the_task=[],
            transcription_data=transcription_data,
            transcription_analysis=transcription_analysis,
            extracted_insights=extracted_insights,
            next=Agent.INTENT_SEEKER.value,
        )


class FallbackWorkflow(BaseWorkflow):
    @property
    def state_schema(self) -> type[BaseState]:
        return State

    def _setup_graph(self, graph: StateGraph) -> StateGraph:
        graph.add_node("touchpoint", touchpoint_node)

        graph.add_edge(START, "touchpoint")
        graph.add_edge("touchpoint", END)

        return graph


class ProcessingWorkflow(BaseWorkflow):
    """Background workflow for processing transcriptions (queue-based)"""

    @property
    def state_schema(self) -> type[BaseState]:
        return ProcessingState

    def _setup_graph(self, graph: StateGraph) -> StateGraph:
        graph.add_node("transcription_loader", transcription_loader_node)
        graph.add_node("transcription_analyzer", transcription_analyzer_node)
        graph.add_node("insight_extractor",  insight_extractor_node)
        graph.add_node("results_storage", results_storage_node)

        graph.add_edge(START, "transcription_loader")
        graph.add_edge("transcription_loader", "transcription_analyzer")
        graph.add_edge("transcription_analyzer", "insight_extractor")
        graph.add_edge("insight_extractor", "results_storage")
        graph.add_edge("results_storage", END)

        return graph

    def get_initial_state(self, *_, **kwargs) -> ProcessingState:
        thread_id: str = kwargs.get("thread_id", None)
        if not thread_id:
            raise ValueError("Thread ID is required.")

        transcription_id: str = kwargs.get("transcription_id", None)
        if not transcription_id:
            raise ValueError("Transcription ID is required.")

        transcription_data: TranscriptionData = kwargs.get(
            "transcription_data", None)
        if not transcription_data:
            raise ValueError("Transcription data is required.")

        return ProcessingState(
            thread_id=thread_id,
            transcription_id=transcription_id,
            transcription_data=transcription_data,
            transcription_analysis=None,
            extracted_insights=None,
        )
