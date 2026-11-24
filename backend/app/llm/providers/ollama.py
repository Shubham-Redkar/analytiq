"""Native Ollama chat API client implementation using asynchronous httpx."""

import json
import logging
import time
from typing import Any

import httpx
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

logger = logging.getLogger(__name__)


class OllamaProvider(LLMProvider):
    """Concrete LLMProvider connecting to local or remote Ollama runtime."""

    def __init__(
        self,
        base_url: str = "http://127.0.0.1:11434",
        model: str = "llama3.2:latest",
        connect_timeout: float = 5.0,
        request_timeout: float = 120.0,
        max_retries: int = 1,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.connect_timeout = connect_timeout
        self.request_timeout = request_timeout
        self.max_retries = max_retries

        self._own_client = http_client is None
        self._client = http_client or httpx.AsyncClient(
            base_url=self.base_url,
            timeout=httpx.Timeout(
                timeout=self.request_timeout,
                connect=self.connect_timeout,
            ),
        )

    async def generate(self, request: LLMRequest) -> LLMResponse:
        """Call Ollama /api/chat with structured JSON format where specified."""
        url = "/api/chat"
        target_model = request.model or self.model

        payload: dict[str, Any] = {
            "model": target_model,
            "messages": [msg.to_dict() for msg in request.messages],
            "stream": False,
            "options": {
                "temperature": request.temperature,
                "num_predict": request.max_tokens,
            },
        }

        # Ollama supports format="json" or format=<json_schema_dict>
        if request.response_schema is not None:
            payload["format"] = request.response_schema
        else:
            payload["format"] = "json"

        timeout_val = request.timeout_seconds or self.request_timeout
        call_timeout = httpx.Timeout(timeout=timeout_val, connect=self.connect_timeout)

        attempts = 0
        last_exception: Exception | None = None
        start_time = time.perf_counter()

        while attempts <= self.max_retries:
            attempts += 1
            try:
                response = await self._client.post(url, json=payload, timeout=call_timeout)
                duration_ms = (time.perf_counter() - start_time) * 1000.0

                if response.status_code == 404:
                    raise LLMModelUnavailableError(
                        f"Model '{target_model}' not found on Ollama server.",
                        provider="ollama",
                    )
                if response.status_code != 200:
                    raise LLMInvalidResponseError(
                        f"Ollama returned HTTP {response.status_code}: {response.text[:200]}",
                        provider="ollama",
                    )

                data = response.json()
                message_payload = data.get("message", {})
                content = message_payload.get("content", "")

                # Usage metrics (Ollama returns prompt_eval_count and eval_count)
                input_tokens = data.get("prompt_eval_count")
                output_tokens = data.get("eval_count")
                finish_reason = data.get("done_reason")

                structured_data: dict[str, Any] | None = None
                try:
                    parsed = json.loads(content)
                    if isinstance(parsed, dict):
                        structured_data = parsed
                except json.JSONDecodeError as jde:
                    raise LLMStructuredOutputError(
                        f"Ollama response was not valid JSON: {jde}. Raw content: {content[:200]}",
                        provider="ollama",
                    ) from jde

                return LLMResponse(
                    content=content,
                    provider="ollama",
                    model=target_model,
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    finish_reason=finish_reason,
                    duration_ms=duration_ms,
                    structured_data=structured_data,
                    metadata={
                        "total_duration_ns": data.get("total_duration"),
                        "load_duration_ns": data.get("load_duration"),
                    },
                )

            except (httpx.ConnectError, httpx.ConnectTimeout) as e:
                last_exception = LLMProviderUnavailableError(
                    f"Could not connect to Ollama at {self.base_url}: {e}",
                    provider="ollama",
                )
            except (httpx.ReadTimeout, httpx.WriteTimeout) as e:
                last_exception = LLMTimeoutError(
                    f"Ollama request timed out after {timeout_val}s: {e}",
                    provider="ollama",
                )
            except (LLMModelUnavailableError, LLMStructuredOutputError):
                raise
            except Exception as e:
                last_exception = LLMInvalidResponseError(
                    f"Unexpected error communicating with Ollama: {e}",
                    provider="ollama",
                )

        if last_exception is not None:
            raise last_exception
        raise LLMProviderUnavailableError("Ollama request failed after retries.", provider="ollama")

    async def health_check(self) -> LLMHealthStatus:
        """Probe /api/tags to verify daemon reachability and target model availability."""
        try:
            resp = await self._client.get(
                "/api/tags",
                timeout=httpx.Timeout(timeout=min(self.connect_timeout, 3.0)),
            )
            if resp.status_code != 200:
                return LLMHealthStatus(
                    available=False,
                    provider="ollama",
                    model=self.model,
                    status="provider_error",
                    error=f"HTTP {resp.status_code}",
                )

            tags_data = resp.json()
            models = [m.get("name") for m in tags_data.get("models", [])]

            # Match exact name or without tag if matching default
            model_installed = any(
                m == self.model or m.startswith(f"{self.model}:")
                for m in models
                if isinstance(m, str)
            )

            if not model_installed:
                return LLMHealthStatus(
                    available=False,
                    provider="ollama",
                    model=self.model,
                    status="model_unavailable",
                    error=f"Model '{self.model}' not found in installed tags: {models}",
                )

            return LLMHealthStatus(
                available=True,
                provider="ollama",
                model=self.model,
                status="ready",
                metadata={"installed_models": models},
            )

        except Exception as e:
            return LLMHealthStatus(
                available=False,
                provider="ollama",
                model=self.model,
                status="provider_unavailable",
                error=str(e),
            )

    async def close(self) -> None:
        if self._own_client and not self._client.is_closed:
            await self._client.aclose()
