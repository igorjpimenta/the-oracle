"""PostgreSQL text2sql agent, with plotting and sql execution capabilities"""

import logging
from langchain_core.runnables import RunnableConfig
from langgraph.graph import StateGraph
from typing import Optional, cast
import time

from .memory import MemoryManager
from .states import State
from .models.messages import (
    ProcessedMessage, MessagePerformance,
    Message, HMessage, SMessage
)
from .models.enums import Agent, Intention
from .workflows import DefaultWorkflow, FallbackWorkflow

logger = logging.getLogger(__name__)


class BaseAgent:
    memory_manager: MemoryManager
    _graph: StateGraph
    _fallback_graph: StateGraph
    _compiled: bool
    _compiled_apps_cache: dict[str, StateGraph]

    def __init__(self):
        self._compiled = False
        self._compiled_apps_cache = {}
        self.memory_manager = MemoryManager(checkpointer_kind="redis")


class Assistant:
    """
    Assistant class that sets up the graph and provides a method to get the
    assistant instance.
    """

    def __init__(self):
        self._graph = None
        self._fallback_graph = None
        self._compiled = False
        self._compiled_apps_cache = {}
        self.memory_manager = MemoryManager(checkpointer_kind="redis")

        default_workflow = DefaultWorkflow()
        fallback_workflow = FallbackWorkflow()

        self._graph = default_workflow.get_graph()
        self._fallback_graph = fallback_workflow.get_graph()

    async def initialize_memory(self) -> None:
        """Initialize memory system"""
        await self.memory_manager.initialize()
        self._compiled = True

        # Pre-warm the compiled graph cache
        await self._get_or_create_compiled_app()

    async def process_message(
        self,
        user_input: str,
        thread_id: str,
        fallback_used: bool = False,
        fallback_state: Optional[State] = None,
        start_time: Optional[float] = None,
    ) -> ProcessedMessage:
        """Process user message with conversation memory."""
        start_time = start_time or time.time()

        if not self._compiled:
            await self.initialize_memory()

        state = None
        initial_state = None

        try:
            if (fallback_used and fallback_state):
                state = fallback_state
            else:
                config = self.memory_manager \
                    .create_thread_config(thread_id=thread_id)

                is_new_thread = (
                    await self.memory_manager.get_thread_state(config)
                ) is None

                initial_state = await self._prepare_initial_state(
                    user_input=user_input,
                    thread_id=thread_id,
                    is_new_thread=is_new_thread,
                )

                state = await self._process_with_graph(
                    initial_state=initial_state,
                    thread_config=config
                )

            total_time = time.time() - start_time
            logger.info(
                f"Processed message in {total_time:.2f}s"
            )

            return ProcessedMessage(
                response=state["chat_history"][-1].content,
                thread_id=thread_id,
                memory_enabled=True,
                fallback_used=fallback_used,
                message_count=len(state["chat_history"]),
                performance=MessagePerformance(
                    total_time=f"{total_time:.2f}s",
                )
            )

        except Exception as e:
            logger.error(
                "Error in process_message: "
                f"{e.with_traceback(e.__traceback__)}"
            )

            # Use initial_state if state is None (failed before
            # _process_with_graph completed). If initial_state is also None,
            # let the fallback method handle it gracefully
            if state is not None:
                fallback_state_param = state.copy()

            if initial_state is not None and state is None:
                fallback_state_param = initial_state.copy()
            else:
                # No state available, create minimal state for fallback
                fallback_state_param = cast(State, {})

            return await self._fallback_process_message(
                user_input=user_input,
                thread_id=thread_id,
                state=fallback_state_param,
                start_time=start_time,
            )

    async def _fallback_process_message(
        self,
        user_input: str,
        thread_id: str,
        state: State,
        start_time: float,
    ) -> ProcessedMessage:
        """Fallback to final answer node"""

        fallback_state = await self._handle_fallback(
            state=state,
            message=SMessage(
                name="GeneralFallback",
                content=(
                    "Algo inesperado aconteceu. Responda com as informações "
                    "disponíveis."
                )
            ),
            thread_id=thread_id,
        )

        return await self.process_message(
            user_input=user_input,
            thread_id=thread_id,
            fallback_used=True,
            fallback_state=fallback_state,
            start_time=start_time,
        )

    async def _process_with_fallback_graph(
        self,
        fallback_state: State,
        thread_id: str,
    ) -> State:
        """Process fallback using dedicated workflow with checkpointer"""
        checkpointer = self.memory_manager.checkpointer
        async with checkpointer.get_checkpointer() as saver:
            if self._fallback_graph is None:
                raise RuntimeError("Fallback graph not initialized")

            # Compile fallback graph with checkpointer for full context access
            compiled_fallback_app = self._fallback_graph.compile(
                checkpointer=saver
            )

            thread_config = self.memory_manager \
                .create_thread_config(thread_id=thread_id)

            # Run the fallback workflow with checkpointer context
            result = cast(State, await compiled_fallback_app.ainvoke(
                fallback_state, thread_config
            ))

            return result

    async def _handle_fallback(
        self,
        state: State,
        message: Message,
        thread_id: str,
    ) -> State:
        """Handle fallback using dedicated workflow with full context"""
        try:
            fallback_state = state.copy()
            fallback_state["messages"] = [message]

            return await self._process_with_fallback_graph(
                fallback_state, thread_id
            )

        except Exception as e:
            raise Exception(
                f"Error in recursion limit fallback handler: {e}"
            )

    async def _get_or_create_compiled_app(
        self, checkpointer_id: str = "default"
    ):
        """Get or create a compiled app with caching for performance"""
        if checkpointer_id not in self._compiled_apps_cache:
            checkpointer = self.memory_manager.checkpointer
            async with checkpointer.get_checkpointer() as saver:
                if self._graph is not None:
                    compiled_app = self._graph.compile(checkpointer=saver)
                    self._compiled_apps_cache[checkpointer_id] = compiled_app
                else:
                    raise RuntimeError("Graph not initialized")

        return self._compiled_apps_cache[checkpointer_id]

    async def _prepare_initial_state(
        self,
        thread_id: str,
        user_input: str,
        is_new_thread: bool,
    ) -> State:
        messages: list[Message] = [HMessage(name="Human", content=user_input)]

        if is_new_thread:
            return State(
                thread_id=thread_id,
                chat_history=messages,
                messages=[],
                next=Agent.INTENT_SEEKER.value,
                current_intention=Intention.OTHER,
                current_inquiry="",
                unhandled_tasks=[],
                data_for_the_task=[],
            )

        initial_state = cast(State, {
            "chat_history": messages,
            "unhandled_tasks": [],
            "data_for_the_task": [],
        })

        return initial_state

    async def _process_with_graph(
        self,
        initial_state: State,
        thread_config: RunnableConfig,
    ) -> State:
        checkpointer = self.memory_manager.checkpointer
        async with checkpointer.get_checkpointer() as saver:
            if self._graph is None:
                raise RuntimeError("Graph not initialized")

            compiled_app = self._graph.compile(checkpointer=saver)
            try:
                result = cast(State, await compiled_app.ainvoke(
                    initial_state, thread_config
                ))
            except RecursionError as e:
                if "recursion limit" in str(e).lower():
                    logger.warning(
                        "Recursion limit reached for thread "
                        f"{thread_config}. Falling back."
                    )
                    thread_id: str | None = thread_config \
                        .get("configurable", {}) \
                        .get("thread_id", None)

                    assert thread_id is not None

                    result = cast(
                        State,
                        await self._handle_recursion_limit_fallback(
                            initial_state,
                            thread_id
                        )
                    )
                else:
                    raise
            return result

    async def _handle_recursion_limit_fallback(
        self,
        state: State,
        thread_id: str,
    ) -> State:
        """Handle recursion limit by forcing a final answer"""
        return await self._handle_fallback(
            state=state,
            message=SMessage(
                name="RecursionFallback",
                content="This conversation between agents became too complex. "
                "It was necessary to interrupt it. "
                "Use the available information to answer the question."
            ),
            thread_id=thread_id,
        )


_assistant: Optional[Assistant] = None


async def get_assistant() -> Assistant:
    """
    Get the global streaming assistant instance.

    Returns:
        Assistant: Global streaming assistant instance
    """
    global _assistant
    if _assistant is None:
        _assistant = Assistant()
        await _assistant.initialize_memory()
    return _assistant
