"""
Pydantic models for API requests and responses.
"""

from abc import ABC
from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, Any
from datetime import datetime

from ..core.models.data import TranscriptionAnalysis, ExtractedInsights
from ..core.models.messages import MessagePerformance


class ChatRequest(BaseModel):
    """Chat request model"""
    message: str = Field(..., description="User message")
    session_id: str = Field(..., description="Session ID")
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
    session_id: Optional[str] = Field(None, description="Session ID")


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


class TranscriptionResponse(BaseModel):
    """Audio transcription response model"""
    id: str = Field(..., description="Transcription ID")
    session_id: str = Field(..., description="Session ID")
    transcription_text: str = Field(..., description="Transcribed text")
    language: str = Field(..., description="Detected language")
    confidence_score: Optional[float] = Field(
        None, description="Confidence score"
    )
    duration_seconds: Optional[float] = Field(
        None, description="Audio duration"
    )
    audio_file_id: str = Field(..., description="Nyxen media file ID")
    original_filename: str = Field(..., description="Original filename")
    model: str = Field(..., description="Model used for transcription")
    processing_time_seconds: Optional[float] = Field(
        None, description="Processing time"
    )
    created_at: datetime = Field(..., description="Creation timestamp")
    metadata: Optional[dict[str, Any]] = Field(
        None, description="Additional metadata"
    )


class TranscriptionListResponse(BaseModel):
    """List of transcriptions response model"""
    transcriptions: list[TranscriptionResponse]
    session_id: str
    total_count: int


class ProcessingResponse(BaseModel):
    """Response from transcription processing"""
    transcription_id: str = Field(..., description="Transcription ID")
    status: str = Field(..., description="Processing status")
    thread_id: str = Field(..., description="Processing thread ID")
    analysis: Optional[TranscriptionAnalysis] = Field(
        None, description="Analysis results"
    )
    insights: Optional[ExtractedInsights] = Field(
        None, description="Extracted insights"
    )
    processing_time: Optional[float] = Field(
        None, description="Processing time in seconds"
    )
    created_at: datetime = Field(..., description="Processing start time")


class ProcessingStatusResponse(BaseModel):
    """Response for processing status check"""
    transcription_id: str = Field(..., description="Transcription ID")
    session_id: Optional[str] = Field(None, description="Session ID")
    analysis: Optional[TranscriptionAnalysis] = Field(
        None, description="Analysis results"
    )
    insights: Optional[ExtractedInsights] = Field(
        None, description="Extracted insights"
    )
    status: str = Field(..., description="Current processing status")
    created_at: Optional[datetime] = Field(
        None, description="Processing start time"
    )
    updated_at: Optional[datetime] = Field(
        None, description="Last update time"
    )
