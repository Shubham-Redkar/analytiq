"""AnalytIQ Models - Persistent analytical session and analysis run entities."""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.dataset import Dataset
    from app.models.user import User


class AnalysisSession(Base):
    """User-owned analytical workspace session linked to a specific dataset."""

    __tablename__ = "analysis_sessions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    dataset_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("datasets.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    title: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    # Relationships
    user: Mapped["User"] = relationship("User")
    dataset: Mapped["Dataset"] = relationship("Dataset")
    runs: Mapped[list["AnalysisRun"]] = relationship(
        "AnalysisRun",
        back_populates="session",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="AnalysisRun.created_at.asc()",
    )

    __table_args__ = (
        Index("ix_analysis_sessions_user_updated", "user_id", "updated_at"),
        Index("ix_analysis_sessions_dataset_created", "dataset_id", "created_at"),
    )


class AnalysisRun(Base):
    """Durable record of an individual analytical execution within a session."""

    __tablename__ = "analysis_runs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("analysis_sessions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    request_id: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        unique=True,
        index=True,
    )
    question: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
    intent: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="aggregation",
    )
    status: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
    )
    authoritative_answer: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    executed_sql: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    result_payload: Mapped[dict[str, Any] | None] = mapped_column(
        JSONB,
        nullable=True,
    )
    verification_payload: Mapped[dict[str, Any] | None] = mapped_column(
        JSONB,
        nullable=True,
    )
    evidence_payload: Mapped[dict[str, Any] | None] = mapped_column(
        JSONB,
        nullable=True,
    )
    clarification_payload: Mapped[dict[str, Any] | None] = mapped_column(
        JSONB,
        nullable=True,
    )
    unsupported_reason: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    error_message: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    returned_row_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )
    dataset_row_count: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )
    total_row_count: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )
    truncated: Mapped[bool] = mapped_column(
        default=False,
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # Relationship
    session: Mapped["AnalysisSession"] = relationship(
        "AnalysisSession",
        back_populates="runs",
    )

    __table_args__ = (
        Index("ix_analysis_runs_session_created", "session_id", "created_at"),
        Index("ix_analysis_runs_status", "status"),
    )
