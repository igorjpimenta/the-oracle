"""
Database schemas for the application.
"""

from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy import String, Text, ForeignKey, TIMESTAMP, func
from sqlalchemy.dialects.postgresql import JSONB
from datetime import datetime
from typing import Optional, Dict, Any
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
    meta_data: Mapped[Optional[Dict[str, Any]]] = mapped_column(
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
    meta_data: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSONB,
        name="metadata",
        nullable=True
    )

    # Relationships
    session: Mapped["Session"] = relationship(
        "Session",
        back_populates="messages"
    )
