"""Independent test suite for schema grounding and clarification generalization.

Verifies at least 12 distinct questions beyond benchmark keywords:
- Ambiguous questions (averages, rankings, missing dimensions/metrics, time grains)
  must trigger needs_clarification with grounded questions.
- Explicit, fully grounded analytical questions must NOT trigger clarification.
"""

import pytest
from app.analysis.contracts import ColumnContext, DatasetAnalyticalContext
from app.orchestration.contracts import ClarificationType
from app.orchestration.grounding import ground_question_in_schema


@pytest.fixture
def ecommerce_context() -> DatasetAnalyticalContext:
    """Standard analytical context for an e-commerce orders dataset."""
    return DatasetAnalyticalContext(
        relation_name="dataset",
        dataset_name="online_retail_orders",
        row_count=50000,
        column_count=9,
        columns=[
            ColumnContext(
                name="order_id",
                physical_type="int64",
                logical_type="dimension",
                nullable=False,
            ),
            ColumnContext(
                name="customer_id",
                physical_type="varchar",
                logical_type="dimension",
                nullable=False,
            ),
            ColumnContext(
                name="region",
                physical_type="varchar",
                logical_type="dimension",
                nullable=False,
            ),
            ColumnContext(
                name="category",
                physical_type="varchar",
                logical_type="dimension",
                nullable=False,
            ),
            ColumnContext(
                name="quantity",
                physical_type="int32",
                logical_type="metric",
                nullable=False,
            ),
            ColumnContext(
                name="unit_price",
                physical_type="float64",
                logical_type="metric",
                nullable=False,
            ),
            ColumnContext(
                name="revenue",
                physical_type="float64",
                logical_type="metric",
                nullable=False,
            ),
            ColumnContext(
                name="discount",
                physical_type="float64",
                logical_type="metric",
                nullable=True,
            ),
            ColumnContext(
                name="order_date",
                physical_type="date",
                logical_type="dimension",
                nullable=False,
            ),
        ],
    )


@pytest.fixture
def flat_sensor_context() -> DatasetAnalyticalContext:
    """Sensor readings dataset without any date/time column."""
    return DatasetAnalyticalContext(
        relation_name="dataset",
        dataset_name="iot_sensor_snapshots",
        row_count=10000,
        column_count=4,
        columns=[
            ColumnContext(
                name="sensor_id",
                physical_type="varchar",
                logical_type="dimension",
                nullable=False,
            ),
            ColumnContext(
                name="location",
                physical_type="varchar",
                logical_type="dimension",
                nullable=False,
            ),
            ColumnContext(
                name="temperature",
                physical_type="float64",
                logical_type="metric",
                nullable=False,
            ),
            ColumnContext(
                name="pressure",
                physical_type="float64",
                logical_type="metric",
                nullable=False,
            ),
        ],
    )


class TestClarificationGeneralization:
    """Verifies that the grounding agent accurately discriminates ambiguity."""

    # -------------------------------------------------------------
    # 1. Ambiguous: Paraphrased Bare Averages
    # -------------------------------------------------------------
    @pytest.mark.parametrize(
        "q",
        [
            "Can you tell me the mean across this entire dataset?",
            "What is the overall average?",
            "Please compute the average for these records",
            "Give me the average value",
        ],
    )
    def test_paraphrased_bare_averages_trigger_clarification(
        self, ecommerce_context: DatasetAnalyticalContext, q: str
    ) -> None:
        result = ground_question_in_schema(q, ecommerce_context)
        assert result["ambiguity_detected"] is True
        assert result["is_grounded"] is False
        assert result["ambiguity_type"] == ClarificationType.MISSING_TARGET_METRIC.value
        assert "revenue" in result["candidate_metrics"]
        assert result["suggested_clarification"] is not None

    # -------------------------------------------------------------
    # 2. Ambiguous: Subjective Rankings Without Criteria
    # -------------------------------------------------------------
    @pytest.mark.parametrize(
        "q",
        [
            "Which are the worst performing regions?",
            "Show me our top performing categories",
            "Identify the most successful customer segments",
            "What are the best items in this catalog?",
        ],
    )
    def test_subjective_rankings_trigger_clarification(
        self, ecommerce_context: DatasetAnalyticalContext, q: str
    ) -> None:
        result = ground_question_in_schema(q, ecommerce_context)
        assert result["ambiguity_detected"] is True
        assert result["is_grounded"] is False
        assert result["ambiguity_type"] == ClarificationType.SUBJECTIVE_RANKING.value
        assert result["suggested_clarification"] is not None
        clar_text = result["suggested_clarification"]
        assert "revenue" in clar_text or "quantity" in clar_text

    # -------------------------------------------------------------
    # 3. Ambiguous: Trends Without Granularity or Without Dates
    # -------------------------------------------------------------
    def test_trend_without_date_column_detected(
        self, flat_sensor_context: DatasetAnalyticalContext
    ) -> None:
        result = ground_question_in_schema(
            "Show me the trend of temperature readings",
            flat_sensor_context,
        )
        assert result["ambiguity_detected"] is True
        assert result["is_grounded"] is False
        assert result["ambiguity_type"] == ClarificationType.MISSING_TIME_GRAIN.value
        assert result["ambiguity_reason"] is not None
        assert "no date column" in result["ambiguity_reason"].lower()

    def test_trend_with_date_but_no_grain_detected(
        self, ecommerce_context: DatasetAnalyticalContext
    ) -> None:
        result = ground_question_in_schema(
            "What is the revenue growth rate over time?",
            ecommerce_context,
        )
        assert result["ambiguity_detected"] is True
        assert result["is_grounded"] is False
        assert result["ambiguity_type"] == ClarificationType.MISSING_TIME_GRAIN.value
        assert result["suggested_clarification"] is not None
        assert "granularity" in result["suggested_clarification"].lower()

    # -------------------------------------------------------------
    # 4. Ambiguous: Unavailable / Missing Metrics (Profit/Margin)
    # -------------------------------------------------------------
    @pytest.mark.parametrize(
        "q",
        [
            "Which region has the highest profit margin?",
            "Show me total profit by product category",
            "Who is our most profitable customer?",
        ],
    )
    def test_missing_profit_metric_suggests_alternatives(
        self, ecommerce_context: DatasetAnalyticalContext, q: str
    ) -> None:
        result = ground_question_in_schema(q, ecommerce_context)
        assert result["ambiguity_detected"] is True
        assert result["is_grounded"] is False
        assert result["ambiguity_type"] == ClarificationType.UNAVAILABLE_METRIC.value
        assert "profit" in result["missing_columns"]
        # Must suggest existing alternate metrics like revenue
        assert result["suggested_clarification"] is not None
        assert "revenue" in result["suggested_clarification"]

    # -------------------------------------------------------------
    # 5. Explicit Analytical Questions MUST NOT Trigger Clarification
    # -------------------------------------------------------------
    @pytest.mark.parametrize(
        "q",
        [
            "What is the average revenue for East region?",
            "What is the total quantity of items sold?",
            "Show the top 5 customers ordered by total revenue descending",
            "Calculate average discount across each product category",
            "Count distinct customer IDs who placed orders in 2026",
            "What is the average unit price for electronics?",
        ],
    )
    def test_explicit_grounded_queries_do_not_clarify(
        self, ecommerce_context: DatasetAnalyticalContext, q: str
    ) -> None:
        result = ground_question_in_schema(q, ecommerce_context)
        assert result["is_grounded"] is True
        assert result["ambiguity_detected"] is False
        assert result["ambiguity_type"] is None
        assert result["suggested_clarification"] is None
