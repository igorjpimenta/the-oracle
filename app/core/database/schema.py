"""
Database schemas for the application.
"""

from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy import String, Text, ForeignKey, TIMESTAMP, func
from sqlalchemy.dialects.postgresql import JSONB
from datetime import datetime
from typing import Optional, Any
import uuid
import logging

logger = logging.getLogger(__name__)


class Base(DeclarativeBase):
    """Base class for all database models"""
    pass


class Session(Base):
    """Session model for storing user sessions"""
    __tablename__ = "sessions"

    id: Mapped[str] = mapped_column(
        String(255),
        primary_key=True,
        default=lambda: str(uuid.uuid4())
    )
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP,
        default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP,
        default=func.now(),
        onupdate=func.now()
    )
    status: Mapped[str] = mapped_column(String(50), default="active")
    meta_data: Mapped[Optional[dict[str, Any]]] = mapped_column(
        JSONB,
        name="metadata",
        nullable=True
    )

    # Relationships
    messages: Mapped[list["Message"]] = relationship(
        "Message",
        back_populates="session",
        cascade="all, delete-orphan"
    )
    transcriptions: Mapped[list["Transcription"]] = relationship(
        "Transcription",
        back_populates="session",
        cascade="all, delete-orphan"
    )


class Message(Base):
    """Message model for storing conversation messages"""
    __tablename__ = "messages"

    id: Mapped[str] = mapped_column(
        String(255),
        primary_key=True,
        default=lambda: str(uuid.uuid4())
    )
    session_id: Mapped[str] = mapped_column(
        String(255),
        ForeignKey("sessions.id"),
        nullable=False
    )
    role: Mapped[str] = mapped_column(String(50), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    timestamp: Mapped[datetime] = mapped_column(
        TIMESTAMP,
        default=func.now()
    )
    meta_data: Mapped[Optional[dict[str, Any]]] = mapped_column(
        JSONB,
        name="metadata",
        nullable=True
    )

    # Relationships
    session: Mapped["Session"] = relationship(
        "Session",
        back_populates="messages"
    )


class Transcription(Base):
    """Transcription model for storing audio transcriptions"""
    __tablename__ = "transcriptions"

    id: Mapped[str] = mapped_column(
        String(255),
        primary_key=True,
        default=lambda: str(uuid.uuid4())
    )
    session_id: Mapped[str] = mapped_column(
        String(255),
        ForeignKey("sessions.id"),
        nullable=False
    )
    audio_file_id: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="Nyxen media file ID"
    )
    original_filename: Mapped[str] = mapped_column(
        String(500),
        nullable=False
    )
    transcription_text: Mapped[str] = mapped_column(
        Text,
        nullable=False
    )
    language: Mapped[str] = mapped_column(
        String(10),
        nullable=False,
        comment="Detected or specified language (en, es, etc.)"
    )
    confidence_score: Mapped[Optional[float]] = mapped_column(
        nullable=True,
        comment="Transcription confidence score"
    )
    duration_seconds: Mapped[Optional[float]] = mapped_column(
        nullable=True,
        comment="Audio duration in seconds"
    )
    audio_size_bytes: Mapped[Optional[int]] = mapped_column(
        nullable=True,
        comment="Audio file size in bytes"
    )
    model: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        comment="Model used for transcription"
    )
    processing_time_seconds: Mapped[Optional[float]] = mapped_column(
        nullable=True,
        comment="Time taken to process the transcription"
    )
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP,
        default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP,
        default=func.now(),
        onupdate=func.now()
    )
    meta_data: Mapped[Optional[dict[str, Any]]] = mapped_column(
        JSONB,
        name="metadata",
        nullable=True,
        comment="Additional metadata like chunks, segments, etc."
    )

    # Relationships
    session: Mapped["Session"] = relationship(
        "Session",
        back_populates="transcriptions"
    )
    transcription_processing: Mapped[Optional["TranscriptionProcessing"]] = \
        relationship(
            "TranscriptionProcessing",
            back_populates="transcription",
            cascade="all, delete-orphan",
            single_parent=True
    )


class TranscriptionProcessing(Base):
    """Transcription processing results for processed transcriptions"""
    __tablename__ = "transcription_processings"

    id: Mapped[str] = mapped_column(
        String(255),
        primary_key=True,
        default=lambda: str(uuid.uuid4())
    )
    transcription_id: Mapped[str] = mapped_column(
        String(255),
        ForeignKey("transcriptions.id"),
        nullable=False,
        unique=True
    )
    analysis_id: Mapped[str] = mapped_column(
        String(255),
        ForeignKey("transcription_analyses.id"),
        nullable=True
    )
    insights_id: Mapped[str] = mapped_column(
        String(255),
        ForeignKey("transcription_insights.id"),
        nullable=True
    )
    status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="pending"  # pending, processing, partial, completed, failed
    )
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP,
        default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP,
        default=func.now(),
        onupdate=func.now()
    )
    meta_data: Mapped[Optional[dict[str, Any]]] = mapped_column(
        JSONB,
        name="metadata",
        nullable=True
    )

    # Relationships
    transcription: Mapped["Transcription"] = relationship(
        "Transcription",
        back_populates="transcription_processing"
    )

    transcription_analysis: Mapped["TranscriptionAnalysis"] = relationship(
        "TranscriptionAnalysis",
        back_populates="transcription_processing",
        cascade="all, delete-orphan",
        single_parent=True
    )
    transcription_insights: Mapped["TranscriptionInsights"] = relationship(
        "TranscriptionInsights",
        back_populates="transcription_processing",
        cascade="all, delete-orphan",
        single_parent=True
    )


class TranscriptionAnalysis(Base):
    __tablename__ = "transcription_analyses"

    id: Mapped[str] = mapped_column(
        String(255),
        primary_key=True,
        default=lambda: str(uuid.uuid4())
    )
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    key_topics: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    sentiment: Mapped[str] = mapped_column(String(50), nullable=False)
    main_themes: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    important_quotes: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    technical_terms: Mapped[list[str]] = mapped_column(JSONB, nullable=False)

    # Relationships
    transcription_processing: Mapped["TranscriptionProcessing"] = relationship(
        "TranscriptionProcessing",
        back_populates="transcription_analysis"
    )


class TranscriptionInsights(Base):
    __tablename__ = "transcription_insights"

    id: Mapped[str] = mapped_column(
        String(255),
        primary_key=True,
        default=lambda: str(uuid.uuid4())
    )
    key_insights: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    action_items: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    recommendations: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    opportunities: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    concerns: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    next_steps: Mapped[list[str]] = mapped_column(JSONB, nullable=False)

    # Relationships
    transcription_processing: Mapped["TranscriptionProcessing"] = relationship(
        "TranscriptionProcessing",
        back_populates="transcription_insights"
    )
