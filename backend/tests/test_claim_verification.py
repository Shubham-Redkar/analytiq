"""Comprehensive unit and integration test suite for deterministic claim verification."""

import uuid
from typing import Any

from app.analysis.contracts import ExecutionEvidence
from app.analysis.evidence import compute_result_fingerprint
from app.verification.claim_validator import ClaimValidator
from app.verification.contracts import (
    ComparisonClaim,
    ComparisonOperator,
    DifferenceClaim,
    DimensionAssociatedValueClaim,
    EmptyResultObservationClaim,
    EvidenceReference,
    ExtremumClaim,
    ExtremumType,
    MissingValueObservationClaim,
    PercentageChangeClaim,
    RankingClaim,
    ScalarValueClaim,
    VerificationStatus,
)


def make_test_evidence(
    columns: list[str],
    rows: list[list[Any]],
    dataset_row_count: int | None = 1000,
    truncated: bool = False,
) -> ExecutionEvidence:
    fingerprint = compute_result_fingerprint(columns, rows)
    return ExecutionEvidence(
        dataset_id=uuid.uuid4(),
        dataset_fingerprint="ds_hash_123",
        schema_fingerprint="schema_hash_123",
        executed_sql="SELECT * FROM dataset",
        row_count=len(rows),
        column_count=len(columns),
        dataset_row_count=dataset_row_count,
        returned_row_count=len(rows),
        truncated=truncated,
        result_fingerprint=fingerprint,
        query_duration_ms=10.0,
        total_duration_ms=20.0,
        provider="ollama",
        model="qwen2.5:7b",
        prompt_version="2026.03.v2",
    )


