from abc import ABC, abstractmethod
from langgraph.graph import START, END

from .nodes import (
    intent_seeker_node,
    manager_node,
    task_orchestrator_node,
    data_collector_node,
    touchpoint_node,
)
from .states import BaseState, State, StateGraph
from .models.enums import Agent, Intention


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
    @property
    def state_schema(self) -> type[BaseState]:
        return State

    def _setup_graph(self, graph: StateGraph) -> StateGraph:
        graph.add_node("intent_seeker", intent_seeker_node)
        graph.add_node("manager", manager_node)
        graph.add_node("task_orchestrator", task_orchestrator_node)
        graph.add_node("data_collector", data_collector_node)
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
                "data_collector": "data_collector",
            }
        )

        graph.add_conditional_edges(
            "data_collector",
            self._next_after_task,
            {
                "data_collector": "data_collector",
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


class FallbackWorkflow(BaseWorkflow):
    @property
    def state_schema(self) -> type[BaseState]:
        return State

    def _setup_graph(self, graph: StateGraph) -> StateGraph:
        graph.add_node("touchpoint", touchpoint_node)

        graph.add_edge(START, "touchpoint")
        graph.add_edge("touchpoint", END)

        return graph
