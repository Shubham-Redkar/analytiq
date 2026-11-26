"""AnalytIQ Models - Persistent analytical report entity."""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.analysis_history import AnalysisSession
    from app.models.dataset import Dataset
    from app.models.user import User


class Report(Base):
    """User-owned durable analytical report compiled from verified session runs."""

    __tablename__ = "reports"

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
    analysis_session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("analysis_sessions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    title: Mapped[str] = mapped_column(
        String(120),
        nullable=False,
    )
    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    status: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default="ready",
    )
    schema_version: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="1.0.0",
    )
    revision: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=1,
    )
    document: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
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
    generated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    # Relationships
    user: Mapped["User"] = relationship("User")
    dataset: Mapped["Dataset"] = relationship("Dataset")
    session: Mapped["AnalysisSession"] = relationship("AnalysisSession")

    __table_args__ = (
        Index("ix_reports_user_updated", "user_id", "updated_at"),
        Index("ix_reports_dataset_created", "dataset_id", "created_at"),
        Index("ix_reports_session_created", "analysis_session_id", "created_at"),
        Index("ix_reports_status", "status"),
    )
