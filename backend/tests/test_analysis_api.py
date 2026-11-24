"""API Integration tests for the Analytical Query endpoints."""

import io
import uuid

import pytest
from app.api.v1.analysis import get_llm_provider
from app.llm.providers.mock import MockLLMProvider
from app.main import app
from httpx import AsyncClient

from tests.test_datasets import register_and_login


@pytest.fixture
def mock_planner_llm() -> MockLLMProvider:
    """Mock LLM provider returning controlled analytical plans."""
    canned = [
        {
            "status": "ready",
            "intent": "Count total records",
            "operation": "aggregation",
            "referenced_columns": [],
            "sql": "SELECT COUNT(*) AS total_rows FROM dataset",
            "assumptions": [],
        }
    ]
    return MockLLMProvider(canned_responses=canned)


class TestAnalysisAPIEndpoints:
    """Verify authentication, ownership, and response contracts on /api/v1/datasets/{id}/query."""

    @pytest.mark.asyncio
    async def test_analysis_status_endpoint(self, client: AsyncClient) -> None:
        mock_provider = MockLLMProvider(model="mock-ready-model")
        app.dependency_overrides[get_llm_provider] = lambda: mock_provider
        try:
            resp = await client.get("/api/v1/analysis/status")
            assert resp.status_code == 200
            data = resp.json()
            assert data["analysis_available"] is True
            assert data["provider"] == "mock"
            assert data["model"] == "mock-ready-model"
            assert data["status"] == "ready"
        finally:
            app.dependency_overrides.pop(get_llm_provider, None)

    @pytest.mark.asyncio
    async def test_unauthenticated_query_rejected(self, client: AsyncClient) -> None:
        fake_id = uuid.uuid4()
        resp = await client.post(
            f"/api/v1/datasets/{fake_id}/query",
            json={"question": "How many records are in this dataset?"},
        )
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_cross_user_isolation_returns_404(
        self,
        client: AsyncClient,
    ) -> None:
        await register_and_login(client, "user_isolation@example.com", "Isolation User")
        fake_id = uuid.uuid4()
        resp = await client.post(
            f"/api/v1/datasets/{fake_id}/query",
            json={"question": "How many records are in this dataset?"},
        )
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_successful_analytical_query_on_owned_dataset(
        self,
        client: AsyncClient,
        mock_planner_llm: MockLLMProvider,
    ) -> None:
        await register_and_login(client, "owner_analyst@example.com", "Owner Analyst")
        app.dependency_overrides[get_llm_provider] = lambda: mock_planner_llm

        try:
            # 1. Upload a CSV dataset first
            csv_content = b"id,name,amount\n1,Alice,100.5\n2,Bob,200.0\n3,Charlie,300.0\n"
            upload_resp = await client.post(
                "/api/v1/datasets",
                files={"file": ("sales.csv", io.BytesIO(csv_content), "text/csv")},
                data={"name": "Sales Dataset"},
            )
            assert upload_resp.status_code == 201
            dataset_id = upload_resp.json()["id"]

            # 2. Query the uploaded dataset
            query_resp = await client.post(
                f"/api/v1/datasets/{dataset_id}/query",
                json={"question": "How many records are in this dataset?"},
            )
            assert query_resp.status_code == 200
            result = query_resp.json()

            assert result["status"] == "completed"
            assert result["question"] == "How many records are in this dataset?"
            assert result["executed_sql"] is not None
            assert result["returned_row_count"] == 1
            assert result["rows"] == [[3]]
            assert result["evidence"] is not None
            assert result["evidence"]["result_fingerprint"] is not None
        finally:
            app.dependency_overrides.pop(get_llm_provider, None)
