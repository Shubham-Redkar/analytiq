"""Regression tests for SSE keepalive streaming and structured claim normalization."""

import json

import pytest
from app.llm.contracts import LLMHealthStatus, LLMResponse
from app.orchestration.agents.interpreter import ResultInterpreterAgent
from app.verification.contracts import (
    DimensionAssociatedValueClaim,
    RowCountClaim,
    ScalarValueClaim,
)


class MockLLMProvider:
    def __init__(self, raw_content: str):
        self.raw_content = raw_content

    async def generate(self, request):
        structured = None
        try:
            structured = json.loads(self.raw_content)
        except Exception:
            structured = None
        return LLMResponse(
            content=self.raw_content,
            structured_data=structured,
            provider="mock",
            model="mock",
        )

    async def health_check(self) -> LLMHealthStatus:
        return LLMHealthStatus(
            available=True,
            provider="mock",
            model="mock",
            status="ok",
        )

    async def close(self) -> None:
        pass


@pytest.mark.asyncio
async def test_claim_value_normalization_scalar():
    """Verify that claims returning 'value' instead of 'claimed_value' are normalized."""
    mock_llm_json = """{
        "summary": "The dataset contains 418 records.",
        "key_findings": ["418 records"],
        "data_points": {"count_star()": 418},
        "claims": [
            {
                "claim_type": "scalar_value",
                "value": 418,
                "metric_name": "count_star()"
            }
        ]
    }"""
    provider = MockLLMProvider(mock_llm_json)
    agent = ResultInterpreterAgent(provider=provider, model="mock")
    claims = agent._parse_structured_claims(
        raw_claims=[{"claim_type": "scalar_value", "value": 418, "metric_name": "count_star()"}],
        fingerprint="test_fp",
    )
    assert len(claims) == 1
    assert isinstance(claims[0], ScalarValueClaim)
    assert claims[0].claimed_value == 418
    assert claims[0].metric_name == "count_star()"


@pytest.mark.asyncio
async def test_claim_value_normalization_dimension_and_count():
    """Verify dimension associated and row count normalization."""
    agent = ResultInterpreterAgent(provider=MockLLMProvider("{}"), model="mock")
    claims = agent._parse_structured_claims(
        raw_claims=[
            {
                "claim_type": "dimension_associated_value",
                "entity": "male",
                "metric_name": "survived",
                "value": 109,
            },
            {
                "claim_type": "row_count",
                "count": 418,
            },
        ],
        fingerprint="test_fp",
    )
    assert len(claims) == 2
    assert isinstance(claims[0], DimensionAssociatedValueClaim)
    assert claims[0].dimension_value == "male"
    assert claims[0].claimed_value == 109
    assert isinstance(claims[1], RowCountClaim)
    assert claims[1].claimed_count == 418
