"""AnalytIQ Schemas - Workflow Progress Streaming and Event Contracts."""

from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, Field

from app.schemas.analysis import WorkflowAnalysisResponse


class StreamProgressEvent(BaseModel):
    """Server-Sent Event payload tracking analytical workflow execution."""

    request_id: str
    seq: int
    event_type: str
    stage: str | None = None
    stage_name: str | None = None
    status: str = "running"
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
    elapsed_ms: float = 0.0
    payload: dict[str, Any] | None = None
    result: WorkflowAnalysisResponse | None = None


class CancellationResponse(BaseModel):
    """Response payload for cancellation requests."""

    request_id: str
    status: str
    message: str