class TestDeterministicClaimVerification:
    """Tests evaluating every supported claim type and adversarial failure mode."""

    def test_scalar_claim_exact_match(self) -> None:
        columns = ["total_revenue"]
        rows = [[8316.0]]
        evidence = make_test_evidence(columns, rows)
        validator = ClaimValidator()

        claim = ScalarValueClaim(
            metric_name="total_revenue",
            claimed_value=8316.0,
        )
        res = validator.verify_claim(claim, evidence, columns, rows)
        assert res.status == VerificationStatus.VERIFIED
        assert res.reason_code == "SCALAR_MATCH"

    def test_scalar_claim_contradicted(self) -> None:
        columns = ["total_revenue"]
        rows = [[8316.0]]
        evidence = make_test_evidence(columns, rows)
        validator = ClaimValidator()

        claim = ScalarValueClaim(
            metric_name="total_revenue",
            claimed_value=9999.0,
        )
        res = validator.verify_claim(claim, evidence, columns, rows)
        assert res.status == VerificationStatus.CONTRADICTED

    def test_dimension_association_verified(self) -> None:
        columns = ["region", "revenue"]
        rows = [["North", 500.0], ["South", 800.0]]
        evidence = make_test_evidence(columns, rows)
        validator = ClaimValidator()

        claim = DimensionAssociatedValueClaim(
            dimension_name="region",
            dimension_value="South",
            metric_name="revenue",
            claimed_value=800.0,
        )
        res = validator.verify_claim(claim, evidence, columns, rows)
        assert res.status == VerificationStatus.VERIFIED
        assert res.reason_code == "DIMENSION_ASSOCIATION_VERIFIED"

    def test_dimension_association_rejects_swapped_values(self) -> None:
        """Adversarial check: North 800 and South 500 must both be contradicted."""
        columns = ["region", "revenue"]
        rows = [["North", 500.0], ["South", 800.0]]
        evidence = make_test_evidence(columns, rows)
        validator = ClaimValidator()

        # Adversarial assertion: North is 800 (actually South)
        claim = DimensionAssociatedValueClaim(
            dimension_name="region",
            dimension_value="North",
            metric_name="revenue",
            claimed_value=800.0,
        )
        res = validator.verify_claim(claim, evidence, columns, rows)
        assert res.status == VerificationStatus.CONTRADICTED
        assert res.reason_code == "METRIC_DIMENSION_MISMATCH"

    def test_comparison_claim_direction_verified_and_contradicted(self) -> None:
        columns = ["region", "revenue"]
        rows = [["North", 500.0], ["South", 800.0]]
        evidence = make_test_evidence(columns, rows)
        validator = ClaimValidator()

        valid_claim = ComparisonClaim(
            left_entity="South",
            left_value=800.0,
            operator=ComparisonOperator.GREATER_THAN,
            right_entity="North",
            right_value=500.0,
            metric_name="revenue",
        )
        assert (
            validator.verify_claim(valid_claim, evidence, columns, rows).status
            == VerificationStatus.VERIFIED
        )

        # Reversing direction
        contradicted_claim = ComparisonClaim(
            left_entity="South",
            left_value=800.0,
            operator=ComparisonOperator.LESS_THAN,
            right_entity="North",
            right_value=500.0,
            metric_name="revenue",
        )
        assert (
            validator.verify_claim(contradicted_claim, evidence, columns, rows).status
            == VerificationStatus.CONTRADICTED
        )

    def test_difference_calculation_verified(self) -> None:
        columns = ["region", "revenue"]
        rows = [["North", 500.0], ["South", 800.0]]
        evidence = make_test_evidence(columns, rows)
        validator = ClaimValidator()

        claim = DifferenceClaim(
            target_entity="South",
            baseline_entity="North",
            metric_name="revenue",
            claimed_difference=300.0,
            evidence_references=[
                EvidenceReference(
                    result_fingerprint=evidence.result_fingerprint,
                    row_index=1,
                    column_name="revenue",
                ),
                EvidenceReference(
                    result_fingerprint=evidence.result_fingerprint,
                    row_index=0,
                    column_name="revenue",
                ),
            ],
        )
        res = validator.verify_claim(claim, evidence, columns, rows)
        assert res.status == VerificationStatus.VERIFIED
        assert res.computed_value == 300.0

    def test_percentage_change_calculation(self) -> None:
        columns = ["period", "sales"]
        rows = [["Q1", 100.0], ["Q2", 120.0]]
        evidence = make_test_evidence(columns, rows)
        validator = ClaimValidator()

        claim = PercentageChangeClaim(
            baseline_entity="Q1",
            target_entity="Q2",
            metric_name="sales",
            claimed_percent_change=20.0,
            evidence_references=[
                EvidenceReference(
                    result_fingerprint=evidence.result_fingerprint, row_index=0, column_name="sales"
                ),
                EvidenceReference(
                    result_fingerprint=evidence.result_fingerprint, row_index=1, column_name="sales"
                ),
            ],
        )
        res = validator.verify_claim(claim, evidence, columns, rows)
        assert res.status == VerificationStatus.VERIFIED

    def test_ranking_and_truncation_safety(self) -> None:
        columns = ["product", "revenue"]
        rows = [["Laptop", 1200.0], ["Phone", 800.0], ["Tablet", 400.0]]
        validator = ClaimValidator()

        # Non-truncated: global ranking is accepted
        evidence_full = make_test_evidence(columns, rows, truncated=False)
        claim_rank1 = RankingClaim(
            entity_name="Laptop",
            metric_name="revenue",
            claimed_rank=1,
            scope_is_global=True,
        )
        assert (
            validator.verify_claim(claim_rank1, evidence_full, columns, rows).status
            == VerificationStatus.VERIFIED
        )

        # Truncated: global ranking must be classified as INSUFFICIENT_EVIDENCE
        evidence_trunc = make_test_evidence(columns, rows, truncated=True)
        res_trunc = validator.verify_claim(claim_rank1, evidence_trunc, columns, rows)
        assert res_trunc.status == VerificationStatus.INSUFFICIENT_EVIDENCE
        assert res_trunc.reason_code == "GLOBAL_RANKING_ON_TRUNCATED_RESULT"

    def test_extremum_verified(self) -> None:
        columns = ["product", "sales"]
        rows = [["ItemA", 10.0], ["ItemB", 95.0], ["ItemC", 35.0]]
        evidence = make_test_evidence(columns, rows)
        validator = ClaimValidator()

        max_claim = ExtremumClaim(
            extremum=ExtremumType.MAXIMUM,
            entity_name="ItemB",
            metric_name="sales",
        )
        assert (
            validator.verify_claim(max_claim, evidence, columns, rows).status
            == VerificationStatus.VERIFIED
        )

        false_max = ExtremumClaim(
            extremum=ExtremumType.MAXIMUM,
            entity_name="ItemA",
            metric_name="sales",
        )
        assert (
            validator.verify_claim(false_max, evidence, columns, rows).status
            == VerificationStatus.CONTRADICTED
        )

    def test_missing_values_and_empty_result(self) -> None:
        columns = ["name", "score"]
        rows = [["Alice", 90.0], ["Bob", None], ["Charlie", None]]
        evidence = make_test_evidence(columns, rows)
        validator = ClaimValidator()

        missing_claim = MissingValueObservationClaim(
            column_name="score",
            missing_count=2,
        )
        assert (
            validator.verify_claim(missing_claim, evidence, columns, rows).status
            == VerificationStatus.VERIFIED
        )

        empty_claim = EmptyResultObservationClaim()
        empty_ev = make_test_evidence(columns, [])
        assert (
            validator.verify_claim(empty_claim, empty_ev, columns, []).status
            == VerificationStatus.VERIFIED
        )
