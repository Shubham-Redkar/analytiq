"""Comprehensive integration and unit tests for M4 LangGraph Multi-Agent Orchestration."""

import io
import uuid
from pathlib import Path

import httpx
import pytest
from app.analysis.contracts import ColumnContext, DatasetAnalyticalContext
from app.api.v1.analysis import get_llm_provider
from app.core.config import Settings
from app.llm.providers.mock import MockLLMProvider
from app.main import app
from app.models.dataset import Dataset
from app.orchestration.agents.clarification import ClarificationAgent
from app.orchestration.agents.supervisor import SupervisorAgent
from app.orchestration.contracts import (
    ClarificationType,
    IntentCategory,
    OrchestrationStatus,
)
from app.orchestration.grounding import ground_question_in_schema
from app.orchestration.service import OrchestrationService
from app.orchestration.state import GroundingAnalysis
from app.services.storage import StorageService

from tests.test_datasets import register_and_login


class TestSchemaGroundingAndAmbiguity:
    """Verify deterministic schema grounding and ambiguity detection."""

    @pytest.fixture
    def sample_context(self) -> DatasetAnalyticalContext:
        return DatasetAnalyticalContext(
            dataset_name="sales_dataset",
            row_count=1000,
            column_count=4,
            columns=[
                ColumnContext(name="order_id", physical_type="BIGINT", logical_type="integer"),
                ColumnContext(
                    name="order_date", physical_type="TIMESTAMP", logical_type="datetime"
                ),
                ColumnContext(name="revenue", physical_type="DOUBLE", logical_type="float"),
                ColumnContext(
                    name="customer_category", physical_type="VARCHAR", logical_type="string"
                ),
            ],
        )

    def test_bare_average_ambiguity_detected(
        self, sample_context: DatasetAnalyticalContext
    ) -> None:
        grounding = ground_question_in_schema(
            "What is the average for this dataset?", sample_context
        )
        assert grounding["ambiguity_detected"] is True
        assert grounding["ambiguity_type"] == ClarificationType.MISSING_TARGET_METRIC.value
        assert "revenue" in (grounding.get("candidate_metrics") or [])

    def test_subjective_ranking_ambiguity_detected(
        self, sample_context: DatasetAnalyticalContext
    ) -> None:
        grounding = ground_question_in_schema("Show me the best orders", sample_context)
        assert grounding["ambiguity_detected"] is True
        assert grounding["ambiguity_type"] == ClarificationType.SUBJECTIVE_RANKING.value

    def test_grounded_ranking_accepted(self, sample_context: DatasetAnalyticalContext) -> None:
        grounding = ground_question_in_schema("Show me the best orders by revenue", sample_context)
        assert grounding["ambiguity_detected"] is False

    def test_missing_time_grain_ambiguity_detected(
        self, sample_context: DatasetAnalyticalContext
    ) -> None:
        grounding = ground_question_in_schema(
            "What is the trend of revenue over time?", sample_context
        )
        assert grounding["ambiguity_detected"] is True
        assert grounding["ambiguity_type"] == ClarificationType.MISSING_TIME_GRAIN.value

    def test_missing_profit_metric_ambiguity_detected(
        self, sample_context: DatasetAnalyticalContext
    ) -> None:
        grounding = ground_question_in_schema(
            "Who is the most profitable customer?", sample_context
        )
        assert grounding["ambiguity_detected"] is True
        assert grounding["ambiguity_type"] == ClarificationType.UNAVAILABLE_METRIC.value
        assert "profit" in (grounding.get("missing_columns") or [])


class TestClarificationAgent:
    """Verify ClarificationAgent creates structured actionable options."""

    def test_clarification_agent_options(self) -> None:
        agent = ClarificationAgent()
        ctx = DatasetAnalyticalContext(
            dataset_name="test",
            row_count=100,
            column_count=2,
            columns=[
                ColumnContext(name="price", physical_type="DOUBLE", logical_type="float"),
                ColumnContext(name="qty", physical_type="INTEGER", logical_type="integer"),
            ],
        )
        grounding = GroundingAnalysis(
            is_grounded=False,
            ambiguity_detected=True,
            ambiguity_type=ClarificationType.MISSING_TARGET_METRIC.value,
            ambiguity_reason="Metric missing",
            referenced_columns=[],
            missing_columns=[],
            candidate_metrics=["price", "qty"],
            candidate_dimensions=[],
            suggested_clarification="Specify metric",
        )
        res = agent.formulate_clarification("average?", ctx, grounding)
        assert res.clarification_type == ClarificationType.MISSING_TARGET_METRIC
        assert len(res.options) == 2
        assert res.options[0].suggested_column == "price"


