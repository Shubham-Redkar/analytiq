"""LLM Provider factory and dependency injection utilities."""

from typing import Any

from app.core.config import Settings, get_settings
from app.llm.contracts import LLMProvider
from app.llm.providers.mock import MockLLMProvider
from app.llm.providers.ollama import OllamaProvider


def create_llm_provider(
    settings: Settings | None = None,
    **overrides: Any,
) -> LLMProvider:
    """Instantiate configured LLMProvider based on settings.

    In production/dev defaults to OllamaProvider. In tests, settings or overrides
    can inject MockLLMProvider.
    """
    cfg = settings or get_settings()
    provider_name = overrides.get("provider", cfg.llm_provider).lower()

    if provider_name == "mock":
        return MockLLMProvider(
            model=overrides.get("model", cfg.llm_model),
            canned_responses=overrides.get("canned_responses"),
            simulate_error=overrides.get("simulate_error"),
            simulate_unhealthy=overrides.get("simulate_unhealthy", False),
        )

    if provider_name == "ollama":
        return OllamaProvider(
            base_url=overrides.get("base_url", cfg.ollama_base_url),
            model=overrides.get("model", cfg.llm_model),
            connect_timeout=overrides.get("connect_timeout", cfg.llm_connect_timeout_seconds),
            request_timeout=overrides.get("request_timeout", cfg.llm_request_timeout_seconds),
            max_retries=overrides.get("max_retries", cfg.llm_max_provider_retries),
            http_client=overrides.get("http_client"),
        )

    raise ValueError(f"Unknown or unsupported LLM provider: '{provider_name}'")
