"""Strongly typed contracts for deterministic analytical claim verification."""

import uuid
from enum import StrEnum
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class ClaimType(StrEnum):
    """Categorized vocabulary of deterministically verifiable analytical claims."""

    SCALAR_VALUE = "scalar_value"
    DIMENSION_ASSOCIATED_VALUE = "dimension_associated_value"
    ROW_COUNT = "row_count"
    COMPARISON = "comparison"
    DIFFERENCE = "difference"
    PERCENTAGE_CHANGE = "percentage_change"
    PROPORTION = "proportion"
    RANKING = "ranking"
    EXTREMUM = "extremum"
    TEMPORAL_OBSERVATION = "temporal_observation"
    MISSING_VALUE_OBSERVATION = "missing_value_observation"
    EMPTY_RESULT_OBSERVATION = "empty_result_observation"


class VerificationStatus(StrEnum):
    """Deterministic status resulting from claim verification."""

    VERIFIED = "verified"
    CONTRADICTED = "contradicted"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"
    UNSUPPORTED = "unsupported"
    INVALID_REFERENCE = "invalid_reference"


class EvidenceReference(BaseModel):
    """Explicit reference linking a factual claim to verified analytical evidence."""

    model_config = ConfigDict(extra="forbid")

    evidence_id: str | None = None
    request_id: str | None = None
    dataset_id: uuid.UUID | None = None
    result_fingerprint: str
    row_index: int = Field(ge=0)
    column_name: str
    expected_value: Any = None


class ComparisonOperator(StrEnum):
    """Supported deterministic comparison operators."""

    GREATER_THAN = ">"
    LESS_THAN = "<"
    EQUAL = "=="
    GREATER_THAN_OR_EQUAL = ">="
    LESS_THAN_OR_EQUAL = "<="
    NOT_EQUAL = "!="


class ExtremumType(StrEnum):
    """Extremum direction."""

    MAXIMUM = "maximum"
    MINIMUM = "minimum"


class BaseClaim(BaseModel):
    """Base model for structured analytical claims."""

    model_config = ConfigDict(extra="forbid")

    claim_id: str = Field(default_factory=lambda: f"claim_{uuid.uuid4().hex[:8]}")
    evidence_references: list[EvidenceReference] = Field(default_factory=list)


class ScalarValueClaim(BaseClaim):
    """Claim asserting a single aggregated or scalar metric value."""

    claim_type: Literal[ClaimType.SCALAR_VALUE] = ClaimType.SCALAR_VALUE
    metric_name: str
    claimed_value: float | int | str | None
    aggregation: str | None = None
    unit: str | None = None


class DimensionAssociatedValueClaim(BaseClaim):
    """Claim asserting a metric value associated with a specific dimension value."""

    claim_type: Literal[ClaimType.DIMENSION_ASSOCIATED_VALUE] = ClaimType.DIMENSION_ASSOCIATED_VALUE
    dimension_name: str
    dimension_value: Any
    metric_name: str
    claimed_value: float | int | str | None
    unit: str | None = None


class RowCountClaim(BaseClaim):
    """Claim asserting returned row count or filtered matching record count."""

    claim_type: Literal[ClaimType.ROW_COUNT] = ClaimType.ROW_COUNT
    claimed_count: int = Field(ge=0)
    is_dataset_total: bool = False


class ComparisonClaim(BaseClaim):
    """Claim asserting a deterministic comparison relation between two entities."""

    claim_type: Literal[ClaimType.COMPARISON] = ClaimType.COMPARISON
    left_entity: str
    left_value: float | int
    operator: ComparisonOperator
    right_entity: str
    right_value: float | int
    metric_name: str


class DifferenceClaim(BaseClaim):
    """Claim asserting the absolute or directional difference between two values."""

    claim_type: Literal[ClaimType.DIFFERENCE] = ClaimType.DIFFERENCE
    target_entity: str
    baseline_entity: str
    metric_name: str
    claimed_difference: float | int
    is_absolute: bool = False


class PercentageChangeClaim(BaseClaim):
    """Claim asserting the percentage change between baseline and target values."""

    claim_type: Literal[ClaimType.PERCENTAGE_CHANGE] = ClaimType.PERCENTAGE_CHANGE
    baseline_entity: str
    target_entity: str
    metric_name: str
    claimed_percent_change: float


