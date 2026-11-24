"""Orchestration domain models, trace contracts, and status definitions for M4."""

import uuid
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.analysis.contracts import (
    AnalyticalQueryResult,
    AnalyticalResultColumn,
    ExecutionEvidence,
)


class WorkflowNodeName(StrEnum):
    """Identities of LangGraph multi-agent workflow nodes."""

    SUPERVISOR = "supervisor"
    SCHEMA_GROUNDING = "schema_grounding"
    CLARIFICATION = "clarification"
    PLANNER = "planner"
    VALIDATOR = "validator"
    EXECUTOR = "executor"
    INTERPRETER = "interpreter"
    REFUSAL = "refusal"


class IntentCategory(StrEnum):
    """Classified user intent category."""

    ANALYTICAL_QUERY = "analytical_query"
    NEEDS_CLARIFICATION = "needs_clarification"
    UNSUPPORTED = "unsupported"
    PROHIBITED = "prohibited"


class ClarificationType(StrEnum):
    """Categorized analytical ambiguity triggering clarification."""

    MISSING_TARGET_METRIC = "missing_target_metric"
    SUBJECTIVE_RANKING = "subjective_ranking"
    MISSING_TIME_GRAIN = "missing_time_grain"
    UNAVAILABLE_METRIC = "unavailable_metric"
    UNSPECIFIED_FILTER = "unspecified_filter"
    GENERAL_AMBIGUITY = "general_ambiguity"


class TraceEvent(BaseModel):
    """Observable trace record capturing discrete workflow milestones."""

    node: str
    action: str
    duration_ms: float
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
    llm_called: bool = False
    tokens_used: int = 0
    status: str = "success"
    details: dict[str, Any] = Field(default_factory=dict)


class ClarificationOption(BaseModel):
    """Suggested option for resolving an analytical ambiguity."""

    label: str
    description: str
    suggested_column: str | None = None
    suggested_filter: str | None = None


class ClarificationOutput(BaseModel):
    """Actionable structured clarification produced by clarification agent."""

    clarification_type: ClarificationType
    question: str
    options: list[ClarificationOption] = Field(default_factory=list)
    available_columns: list[str] = Field(default_factory=list)


class InterpretationOutput(BaseModel):
    """Grounded explanation of analytical results linked to execution evidence."""

    summary: str
    key_findings: list[str] = Field(default_factory=list)
    data_points: dict[str, Any] = Field(default_factory=dict)
    caveats: list[str] = Field(default_factory=list)
    is_fallback: bool = False


class OrchestrationStatus(StrEnum):
    """Public lifecycle status of an analytical orchestration execution."""

    COMPLETED = "completed"
    NEEDS_CLARIFICATION = "needs_clarification"
    UNSUPPORTED = "unsupported"
    PROHIBITED = "prohibited"
    VALIDATION_REJECTED = "validation_rejected"
    FAILED = "failed"
    TIMEOUT = "timeout"


class OrchestrationResult(BaseModel):
    """Comprehensive response from the LangGraph multi-agent workflow."""

    model_config = ConfigDict(from_attributes=True)

    request_id: str
    dataset_id: uuid.UUID
    status: OrchestrationStatus
    question: str
    intent: str
    clarification: ClarificationOutput | None = None
    interpretation: InterpretationOutput | None = None
    executed_sql: str | None = None
    columns: list[AnalyticalResultColumn] = Field(default_factory=list)
    rows: list[list[Any]] = Field(default_factory=list)
    returned_row_count: int = 0
    dataset_row_count: int | None = None
    total_row_count: int | None = None
    truncated: bool = False
    unsupported_reason: str | None = None
    error_message: str | None = None
    evidence: ExecutionEvidence | None = None
    trace_events: list[TraceEvent] = Field(default_factory=list)
    total_llm_calls: int = 0
    correction_attempts: int = 0
    total_duration_ms: float = 0.0

    def to_legacy_query_result(self) -> AnalyticalQueryResult:
        """Convert orchestration result to backward-compatible AnalyticalQueryResult."""
        legacy_status = self.status.value
        if (
            self.status == OrchestrationStatus.VALIDATION_REJECTED
            or self.status == OrchestrationStatus.PROHIBITED
        ):
            legacy_status = "unsupported"

        clarification_text = None
        if self.clarification:
            clarification_text = self.clarification.question

        return AnalyticalQueryResult(
            request_id=self.request_id,
            dataset_id=self.dataset_id,
            status=legacy_status,
            question=self.question,
            intent=self.intent,
            executed_sql=self.executed_sql,
            columns=self.columns,
            rows=self.rows,
            returned_row_count=self.returned_row_count,
            dataset_row_count=self.dataset_row_count,
            total_row_count=self.total_row_count,
            truncated=self.truncated,
            clarification_question=clarification_text,
            unsupported_reason=self.unsupported_reason,
            error_message=self.error_message,
            evidence=self.evidence,
        )
