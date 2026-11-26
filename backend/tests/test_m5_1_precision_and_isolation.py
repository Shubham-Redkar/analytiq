"""M5.1 Targeted Regression Suite: Precision, Isolation, and Intent Consistency."""

import uuid
from typing import Any

from app.analysis.contracts import (
    AnalyticalOperation,
    AnalyticalResultColumn,
    ExecutionEvidence,
    PlanStatus,
    StructuredAnalyticalPlan,
)
from app.verification.contracts import (
    EvidenceReference,
    IntentConsistencyStatus,
    ScalarValueClaim,
    VerificationStatus,
)
from app.verification.derived_metrics import (
    calculate_percentage_change,
    calculate_proportion,
    numbers_match,
)
from app.verification.intent_consistency import verify_intent_consistency
from app.verification.references import validate_evidence_reference
from app.verification.service import EvidenceVerificationService


def make_test_evidence(
    rows: list[list[Any]],
    columns: list[str],
    dataset_id: uuid.UUID | None = None,
    result_fingerprint: str = "sha256:valid_evidence_fingerprint",
    truncated: bool = False,
) -> ExecutionEvidence:
    """Create test ExecutionEvidence fixture."""
    return ExecutionEvidence(
        dataset_id=dataset_id or uuid.uuid4(),
        dataset_fingerprint="sha256:dataset_fingerprint",
        schema_fingerprint="sha256:schema_fingerprint",
        executed_sql="SELECT * FROM dataset",
        row_count=len(rows),
        column_count=len(columns),
        returned_row_count=len(rows),
        truncated=truncated,
        result_fingerprint=result_fingerprint,
        query_duration_ms=1.5,
        total_duration_ms=3.2,
        provider="ollama",
        model="qwen2.5:7b",
        prompt_version="2026.03.v2",
    )


class TestNumericalPrecisionPolicy:
    """Verifies Phase 2: strict, type-aware numerical precision rules."""

    def test_integers_require_exact_equality(self) -> None:
        assert numbers_match(1000, 1000) is True
        # 1000 vs 1009 must NEVER match under M5.1 policy
        assert numbers_match(1000, 1009) is False
        assert numbers_match(1000000, 1009000) is False
        assert numbers_match(100, 101) is False

    def test_boolean_cannot_masquerade_as_numeric(self) -> None:
        assert numbers_match(True, 1) is False
        assert numbers_match(False, 0) is False
        assert numbers_match(True, True) is True
        assert numbers_match(False, False) is True

    def test_floating_point_strict_tolerance(self) -> None:
        assert numbers_match(100.0, 100.0) is True
        assert numbers_match(100.0, 100.00000000001) is True
        assert numbers_match(100.0, 100.5) is False
        assert numbers_match(100.0, 100.01) is False

    def test_display_rounding_policy(self) -> None:
        # Canonical 33.3333333 with 2 decimal display places matches 33.33
        assert numbers_match(33.3333333, 33.33, display_places=2) is True
        # But fails without explicit display rounding
        assert numbers_match(33.3333333, 33.33) is False

    def test_nan_and_infinity_semantics(self) -> None:
        assert numbers_match(float("nan"), float("nan")) is False
        assert numbers_match(float("inf"), float("inf")) is True
        assert numbers_match(float("-inf"), float("inf")) is False
        assert numbers_match(None, 0) is False
        assert numbers_match(None, None) is True


class TestEvidenceIsolationAndIdentity:
    """Verifies Phase 3: request and dataset scoped evidence isolation."""

    def test_matching_evidence_and_request_resolves_valid(self) -> None:
        dataset_id = uuid.uuid4()
        req_id = "req-12345"
        ev = make_test_evidence([[150.0]], ["amount"], dataset_id=dataset_id)
        ref = EvidenceReference(
            dataset_id=dataset_id,
            request_id=req_id,
            result_fingerprint=ev.result_fingerprint,
            row_index=0,
            column_name="amount",
            expected_value=150.0,
        )
        ok, code, val = validate_evidence_reference(
            ref, ev, ["amount"], [[150.0]], current_request_id=req_id
        )
        assert ok is True
        assert code == "VALID_REFERENCE"
        assert val == 150.0

    def test_cross_dataset_reference_rejected(self) -> None:
        dataset_a = uuid.uuid4()
        dataset_b = uuid.uuid4()
        ev = make_test_evidence([[500.0]], ["revenue"], dataset_id=dataset_a)
        ref_from_b = EvidenceReference(
            dataset_id=dataset_b,
            result_fingerprint=ev.result_fingerprint,
            row_index=0,
            column_name="revenue",
        )
        ok, code, _ = validate_evidence_reference(ref_from_b, ev, ["revenue"], [[500.0]])
        assert ok is False
        assert code == "DATASET_MISMATCH"

    def test_cross_request_reference_rejected(self) -> None:
        dataset_id = uuid.uuid4()
        ev = make_test_evidence([[500.0]], ["revenue"], dataset_id=dataset_id)
        ref = EvidenceReference(
            dataset_id=dataset_id,
            request_id="foreign_req_999",
            result_fingerprint=ev.result_fingerprint,
            row_index=0,
            column_name="revenue",
        )
        ok, code, _ = validate_evidence_reference(
            ref, ev, ["revenue"], [[500.0]], current_request_id="current_req_001"
        )
        assert ok is False
        assert code == "REQUEST_MISMATCH"

    def test_identical_fingerprint_from_different_dataset_blocked(self) -> None:
        # Even if two queries produce identical result tables & fingerprints,
        # reference bound to Dataset A cannot resolve against Dataset B
        dataset_a = uuid.uuid4()
        dataset_b = uuid.uuid4()
        ev_b = make_test_evidence(
            [[100]], ["count"], dataset_id=dataset_b, result_fingerprint="sha256:same_hash"
        )
        ref_a = EvidenceReference(
            dataset_id=dataset_a,
            result_fingerprint="sha256:same_hash",
            row_index=0,
            column_name="count",
        )
        ok, code, _ = validate_evidence_reference(ref_a, ev_b, ["count"], [[100]])
        assert ok is False
        assert code == "DATASET_MISMATCH"


