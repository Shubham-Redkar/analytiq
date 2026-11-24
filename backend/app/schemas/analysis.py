"""AnalytIQ Schemas - Analytical Query Contracts for API requests and responses."""

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.analysis.contracts import AnalyticalResultColumn, ExecutionEvidence


class AnalysisQueryRequest(BaseModel):
    """User request to analyze an owned dataset with natural language."""

    question: str = Field(
        min_length=3,
        max_length=2000,
        description="Natural language analytical question about the dataset.",
    )


class AnalysisStatusResponse(BaseModel):
    """Diagnostic status of analytical capability and LLM provider."""

    analysis_available: bool
    provider: str
    model: str
    status: str
    error: str | None = None
    timestamp: datetime


class AnalysisQueryResponse(BaseModel):
    """Comprehensive analytical response with computed results and verifiable evidence."""

    model_config = ConfigDict(from_attributes=True)

    request_id: str
    dataset_id: uuid.UUID
    status: str
    question: str
    intent: str
    executed_sql: str | None = None
    columns: list[AnalyticalResultColumn] = Field(default_factory=list)
    rows: list[list[Any]] = Field(default_factory=list)
    returned_row_count: int = 0
    dataset_row_count: int | None = None
    total_row_count: int | None = None
    truncated: bool = False
    clarification_question: str | None = None
    unsupported_reason: str | None = None
    error_message: str | None = None
    evidence: ExecutionEvidence | None = None
