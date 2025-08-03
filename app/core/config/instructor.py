from enum import Enum
from openai import OpenAI
import instructor
from typing import Optional, Any
from contextvars import ContextVar
import logging

from . import get_instructor_settings

logger = logging.getLogger(__name__)


class LLM(str, Enum):
    """LLM enum"""
    GPT_4O = "gpt-4o"
    GPT_4_1 = "gpt-4.1"


_default_llm_name: str = LLM.GPT_4_1.value

_current_llm_model: ContextVar[Optional[str]] = ContextVar(
    'current_llm_model', default=None
)

instructor_settings = get_instructor_settings().model_dump()

openai_client = OpenAI(**instructor_settings)


class LLMNameProxy(str):
    """
    Proxy class that behaves like a string but dynamically resolves
    the current LLM model name.
    """

    def __new__(cls):
        obj = str.__new__(cls, "")
        return obj

    def __str__(self) -> str:
        return get_current_llm_model()

    def __repr__(self) -> str:
        return f"'{get_current_llm_model()}'"

    def __eq__(self, other: Any) -> bool:
        return get_current_llm_model() == other

    def __getattr__(self, name: str) -> Any:
        """Delegate string methods to the current model name"""
        current_name = get_current_llm_model()
        return getattr(current_name, name)

    def __reduce__(self) -> tuple:
        """Support for pickling/JSON serialization by returning the actual
        string value"""
        return (str, (get_current_llm_model(),))

    def __getnewargs__(self) -> tuple:
        """Support for pickling/JSON serialization"""
        return (get_current_llm_model(),)

    def __json__(self) -> str:
        """Custom JSON serialization method"""
        return get_current_llm_model()

    def __class_getitem__(cls, item):
        """Support for type hinting"""
        return str


def get_default_llm_model() -> str:
    """Get default LLM model"""
    return LLM.GPT_4_1.value


def get_llm_model_from_thread(
    thread_metadata: Optional[dict[str, Any]],
    request_llm_model: Optional[LLM] = None
) -> str:
    """
    Get LLM model from thread metadata or request, with fallback to default.

    Priority order:
    1. Request LLM model (if provided)
    2. thread metadata LLM model
    3. Default LLM model

    Args:
        thread_metadata: thread metadata dict
        request_llm_model: LLM model from request

    Returns:
        str: LLM model name to use
    """
    # First check request parameter
    if (
        request_llm_model
        and request_llm_model in [model.value for model in LLM]
    ):
        return request_llm_model.value

    # Then check thread metadata
    if thread_metadata and "llm_model" in thread_metadata:
        thread_llm = thread_metadata["llm_model"]
        if thread_llm and thread_llm in [model.value for model in LLM]:
            return thread_llm

    # Default fallback
    return get_default_llm_model()


def set_current_llm_model(model_name: str) -> None:
    """Set the current LLM model for the request context"""
    _current_llm_model.set(model_name)


def get_current_llm_model() -> str:
    """Get the current LLM model, fallback to default if not set"""
    model = _current_llm_model.get()
    return model if model else _default_llm_name


# Create proxy instances that nodes can import and use directly
instructor_client = instructor.from_openai(openai_client)
llm_name = LLMNameProxy()

__all__ = [
    "instructor_client", "llm_name",
    "get_default_llm_model",
    "get_llm_model_from_thread",
    "LLM",
    "set_current_llm_model",
]
