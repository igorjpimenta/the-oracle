"""
Pydantic models for API requests and responses.
"""

from abc import ABC
from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, Any
from datetime import datetime

from ..core.models.messages import MessagePerformance


class ChatRequest(BaseModel):
    """Chat request model"""
    message: str = Field(..., description="User message")
    session_id: Optional[str] = Field(None, description="Session ID")
    parameters: Optional[dict[str, Any]] = Field(
        None,
        description="Parameters for the agent to use"
    )


class ChatResponse(BaseModel):
    """Chat response model"""
    response: str = Field(..., description="Assistant response")
    session_id: str = Field(..., description="Session ID")
    memory_enabled: bool = Field(..., description="Memory enabled")
    fallback_used: bool = Field(..., description="Fallback used")
    message_count: int = Field(..., description="Message count")
    performance: MessagePerformance = Field(..., description="Performance")


class SessionBase(BaseModel, ABC):
    """Session base model"""
    model_config = ConfigDict(from_attributes=True)

    metadata: Optional[dict[str, Any]] = Field(None)


class SessionCreate(SessionBase):
    """Session creation model"""


class SessionResponse(SessionBase):
    """Session response model"""
    id: str
    created_at: datetime
    updated_at: datetime
    status: str


class SessionMessagesResponse(SessionBase):
    """Message response model"""
    id: str
    session_id: str
    role: str
    content: str
    timestamp: datetime


class SessionCheckpointResponse(BaseModel):
    """Session checkpoint response model"""
    session_id: str
    checkpoint_count: int
    checkpoints: list[dict[str, Any]]
    limit: int


class HealthResponse(BaseModel):
    """Health check response"""
    status: str
    timestamp: datetime
    version: str
