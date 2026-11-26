"""Request budget tracker and resource guard for multi-agent workflows."""

import time

from app.core.config import Settings


class WorkflowBudgetTracker:
    """Enforces monolithic request deadlines, LLM call limits, and retry bounds."""

    def __init__(
        self,
        settings: Settings,
        max_total_timeout_seconds: float | None = None,
        max_llm_calls: int = 4,
        max_corrections: int = 1,
        max_steps: int = 20,
    ) -> None:
        self.settings = settings
        # Overall deadline defaults to configured request timeout (default 120s)
        self.max_timeout_seconds = (
            max_total_timeout_seconds
            if max_total_timeout_seconds is not None
            else settings.llm_request_timeout_seconds
        )
        self.max_llm_calls = min(
            max_llm_calls,
            getattr(settings, "analysis_max_llm_calls_per_workflow", 4),
        )
        self.max_corrections = min(
            max_corrections,
            settings.analysis_max_correction_attempts,
        )
        self.max_steps = min(
            max_steps,
            getattr(settings, "analysis_max_graph_transitions", 20),
        )

        self.start_time = time.monotonic()
        self.llm_call_count = 0
        self.correction_count = 0
        self.step_count = 0

    @property
    def elapsed_seconds(self) -> float:
        return time.monotonic() - self.start_time

    @property
    def remaining_seconds(self) -> float:
        remaining = self.max_timeout_seconds - self.elapsed_seconds
        return max(0.0, remaining)

    def is_timed_out(self) -> bool:
        return self.remaining_seconds <= 0.1

    def can_make_llm_call(self) -> bool:
        if self.is_timed_out():
            return False
        return self.llm_call_count < self.max_llm_calls

    def record_llm_call(self) -> None:
        self.llm_call_count += 1

    def can_attempt_correction(self) -> bool:
        if self.is_timed_out():
            return False
        if not self.can_make_llm_call():
            return False
        return self.correction_count < self.max_corrections

    def record_correction(self) -> None:
        self.correction_count += 1

    def increment_step(self) -> bool:
        """Increment step counter. Returns False if max steps exceeded."""
        self.step_count += 1
        return self.step_count <= self.max_steps
