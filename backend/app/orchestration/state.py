"""LangGraph State definition for the multi-agent analytical workflow."""

from typing import Any, TypedDict

from app.analysis.contracts import (
    AnalyticalResultColumn,
    DatasetAnalyticalContext,
    ExecutionEvidence,
    SQLValidationResult,
    StructuredAnalyticalPlan,
)
from app.orchestration.contracts import (
    ClarificationOutput,
    IntentCategory,
    InterpretationOutput,
    OrchestrationStatus,
    TraceEvent,
)


class GroundingAnalysis(TypedDict, total=True):
    """Deterministic schema grounding output."""

    is_grounded: bool
    ambiguity_detected: bool
    ambiguity_type: str | None
    ambiguity_reason: str | None
    referenced_columns: list[str]
    missing_columns: list[str]
    candidate_metrics: list[str]
    candidate_dimensions: list[str]
    suggested_clarification: str | None


class WorkflowStateRequired(TypedDict):
    """Immutable required inputs and metadata."""

    request_id: str
    dataset_id: str
    user_id: str
    question: str
    dataset_context: DatasetAnalyticalContext
    dataset_parquet_path: str


class WorkflowState(WorkflowStateRequired, total=False):
    """Comprehensive state container for the LangGraph analytical workflow."""

    # Control & Budget
    status: OrchestrationStatus
    intent: IntentCategory
    step_count: int
    llm_call_count: int
    correction_count: int
    total_start_monotonic: float
    deadline_monotonic: float
    timed_out: bool
    error_message: str | None
    unsupported_reason: str | None

    # Intermediate Artifacts
    grounding: GroundingAnalysis
    clarification: ClarificationOutput | None
    plan: StructuredAnalyticalPlan | None
    validation_result: SQLValidationResult | None
    validated_sql: str | None

    # Execution Results & Evidence
    query_columns: list[AnalyticalResultColumn]
    query_rows: list[list[Any]]
    returned_row_count: int
    dataset_row_count: int | None
    total_row_count: int | None
    truncated: bool
    evidence: ExecutionEvidence | None

    # Interpretation & Tracing
    interpretation: InterpretationOutput | None
    trace_events: list[TraceEvent]
