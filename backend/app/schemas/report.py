"""AnalytIQ Schemas - Request and response contracts for Report management."""

import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from app.reports.contracts import ReportDocument


class CreateReportRequest(BaseModel):
    """Payload to compile selected analytical session runs into a Report."""

    analysis_session_id: uuid.UUID
    run_ids: list[str] = Field(default_factory=list, max_length=20)
    title: str | None = Field(default=None, max_length=120)
    description: str | None = Field(default=None, max_length=1000)


class UpdateReportRequest(BaseModel):
    """Payload to safely update report metadata or section configuration."""

    title: str | None = Field(default=None, max_length=120)
    description: str | None = Field(default=None, max_length=1000)
    revision: int = Field(ge=1)
    document: ReportDocument | None = None


class ReportSummaryResponse(BaseModel):
    """Lightweight summary response for report listing."""

    id: uuid.UUID
    dataset_id: uuid.UUID
    dataset_name: str
    analysis_session_id: uuid.UUID
    title: str
    description: str | None = None
    status: str
    revision: int
    created_at: datetime
    updated_at: datetime


class ReportDetailResponse(BaseModel):
    """Full detail response containing structured document."""

    id: uuid.UUID
    dataset_id: uuid.UUID
    analysis_session_id: uuid.UUID
    title: str
    description: str | None = None
    status: str
    revision: int
    schema_version: str
    document: ReportDocument
    created_at: datetime
    updated_at: datetime
    generated_at: datetime
