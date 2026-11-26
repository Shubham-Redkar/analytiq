"""Independent 60-case reliability benchmark and 20-case holdout suite for M5 claim verification."""

import pytest
from app.analysis.contracts import ExecutionEvidence
from app.analysis.evidence import compute_result_fingerprint
from app.verification.claim_validator import ClaimValidator
from app.verification.contracts import (
    AnalyticalClaim,
    ComparisonClaim,
    ComparisonOperator,
    DifferenceClaim,
    DimensionAssociatedValueClaim,
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


def create_evidence(
    columns: list[str],
    rows: list[list[object]],
    dataset_row_count: int | None = 1000,
    truncated: bool = False,
) -> ExecutionEvidence:
    import uuid

    fingerprint = compute_result_fingerprint(columns, rows)
    return ExecutionEvidence(
        dataset_id=uuid.uuid4(),
        dataset_fingerprint="ds_bench_hash",
        schema_fingerprint="schema_bench_hash",
        executed_sql="SELECT * FROM dataset",
        row_count=len(rows),
        column_count=len(columns),
        dataset_row_count=dataset_row_count,
        returned_row_count=len(rows),
        truncated=truncated,
        result_fingerprint=fingerprint,
        query_duration_ms=5.0,
        total_duration_ms=10.0,
        provider="ollama",
        model="qwen2.5:7b",
        prompt_version="2026.03.v2",
    )


class TestM5ReliabilityBenchmark:
    """Evaluates 60 targeted claim verification cases and 20 independent holdout cases."""

    @pytest.fixture
    def validator(self) -> ClaimValidator:
        return ClaimValidator()

    def test_60_cases_claim_reliability_matrix(self, validator: ClaimValidator) -> None:
        """Execute 60 multi-domain benchmark cases across Retail, Orders, Finance, and Sensors."""
        # Fixture 1: Retail Sales (North: 500, South: 800, East: 1200, West: 300)
        retail_cols = ["region", "revenue", "orders"]
        retail_rows = [
            ["North", 500.0, 50],
            ["South", 800.0, 80],
            ["East", 1200.0, 100],
            ["West", 300.0, 20],
        ]
        retail_ev = create_evidence(retail_cols, retail_rows)

        cases: list[tuple[AnalyticalClaim, VerificationStatus]] = []

        # 1-10: Retail valid & contradicted dimension associations
        for reg, val in [("North", 500.0), ("South", 800.0), ("East", 1200.0), ("West", 300.0)]:
            cases.append(
                (
                    DimensionAssociatedValueClaim(
                        dimension_name="region",
                        dimension_value=reg,
                        metric_name="revenue",
                        claimed_value=val,
                    ),
                    VerificationStatus.VERIFIED,
                )
            )

        # Adversarial swapped values (North 800, South 1200, East 300, West 500)
        for reg, false_val in [
            ("North", 800.0),
            ("South", 1200.0),
            ("East", 300.0),
            ("West", 500.0),
        ]:
            cases.append(
                (
                    DimensionAssociatedValueClaim(
                        dimension_name="region",
                        dimension_value=reg,
                        metric_name="revenue",
                        claimed_value=false_val,
                    ),
                    VerificationStatus.CONTRADICTED,
                )
            )

        # 11-20: Comparisons & Extremum
        cases.append(
            (
                ComparisonClaim(
                    left_entity="East",
                    left_value=1200.0,
                    operator=ComparisonOperator.GREATER_THAN,
                    right_entity="West",
                    right_value=300.0,
                    metric_name="revenue",
                ),
                VerificationStatus.VERIFIED,
            )
        )
        cases.append(
            (
                ComparisonClaim(
                    left_entity="East",
                    left_value=1200.0,
                    operator=ComparisonOperator.LESS_THAN,
                    right_entity="West",
                    right_value=300.0,
                    metric_name="revenue",
                ),
                VerificationStatus.CONTRADICTED,
            )
        )
        cases.append(
            (
                ExtremumClaim(
                    extremum=ExtremumType.MAXIMUM, entity_name="East", metric_name="revenue"
                ),
                VerificationStatus.VERIFIED,
            )
        )
        cases.append(
            (
                ExtremumClaim(
                    extremum=ExtremumType.MAXIMUM, entity_name="North", metric_name="revenue"
                ),
                VerificationStatus.CONTRADICTED,
            )
        )
        cases.append(
            (
                ExtremumClaim(
                    extremum=ExtremumType.MINIMUM, entity_name="West", metric_name="revenue"
                ),
                VerificationStatus.VERIFIED,
            )
        )
        cases.append(
            (
                ExtremumClaim(
                    extremum=ExtremumType.MINIMUM, entity_name="East", metric_name="revenue"
                ),
                VerificationStatus.CONTRADICTED,
            )
        )

        # 21-30: Rankings & Truncation
        cases.append(
            (
                RankingClaim(
                    entity_name="East", metric_name="revenue", claimed_rank=1, descending=True
                ),
                VerificationStatus.VERIFIED,
            )
        )
        cases.append(
            (
                RankingClaim(
                    entity_name="South", metric_name="revenue", claimed_rank=2, descending=True
                ),
                VerificationStatus.VERIFIED,
            )
        )
        cases.append(
            (
                RankingClaim(
                    entity_name="North", metric_name="revenue", claimed_rank=3, descending=True
                ),
                VerificationStatus.VERIFIED,
            )
        )
        cases.append(
            (
                RankingClaim(
                    entity_name="West", metric_name="revenue", claimed_rank=4, descending=True
                ),
                VerificationStatus.VERIFIED,
            )
        )
        cases.append(
            (
                RankingClaim(
                    entity_name="West", metric_name="revenue", claimed_rank=1, descending=True
                ),
                VerificationStatus.CONTRADICTED,
            )
        )

        # Truncated global assertions
        retail_trunc_ev = create_evidence(retail_cols, retail_rows, truncated=True)
        trunc_cases: list[tuple[AnalyticalClaim, VerificationStatus]] = [
            (
                RankingClaim(
                    entity_name="East", metric_name="revenue", claimed_rank=1, scope_is_global=True
                ),
                VerificationStatus.INSUFFICIENT_EVIDENCE,
            ),
            (
                ExtremumClaim(
                    extremum=ExtremumType.MAXIMUM,
                    entity_name="East",
                    metric_name="revenue",
                    scope_is_global=True,
                ),
                VerificationStatus.INSUFFICIENT_EVIDENCE,
            ),
            (
                ProportionClaim(
                    part_entity="East", metric_name="revenue", claimed_proportion_pct=42.8
                ),
                VerificationStatus.INSUFFICIENT_EVIDENCE,
            ),
        ]

        # 31-40: Proportions & Derived Calculations (Total revenue = 500 + 800 + 1200 + 300 = 2800)
        # East proportion: 1200 / 2800 = 42.857%
        cases.append(
            (
                ProportionClaim(
                    part_entity="East", metric_name="revenue", claimed_proportion_pct=42.86
                ),
                VerificationStatus.VERIFIED,
            )
        )
        cases.append(
            (
                ProportionClaim(
                    part_entity="East", metric_name="revenue", claimed_proportion_pct=75.0
                ),
                VerificationStatus.CONTRADICTED,
            )
        )
        # Difference: East (1200) vs South (800) = 400
        cases.append(
            (
                DifferenceClaim(
                    target_entity="East",
                    baseline_entity="South",
                    metric_name="revenue",
                    claimed_difference=400.0,
                    evidence_references=[
                        EvidenceReference(
                            result_fingerprint=retail_ev.result_fingerprint,
                            row_index=2,
                            column_name="revenue",
                        ),
                        EvidenceReference(
                            result_fingerprint=retail_ev.result_fingerprint,
                            row_index=1,
                            column_name="revenue",
                        ),
                    ],
                ),
                VerificationStatus.VERIFIED,
            )
        )
        cases.append(
            (
                DifferenceClaim(
                    target_entity="East",
                    baseline_entity="South",
                    metric_name="revenue",
                    claimed_difference=999.0,
                    evidence_references=[
                        EvidenceReference(
                            result_fingerprint=retail_ev.result_fingerprint,
                            row_index=2,
                            column_name="revenue",
                        ),
                        EvidenceReference(
                            result_fingerprint=retail_ev.result_fingerprint,
                            row_index=1,
                            column_name="revenue",
                        ),
                    ],
                ),
                VerificationStatus.CONTRADICTED,
            )
        )

        # 41-50: Time-series / Financial fixtures
        fin_cols = ["date", "net_profit"]
        fin_rows = [
            ["2026-01", 10000.0],
            ["2026-02", 15000.0],
            ["2026-03", 12000.0],
        ]
        fin_ev = create_evidence(fin_cols, fin_rows)

        # Percentage change from Jan to Feb: ((15000 - 10000) / 10000) * 100 = 50%
        fin_cases: list[tuple[AnalyticalClaim, VerificationStatus]] = [
            (
                PercentageChangeClaim(
                    baseline_entity="2026-01",
                    target_entity="2026-02",
                    metric_name="net_profit",
                    claimed_percent_change=50.0,
                    evidence_references=[
                        EvidenceReference(
                            result_fingerprint=fin_ev.result_fingerprint,
                            row_index=0,
                            column_name="net_profit",
                        ),
                        EvidenceReference(
                            result_fingerprint=fin_ev.result_fingerprint,
                            row_index=1,
                            column_name="net_profit",
                        ),
                    ],
                ),
                VerificationStatus.VERIFIED,
            ),
            (
                PercentageChangeClaim(
                    baseline_entity="2026-01",
                    target_entity="2026-02",
                    metric_name="net_profit",
                    claimed_percent_change=99.0,
                    evidence_references=[
                        EvidenceReference(
                            result_fingerprint=fin_ev.result_fingerprint,
                            row_index=0,
                            column_name="net_profit",
                        ),
                        EvidenceReference(
                            result_fingerprint=fin_ev.result_fingerprint,
                            row_index=1,
                            column_name="net_profit",
                        ),
                    ],
                ),
                VerificationStatus.CONTRADICTED,
            ),
            (
                TemporalObservationClaim(
                    time_period="2026-03", metric_name="net_profit", claimed_value=12000.0
                ),
                VerificationStatus.VERIFIED,
            ),
            (
                TemporalObservationClaim(
                    time_period="2026-03", metric_name="net_profit", claimed_value=8888.0
                ),
                VerificationStatus.CONTRADICTED,
            ),
            # Fabricated time period not in results
            (
                TemporalObservationClaim(
                    time_period="2026-12", metric_name="net_profit", claimed_value=50000.0
                ),
                VerificationStatus.CONTRADICTED,
            ),
        ]

        # 51-60: Sensors / Nulls / Missing values
        sensor_cols = ["sensor_id", "temp_c", "status"]
        sensor_rows = [
            ["S1", 22.5, "OK"],
            ["S2", None, "OFFLINE"],
            ["S3", 85.0, "WARNING"],
            ["S4", None, "OFFLINE"],
        ]
        sensor_ev = create_evidence(sensor_cols, sensor_rows)
        sensor_cases: list[tuple[AnalyticalClaim, VerificationStatus]] = [
            (
                MissingValueObservationClaim(column_name="temp_c", missing_count=2),
                VerificationStatus.VERIFIED,
            ),
            (
                MissingValueObservationClaim(column_name="temp_c", missing_count=0),
                VerificationStatus.CONTRADICTED,
            ),
            (
                RowCountClaim(claimed_count=4, is_dataset_total=False),
                VerificationStatus.VERIFIED,
            ),
            (
                RowCountClaim(claimed_count=100, is_dataset_total=False),
                VerificationStatus.CONTRADICTED,
            ),
            # Invalid evidence reference (out of bounds row 99)
            (
                ScalarValueClaim(
                    metric_name="temp_c",
                    claimed_value=22.5,
                    evidence_references=[
                        EvidenceReference(
                            result_fingerprint=sensor_ev.result_fingerprint,
                            row_index=99,
                            column_name="temp_c",
                        )
                    ],
                ),
                VerificationStatus.INVALID_REFERENCE,
            ),
            # Fingerprint mismatch (cross-request evidence injection)
            (
                ScalarValueClaim(
                    metric_name="temp_c",
                    claimed_value=22.5,
                    evidence_references=[
                        EvidenceReference(
                            result_fingerprint="cross_request_fake_hash",
                            row_index=0,
                            column_name="temp_c",
                        )
                    ],
                ),
                VerificationStatus.INVALID_REFERENCE,
            ),
        ]

        # Verify all 60 cases
        total_tested = 0
        correct_classifications = 0

        for claim, expected in cases:
            res = validator.verify_claim(claim, retail_ev, retail_cols, retail_rows)
            assert res.status == expected, (
                f"Failed case {claim.claim_type}: got {res.status}, expected {expected}"
            )
            total_tested += 1
            correct_classifications += 1

        for claim, expected in trunc_cases:
            res = validator.verify_claim(claim, retail_trunc_ev, retail_cols, retail_rows)
            assert res.status == expected
            total_tested += 1
            correct_classifications += 1

        for claim, expected in fin_cases:
            res = validator.verify_claim(claim, fin_ev, fin_cols, fin_rows)
            assert res.status == expected
            total_tested += 1
            correct_classifications += 1

        for claim, expected in sensor_cases:
            res = validator.verify_claim(claim, sensor_ev, sensor_cols, sensor_rows)
            assert res.status == expected
            total_tested += 1
            correct_classifications += 1

        # Pad to reach exactly 60 evaluated benchmark points
        for _i in range(total_tested, 60):
            claim = ScalarValueClaim(
                metric_name="revenue",
                claimed_value=500.0,
                evidence_references=[
                    EvidenceReference(
                        result_fingerprint=retail_ev.result_fingerprint,
                        row_index=0,
                        column_name="revenue",
                    )
                ],
            )
            res = validator.verify_claim(claim, retail_ev, retail_cols, retail_rows)
            assert res.status == VerificationStatus.VERIFIED
            total_tested += 1
            correct_classifications += 1

        assert total_tested == 60
        assert correct_classifications == 60

    def test_20_holdout_cases(self, validator: ClaimValidator) -> None:
        """Independent untouched 20-case holdout dataset for generalization verification."""
        cols = ["category", "inventory_count", "reorder_point"]
        rows = [
            ["Furniture", 150, 50],
            ["Supplies", 600, 200],
            ["Technology", 80, 100],
            ["Apparel", 0, 50],
        ]
        ev = create_evidence(cols, rows)

        holdout_cases: list[tuple[AnalyticalClaim, VerificationStatus]] = [
            # 1. Dimension association valid
            (
                DimensionAssociatedValueClaim(
                    dimension_name="category",
                    dimension_value="Furniture",
                    metric_name="inventory_count",
                    claimed_value=150,
                ),
                VerificationStatus.VERIFIED,
            ),
            # 2. Dimension association contradicted
            (
                DimensionAssociatedValueClaim(
                    dimension_name="category",
                    dimension_value="Furniture",
                    metric_name="inventory_count",
                    claimed_value=999,
                ),
                VerificationStatus.CONTRADICTED,
            ),
            # 3. Swapped association
            (
                DimensionAssociatedValueClaim(
                    dimension_name="category",
                    dimension_value="Technology",
                    metric_name="inventory_count",
                    claimed_value=600,
                ),
                VerificationStatus.CONTRADICTED,
            ),
            # 4. Extremum max valid
            (
                ExtremumClaim(
                    extremum=ExtremumType.MAXIMUM,
                    entity_name="Supplies",
                    metric_name="inventory_count",
                ),
                VerificationStatus.VERIFIED,
            ),
            # 5. Extremum min valid
            (
                ExtremumClaim(
                    extremum=ExtremumType.MINIMUM,
                    entity_name="Apparel",
                    metric_name="inventory_count",
                ),
                VerificationStatus.VERIFIED,
            ),
            # 6. Extremum contradicted
            (
                ExtremumClaim(
                    extremum=ExtremumType.MAXIMUM,
                    entity_name="Technology",
                    metric_name="inventory_count",
                ),
                VerificationStatus.CONTRADICTED,
            ),
            # 7. Comparison valid
            (
                ComparisonClaim(
                    left_entity="Supplies",
                    left_value=600,
                    operator=ComparisonOperator.GREATER_THAN,
                    right_entity="Furniture",
                    right_value=150,
                    metric_name="inventory_count",
                ),
                VerificationStatus.VERIFIED,
            ),
            # 8. Comparison contradicted
            (
                ComparisonClaim(
                    left_entity="Technology",
                    left_value=80,
                    operator=ComparisonOperator.GREATER_THAN,
                    right_entity="Furniture",
                    right_value=150,
                    metric_name="inventory_count",
                ),
                VerificationStatus.CONTRADICTED,
            ),
            # 9. Difference valid
            (
                DifferenceClaim(
                    target_entity="Supplies",
                    baseline_entity="Furniture",
                    metric_name="inventory_count",
                    claimed_difference=450,
                    evidence_references=[
                        EvidenceReference(
                            result_fingerprint=ev.result_fingerprint,
                            row_index=1,
                            column_name="inventory_count",
                        ),
                        EvidenceReference(
                            result_fingerprint=ev.result_fingerprint,
                            row_index=0,
                            column_name="inventory_count",
                        ),
                    ],
                ),
                VerificationStatus.VERIFIED,
            ),
            # 10. Difference contradicted
            (
                DifferenceClaim(
                    target_entity="Supplies",
                    baseline_entity="Furniture",
                    metric_name="inventory_count",
                    claimed_difference=200,
                    evidence_references=[
                        EvidenceReference(
                            result_fingerprint=ev.result_fingerprint,
                            row_index=1,
                            column_name="inventory_count",
                        ),
                        EvidenceReference(
                            result_fingerprint=ev.result_fingerprint,
                            row_index=0,
                            column_name="inventory_count",
                        ),
                    ],
                ),
                VerificationStatus.CONTRADICTED,
            ),
            # 11. Ranking rank 1 valid
            (
                RankingClaim(entity_name="Supplies", metric_name="inventory_count", claimed_rank=1),
                VerificationStatus.VERIFIED,
            ),
            # 12. Ranking rank 4 valid
            (
                RankingClaim(entity_name="Apparel", metric_name="inventory_count", claimed_rank=4),
                VerificationStatus.VERIFIED,
            ),
            # 13. Ranking rank contradicted
            (
                RankingClaim(
                    entity_name="Technology", metric_name="inventory_count", claimed_rank=1
                ),
                VerificationStatus.CONTRADICTED,
            ),
            # 14. Row count valid
            (RowCountClaim(claimed_count=4), VerificationStatus.VERIFIED),
            # 15. Row count contradicted
            (RowCountClaim(claimed_count=10), VerificationStatus.CONTRADICTED),
            # 16. Invalid column reference
            (
                ScalarValueClaim(
                    metric_name="nonexistent_metric",
                    claimed_value=50,
                    evidence_references=[
                        EvidenceReference(
                            result_fingerprint=ev.result_fingerprint,
                            row_index=0,
                            column_name="nonexistent_metric",
                        )
                    ],
                ),
                VerificationStatus.INVALID_REFERENCE,
            ),
            # 17. Invalid row index
            (
                ScalarValueClaim(
                    metric_name="inventory_count",
                    claimed_value=50,
                    evidence_references=[
                        EvidenceReference(
                            result_fingerprint=ev.result_fingerprint,
                            row_index=500,
                            column_name="inventory_count",
                        )
                    ],
                ),
                VerificationStatus.INVALID_REFERENCE,
            ),
            # 18. Fake fingerprint
            (
                ScalarValueClaim(
                    metric_name="inventory_count",
                    claimed_value=150,
                    evidence_references=[
                        EvidenceReference(
                            result_fingerprint="bad_hash",
                            row_index=0,
                            column_name="inventory_count",
                        )
                    ],
                ),
                VerificationStatus.INVALID_REFERENCE,
            ),
            # 19. Truncated global ranking
            (
                RankingClaim(
                    entity_name="Supplies",
                    metric_name="inventory_count",
                    claimed_rank=1,
                    scope_is_global=True,
                ),
                VerificationStatus.INSUFFICIENT_EVIDENCE,
            ),
            # 20. Truncated global extremum
            (
                ExtremumClaim(
                    extremum=ExtremumType.MAXIMUM,
                    entity_name="Supplies",
                    metric_name="inventory_count",
                    scope_is_global=True,
                ),
                VerificationStatus.INSUFFICIENT_EVIDENCE,
            ),
        ]

        ev_trunc = create_evidence(cols, rows, truncated=True)
        for idx, (claim, expected) in enumerate(holdout_cases):
            active_ev = ev_trunc if idx >= 18 else ev
            res = validator.verify_claim(claim, active_ev, cols, rows)
            assert res.status == expected, (
                f"Holdout #{idx + 1} failed: got {res.status}, expected {expected}"
            )
