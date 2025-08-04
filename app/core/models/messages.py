from abc import ABC, abstractmethod
from pydantic import BaseModel
from openai.types.chat.chat_completion_message_param import (
    ChatCompletionMessageParam
)
from typing import Literal, cast, Optional

from ..models.data import TranscriptionAnalysis, ExtractedInsights


class InstructorMessage(BaseModel):
    """Class that manage the Instructor messages
    Args:
        role (str): role of the message
        content (str): content of the message
    """
    role: Literal["system", "user", "assistant"]
    content: str

    def to_dict(self) -> ChatCompletionMessageParam:
        return cast(ChatCompletionMessageParam, {
            "role": self.role,
            "content": self.content
        })


class Message(BaseModel, ABC):
    """Class that manage the messages
    Args:
        role (str): role of the message
        name (str): name of the agent
        content (str): content of the message
    """

    @property
    @abstractmethod
    def role(self) -> Literal["user", "system", "assistant"]:
        """The role must be defined in child classes"""
        pass

    content: str
    name: str

    def to_string(self) -> str:
        return f"[{self.role}] {self.name}: {self.content}"

    def to_dict(self) -> ChatCompletionMessageParam:
        return cast(ChatCompletionMessageParam, {
            "role": self.role,
            "name": self.name,
            "content": self.content
        })

    def to_instructor_message(self) -> ChatCompletionMessageParam:
        return InstructorMessage(
            role=self.role,
            content=self.content
        ).to_dict()


class HMessage(Message):
    """Class that manage the User messages
    Args:
        role (str): role of the message
        content (str): content of the message
    """

    @property
    def role(self) -> Literal["user"]:
        return "user"


class SMessage(Message):
    """Class that manage the System messages
    Args:
        role (str): role of the message
        content (str): content of the message
    """

    @property
    def role(self) -> Literal["system"]:
        return "system"


class AMessage(Message):
    """Class that manage the Assistant messages
    Args:
        role (str): role of the message
        content (str): content of the message
    """

    @property
    def role(self) -> Literal["assistant"]:
        return "assistant"


class MessagePerformance(BaseModel):
    """Class that manage the Performance of the message
    Args:
        total_time (str): total time of the message
    """
    total_time: str


class ProcessedMessage(BaseModel):
    """Class that manage the Processed Message
    Args:
        response (str): response from the last agent message
        thread_id (str): thread id
        memory_enabled (bool): if the memory is enabled
        fallback_used (bool): if the fallback is used
        message_count (int): total messages of the conversation
        performance (MessagePerformance): performance metrics of the processing
    """
    response: str
    thread_id: str
    memory_enabled: bool
    fallback_used: bool
    message_count: int
    performance: MessagePerformance


class ProcessedTranscription(BaseModel):
    """Class that manage the Processed Transcription
    Args:
        transcription_id (str): transcription id
        status (str): status of the transcription
        thread_id (str): thread id
        analysis (TranscriptionAnalysis): analysis of the transcription
        insights (ExtractedInsights): insights from the transcription
        processing_time (float): processing time
    """
    transcription_id: str
    status: str
    thread_id: str
    analysis: Optional[TranscriptionAnalysis]
    insights: Optional[ExtractedInsights]
    processing_time: float
