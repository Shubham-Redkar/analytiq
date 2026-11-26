"""Unit tests for AnalyticalAdmissionController and bounded overload queuing."""

import asyncio

import pytest
from app.analysis.admission import AnalyticalAdmissionController, AnalyticalOverloadError


@pytest.mark.asyncio
async def test_admission_controller_concurrency_and_saturation() -> None:
    # 1 concurrent, max 2 pending -> total capacity = 3
    controller = AnalyticalAdmissionController(max_concurrent=1, max_pending=2)

    active_executions: list[int] = []

    async def worker(worker_id: int, hold_seconds: float) -> None:
        async with controller.acquire_ticket(timeout_seconds=5.0):
            active_executions.append(worker_id)
            await asyncio.sleep(hold_seconds)
            active_executions.remove(worker_id)

    # Launch task 1 (executing)
    t1 = asyncio.create_task(worker(1, 0.2))
    await asyncio.sleep(0.01)
    assert controller.active_count == 1
    assert controller.pending_count == 0

    # Launch task 2 & 3 (queued in pending)
    t2 = asyncio.create_task(worker(2, 0.1))
    t3 = asyncio.create_task(worker(3, 0.1))
    await asyncio.sleep(0.01)
    assert controller.active_count == 1
    assert controller.pending_count == 2

    # Launch task 4 -> Must be rejected immediately with AnalyticalOverloadError
    with pytest.raises(AnalyticalOverloadError) as exc_info:
        async with controller.acquire_ticket(timeout_seconds=1.0):
            pass

    assert exc_info.value.retry_after == 5

    await asyncio.gather(t1, t2, t3)
    assert controller.active_count == 0
    assert controller.pending_count == 0


@pytest.mark.asyncio
async def test_admission_controller_cancellation_cleans_up_queue() -> None:
    controller = AnalyticalAdmissionController(max_concurrent=1, max_pending=2)

    # Acquire active slot
    ticket = controller.acquire_ticket(timeout_seconds=5.0)
    await ticket.__aenter__()
    assert controller.active_count == 1

    # Task waiting in queue gets cancelled
    async def queued_worker() -> None:
        async with controller.acquire_ticket(timeout_seconds=5.0):
            pass

    t = asyncio.create_task(queued_worker())
    await asyncio.sleep(0.01)
    assert controller.pending_count == 1

    t.cancel()
    with pytest.raises(asyncio.CancelledError):
        await t

    # Ensure queue slot was decremented
    assert controller.pending_count == 0
    assert controller.active_count == 1

    await ticket.__aexit__(None, None, None)
    assert controller.active_count == 0


@pytest.mark.asyncio
async def test_admission_controller_queue_deadline_expiration() -> None:
    controller = AnalyticalAdmissionController(max_concurrent=1, max_pending=2)

    # Acquire active slot
    ticket = controller.acquire_ticket(timeout_seconds=5.0)
    await ticket.__aenter__()

    # Wait with a short timeout
    with pytest.raises(asyncio.TimeoutError):
        async with controller.acquire_ticket(timeout_seconds=0.05):
            pass

    assert controller.pending_count == 0
    assert controller.active_count == 1

    await ticket.__aexit__(None, None, None)
    assert controller.active_count == 0
