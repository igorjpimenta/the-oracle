from abc import ABC, abstractmethod
from langgraph.graph import START, END
from langgraph.graph.state import CompiledStateGraph, StateGraph
from langgraph.types import Send
from typing import cast

from .nodes.conversation import (
    intent_seeker_node,
    manager_node,
    task_orchestrator_node,
    transcription_digger_node,
    touchpoint_node,
)
from .nodes.processing import (
    transcription_loader_node,
    transcription_analyzer_node,
    insight_extractor_node,
    results_storage_node,
)
from .states import (
    BaseState, State, WorkerState, ProcessingState
)
from .models.enums import Agent, Intention
from .models.data import TranscriptionData
from .models.messages import HMessage


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
        graph.add_node("task_orchestrator", self._worker_subgraph_handler)
        graph.add_node("touchpoint", touchpoint_node)

        graph.add_edge(START, "intent_seeker")
        graph.add_edge("intent_seeker", "manager")

        graph.add_conditional_edges(
            "manager",
            self._continue_after_manager  # type: ignore
        )

        graph.add_edge("task_orchestrator", "touchpoint")
        graph.add_edge("touchpoint", END)

        return graph

    def _setup_worker_subgraph(self) -> CompiledStateGraph:
        graph = StateGraph(WorkerState)

        graph.add_node("task_orchestrator", task_orchestrator_node)
        graph.add_node("transcription_digger", transcription_digger_node)

        graph.add_edge(START, "task_orchestrator")

        graph.add_conditional_edges(
            "task_orchestrator",
            self._next_worker,
            {
                "transcription_digger": "transcription_digger",
            }
        )

        graph.add_edge("transcription_digger", END)

        return graph.compile()

    def _next_worker(self, state: WorkerState) -> str:
        return state["next"]

    def _worker_subgraph_handler(self, state: WorkerState) -> State:
        worker_subgraph = self._setup_worker_subgraph()
        result = worker_subgraph.invoke(state)

        return cast(State, {
            "messages": result["messages"],
            "data_for_the_task": result["data_for_the_task"],

        })

    def _continue_after_manager(self, state: State):
        if state["current_intention"] == Intention.GREET:
            return [Send(Agent.TOUCHPOINT.value, state)]

        def get_updated_state(task: str) -> WorkerState:
            return WorkerState(
                thread_id=state["thread_id"],
                chat_history=state["chat_history"],
                messages=[],
                current_task=task,
                orientations_for_the_task=None,
                data_for_the_task=state["data_for_the_task"],
                analysis=state["transcription_analysis"],
                insights=state["extracted_insights"],
                next=Agent.TASK_ORCHESTRATOR.value,
            )

        return [
            Send(Agent.TASK_ORCHESTRATOR.value, get_updated_state(task))
            for task in state["current_tasks"]
        ]

    def get_initial_state(
        self,
        thread_id: str,
        user_input: str,
        transcription_data: TranscriptionData,
        **kwargs
    ) -> State:
        transcription_analysis = kwargs.get("transcription_analysis", None)
        extracted_insights = kwargs.get("extracted_insights", None)

        return State(
            thread_id=thread_id,
            chat_history=[
                HMessage(
                    name="Human",
                    content=user_input,
                )
            ],
            messages=[],
            current_intention=Intention.GREET,
            current_inquiry="",
            current_tasks=[],
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

        transcription_data: TranscriptionData = kwargs \
            .get("transcription_data", None)

        if not transcription_data:
            raise ValueError("Transcription data is required.")

        return ProcessingState(
            thread_id=thread_id,
            transcription_id=transcription_id,
            transcription_data=transcription_data,
            transcription_analysis=None,
            extracted_insights=None,
        )
