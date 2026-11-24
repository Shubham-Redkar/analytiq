"""Deterministic mock LLM provider for tests, CI, and offline verification."""

import json
from collections.abc import Sequence
from typing import Any

from app.llm.contracts import (
    LLMHealthStatus,
    LLMProvider,
    LLMRequest,
    LLMResponse,
)
from app.llm.exceptions import (
    LLMInvalidResponseError,
    LLMModelUnavailableError,
    LLMProviderUnavailableError,
    LLMStructuredOutputError,
    LLMTimeoutError,
)


class MockLLMProvider(LLMProvider):
    """A deterministic test double providing controlled canned or rule-based outputs."""

    def __init__(
        self,
        *,
        model: str = "mock-model",
        canned_responses: Sequence[str | dict[str, Any]] | None = None,
        simulate_error: type[Exception] | None = None,
        simulate_unhealthy: bool = False,
    ) -> None:
        self.model = model
        self.canned_responses = list(canned_responses or [])
        self.simulate_error = simulate_error
        self.simulate_unhealthy = simulate_unhealthy
        self.recorded_requests: list[LLMRequest] = []
        self._closed = False

    async def generate(self, request: LLMRequest) -> LLMResponse:
        self.recorded_requests.append(request)

        if self.simulate_error is not None:
            if issubclass(
                self.simulate_error,
                (
                    LLMProviderUnavailableError,
                    LLMModelUnavailableError,
                    LLMTimeoutError,
                    LLMInvalidResponseError,
                    LLMStructuredOutputError,
                ),
            ):
                raise self.simulate_error("Simulated provider failure", provider="mock")
            raise self.simulate_error("Unexpected simulated exception")

        if self.canned_responses:
            next_resp = self.canned_responses.pop(0)
            if isinstance(next_resp, dict):
                content = json.dumps(next_resp)
                structured = next_resp
            else:
                content = str(next_resp)
                try:
                    loaded = json.loads(content)
                    structured = loaded if isinstance(loaded, dict) else None
                except Exception:
                    structured = None

            return LLMResponse(
                content=content,
                provider="mock",
                model=request.model or self.model,
                input_tokens=50,
                output_tokens=30,
                finish_reason="stop",
                duration_ms=1.5,
                structured_data=structured,
            )

        # Default fallback response: minimal analytical plan
        default_plan = {
            "status": "ready",
            "intent": "Count total records in dataset",
            "operation": "aggregation",
            "referenced_columns": [],
            "sql": "SELECT COUNT(*) AS total_rows FROM dataset",
            "assumptions": [],
            "clarification_question": None,
            "unsupported_reason": None,
        }
        return LLMResponse(
            content=json.dumps(default_plan),
            provider="mock",
            model=request.model or self.model,
            input_tokens=40,
            output_tokens=25,
            finish_reason="stop",
            duration_ms=1.0,
            structured_data=default_plan,
        )

    async def health_check(self) -> LLMHealthStatus:
        if self.simulate_unhealthy:
            return LLMHealthStatus(
                available=False,
                provider="mock",
                model=self.model,
                status="provider_unavailable",
                error="Simulated mock unhealthiness",
            )
        return LLMHealthStatus(
            available=True,
            provider="mock",
            model=self.model,
            status="ready",
        )

    async def close(self) -> None:
        self._closed = True
