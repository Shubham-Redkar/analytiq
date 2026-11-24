"""Provider-independent Analytical Planner service."""

import json
import logging
from typing import Any

from pydantic import ValidationError

from app.analysis.context_builder import serialize_context_for_prompt
from app.analysis.contracts import (
    DatasetAnalyticalContext,
    PlanStatus,
    StructuredAnalyticalPlan,
)
from app.analysis.prompts import (
    PLAN_JSON_SCHEMA,
    PLANNER_SYSTEM_PROMPT,
    build_correction_user_message,
    build_planner_user_message,
)
from app.llm.contracts import (
    ChatMessage,
    LLMProvider,
    LLMRequest,
    MessageRole,
)
from app.llm.exceptions import LLMStructuredOutputError

logger = logging.getLogger(__name__)


class AnalyticalPlannerError(Exception):
    """Raised when analytical plan generation fails."""


class AnalyticalPlanner:
    """Generates structured analytical plans using an injected LLM provider."""

    def __init__(
        self,
        provider: LLMProvider,
        model: str,
        temperature: float = 0.0,
        max_tokens: int = 2048,
        timeout_seconds: float = 60.0,
    ) -> None:
        self.provider = provider
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.timeout_seconds = timeout_seconds

    async def plan(
        self,
        question: str,
        context: DatasetAnalyticalContext,
    ) -> tuple[StructuredAnalyticalPlan, dict[str, Any]]:
        """Generate an initial structured analytical plan for the user question."""
        context_str = serialize_context_for_prompt(context)
        user_msg = build_planner_user_message(context_str, question)

        messages = [
            ChatMessage(role=MessageRole.SYSTEM, content=PLANNER_SYSTEM_PROMPT),
            ChatMessage(role=MessageRole.USER, content=user_msg),
        ]

        req = LLMRequest(
            messages=messages,
            model=self.model,
            temperature=self.temperature,
            max_tokens=self.max_tokens,
            response_schema=PLAN_JSON_SCHEMA,
            timeout_seconds=self.timeout_seconds,
        )

        response = await self.provider.generate(req)
        plan = self._parse_and_validate_plan(response.structured_data, response.content)
        metadata = {
            "provider": response.provider,
            "model": response.model,
            "duration_ms": response.duration_ms,
            "input_tokens": response.input_tokens,
            "output_tokens": response.output_tokens,
        }
        return plan, metadata

    async def correct_plan(
        self,
        question: str,
        context: DatasetAnalyticalContext,
        failed_sql: str | None,
        error_feedback: str,
    ) -> tuple[StructuredAnalyticalPlan, dict[str, Any]]:
        """Request a bounded correction from the LLM for a syntax/schema error."""
        context_str = serialize_context_for_prompt(context)
        correction_msg = build_correction_user_message(
            context_str, question, failed_sql, error_feedback
        )

        messages = [
            ChatMessage(role=MessageRole.SYSTEM, content=PLANNER_SYSTEM_PROMPT),
            ChatMessage(role=MessageRole.USER, content=correction_msg),
        ]

        req = LLMRequest(
            messages=messages,
            model=self.model,
            temperature=self.temperature,
            max_tokens=self.max_tokens,
            response_schema=PLAN_JSON_SCHEMA,
            timeout_seconds=self.timeout_seconds,
        )

        response = await self.provider.generate(req)
        plan = self._parse_and_validate_plan(response.structured_data, response.content)
        metadata = {
            "provider": response.provider,
            "model": response.model,
            "duration_ms": response.duration_ms,
            "input_tokens": response.input_tokens,
            "output_tokens": response.output_tokens,
        }
        return plan, metadata

    def _parse_and_validate_plan(
        self,
        structured_data: dict[str, Any] | None,
        raw_content: str,
    ) -> StructuredAnalyticalPlan:
        """Parse dictionary or raw content into a validated StructuredAnalyticalPlan."""
        data = structured_data
        if data is None:
            try:
                parsed = json.loads(raw_content)
                if isinstance(parsed, dict):
                    data = parsed
            except Exception as e:
                raise LLMStructuredOutputError(
                    f"Model output could not be parsed as JSON: {e}",
                    provider="analytical_planner",
                ) from e

        if not isinstance(data, dict):
            raise LLMStructuredOutputError(
                f"Model output did not produce a JSON object: {raw_content[:200]}",
                provider="analytical_planner",
            )

        try:
            plan = StructuredAnalyticalPlan.model_validate(data)
        except ValidationError as ve:
            raise LLMStructuredOutputError(
                f"Plan failed Pydantic schema validation: {ve}",
                provider="analytical_planner",
            ) from ve

        # Enforce contract integrity
        if plan.status == PlanStatus.READY and not plan.sql:
            raise LLMStructuredOutputError(
                "Model returned status='ready' but did not provide 'sql'.",
                provider="analytical_planner",
            )

        return plan
