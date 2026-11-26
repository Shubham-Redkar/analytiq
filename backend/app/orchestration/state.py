"""LangGraph State definition for the multi-agent analytical workflow."""

from typing import Any, NotRequired, TypedDict

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
from app.verification.contracts import AnalyticalClaim, VerificationSummary


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


class WorkflowState(TypedDict):
    """Comprehensive state container for the LangGraph analytical workflow.

    Uses PEP 655 `typing.NotRequired` for single-class definition, ensuring complete
    structural compatibility across all Python type checkers (Pyright, Mypy, VS Code Pylance)
    and LangGraph's internal `StateT` bound protocol (`TypedDictLikeV1` / `TypedDictLikeV2`).
    """

    # 1. Inputs & Trusted Metadata (Required)
    request_id: str
    dataset_id: str
    user_id: str
    question: str
    dataset_context: DatasetAnalyticalContext
    dataset_parquet_path: str

    # 2. Control & Budget (Optional / Mutable in graph)
    status: NotRequired[OrchestrationStatus]
    intent: NotRequired[IntentCategory]
    step_count: NotRequired[int]
    llm_call_count: NotRequired[int]
    correction_count: NotRequired[int]
    total_start_monotonic: NotRequired[float]
    deadline_monotonic: NotRequired[float]
    timed_out: NotRequired[bool]
    error_message: NotRequired[str | None]
    unsupported_reason: NotRequired[str | None]

    # 3. Intermediate Artifacts
    grounding: NotRequired[GroundingAnalysis]
    clarification: NotRequired[ClarificationOutput | None]
    plan: NotRequired[StructuredAnalyticalPlan | None]
    validation_result: NotRequired[SQLValidationResult | None]
    validated_sql: NotRequired[str | None]

    # 4. Execution Results & Evidence
    query_columns: NotRequired[list[AnalyticalResultColumn]]
    query_rows: NotRequired[list[list[Any]]]
    returned_row_count: NotRequired[int]
    dataset_row_count: NotRequired[int | None]
    total_row_count: NotRequired[int | None]
    truncated: NotRequired[bool]
    evidence: NotRequired[ExecutionEvidence | None]

    # 5. Interpretation, Verification & Tracing
    interpretation: NotRequired[InterpretationOutput | None]
    structured_claims: NotRequired[list[AnalyticalClaim]]
    verification: NotRequired[VerificationSummary | None]
    trace_events: NotRequired[list[TraceEvent]]
