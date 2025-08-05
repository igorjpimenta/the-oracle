from abc import ABC
import logging
from langchain_core.runnables import RunnableConfig
from langgraph.graph import StateGraph
from langgraph.graph.state import CompiledStateGraph
from typing import Optional, cast, TypeVar
import time


from .memory import MemoryManager
from .states import State, ProcessingState, BaseState
from .models.messages import (
    ProcessedMessage, MessagePerformance,
    Message, HMessage, SMessage, ProcessedTranscription
)
from .models.data import TranscriptionData, TranscriptionProcessingData
from .workflows import DefaultWorkflow, FallbackWorkflow, ProcessingWorkflow

logger = logging.getLogger(__name__)


T = TypeVar("T", bound=BaseState)


class BaseAgent(ABC):
    compiled: bool
    compiled_apps_cache: dict[str, StateGraph]
    memory_manager: MemoryManager
    _graph: StateGraph
    _compiled_apps_cache: dict[str, CompiledStateGraph]

    def __init__(self):
        self.memory_manager = MemoryManager(checkpointer_kind="redis")
        self._compiled_apps_cache = {}
        self._compiled = False

    async def initialize_memory(self) -> None:
        """Initialize memory system"""
        await self.memory_manager.initialize()
        self._compiled = True

        # Pre-warm the compiled graph cache
        await self._get_or_create_compiled_app()

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


class Assistant(BaseAgent):
    """
    Assistant class that sets up the graph and provides a method to get the
    assistant instance.
    """

    def __init__(self):
        super().__init__()
        self._fallback_graph = None

        self._default_workflow = DefaultWorkflow()
        self._fallback_workflow = FallbackWorkflow()

        self._graph = self._default_workflow.get_graph()
        self._fallback_graph = self._fallback_workflow.get_graph()

    async def process_message(
        self,
        user_input: str,
        thread_id: str,
        transcription_data: TranscriptionProcessingData,
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

                is_new_thread = not (
                    await self.memory_manager.get_thread_state(config)
                )

                initial_state = await self._prepare_initial_state(
                    user_input=user_input,
                    thread_id=thread_id,
                    transcription_data=transcription_data,
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

            return await self._fallback_process_message(
                user_input=user_input,
                thread_id=thread_id,
                transcription_data=transcription_data,
                start_time=start_time,
            )

    async def _fallback_process_message(
        self,
        user_input: str,
        thread_id: str,
        transcription_data: TranscriptionProcessingData,
        start_time: float,
    ) -> ProcessedMessage:
        """Fallback to final answer node"""

        fallback_state = await self._handle_fallback(
            message=SMessage(
                name="GeneralFallback",
                content=(
                    "Something unexpected happened. Respond with the "
                    "available information."
                )
            ),
            thread_id=thread_id,
        )

        return await self.process_message(
            user_input=user_input,
            thread_id=thread_id,
            transcription_data=transcription_data,
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
        message: Message,
        thread_id: str,
    ) -> State:
        """Handle fallback using dedicated workflow with full context"""
        try:
            fallback_state = cast(State, {
                "messages": [message],
            })

            return await self._process_with_fallback_graph(
                fallback_state, thread_id
            )

        except Exception as e:
            raise Exception(
                f"Error in recursion limit fallback handler: {e}"
            )

    async def _prepare_initial_state(
        self,
        thread_id: str,
        user_input: str,
        transcription_data: TranscriptionProcessingData,
        is_new_thread: bool,
    ) -> State:
        messages: list[Message] = [HMessage(name="Human", content=user_input)]

        if is_new_thread:
            return self._default_workflow.get_initial_state(
                thread_id=thread_id,
                user_input=user_input,
                transcription_data=transcription_data["data"],
                transcription_analysis=transcription_data["analysis"],
                extracted_insights=transcription_data["insights"]
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
                            thread_id
                        )
                    )
                else:
                    raise
            return result

    async def _handle_recursion_limit_fallback(
        self,
        thread_id: str,
    ) -> State:
        """Handle recursion limit by forcing a final answer"""
        return await self._handle_fallback(
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


class ProcessingAgent(BaseAgent):
    """
    Processing agent class that sets up the graph and provides a method to get
    the processing agent instance.
    """

    def __init__(self):
        super().__init__()

        self._processing_workflow = ProcessingWorkflow()
        self._graph = self._processing_workflow.get_graph()

    async def process_transcription(
        self,
        thread_id: str,
        transcription_id: str,
        transcription_data: TranscriptionData,
        start_time: Optional[float] = None,
    ) -> ProcessedTranscription:
        """Process transcription with conversation memory."""
        start_time = start_time or time.time()

        if not self._compiled:
            await self.initialize_memory()

        final_state = None
        initial_state = None

        try:
            config = self.memory_manager \
                .create_thread_config(thread_id=thread_id)

            is_new_thread = (
                await self.memory_manager.get_thread_state(config)
            ) is None

            initial_state = await self._prepare_initial_state(
                thread_id=thread_id,
                transcription_id=transcription_id,
                transcription_data=transcription_data,
                is_new_thread=is_new_thread,
            )

            final_state = await self._process_with_graph(
                initial_state=initial_state,
                thread_config=config
            )

            total_time = time.time() - start_time
            logger.info(
                f"Processed message in {total_time:.2f}s"
            )

            status = "completed"
            if (
                (final_state["transcription_analysis"] is None) ^
                (final_state["extracted_insights"] is None)
            ):
                status = "partial"
            else:
                status = "failed"

            return ProcessedTranscription(
                transcription_id=transcription_id,
                status=status,
                thread_id=thread_id,
                analysis=final_state["transcription_analysis"],
                insights=final_state["extracted_insights"],
                processing_time=total_time,
            )

        except Exception as e:
            logger.error(
                "Error in process_message: "
                f"{e.with_traceback(e.__traceback__)}"
            )
            raise e

    async def _process_with_graph(
        self,
        initial_state: ProcessingState,
        thread_config: RunnableConfig,
    ) -> ProcessingState:
        checkpointer = self.memory_manager.checkpointer
        async with checkpointer.get_checkpointer() as saver:
            if self._graph is None:
                raise RuntimeError("Graph not initialized")

            compiled_app = self._graph.compile(checkpointer=saver)
            result = cast(ProcessingState, await compiled_app.ainvoke(
                initial_state, thread_config
            ))

            return result

    async def _prepare_initial_state(
        self,
        thread_id: str,
        transcription_id: str,
        transcription_data: TranscriptionData,
        is_new_thread: bool,
    ) -> ProcessingState:
        if is_new_thread:
            return self._processing_workflow.get_initial_state(
                thread_id=thread_id,
                transcription_id=transcription_id,
                transcription_data=transcription_data,
            )

        initial_state = cast(ProcessingState, {
            "thread_id": thread_id,
        })

        return initial_state


_processing_agent: Optional[ProcessingAgent] = None


async def get_processing_agent() -> ProcessingAgent:
    """
    Get the global processing agent instance.

    Returns:
        ProcessingAgent: Global processing agent instance
    """
    global _processing_agent
    if _processing_agent is None:
        _processing_agent = ProcessingAgent()
        await _processing_agent.initialize_memory()
    return _processing_agent
