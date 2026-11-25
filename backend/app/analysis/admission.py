"""Shared analytical admission control and bounded queue management.

Enforces a unified local resource policy across both analytical endpoints:
- POST /api/v1/datasets/{dataset_id}/query (Direct M3)
- POST /api/v1/datasets/{dataset_id}/analysis (Orchestration M4)

Constraints:
- Exactly `max_concurrent` active analytical execution per application worker (default: 1).
- At most `max_pending` queued requests waiting for an execution permit (default: 2).
- Additional requests receive an immediate explicit overload rejection (HTTP 429).
- Cancelled waiting requests safely leave the queue without consuming or leaking capacity.
- Waiting in queue consumes the overall request deadline.
"""

import asyncio
import logging
import time
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

logger = logging.getLogger(__name__)


class AnalyticalOverloadError(Exception):
    """Raised when the analytical execution queue is at full capacity."""

    def __init__(
        self,
        message: str = (
            "The analytical engine is currently processing maximum concurrent workloads. "
            "Please retry shortly."
        ),
        retry_after: int = 5,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.retry_after = retry_after


class AnalyticalAdmissionController:
    """In-process shared admission controller with a strictly bounded waiting queue."""

    def __init__(self, max_concurrent: int = 1, max_pending: int = 2) -> None:
        self.max_concurrent = max(1, max_concurrent)
        self.max_pending = max(0, max_pending)
        self._semaphore = asyncio.Semaphore(self.max_concurrent)
        self._pending_count = 0
        self._lock = asyncio.Lock()

    @property
    def active_count(self) -> int:
        """Number of active analytical requests currently executing."""
        return self.max_concurrent - self._semaphore._value

    @property
    def pending_count(self) -> int:
        """Number of requests currently waiting in the admission queue."""
        return self._pending_count

    @asynccontextmanager
    async def acquire_ticket(
        self,
        timeout_seconds: float = 120.0,
    ) -> AsyncIterator[float]:
        """Acquire an analytical execution permit or raise AnalyticalOverloadError if saturated.

        Yields:
            The remaining timeout in seconds after queue admission.
        """
        queue_start = time.monotonic()

        # Step 1: Check capacity under atomic lock
        async with self._lock:
            # If a permit is immediately available without waiting
            if self._semaphore._value > 0:
                await self._semaphore.acquire()
                acquired_immediately = True
            else:
                # Need to wait; check if queue limit exceeded
                if self._pending_count >= self.max_pending:
                    logger.warning(
                        "Analytical admission rejected: active=%d/%d, pending=%d/%d (saturated).",
                        self.active_count,
                        self.max_concurrent,
                        self._pending_count,
                        self.max_pending,
                    )
                    raise AnalyticalOverloadError()
                self._pending_count += 1
                acquired_immediately = False

        # Step 2: If we had to wait, wait for the semaphore with timeout and cancellation safety
        if not acquired_immediately:
            try:
                # Calculate time remaining on the overall request deadline
                elapsed_pre = time.monotonic() - queue_start
                wait_deadline = max(0.0, timeout_seconds - elapsed_pre)

                await asyncio.wait_for(
                    self._semaphore.acquire(),
                    timeout=wait_deadline,
                )
            except TimeoutError as te:
                logger.info(
                    "Analytical admission queue wait timed out after %.2fs.", timeout_seconds
                )
                raise TimeoutError("Analytical admission queue wait exceeded deadline.") from te
            except asyncio.CancelledError:
                logger.info("Analytical admission request was cancelled while waiting in queue.")
                raise
            finally:
                async with self._lock:
                    self._pending_count -= 1

        # Step 3: Yield to worker execution, then guarantee permit release in finally block
        queue_wait_duration = time.monotonic() - queue_start
        remaining_timeout = max(0.0, timeout_seconds - queue_wait_duration)

        try:
            yield remaining_timeout
        finally:
            self._semaphore.release()


# Global in-process singleton instance shared across API routes
_global_admission_controller: AnalyticalAdmissionController | None = None


def get_shared_admission_controller(
    max_concurrent: int = 1,
    max_pending: int = 2,
) -> AnalyticalAdmissionController:
    """Retrieve or initialize the global shared analytical admission controller."""
    global _global_admission_controller
    if _global_admission_controller is None:
        _global_admission_controller = AnalyticalAdmissionController(
            max_concurrent=max_concurrent,
            max_pending=max_pending,
        )
    return _global_admission_controller
