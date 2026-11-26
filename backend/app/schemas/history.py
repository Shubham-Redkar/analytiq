"""AnalytIQ Schemas - Analytical workspace session and history contracts."""

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.analysis.contracts import AnalyticalResultColumn, ExecutionEvidence
from app.orchestration.contracts import ClarificationOutput
from app.verification.contracts import VerificationSummary


class SessionCreateRequest(BaseModel):
    """Request to create a new analytical session for a dataset."""

    dataset_id: uuid.UUID
    title: str | None = Field(default=None, max_length=255)


class SessionUpdateRequest(BaseModel):
    """Request to update an existing analytical session."""

    title: str = Field(min_length=1, max_length=255)


class AnalysisRunSummary(BaseModel):
    """Lightweight representation of an analytical run within a session."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    session_id: uuid.UUID
    request_id: str
    question: str
    intent: str
    status: str
    authoritative_answer: str | None = None
    returned_row_count: int = 0
    truncated: bool = False
    created_at: datetime
    completed_at: datetime | None = None


class AnalysisRunDetail(AnalysisRunSummary):
    """Full detail of an analytical run including evidence, SQL, and results."""

    executed_sql: str | None = None
    columns: list[AnalyticalResultColumn] = Field(default_factory=list)
    rows: list[list[Any]] = Field(default_factory=list)
    dataset_row_count: int | None = None
    total_row_count: int | None = None
    unsupported_reason: str | None = None
    error_message: str | None = None
    evidence: ExecutionEvidence | None = None
    verification: VerificationSummary | None = None
    clarification: ClarificationOutput | None = None


class AnalysisSessionResponse(BaseModel):
    """Full analytical session response with runs and dataset metadata."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: uuid.UUID
    dataset_id: uuid.UUID
    dataset_name: str | None = None
    title: str
    created_at: datetime
    updated_at: datetime
    runs: list[AnalysisRunDetail] = Field(default_factory=list)


class AnalysisSessionSummary(BaseModel):
    """Paginated item for session list."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    dataset_id: uuid.UUID
    dataset_name: str | None = None
    title: str
    run_count: int = 0
    last_question: str | None = None
    created_at: datetime
    updated_at: datetime


class AnalysisSessionListResponse(BaseModel):
    """Paginated list of analytical sessions."""

    items: list[AnalysisSessionSummary]
    total: int
    page: int
    page_size: int
    total_pages: int