class ProportionClaim(BaseClaim):
    """Claim asserting part-to-whole contribution percentage or ratio."""

    claim_type: Literal[ClaimType.PROPORTION] = ClaimType.PROPORTION
    part_entity: str
    whole_entity: str = "total"
    metric_name: str
    claimed_proportion_pct: float = Field(ge=0.0, le=100.0)


class RankingClaim(BaseClaim):
    """Claim asserting an ordinal ranking position for an entity."""

    claim_type: Literal[ClaimType.RANKING] = ClaimType.RANKING
    entity_name: str
    metric_name: str
    claimed_rank: int = Field(ge=1)
    descending: bool = True
    scope_is_global: bool = False


class ExtremumClaim(BaseClaim):
    """Claim asserting an entity holds the minimum or maximum value."""

    claim_type: Literal[ClaimType.EXTREMUM] = ClaimType.EXTREMUM
    extremum: ExtremumType
    entity_name: str
    metric_name: str
    claimed_value: float | int | None = None
    scope_is_global: bool = False


class TemporalObservationClaim(BaseClaim):
    """Claim asserting a chronological or date-associated observation."""

    claim_type: Literal[ClaimType.TEMPORAL_OBSERVATION] = ClaimType.TEMPORAL_OBSERVATION
    time_period: str
    metric_name: str
    claimed_value: float | int | str | None


class MissingValueObservationClaim(BaseClaim):
    """Claim asserting presence of null or missing records."""

    claim_type: Literal[ClaimType.MISSING_VALUE_OBSERVATION] = ClaimType.MISSING_VALUE_OBSERVATION
    column_name: str
    missing_count: int = Field(ge=0)


class EmptyResultObservationClaim(BaseClaim):
    """Claim asserting that the query returned zero records."""

    claim_type: Literal[ClaimType.EMPTY_RESULT_OBSERVATION] = ClaimType.EMPTY_RESULT_OBSERVATION
    filter_criteria: str | None = None


# Discriminated Union of all supported claim models
AnalyticalClaim = Annotated[
    ScalarValueClaim
    | DimensionAssociatedValueClaim
    | RowCountClaim
    | ComparisonClaim
    | DifferenceClaim
    | PercentageChangeClaim
    | ProportionClaim
    | RankingClaim
    | ExtremumClaim
    | TemporalObservationClaim
    | MissingValueObservationClaim
    | EmptyResultObservationClaim,
    Field(discriminator="claim_type"),
]


class ClaimVerificationResult(BaseModel):
    """Deterministic verification result for an individual analytical claim."""

    claim_id: str
    claim_type: ClaimType
    status: VerificationStatus
    reason_code: str
    explanation: str
    expected_value: Any = None
    claimed_value: Any = None
    computed_value: Any = None
    evidence_references: list[EvidenceReference] = Field(default_factory=list)


class IntentConsistencyStatus(StrEnum):
    """Status of deterministic intent-to-result consistency verification."""

    CONSISTENT = "consistent"
    CONTRADICTED = "contradicted"
    INSUFFICIENT_INFORMATION = "insufficient_information"


class IntentConsistencyResult(BaseModel):
    """Result of validating structured analytical intent against executed SQL and results."""

    status: IntentConsistencyStatus
    reason_code: str
    details: str
    mismatched_dimension: str | None = None
    mismatched_metric: str | None = None
    mismatched_aggregation: str | None = None


class VerificationSummary(BaseModel):
    """Aggregate summary of analytical verification across all claims and intent."""

    status: VerificationStatus
    total_claims: int
    verified_claims_count: int
    contradicted_claims_count: int
    insufficient_evidence_count: int
    unsupported_claims_count: int
    invalid_references_count: int
    intent_consistency: IntentConsistencyResult
    verified_claims: list[ClaimVerificationResult] = Field(default_factory=list)
    rejected_claims: list[ClaimVerificationResult] = Field(default_factory=list)
    verification_duration_ms: float = 0.0
    verified_explanation: str | None = None
    limitations: list[str] = Field(default_factory=list)