class TestDerivedCalculationsAndIntentConsistency:
    """Verifies Phase 5 & Phase 6: percentage change semantics and AST intent checks."""

    def test_percentage_change_positive_baseline(self) -> None:
        # (150 - 100) / 100 * 100 = 50.0%
        pct = calculate_percentage_change(100.0, 150.0)
        assert pct is not None
        assert numbers_match(pct, 50.0)

    def test_percentage_change_zero_and_negative_baseline_undefined(self) -> None:
        assert calculate_percentage_change(0.0, 100.0) is None
        assert calculate_percentage_change(-50.0, 50.0) is None

    def test_proportion_vs_percentage_distinction(self) -> None:
        prop = calculate_proportion(25.0, 100.0, as_percentage=False)
        assert prop == 0.25
        pct = calculate_proportion(25.0, 100.0, as_percentage=True)
        assert pct == 25.0

    def test_intent_consistency_detects_wrong_metric_queried(self) -> None:
        plan = StructuredAnalyticalPlan(
            status=PlanStatus.READY,
            intent="Calculate total revenue",
            operation=AnalyticalOperation.AGGREGATION,
            referenced_columns=["revenue"],
            sql="SELECT SUM(quantity) AS total_qty FROM dataset",
            assumptions=[],
        )
        res = verify_intent_consistency(
            question="What is total revenue?",
            plan=plan,
            executed_sql=plan.sql,
            columns=["total_qty"],
        )
        assert res.status == IntentConsistencyStatus.CONTRADICTED
        assert res.reason_code == "METRIC_COLUMN_MISMATCH"

    def test_intent_consistency_detects_filter_polarity_mismatch(self) -> None:
        plan = StructuredAnalyticalPlan(
            status=PlanStatus.READY,
            intent="Revenue in North region",
            operation=AnalyticalOperation.FILTERING,
            referenced_columns=["region", "revenue"],
            sql="SELECT SUM(revenue) FROM dataset WHERE region = 'South'",
            assumptions=[],
        )
        res = verify_intent_consistency(
            question="What is the revenue for North?",
            plan=plan,
            executed_sql=plan.sql,
            columns=["sum"],
        )
        assert res.status == IntentConsistencyStatus.CONTRADICTED
        assert res.reason_code == "FILTER_POLARITY_MISMATCH"


class TestAuthoritativeAnswerSynthesis:
    """Verifies Phase 4: rejected claims cannot leak into the final authoritative explanation."""

    def test_rejected_claim_does_not_leak_into_answer(self) -> None:
        service = EvidenceVerificationService()
        ev = make_test_evidence([[100.0]], ["revenue"])
        cols = [AnalyticalResultColumn(name="revenue", type="DOUBLE")]
        rows = [[100.0]]

        # LLM proposes an ungrounded hallucinated claim of 500
        false_claim = ScalarValueClaim(
            metric_name="revenue",
            claimed_value=500.0,
            evidence_references=[
                EvidenceReference(
                    result_fingerprint=ev.result_fingerprint, row_index=0, column_name="revenue"
                )
            ],
        )

        summary = service.verify_analysis(
            question="What is the revenue?",
            plan=None,
            executed_sql="SELECT revenue FROM dataset",
            evidence=ev,
            columns=cols,
            rows=rows,
            claims=[false_claim],
        )

        assert summary.status == VerificationStatus.CONTRADICTED
        assert summary.verified_claims_count == 0
        assert len(summary.rejected_claims) == 1
        # The authoritative explanation must NOT mention 500
        assert "500" not in (summary.verified_explanation or "")
        # Fallback uses actual evidence value (100.0)
        assert "100.0" in (summary.verified_explanation or "")
