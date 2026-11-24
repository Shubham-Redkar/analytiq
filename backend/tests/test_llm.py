"""Tests for provider-independent LLM contracts, Ollama, and Mock providers."""

import httpx
import pytest
from app.core.config import Settings
from app.llm.contracts import ChatMessage, LLMRequest, MessageRole
from app.llm.exceptions import (
    LLMModelUnavailableError,
    LLMProviderUnavailableError,
    LLMStructuredOutputError,
)
from app.llm.factory import create_llm_provider
from app.llm.providers.mock import MockLLMProvider
from app.llm.providers.ollama import OllamaProvider


class TestMockLLMProvider:
    """Verify deterministic mock provider behavior for tests and CI."""

    @pytest.mark.asyncio
    async def test_mock_default_generation(self) -> None:
        provider = MockLLMProvider(model="mock-v1")
        req = LLMRequest(
            messages=[ChatMessage(role=MessageRole.USER, content="Hello")],
            model="mock-v1",
        )
        resp = await provider.generate(req)
        assert resp.provider == "mock"
        assert resp.model == "mock-v1"
        assert resp.structured_data is not None
        assert resp.structured_data["status"] == "ready"
        assert "SELECT COUNT(*)" in resp.structured_data["sql"]
        await provider.close()

    @pytest.mark.asyncio
    async def test_mock_canned_responses(self) -> None:
        canned = [
            {"status": "needs_clarification", "clarification_question": "Which column?"},
            {"status": "unsupported", "unsupported_reason": "Forecasting not supported"},
        ]
        provider = MockLLMProvider(canned_responses=canned)
        req = LLMRequest(
            messages=[ChatMessage(role=MessageRole.USER, content="Q1")],
            model="mock",
        )
        r1 = await provider.generate(req)
        assert r1.structured_data == canned[0]

        r2 = await provider.generate(req)
        assert r2.structured_data == canned[1]

    @pytest.mark.asyncio
    async def test_mock_error_simulation(self) -> None:
        provider = MockLLMProvider(simulate_error=LLMProviderUnavailableError)
        req = LLMRequest(
            messages=[ChatMessage(role=MessageRole.USER, content="Test")],
            model="mock",
        )
        with pytest.raises(LLMProviderUnavailableError):
            await provider.generate(req)

    @pytest.mark.asyncio
    async def test_mock_health_check(self) -> None:
        healthy = MockLLMProvider()
        h_stat = await healthy.health_check()
        assert h_stat.available is True
        assert h_stat.status == "ready"

        unhealthy = MockLLMProvider(simulate_unhealthy=True)
        u_stat = await unhealthy.health_check()
        assert u_stat.available is False
        assert u_stat.status == "provider_unavailable"


class TestOllamaProviderWithMockTransport:
    """Verify OllamaProvider protocol handling using mock httpx transport."""

    @pytest.mark.asyncio
    async def test_ollama_successful_chat_generation(self) -> None:
        async def handler(request: httpx.Request) -> httpx.Response:
            assert request.url.path == "/api/chat"
            return httpx.Response(
                status_code=200,
                json={
                    "model": "llama3.2:latest",
                    "message": {"role": "assistant", "content": '{"status": "ready", "count": 10}'},
                    "done": True,
                    "done_reason": "stop",
                    "prompt_eval_count": 45,
                    "eval_count": 20,
                    "total_duration": 150000000,
                },
            )

        client = httpx.AsyncClient(
            base_url="http://mock-ollama:11434", transport=httpx.MockTransport(handler)
        )
        provider = OllamaProvider(
            base_url="http://mock-ollama:11434",
            model="llama3.2:latest",
            http_client=client,
        )

        req = LLMRequest(
            messages=[ChatMessage(role=MessageRole.USER, content="Count rows")],
            model="llama3.2:latest",
        )
        resp = await provider.generate(req)

        assert resp.provider == "ollama"
        assert resp.model == "llama3.2:latest"
        assert resp.input_tokens == 45
        assert resp.output_tokens == 20
        assert resp.structured_data == {"status": "ready", "count": 10}
        await provider.close()

    @pytest.mark.asyncio
    async def test_ollama_model_not_found_raises(self) -> None:
        async def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(status_code=404, text="model not found")

        client = httpx.AsyncClient(
            base_url="http://mock-ollama:11434", transport=httpx.MockTransport(handler)
        )
        provider = OllamaProvider(
            base_url="http://mock-ollama:11434",
            model="nonexistent-model",
            http_client=client,
            max_retries=0,
        )

        req = LLMRequest(
            messages=[ChatMessage(role=MessageRole.USER, content="test")],
            model="nonexistent-model",
        )
        with pytest.raises(LLMModelUnavailableError):
            await provider.generate(req)

    @pytest.mark.asyncio
    async def test_ollama_invalid_json_raises_structured_output_error(self) -> None:
        async def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(
                status_code=200,
                json={
                    "model": "llama3.2:latest",
                    "message": {"role": "assistant", "content": "not json content"},
                },
            )

        client = httpx.AsyncClient(
            base_url="http://mock-ollama:11434", transport=httpx.MockTransport(handler)
        )
        provider = OllamaProvider(
            base_url="http://mock-ollama:11434",
            model="llama3.2:latest",
            http_client=client,
            max_retries=0,
        )

        req = LLMRequest(
            messages=[ChatMessage(role=MessageRole.USER, content="test")],
            model="llama3.2:latest",
        )
        with pytest.raises(LLMStructuredOutputError):
            await provider.generate(req)

    @pytest.mark.asyncio
    async def test_ollama_health_check_ready_and_model_unavailable(self) -> None:
        async def handler(request: httpx.Request) -> httpx.Response:
            assert request.url.path == "/api/tags"
            return httpx.Response(
                status_code=200,
                json={"models": [{"name": "llama3.2:latest"}, {"name": "mistral:latest"}]},
            )

        client = httpx.AsyncClient(
            base_url="http://mock-ollama:11434", transport=httpx.MockTransport(handler)
        )
        provider = OllamaProvider(
            base_url="http://mock-ollama:11434",
            model="llama3.2:latest",
            http_client=client,
        )
        health = await provider.health_check()
        assert health.available is True
        assert health.status == "ready"

        provider_missing = OllamaProvider(
            base_url="http://mock-ollama:11434",
            model="qwen-missing",
            http_client=client,
        )
        health_missing = await provider_missing.health_check()
        assert health_missing.available is False
        assert health_missing.status == "model_unavailable"


class TestLLMFactory:
    """Verify factory dependency injection and configuration mapping."""

    def test_factory_creates_ollama_by_default(self) -> None:
        cfg = Settings(llm_provider="ollama", llm_model="llama3.2:latest")
        p = create_llm_provider(settings=cfg)
        assert isinstance(p, OllamaProvider)
        assert p.model == "llama3.2:latest"

    def test_factory_creates_mock_provider(self) -> None:
        cfg = Settings(llm_provider="mock", llm_model="mock-test")
        p = create_llm_provider(settings=cfg)
        assert isinstance(p, MockLLMProvider)
        assert p.model == "mock-test"
