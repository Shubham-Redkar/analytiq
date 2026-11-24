"""Bounded workflow tracing and event recording."""

from datetime import UTC, datetime
from typing import Any

from app.orchestration.contracts import TraceEvent


class WorkflowTracer:
    """Thread-safe, bounded recorder for workflow execution events."""

    def __init__(self, max_events: int = 50) -> None:
        self.max_events = max_events
        self.events: list[TraceEvent] = []

    def record(
        self,
        node: str,
        action: str,
        duration_ms: float,
        status: str = "success",
        llm_called: bool = False,
        tokens_used: int = 0,
        details: dict[str, Any] | None = None,
    ) -> TraceEvent:
        """Record an observable event, ensuring trace history remains bounded."""
        event = TraceEvent(
            node=node,
            action=action,
            duration_ms=round(duration_ms, 2),
            timestamp=datetime.now(UTC),
            llm_called=llm_called,
            tokens_used=tokens_used,
            status=status,
            details=details or {},
        )
        if len(self.events) >= self.max_events:
            self.events.pop(0)
        self.events.append(event)
        return event

    def get_events(self) -> list[TraceEvent]:
        return list(self.events)
