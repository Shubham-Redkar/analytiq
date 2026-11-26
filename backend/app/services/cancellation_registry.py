"""AnalytIQ Cancellation Registry - In-memory cooperative cancellation registry."""

import asyncio
import logging
import uuid
from typing import NamedTuple

logger = logging.getLogger(__name__)


class RegisteredRequest(NamedTuple):
    """Metadata for an active cancellable analytical request."""

    request_id: str
    user_id: uuid.UUID
    dataset_id: uuid.UUID
    cancel_event: asyncio.Event


class CancellationRegistry:
    """Thread-safe cooperative registry mapping active request_ids to cancellation events."""

    def __init__(self) -> None:
        self._requests: dict[str, RegisteredRequest] = {}
        self._lock = asyncio.Lock()

    async def register(
        self,
        request_id: str,
        user_id: uuid.UUID,
        dataset_id: uuid.UUID,
    ) -> asyncio.Event:
        """Register an active request and return its cooperative cancellation Event."""
        event = asyncio.Event()
        async with self._lock:
            self._requests[request_id] = RegisteredRequest(
                request_id=request_id,
                user_id=user_id,
                dataset_id=dataset_id,
                cancel_event=event,
            )
        return event

    async def unregister(self, request_id: str) -> None:
        """Unregister a completed or terminated request."""
        async with self._lock:
            self._requests.pop(request_id, None)

    async def cancel(self, request_id: str, user_id: uuid.UUID) -> bool:
        """Signal cooperative cancellation if the request is registered and owned by user_id."""
        async with self._lock:
            item = self._requests.get(request_id)
            if not item:
                return False
            if item.user_id != user_id:
                logger.warning(
                    "Unauthorized cancellation: user %s tried to cancel request %s owned by %s",
                    user_id,
                    request_id,
                    item.user_id,
                )
                return False
            item.cancel_event.set()
            return True

    async def is_cancelled(self, request_id: str) -> bool:
        """Check if cooperative cancellation has been signalled for a request."""
        async with self._lock:
            item = self._requests.get(request_id)
            if item and item.cancel_event.is_set():
                return True
        return False


cancellation_registry = CancellationRegistry()
