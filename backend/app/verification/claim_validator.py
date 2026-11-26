"""Core deterministic claim validator evaluating structured claims against evidence."""

from typing import Any

from app.analysis.contracts import ExecutionEvidence
from app.verification.contracts import (
    AnalyticalClaim,
    ClaimVerificationResult,
    ComparisonClaim,
    DifferenceClaim,
    DimensionAssociatedValueClaim,
    EmptyResultObservationClaim,
    EvidenceReference,
    ExtremumClaim,
    ExtremumType,
    MissingValueObservationClaim,
    PercentageChangeClaim,
    ProportionClaim,
    RankingClaim,
    RowCountClaim,
    ScalarValueClaim,
    TemporalObservationClaim,
    VerificationStatus,
)
from app.verification.derived_metrics import (
    calculate_difference,
    calculate_percentage_change,
    calculate_proportion,
    numbers_match,
    safe_float,
)
from app.verification.references import validate_evidence_reference


class ClaimValidator:
    """Evaluates analytical claims against trusted execution evidence deterministically."""

    def __init__(
        self,
        max_claims_per_interpretation: int = 15,
        max_references_per_claim: int = 5,
    ) -> None:
        self.max_claims = max_claims_per_interpretation
        self.max_refs = max_references_per_claim

    def verify_claim(
        self,
        claim: AnalyticalClaim,
        evidence: ExecutionEvidence,
        columns: list[str],
        rows: list[list[Any]],
    ) -> ClaimVerificationResult:
        """Validate an individual claim against evidence and table data."""
        # 0. Check complexity ceiling
        if len(claim.evidence_references) > self.max_refs:
            return ClaimVerificationResult(
                claim_id=claim.claim_id,
                claim_type=claim.claim_type,
                status=VerificationStatus.UNSUPPORTED,
                reason_code="EXCESSIVE_REFERENCES_CEILING",
                explanation=(
                    f"Claim has {len(claim.evidence_references)} references; "
                    f"maximum permitted is {self.max_refs}."
                ),
                claimed_value=None,
            )

        # Dispatch by claim type
        if isinstance(claim, ScalarValueClaim):
            return self._verify_scalar(claim, evidence, columns, rows)
        elif isinstance(claim, DimensionAssociatedValueClaim):
            return self._verify_dimension_associated(claim, evidence, columns, rows)
        elif isinstance(claim, RowCountClaim):
            return self._verify_row_count(claim, evidence, columns, rows)
        elif isinstance(claim, ComparisonClaim):
            return self._verify_comparison(claim, evidence, columns, rows)
        elif isinstance(claim, DifferenceClaim):
            return self._verify_difference(claim, evidence, columns, rows)
        elif isinstance(claim, PercentageChangeClaim):
            return self._verify_percentage_change(claim, evidence, columns, rows)
        elif isinstance(claim, ProportionClaim):
            return self._verify_proportion(claim, evidence, columns, rows)
        elif isinstance(claim, RankingClaim):
            return self._verify_ranking(claim, evidence, columns, rows)
        elif isinstance(claim, ExtremumClaim):
            return self._verify_extremum(claim, evidence, columns, rows)
        elif isinstance(claim, TemporalObservationClaim):
            return self._verify_temporal(claim, evidence, columns, rows)
        elif isinstance(claim, MissingValueObservationClaim):
            return self._verify_missing_values(claim, evidence, columns, rows)
        elif isinstance(claim, EmptyResultObservationClaim):
            return self._verify_empty_result(claim, evidence, columns, rows)
        else:
            return ClaimVerificationResult(
                claim_id=claim.claim_id,
                claim_type=claim.claim_type,
                status=VerificationStatus.UNSUPPORTED,
                reason_code="UNSUPPORTED_CLAIM_TYPE",
                explanation="Claim type is not in supported verification vocabulary.",
            )

    # -------------------------------------------------------------------------
    # Internal Verifiers
    # -------------------------------------------------------------------------

    def _verify_scalar(
        self,
        claim: ScalarValueClaim,
        evidence: ExecutionEvidence,
        columns: list[str],
        rows: list[list[Any]],
    ) -> ClaimVerificationResult:
        if not claim.evidence_references:
            # Check if 1 row, 1 column scalar
            if len(rows) == 1 and len(columns) == 1:
                val = rows[0][0]
                if self._values_equal(claim.claimed_value, val):
                    return ClaimVerificationResult(
                        claim_id=claim.claim_id,
                        claim_type=claim.claim_type,
                        status=VerificationStatus.VERIFIED,
                        reason_code="SCALAR_MATCH",
                        explanation="Scalar value matches single-cell query output.",
                        expected_value=val,
                        claimed_value=claim.claimed_value,
                        computed_value=val,
                    )
                else:
                    return ClaimVerificationResult(
                        claim_id=claim.claim_id,
                        claim_type=claim.claim_type,
                        status=VerificationStatus.CONTRADICTED,
                        reason_code="SCALAR_VALUE_CONTRADICTED",
                        explanation=(
                            f"Claim asserted {claim.claimed_value}, but query computed {val}."
                        ),
                        expected_value=val,
                        claimed_value=claim.claimed_value,
                    )
            return ClaimVerificationResult(
                claim_id=claim.claim_id,
                claim_type=claim.claim_type,
                status=VerificationStatus.INSUFFICIENT_EVIDENCE,
                reason_code="MISSING_EVIDENCE_REFERENCES",
                explanation="Scalar claim provides no reference for multi-cell result.",
                claimed_value=claim.claimed_value,
            )

        ref = claim.evidence_references[0]
        ok, reason, actual = validate_evidence_reference(ref, evidence, columns, rows)
        if not ok:
            return ClaimVerificationResult(
                claim_id=claim.claim_id,
                claim_type=claim.claim_type,
                status=VerificationStatus.INVALID_REFERENCE,
                reason_code=reason,
                explanation=f"Evidence reference failed validation: {reason}",
                evidence_references=[ref],
            )

        if self._values_equal(claim.claimed_value, actual):
            return ClaimVerificationResult(
                claim_id=claim.claim_id,
                claim_type=claim.claim_type,
                status=VerificationStatus.VERIFIED,
                reason_code="SCALAR_MATCH",
                explanation="Claimed scalar metric matches referenced cell value.",
                expected_value=actual,
                claimed_value=claim.claimed_value,
                computed_value=actual,
                evidence_references=[ref],
            )
        return ClaimVerificationResult(
            claim_id=claim.claim_id,
            claim_type=claim.claim_type,
            status=VerificationStatus.CONTRADICTED,
            reason_code="VALUE_MISMATCH",
            explanation=f"Claim asserted {claim.claimed_value}, but referenced cell is {actual}.",
            expected_value=actual,
            claimed_value=claim.claimed_value,
            evidence_references=[ref],
        )

    def _verify_dimension_associated(
        self,
        claim: DimensionAssociatedValueClaim,
        evidence: ExecutionEvidence,
        columns: list[str],
        rows: list[list[Any]],
    ) -> ClaimVerificationResult:
        # Find column indices
        col_names_lower = [c.lower().strip() for c in columns]
        dim_col = claim.dimension_name.lower().strip()
        metric_col = claim.metric_name.lower().strip()

        if dim_col not in col_names_lower:
            return ClaimVerificationResult(
                claim_id=claim.claim_id,
                claim_type=claim.claim_type,
                status=VerificationStatus.INVALID_REFERENCE,
                reason_code="UNKNOWN_DIMENSION_COLUMN",
                explanation=(f"Dimension '{claim.dimension_name}' not in columns {columns}."),
                claimed_value=claim.claimed_value,
            )

        if metric_col not in col_names_lower:
            return ClaimVerificationResult(
                claim_id=claim.claim_id,
                claim_type=claim.claim_type,
                status=VerificationStatus.INVALID_REFERENCE,
                reason_code="UNKNOWN_METRIC_COLUMN",
                explanation=(f"Metric '{claim.metric_name}' not in columns {columns}."),
                claimed_value=claim.claimed_value,
            )

        dim_idx = col_names_lower.index(dim_col)
        metric_idx = col_names_lower.index(metric_col)

        # Find rows matching dimension value
        matching_rows: list[tuple[int, list[Any]]] = []
        for r_idx, row in enumerate(rows):
            cell_dim = row[dim_idx]
            if str(cell_dim).strip().lower() == str(claim.dimension_value).strip().lower():
                matching_rows.append((r_idx, row))

        if not matching_rows:
            return ClaimVerificationResult(
                claim_id=claim.claim_id,
                claim_type=claim.claim_type,
                status=VerificationStatus.CONTRADICTED,
                reason_code="DIMENSION_VALUE_NOT_FOUND",
                explanation=(f"Dimension value '{claim.dimension_value}' not found in rows."),
                claimed_value=claim.claimed_value,
            )

        # Check metric value for matching dimension
        r_idx, match_row = matching_rows[0]
        actual_metric = match_row[metric_idx]

        if self._values_equal(claim.claimed_value, actual_metric):
            ref = EvidenceReference(
                evidence_id=str(evidence.dataset_id),
                result_fingerprint=evidence.result_fingerprint,
                row_index=r_idx,
                column_name=columns[metric_idx],
                expected_value=actual_metric,
            )
            return ClaimVerificationResult(
                claim_id=claim.claim_id,
                claim_type=claim.claim_type,
                status=VerificationStatus.VERIFIED,
                reason_code="DIMENSION_ASSOCIATION_VERIFIED",
                explanation=(
                    f"Verified {claim.metric_name} = {actual_metric} for "
                    f"{claim.dimension_name} = {claim.dimension_value}."
                ),
                expected_value=actual_metric,
                claimed_value=claim.claimed_value,
                computed_value=actual_metric,
                evidence_references=[ref],
            )
        else:
            return ClaimVerificationResult(
                claim_id=claim.claim_id,
                claim_type=claim.claim_type,
                status=VerificationStatus.CONTRADICTED,
                reason_code="METRIC_DIMENSION_MISMATCH",
                explanation=(
                    f"Claim asserted {claim.metric_name} = {claim.claimed_value} for "
                    f"{claim.dimension_name} = {claim.dimension_value}, "
                    f"but computed value is {actual_metric}."
                ),
                expected_value=actual_metric,
                claimed_value=claim.claimed_value,
            )

    def _verify_row_count(
        self,
        claim: RowCountClaim,
        evidence: ExecutionEvidence,
        columns: list[str],
        rows: list[list[Any]],
    ) -> ClaimVerificationResult:
        if claim.is_dataset_total:
            # Cannot assert dataset total if truncated or if dataset_row_count is not provided
            if evidence.dataset_row_count is None:
                return ClaimVerificationResult(
                    claim_id=claim.claim_id,
                    claim_type=claim.claim_type,
                    status=VerificationStatus.INSUFFICIENT_EVIDENCE,
                    reason_code="DATASET_TOTAL_UNAVAILABLE",
                    explanation="Dataset total row count is not established in execution evidence.",
                    claimed_value=claim.claimed_count,
                )
            if claim.claimed_count == evidence.dataset_row_count:
                return ClaimVerificationResult(
                    claim_id=claim.claim_id,
                    claim_type=claim.claim_type,
                    status=VerificationStatus.VERIFIED,
                    reason_code="DATASET_ROW_COUNT_VERIFIED",
                    explanation=f"Dataset row count {claim.claimed_count} matches evidence.",
                    expected_value=evidence.dataset_row_count,
                    claimed_value=claim.claimed_count,
                )
            return ClaimVerificationResult(
                claim_id=claim.claim_id,
                claim_type=claim.claim_type,
                status=VerificationStatus.CONTRADICTED,
                reason_code="DATASET_ROW_COUNT_CONTRADICTED",
                explanation=(
                    f"Claimed dataset total {claim.claimed_count}, "
                    f"but evidence is {evidence.dataset_row_count}."
                ),
                expected_value=evidence.dataset_row_count,
                claimed_value=claim.claimed_count,
            )
        else:
            # Query returned row count
            actual_count = len(rows)
            if claim.claimed_count == actual_count:
                return ClaimVerificationResult(
                    claim_id=claim.claim_id,
                    claim_type=claim.claim_type,
                    status=VerificationStatus.VERIFIED,
                    reason_code="RETURNED_ROW_COUNT_VERIFIED",
                    explanation=f"Returned row count {actual_count} matches query output.",
                    expected_value=actual_count,
                    claimed_value=claim.claimed_count,
                )
            return ClaimVerificationResult(
                claim_id=claim.claim_id,
                claim_type=claim.claim_type,
                status=VerificationStatus.CONTRADICTED,
                reason_code="ROW_COUNT_CONTRADICTED",
                explanation=(
                    f"Claim asserted {claim.claimed_count} rows, but query returned {actual_count}."
                ),
                expected_value=actual_count,
                claimed_value=claim.claimed_count,
            )

    def _verify_comparison(
        self,
        claim: ComparisonClaim,
        evidence: ExecutionEvidence,
        columns: list[str],
        rows: list[list[Any]],
    ) -> ClaimVerificationResult:
        left = float(claim.left_value)
        right = float(claim.right_value)

        # Evaluate deterministic relation
        relation_holds = False
        if claim.operator == ">":
            relation_holds = left > right
        elif claim.operator == "<":
            relation_holds = left < right
        elif claim.operator in ("==", "="):
            relation_holds = numbers_match(left, right)
        elif claim.operator == ">=":
            relation_holds = left >= right or numbers_match(left, right)
        elif claim.operator == "<=":
            relation_holds = left <= right or numbers_match(left, right)
        elif claim.operator == "!=":
            relation_holds = not numbers_match(left, right)

        if not relation_holds:
            return ClaimVerificationResult(
                claim_id=claim.claim_id,
                claim_type=claim.claim_type,
                status=VerificationStatus.CONTRADICTED,
                reason_code="COMPARISON_DIRECTION_CONTRADICTED",
                explanation=f"Comparison {left} {claim.operator} {right} is mathematically false.",
                claimed_value=f"{left} {claim.operator} {right}",
            )

        # Also verify that left_value and right_value exist in the evidence
        metric_col_idx = self._find_column_index(claim.metric_name, columns)
        if metric_col_idx is None:
            return ClaimVerificationResult(
                claim_id=claim.claim_id,
                claim_type=claim.claim_type,
                status=VerificationStatus.INSUFFICIENT_EVIDENCE,
                reason_code="METRIC_COLUMN_NOT_IN_RESULT",
                explanation=(f"Metric '{claim.metric_name}' not in query results for operands."),
            )

        col_values = [safe_float(r[metric_col_idx]) for r in rows]
        has_left = any(numbers_match(left, v) for v in col_values if v is not None)
        has_right = any(numbers_match(right, v) for v in col_values if v is not None)

        if not (has_left and has_right):
            return ClaimVerificationResult(
                claim_id=claim.claim_id,
                claim_type=claim.claim_type,
                status=VerificationStatus.CONTRADICTED,
                reason_code="COMPARISON_OPERANDS_UNGROUNDED",
                explanation="Comparison operand values do not exist in the query result rows.",
            )

        return ClaimVerificationResult(
            claim_id=claim.claim_id,
            claim_type=claim.claim_type,
            status=VerificationStatus.VERIFIED,
            reason_code="COMPARISON_VERIFIED",
            explanation=(
                f"Verified: {claim.left_entity} ({left}) "
                f"{claim.operator} {claim.right_entity} ({right})."
            ),
            computed_value=f"{left} {claim.operator} {right}",
        )

    def _verify_difference(
        self,
        claim: DifferenceClaim,
        evidence: ExecutionEvidence,
        columns: list[str],
        rows: list[list[Any]],
    ) -> ClaimVerificationResult:
        # Require 2 evidence references (target and baseline)
        if len(claim.evidence_references) < 2:
            return ClaimVerificationResult(
                claim_id=claim.claim_id,
                claim_type=claim.claim_type,
                status=VerificationStatus.INSUFFICIENT_EVIDENCE,
                reason_code="INSUFFICIENT_REFERENCES",
                explanation="Difference claim requires 2 references (target and baseline).",
                claimed_value=claim.claimed_difference,
            )

        ref_target = claim.evidence_references[0]
        ref_base = claim.evidence_references[1]

        ok1, _, v1 = validate_evidence_reference(ref_target, evidence, columns, rows)
        ok2, _, v2 = validate_evidence_reference(ref_base, evidence, columns, rows)

        if not (ok1 and ok2):
            return ClaimVerificationResult(
                claim_id=claim.claim_id,
                claim_type=claim.claim_type,
                status=VerificationStatus.INVALID_REFERENCE,
                reason_code="INVALID_DIFFERENCE_OPERANDS",
                explanation="Evidence references for difference operands could not be resolved.",
                claimed_value=claim.claimed_difference,
            )

        fv1 = safe_float(v1)
        fv2 = safe_float(v2)
        if fv1 is None or fv2 is None:
            return ClaimVerificationResult(
                claim_id=claim.claim_id,
                claim_type=claim.claim_type,
                status=VerificationStatus.INSUFFICIENT_EVIDENCE,
                reason_code="NON_NUMERIC_OPERANDS",
                explanation="Difference operands are not valid finite numbers.",
            )

        expected_diff = calculate_difference(fv1, fv2, is_absolute=claim.is_absolute)
        claimed_diff = float(claim.claimed_difference)

        if numbers_match(claimed_diff, expected_diff):
            return ClaimVerificationResult(
                claim_id=claim.claim_id,
                claim_type=claim.claim_type,
                status=VerificationStatus.VERIFIED,
                reason_code="DIFFERENCE_VERIFIED",
                explanation=(
                    f"Verified difference between {claim.target_entity} ({fv1}) and "
                    f"{claim.baseline_entity} ({fv2}) is {expected_diff}."
                ),
                expected_value=expected_diff,
                claimed_value=claimed_diff,
                computed_value=expected_diff,
                evidence_references=[ref_target, ref_base],
            )
        else:
            return ClaimVerificationResult(
                claim_id=claim.claim_id,
                claim_type=claim.claim_type,
                status=VerificationStatus.CONTRADICTED,
                reason_code="DIFFERENCE_CALCULATION_MISMATCH",
                explanation=(
                    f"Claimed difference {claimed_diff}, "
                    f"but calculated difference is {expected_diff}."
                ),
                expected_value=expected_diff,
                claimed_value=claimed_diff,
                computed_value=expected_diff,
            )

    def _verify_percentage_change(
        self,
        claim: PercentageChangeClaim,
        evidence: ExecutionEvidence,
        columns: list[str],
        rows: list[list[Any]],
    ) -> ClaimVerificationResult:
        if len(claim.evidence_references) < 2:
            return ClaimVerificationResult(
                claim_id=claim.claim_id,
                claim_type=claim.claim_type,
                status=VerificationStatus.INSUFFICIENT_EVIDENCE,
                reason_code="INSUFFICIENT_REFERENCES",
                explanation="Percentage change requires 2 references (baseline and target).",
                claimed_value=claim.claimed_percent_change,
            )

        ref_base = claim.evidence_references[0]
        ref_target = claim.evidence_references[1]

        ok1, _, v1 = validate_evidence_reference(ref_base, evidence, columns, rows)
        ok2, _, v2 = validate_evidence_reference(ref_target, evidence, columns, rows)

        if not (ok1 and ok2):
            return ClaimVerificationResult(
                claim_id=claim.claim_id,
                claim_type=claim.claim_type,
                status=VerificationStatus.INVALID_REFERENCE,
                reason_code="INVALID_PERCENTAGE_CHANGE_OPERANDS",
                explanation="Evidence references for percentage change could not be resolved.",
                claimed_value=claim.claimed_percent_change,
            )

        f_base = safe_float(v1)
        f_target = safe_float(v2)

        if f_base is None or f_target is None:
            return ClaimVerificationResult(
                claim_id=claim.claim_id,
                claim_type=claim.claim_type,
                status=VerificationStatus.INSUFFICIENT_EVIDENCE,
                reason_code="NON_NUMERIC_OPERANDS",
                explanation="Percentage change operands are non-numeric.",
            )

        if f_base == 0.0:
            return ClaimVerificationResult(
                claim_id=claim.claim_id,
                claim_type=claim.claim_type,
                status=VerificationStatus.UNSUPPORTED,
                reason_code="DIVISION_BY_ZERO",
                explanation="Baseline value is 0.0; percentage change is undefined.",
            )

        expected_pct = calculate_percentage_change(f_base, f_target)
        if expected_pct is None:
            return ClaimVerificationResult(
                claim_id=claim.claim_id,
                claim_type=claim.claim_type,
                status=VerificationStatus.UNSUPPORTED,
                reason_code="UNDEFINED_PERCENTAGE_CHANGE",
                explanation="Calculation produced undefined percentage change.",
            )

        claimed_pct = float(claim.claimed_percent_change)
        if numbers_match(claimed_pct, expected_pct, rel_tol=0.05, abs_tol=0.1):
            return ClaimVerificationResult(
                claim_id=claim.claim_id,
                claim_type=claim.claim_type,
                status=VerificationStatus.VERIFIED,
                reason_code="PERCENTAGE_CHANGE_VERIFIED",
                explanation=(
                    f"Verified percentage change from {f_base} to "
                    f"{f_target} is {expected_pct:.2f}%."
                ),
                expected_value=expected_pct,
                claimed_value=claimed_pct,
                computed_value=expected_pct,
                evidence_references=[ref_base, ref_target],
            )
        else:
            return ClaimVerificationResult(
                claim_id=claim.claim_id,
                claim_type=claim.claim_type,
                status=VerificationStatus.CONTRADICTED,
                reason_code="PERCENTAGE_CHANGE_CONTRADICTED",
                explanation=(
                    f"Claimed change {claimed_pct}%, but calculated change is {expected_pct:.2f}%."
                ),
                expected_value=expected_pct,
                claimed_value=claimed_pct,
                computed_value=expected_pct,
            )

    def _verify_proportion(
        self,
        claim: ProportionClaim,
        evidence: ExecutionEvidence,
        columns: list[str],
        rows: list[list[Any]],
    ) -> ClaimVerificationResult:
        # Check truncation limitation: cannot calculate dataset proportion from truncated rows
        if evidence.truncated:
            return ClaimVerificationResult(
                claim_id=claim.claim_id,
                claim_type=claim.claim_type,
                status=VerificationStatus.INSUFFICIENT_EVIDENCE,
                reason_code="TRUNCATED_POPULATION",
                explanation="Cannot verify proportion from a system-truncated result set.",
                claimed_value=claim.claimed_proportion_pct,
            )

        metric_col_idx = self._find_column_index(claim.metric_name, columns)
        if metric_col_idx is None:
            return ClaimVerificationResult(
                claim_id=claim.claim_id,
                claim_type=claim.claim_type,
                status=VerificationStatus.INVALID_REFERENCE,
                reason_code="UNKNOWN_METRIC_COLUMN",
                explanation=f"Metric '{claim.metric_name}' not in columns.",
                claimed_value=claim.claimed_proportion_pct,
            )

        # Sum total for whole column
        col_vals = [safe_float(r[metric_col_idx]) for r in rows]
        if any(v is None for v in col_vals):
            return ClaimVerificationResult(
                claim_id=claim.claim_id,
                claim_type=claim.claim_type,
                status=VerificationStatus.INSUFFICIENT_EVIDENCE,
                reason_code="NON_NUMERIC_COLUMN_VALUES",
                explanation="Column contains non-numeric values; cannot compute whole.",
            )

        total_sum = sum(v for v in col_vals if v is not None)
        if total_sum == 0.0:
            return ClaimVerificationResult(
                claim_id=claim.claim_id,
                claim_type=claim.claim_type,
                status=VerificationStatus.UNSUPPORTED,
                reason_code="ZERO_TOTAL_SUM",
                explanation="Total sum of metric is 0; proportion is undefined.",
            )

        # Find part value
        # Look for entity across all text/string columns in the row
        part_row: list[Any] | None = None
        for r in rows:
            for cell in r:
                if str(cell).strip().lower() == claim.part_entity.strip().lower():
                    part_row = r
                    break
            if part_row:
                break

        if not part_row:
            return ClaimVerificationResult(
                claim_id=claim.claim_id,
                claim_type=claim.claim_type,
                status=VerificationStatus.CONTRADICTED,
                reason_code="PART_ENTITY_NOT_FOUND",
                explanation=f"Entity '{claim.part_entity}' not found in query results.",
                claimed_value=claim.claimed_proportion_pct,
            )

        part_val = safe_float(part_row[metric_col_idx])
        if part_val is None:
            return ClaimVerificationResult(
                claim_id=claim.claim_id,
                claim_type=claim.claim_type,
                status=VerificationStatus.INSUFFICIENT_EVIDENCE,
                reason_code="PART_VALUE_NOT_NUMERIC",
                explanation="Entity metric value is not numeric.",
            )

        expected_prop = calculate_proportion(part_val, total_sum)
        if expected_prop is None:
            return ClaimVerificationResult(
                claim_id=claim.claim_id,
                claim_type=claim.claim_type,
                status=VerificationStatus.UNSUPPORTED,
                reason_code="UNDEFINED_PROPORTION",
                explanation="Proportion calculation undefined.",
            )

        claimed_prop = float(claim.claimed_proportion_pct)
        if numbers_match(claimed_prop, expected_prop, rel_tol=0.05, abs_tol=0.1):
            return ClaimVerificationResult(
                claim_id=claim.claim_id,
                claim_type=claim.claim_type,
                status=VerificationStatus.VERIFIED,
                reason_code="PROPORTION_VERIFIED",
                explanation=(
                    f"Verified {claim.part_entity} contributes "
                    f"{expected_prop:.2f}% of total ({total_sum})."
                ),
                expected_value=expected_prop,
                claimed_value=claimed_prop,
                computed_value=expected_prop,
            )
        else:
            return ClaimVerificationResult(
                claim_id=claim.claim_id,
                claim_type=claim.claim_type,
                status=VerificationStatus.CONTRADICTED,
                reason_code="PROPORTION_CONTRADICTED",
                explanation=(
                    f"Claimed proportion {claimed_prop}%, but calculated is {expected_prop:.2f}%."
                ),
                expected_value=expected_prop,
                claimed_value=claimed_prop,
                computed_value=expected_prop,
            )

    def _verify_ranking(
        self,
        claim: RankingClaim,
        evidence: ExecutionEvidence,
        columns: list[str],
        rows: list[list[Any]],
    ) -> ClaimVerificationResult:
        if claim.scope_is_global and evidence.truncated:
            return ClaimVerificationResult(
                claim_id=claim.claim_id,
                claim_type=claim.claim_type,
                status=VerificationStatus.INSUFFICIENT_EVIDENCE,
                reason_code="GLOBAL_RANKING_ON_TRUNCATED_RESULT",
                explanation="Cannot assert global ranking from a truncated result set.",
                claimed_value=claim.claimed_rank,
            )

        metric_idx = self._find_column_index(claim.metric_name, columns)
        if metric_idx is None:
            return ClaimVerificationResult(
                claim_id=claim.claim_id,
                claim_type=claim.claim_type,
                status=VerificationStatus.INVALID_REFERENCE,
                reason_code="UNKNOWN_METRIC_COLUMN",
                explanation=f"Metric '{claim.metric_name}' not in columns.",
                claimed_value=claim.claimed_rank,
            )

        # Build list of (entity, metric_val)
        ranked_items: list[tuple[str, float]] = []
        for r in rows:
            val = safe_float(r[metric_idx])
            if val is not None:
                # Entity is first non-metric column or row index
                ent_name = str(r[0]) if len(r) > 1 else f"row_{len(ranked_items)}"
                ranked_items.append((ent_name, val))

        # Sort
        ranked_items.sort(key=lambda x: x[1], reverse=claim.descending)

        # Find target entity rank (1-indexed)
        target_rank = None
        for idx, (ent, _) in enumerate(ranked_items):
            if ent.strip().lower() == claim.entity_name.strip().lower():
                target_rank = idx + 1
                break

        if target_rank is None:
            return ClaimVerificationResult(
                claim_id=claim.claim_id,
                claim_type=claim.claim_type,
                status=VerificationStatus.CONTRADICTED,
                reason_code="RANKING_ENTITY_NOT_FOUND",
                explanation=f"Entity '{claim.entity_name}' not found among ranked result rows.",
                claimed_value=claim.claimed_rank,
            )

        if target_rank == claim.claimed_rank:
            return ClaimVerificationResult(
                claim_id=claim.claim_id,
                claim_type=claim.claim_type,
                status=VerificationStatus.VERIFIED,
                reason_code="RANKING_VERIFIED",
                explanation=(
                    f"Verified {claim.entity_name} ranks #{target_rank} by {claim.metric_name}."
                ),
                expected_value=target_rank,
                claimed_value=claim.claimed_rank,
                computed_value=target_rank,
            )
        else:
            return ClaimVerificationResult(
                claim_id=claim.claim_id,
                claim_type=claim.claim_type,
                status=VerificationStatus.CONTRADICTED,
                reason_code="RANKING_MISMATCH",
                explanation=(
                    f"Claim asserted rank #{claim.claimed_rank}, but actual rank is #{target_rank}."
                ),
                expected_value=target_rank,
                claimed_value=claim.claimed_rank,
                computed_value=target_rank,
            )

    def _verify_extremum(
        self,
        claim: ExtremumClaim,
        evidence: ExecutionEvidence,
        columns: list[str],
        rows: list[list[Any]],
    ) -> ClaimVerificationResult:
        if claim.scope_is_global and evidence.truncated:
            return ClaimVerificationResult(
                claim_id=claim.claim_id,
                claim_type=claim.claim_type,
                status=VerificationStatus.INSUFFICIENT_EVIDENCE,
                reason_code="GLOBAL_EXTREMUM_ON_TRUNCATED_RESULT",
                explanation="Cannot assert global extremum on truncated results.",
                claimed_value=claim.claimed_value,
            )

        metric_idx = self._find_column_index(claim.metric_name, columns)
        if metric_idx is None:
            return ClaimVerificationResult(
                claim_id=claim.claim_id,
                claim_type=claim.claim_type,
                status=VerificationStatus.INVALID_REFERENCE,
                reason_code="UNKNOWN_METRIC_COLUMN",
                explanation=f"Metric '{claim.metric_name}' not in columns.",
            )

        # Find min or max
        best_row: list[Any] | None = None
        best_val: float | None = None

        for r in rows:
            val = safe_float(r[metric_idx])
            if val is not None:
                if best_val is None:
                    best_val = val
                    best_row = r
                elif claim.extremum == ExtremumType.MAXIMUM and val > best_val:
                    best_val = val
                    best_row = r
                elif claim.extremum == ExtremumType.MINIMUM and val < best_val:
                    best_val = val
                    best_row = r

        if best_row is None:
            return ClaimVerificationResult(
                claim_id=claim.claim_id,
                claim_type=claim.claim_type,
                status=VerificationStatus.INSUFFICIENT_EVIDENCE,
                reason_code="NO_NUMERIC_CANDIDATES",
                explanation="No valid numeric rows found to determine extremum.",
            )

        # Check if entity matches best_row
        entity_matches = any(
            str(c).strip().lower() == claim.entity_name.strip().lower() for c in best_row
        )
        if entity_matches:
            return ClaimVerificationResult(
                claim_id=claim.claim_id,
                claim_type=claim.claim_type,
                status=VerificationStatus.VERIFIED,
                reason_code="EXTREMUM_VERIFIED",
                explanation=(
                    f"Verified {claim.entity_name} holds {claim.extremum} "
                    f"{claim.metric_name} ({best_val})."
                ),
                expected_value=best_val,
                claimed_value=claim.claimed_value or best_val,
                computed_value=best_val,
            )
        else:
            return ClaimVerificationResult(
                claim_id=claim.claim_id,
                claim_type=claim.claim_type,
                status=VerificationStatus.CONTRADICTED,
                reason_code="EXTREMUM_CONTRADICTED",
                explanation=(
                    f"Entity '{claim.entity_name}' does not hold "
                    f"{claim.extremum} value ({best_val})."
                ),
                expected_value=best_val,
            )

    def _verify_temporal(
        self,
        claim: TemporalObservationClaim,
        evidence: ExecutionEvidence,
        columns: list[str],
        rows: list[list[Any]],
    ) -> ClaimVerificationResult:
        # Grounding: time period must exist in result rows
        found_time_row: list[Any] | None = None
        for r in rows:
            for cell in r:
                if claim.time_period.strip().lower() in str(cell).strip().lower():
                    found_time_row = r
                    break
            if found_time_row:
                break

        if not found_time_row:
            return ClaimVerificationResult(
                claim_id=claim.claim_id,
                claim_type=claim.claim_type,
                status=VerificationStatus.CONTRADICTED,
                reason_code="TIME_PERIOD_NOT_FOUND",
                explanation=f"Time period '{claim.time_period}' not found in query results.",
                claimed_value=claim.claimed_value,
            )

        metric_idx = self._find_column_index(claim.metric_name, columns)
        if metric_idx is not None:
            actual_val = found_time_row[metric_idx]
            if self._values_equal(claim.claimed_value, actual_val):
                return ClaimVerificationResult(
                    claim_id=claim.claim_id,
                    claim_type=claim.claim_type,
                    status=VerificationStatus.VERIFIED,
                    reason_code="TEMPORAL_OBSERVATION_VERIFIED",
                    explanation=(
                        f"Verified temporal observation for {claim.time_period}: {actual_val}."
                    ),
                    expected_value=actual_val,
                    claimed_value=claim.claimed_value,
                    computed_value=actual_val,
                )
            return ClaimVerificationResult(
                claim_id=claim.claim_id,
                claim_type=claim.claim_type,
                status=VerificationStatus.CONTRADICTED,
                reason_code="TEMPORAL_VALUE_MISMATCH",
                explanation=(
                    f"Time period '{claim.time_period}' has metric value "
                    f"{actual_val}, not {claim.claimed_value}."
                ),
                expected_value=actual_val,
                claimed_value=claim.claimed_value,
            )

        return ClaimVerificationResult(
            claim_id=claim.claim_id,
            claim_type=claim.claim_type,
            status=VerificationStatus.VERIFIED,
            reason_code="TEMPORAL_PERIOD_GROUNDED",
            explanation=f"Time period '{claim.time_period}' verified in query output.",
            expected_value=claim.time_period,
            claimed_value=claim.claimed_value,
        )

    def _verify_missing_values(
        self,
        claim: MissingValueObservationClaim,
        evidence: ExecutionEvidence,
        columns: list[str],
        rows: list[list[Any]],
    ) -> ClaimVerificationResult:
        col_idx = self._find_column_index(claim.column_name, columns)
        if col_idx is None:
            return ClaimVerificationResult(
                claim_id=claim.claim_id,
                claim_type=claim.claim_type,
                status=VerificationStatus.INVALID_REFERENCE,
                reason_code="UNKNOWN_COLUMN",
                explanation=f"Column '{claim.column_name}' not in query results.",
            )

        # Count actual NULLs in rows
        null_count = sum(1 for r in rows if r[col_idx] is None)
        if null_count == claim.missing_count:
            return ClaimVerificationResult(
                claim_id=claim.claim_id,
                claim_type=claim.claim_type,
                status=VerificationStatus.VERIFIED,
                reason_code="MISSING_VALUES_VERIFIED",
                explanation=f"Verified {null_count} missing values in '{claim.column_name}'.",
                expected_value=null_count,
                claimed_value=claim.missing_count,
            )
        else:
            return ClaimVerificationResult(
                claim_id=claim.claim_id,
                claim_type=claim.claim_type,
                status=VerificationStatus.CONTRADICTED,
                reason_code="MISSING_VALUES_COUNT_MISMATCH",
                explanation=(
                    f"Claim asserted {claim.missing_count} missing values, "
                    f"but actual count is {null_count}."
                ),
                expected_value=null_count,
                claimed_value=claim.missing_count,
            )

    def _verify_empty_result(
        self,
        claim: EmptyResultObservationClaim,
        evidence: ExecutionEvidence,
        columns: list[str],
        rows: list[list[Any]],
    ) -> ClaimVerificationResult:
        if len(rows) == 0:
            return ClaimVerificationResult(
                claim_id=claim.claim_id,
                claim_type=claim.claim_type,
                status=VerificationStatus.VERIFIED,
                reason_code="EMPTY_RESULT_VERIFIED",
                explanation="Verified query returned 0 rows matching filter criteria.",
                expected_value=0,
                claimed_value=0,
            )
        return ClaimVerificationResult(
            claim_id=claim.claim_id,
            claim_type=claim.claim_type,
            status=VerificationStatus.CONTRADICTED,
            reason_code="RESULT_NOT_EMPTY",
            explanation=f"Claim asserted empty result, but query returned {len(rows)} rows.",
            expected_value=len(rows),
            claimed_value=0,
        )

    # -------------------------------------------------------------------------
    # Helper utilities
    # -------------------------------------------------------------------------

    def _find_column_index(self, name: str, columns: list[str]) -> int | None:
        target = name.lower().strip()
        for idx, col in enumerate(columns):
            if col.lower().strip() == target:
                return idx
        return None

    def _values_equal(self, a: Any, b: Any) -> bool:
        if a is None or b is None:
            return a is None and b is None
        fa = safe_float(a)
        fb = safe_float(b)
        if fa is not None and fb is not None:
            return numbers_match(fa, fb)
        return str(a).strip().lower() == str(b).strip().lower()