class TestSupervisorSafety:
    """Verify Supervisor deterministic safety filtering."""

    def test_mutation_prohibited(self) -> None:
        provider = MockLLMProvider()
        supervisor = SupervisorAgent(provider=provider, model="mock")
        intent, reason = supervisor.check_deterministic_safety("DROP TABLE dataset")
        assert intent == IntentCategory.PROHIBITED
        assert reason is not None

    def test_delete_prohibited(self) -> None:
        provider = MockLLMProvider()
        supervisor = SupervisorAgent(provider=provider, model="mock")
        intent, _reason = supervisor.check_deterministic_safety(
            "DELETE FROM dataset WHERE order_id > 1"
        )
        assert intent == IntentCategory.PROHIBITED

    def test_unsupported_forecast(self) -> None:
        provider = MockLLMProvider()
        supervisor = SupervisorAgent(provider=provider, model="mock")
        intent, _reason = supervisor.check_deterministic_safety("Forecast revenue for next year")
        assert intent == IntentCategory.UNSUPPORTED


class TestEndToEndWorkflow:
    """Verify complete LangGraph multi-agent execution with mock provider."""

    @pytest.mark.asyncio
    async def test_workflow_successful_execution(self, tmp_path: Path) -> None:
        import pyarrow as pa
        import pyarrow.parquet as pq

        dataset_id = uuid.uuid4()
        table = pa.Table.from_pydict({"val": [10, 20, 30], "cat": ["a", "b", "c"]})
        # Create the standard parquet file structure expected by StorageService
        parquet_dir = tmp_path / "parquet" / str(dataset_id)
        parquet_dir.mkdir(parents=True, exist_ok=True)
        parquet_file = parquet_dir / "data.parquet"
        pq.write_table(table, parquet_file)

        mock_plan = {
            "status": "ready",
            "intent": "Calculate sum of val",
            "operation": "aggregation",
            "referenced_columns": ["val"],
            "sql": "SELECT SUM(val) AS total_val FROM dataset",
            "assumptions": [],
        }

        mock_provider = MockLLMProvider(canned_responses=[mock_plan])
        storage = StorageService(root_path=tmp_path)
        settings = Settings()

        svc = OrchestrationService(
            llm_provider=mock_provider,
            settings=settings,
            storage_svc=storage,
        )

        dataset = Dataset(
            id=dataset_id,
            owner_id=uuid.uuid4(),
            name="test_dataset",
            original_filename="test.parquet",
            file_format="parquet",
            file_size_bytes=1000,
            storage_key=str(parquet_file),
            status="ready",
            row_count=3,
            column_count=2,
            schema_json={
                "columns": [
                    {
                        "name": "val",
                        "type": "INTEGER",
                        "physical_type": "INTEGER",
                        "logical_type": "integer",
                        "nullable": True,
                    },
                    {
                        "name": "cat",
                        "type": "VARCHAR",
                        "physical_type": "VARCHAR",
                        "logical_type": "string",
                        "nullable": True,
                    },
                ]
            },
        )

        res = await svc.execute_workflow(
            dataset=dataset,
            question="Calculate total sum of val",
            user_id=dataset.owner_id,
        )

        assert res.status == OrchestrationStatus.COMPLETED
        assert "SELECT SUM(val) AS total_val FROM dataset" in (res.executed_sql or "")
        assert res.rows == [[60]]
        assert len(res.trace_events) >= 5
        assert res.interpretation is not None
        assert res.evidence is not None

    @pytest.mark.asyncio
    async def test_workflow_clarification_flow(self, tmp_path: Path) -> None:
        import pyarrow as pa
        import pyarrow.parquet as pq

        dataset_id = uuid.uuid4()
        table = pa.Table.from_pydict({"val": [10, 20], "cat": ["a", "b"]})
        # Create the standard parquet file structure expected by StorageService
        parquet_dir = tmp_path / "parquet" / str(dataset_id)
        parquet_dir.mkdir(parents=True, exist_ok=True)
        parquet_file = parquet_dir / "data.parquet"
        pq.write_table(table, parquet_file)

        mock_provider = MockLLMProvider()
        storage = StorageService(root_path=tmp_path)
        settings = Settings()

        svc = OrchestrationService(
            llm_provider=mock_provider,
            settings=settings,
            storage_svc=storage,
        )

        dataset = Dataset(
            id=dataset_id,
            owner_id=uuid.uuid4(),
            name="test_dataset",
            original_filename="test.parquet",
            file_format="parquet",
            file_size_bytes=1000,
            storage_key=str(parquet_file),
            status="ready",
            row_count=2,
            column_count=2,
            schema_json={
                "columns": [
                    {
                        "name": "val",
                        "type": "INTEGER",
                        "physical_type": "INTEGER",
                        "logical_type": "integer",
                        "nullable": True,
                    },
                    {
                        "name": "cat",
                        "type": "VARCHAR",
                        "physical_type": "VARCHAR",
                        "logical_type": "string",
                        "nullable": True,
                    },
                ]
            },
        )

        # Ambiguous question
        res = await svc.execute_workflow(
            dataset=dataset,
            question="What is the average for this dataset?",
            user_id=dataset.owner_id,
        )

        assert res.status == OrchestrationStatus.NEEDS_CLARIFICATION
        assert res.clarification is not None
        assert res.clarification.clarification_type == ClarificationType.MISSING_TARGET_METRIC
        # Ensure no SQL was executed
        assert res.executed_sql is None
        assert len(res.rows) == 0


