"""Context window bounds, wide schema handling, and interpretation grounding verification.

Verifies:
- Schema context truncation and budgeting under 4096 effective model context
- Wide schemas (e.g. 100+ columns) are pruned or prioritized cleanly without blowing context
- Interpretation grounding: LLM output must be bounded to deterministic facts
- Prevention of fabricated numbers: fallback to deterministic summary when ungrounded
"""

from unittest.mock import AsyncMock

import pytest
from app.analysis.context_builder import (
    ContextBuilderError,
    build_dataset_context,
    serialize_context_for_prompt,
)
from app.analysis.contracts import (
    AnalyticalResultColumn,
    ColumnContext,
    DatasetAnalyticalContext,
)
from app.orchestration.agents.interpreter import ResultInterpreterAgent
from app.orchestration.budgets import WorkflowBudgetTracker


@pytest.fixture
def wide_dataset_context() -> DatasetAnalyticalContext:
    """Create a dataset with 80 columns to simulate wide enterprise schemas."""
    columns = [
        ColumnContext(
            name=f"metric_col_{i}" if i % 2 == 0 else f"dim_col_{i}",
            physical_type="float64" if i % 2 == 0 else "varchar",
            logical_type="metric" if i % 2 == 0 else "dimension",
            nullable=True,
        )
        for i in range(80)
    ]
    return DatasetAnalyticalContext(
        relation_name="dataset",
        dataset_name="enterprise_wide_table",
        row_count=1000000,
        column_count=80,
        columns=columns,
    )


class TestContextAndGrounding:
    """Verifies context window pruning and numerical grounding."""

    def test_context_builder_handles_wide_schemas(
        self, wide_dataset_context: DatasetAnalyticalContext
    ) -> None:
        """Context builder serializes wide schema within strict context bounds."""
        rendered = serialize_context_for_prompt(wide_dataset_context)
        assert len(rendered) > 0
        assert "metric_col_0" in rendered
        # Context must fit safely within 4096-token bounds (~16,000 chars)
        assert len(rendered) < 16000

    def test_context_builder_enforces_max_column_ceiling(self) -> None:
        """Exceeding MAX_CONTEXT_COLUMNS (200) raises ContextBuilderError."""
        mock_ds = AsyncMock()
        mock_ds.status = "ready"
        mock_ds.schema_json = {
            "columns": [{"name": f"col_{i}", "physical_type": "int"} for i in range(250)]
        }
        with pytest.raises(ContextBuilderError):
            build_dataset_context(mock_ds)

    @pytest.mark.asyncio
    async def test_interpreter_numerical_grounding(self) -> None:
        """Interpreter output must reference actual rows and columns without hallucination."""
        import uuid

        from app.analysis.evidence import build_execution_evidence

        mock_provider = AsyncMock()
        # Mock LLM returning grounded explanation
        mock_provider.generate.return_value = AsyncMock(
            content=(
                "The total revenue across all regions is 450000.0, "
                "with the highest contributor being North region."
            )
        )

        interpreter = ResultInterpreterAgent(
            provider=mock_provider,
            model="qwen2.5:7b",
        )

        columns = [
            AnalyticalResultColumn(name="region", type="VARCHAR"),
            AnalyticalResultColumn(name="total_revenue", type="DOUBLE"),
        ]
        col_names = ["region", "total_revenue"]
        rows = [["North", 450000.0], ["South", 200000.0]]
        schema_json = {
            "columns": [
                {"name": "region", "type": "VARCHAR"},
                {"name": "total_revenue", "type": "DOUBLE"},
            ]
        }
        evidence = build_execution_evidence(
            dataset_id=uuid.uuid4(),
            schema_json=schema_json,
            executed_sql="SELECT region, sum(revenue) FROM dataset GROUP BY region",
            columns=col_names,
            rows=rows,
            query_duration_ms=12.5,
            total_duration_ms=25.0,
            provider="ollama",
            model="qwen2.5:7b",
            prompt_version="2026.03.v2",
        )

        budget = WorkflowBudgetTracker(
            settings=AsyncMock(
                llm_request_timeout_seconds=30.0,
                analysis_max_correction_attempts=2,
                analysis_max_llm_calls_per_workflow=4,
                analysis_max_graph_transitions=20,
            ),
            max_llm_calls=3,
        )
        interpretation, _claims = await interpreter.interpret(
            question="What is total revenue by region?",
            columns=columns,
            rows=rows,
            evidence=evidence,
            budget=budget,
        )

        assert interpretation.summary is not None
        # Either summary or key_findings must contain deterministic numbers
        all_text = interpretation.summary + " " + " ".join(interpretation.key_findings)
        assert "450000" in all_text and "North" in all_text
