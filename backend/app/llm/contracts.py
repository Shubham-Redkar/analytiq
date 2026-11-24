"""Provider-independent LLM contracts and types for AnalytIQ.

These types define the normalized protocol, request, response, and diagnostic
contracts implemented by concrete LLM providers (e.g., Ollama, Mock, and future providers).
"""

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any, Protocol, runtime_checkable


class MessageRole(StrEnum):
    """Normalized message roles across LLM providers."""

    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"


@dataclass(frozen=True)
class ChatMessage:
    """A single normalized chat message."""

    role: MessageRole
    content: str

    def to_dict(self) -> dict[str, str]:
        return {"role": self.role.value, "content": self.content}


@dataclass(frozen=True)
class LLMRequest:
    """Provider-independent request for LLM generation."""

    messages: list[ChatMessage]
    model: str
    temperature: float = 0.0
    max_tokens: int = 2048
    response_schema: dict[str, Any] | None = None
    correlation_id: str | None = None
    timeout_seconds: float | None = None


@dataclass(frozen=True)
class LLMResponse:
    """Normalized response produced by an LLM provider."""

    content: str
    provider: str
    model: str
    input_tokens: int | None = None
    output_tokens: int | None = None
    finish_reason: str | None = None
    duration_ms: float = 0.0
    structured_data: dict[str, Any] | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class LLMHealthStatus:
    """Lightweight connectivity and availability diagnostic status."""

    available: bool
    provider: str
    model: str
    status: str
    error: str | None = None
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))
    metadata: dict[str, Any] = field(default_factory=dict)


@runtime_checkable
class LLMProvider(Protocol):
    """Asynchronous protocol implemented by all LLM providers."""

    async def generate(self, request: LLMRequest) -> LLMResponse:
        """Generate a completion for the provided normalized request."""
        ...

    async def health_check(self) -> LLMHealthStatus:
        """Perform a lightweight provider connectivity diagnostic."""
        ...

    async def close(self) -> None:
        """Release underlying HTTP connections and worker resources."""
        ...