class TestOrchestrationAPIEndpoints:
    """Verify HTTP endpoint POST /api/v1/datasets/{id}/analysis."""

    @pytest.mark.asyncio
    async def test_authenticated_workflow_analysis_endpoint(
        self,
        client: httpx.AsyncClient,
    ) -> None:
        await register_and_login(client, "orch_user@example.com", "Orchestration User")
        mock_provider = MockLLMProvider()
        app.dependency_overrides[get_llm_provider] = lambda: mock_provider

        try:
            # 1. Upload a dataset
            csv_content = b"order_id,amount\n1,100\n2,200\n"
            upload_resp = await client.post(
                "/api/v1/datasets",
                files={"file": ("orders.csv", io.BytesIO(csv_content), "text/csv")},
                data={"name": "Orders"},
            )
            assert upload_resp.status_code == 201
            dataset_id = upload_resp.json()["id"]

            # 2. Submit ambiguous question to new M4 endpoint
            resp = await client.post(
                f"/api/v1/datasets/{dataset_id}/analysis",
                json={"question": "What is the average for this dataset?"},
            )
            assert resp.status_code == 200
            data = resp.json()
            assert data["status"] == "needs_clarification"
            assert "clarification" in data
            assert data["clarification"]["clarification_type"] == "missing_target_metric"
            assert len(data["trace_events"]) > 0
        finally:
            app.dependency_overrides.pop(get_llm_provider, None)

    @pytest.mark.asyncio
    async def test_authenticated_workflow_analysis_endpoint_completed_with_verification(
        self,
        client: httpx.AsyncClient,
    ) -> None:
        await register_and_login(client, "verified_user@example.com", "Verified User")

        mock_plan = {
            "status": "ready",
            "intent": "Calculate total amount",
            "operation": "aggregation",
            "referenced_columns": ["amount"],
            "sql": 'SELECT SUM("amount") AS total_amount FROM dataset',
            "assumptions": [],
        }
        mock_interpretation = {
            "summary": "Total amount is 300.",
            "key_takeaways": ["Amounts sum to 300."],
            "structured_claims": [
                {
                    "claim_type": "scalar_value",
                    "metric_name": "total_amount",
                    "claimed_value": 300.0,
                    "evidence_references": [{"row_index": 0, "column_name": "total_amount"}],
                }
            ],
        }
        mock_provider = MockLLMProvider(canned_responses=[mock_plan, mock_interpretation])
        app.dependency_overrides[get_llm_provider] = lambda: mock_provider

        try:
            csv_content = b"order_id,amount\n1,100\n2,200\n"
            upload_resp = await client.post(
                "/api/v1/datasets",
                files={"file": ("orders.csv", io.BytesIO(csv_content), "text/csv")},
                data={"name": "Orders"},
            )
            assert upload_resp.status_code == 201
            dataset_id = upload_resp.json()["id"]

            resp = await client.post(
                f"/api/v1/datasets/{dataset_id}/analysis",
                json={"question": "What is the total amount?"},
            )
            assert resp.status_code == 200
            data = resp.json()
            assert data["status"] == "completed"
            assert data["interpretation"] is not None
            assert data["verification"] is not None
            assert data["verification"]["status"] == "verified"
            assert data["verification"]["total_claims"] == 1
            assert data["verification"]["verified_claims_count"] == 1
            assert data["verification"]["intent_consistency"]["status"] == "consistent"
        finally:
            app.dependency_overrides.pop(get_llm_provider, None)

    @pytest.mark.asyncio
    async def test_legacy_endpoint_backward_compatibility(
        self,
        client: httpx.AsyncClient,
    ) -> None:
        await register_and_login(client, "legacy_user@example.com", "Legacy User")
        mock_plan = {
            "status": "ready",
            "intent": "Count records",
            "operation": "aggregation",
            "referenced_columns": [],
            "sql": "SELECT COUNT(*) FROM dataset",
            "assumptions": [],
        }
        mock_provider = MockLLMProvider(canned_responses=[mock_plan])
        app.dependency_overrides[get_llm_provider] = lambda: mock_provider

        try:
            csv_content = b"col1\nval1\n"
            upload_resp = await client.post(
                "/api/v1/datasets",
                files={"file": ("simple.csv", io.BytesIO(csv_content), "text/csv")},
                data={"name": "Simple"},
            )
            assert upload_resp.status_code == 201
            dataset_id = upload_resp.json()["id"]

            resp = await client.post(
                f"/api/v1/datasets/{dataset_id}/query",
                json={"question": "Count total records"},
            )
            assert resp.status_code == 200
            data = resp.json()
            assert data["status"] == "completed"
            assert "SELECT COUNT(*) FROM dataset" in data["executed_sql"]
        finally:
            app.dependency_overrides.pop(get_llm_provider, None)
