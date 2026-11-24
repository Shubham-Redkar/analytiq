"""Exceptions raised by LLM providers with safe, categorized error definitions."""


class LLMError(Exception):
    """Base exception for all LLM provider errors."""

    def __init__(self, message: str, provider: str = "unknown") -> None:
        super().__init__(message)
        self.message = message
        self.provider = provider


class LLMProviderUnavailableError(LLMError):
    """The configured LLM provider service could not be reached."""


class LLMModelUnavailableError(LLMError):
    """The configured model is not installed or available on the provider."""


class LLMTimeoutError(LLMError):
    """The LLM request exceeded the configured connection or read deadline."""


class LLMInvalidResponseError(LLMError):
    """The provider returned a malformed or non-compliant response."""


class LLMStructuredOutputError(LLMError):
    """The provider output could not be parsed as valid structured JSON matching schema."""


class LLMContextLimitExceededError(LLMError):
    """The request exceeded the provider's token or context window ceiling."""


class LLMProviderOverloadError(LLMError):
    """The provider is overloaded or resource-constrained."""
