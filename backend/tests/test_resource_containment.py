"""Resource containment, deadlines, cancellation, and concurrency test suite.

Verifies:
- Monotonic request deadline enforcement across nodes
- Shared inference and correction budget enforcement (max LLM calls = 3, max corrections = 2)
- Concurrency limiting via asyncio.Semaphore
- Cancellation propagation and resource release
"""

import asyncio
import time
import uuid
from unittest.mock import AsyncMock, patch

import pytest
from app.analysis.contracts import (
    ColumnContext,
    DatasetAnalyticalContext,
)
from app.core.config import Settings
from app.orchestration.budgets import WorkflowBudgetTracker
from app.orchestration.service import OrchestrationService


@pytest.fixture
def test_dataset_context() -> DatasetAnalyticalContext:
    """Analytical context for resource testing."""
    return DatasetAnalyticalContext(
        relation_name="dataset",
        dataset_name="metrics_data",
        row_count=1000,
        column_count=2,
        columns=[
            ColumnContext(
                name="id",
                physical_type="int64",
                logical_type="dimension",
                nullable=False,
            ),
            ColumnContext(
                name="val",
                physical_type="float64",
                logical_type="metric",
                nullable=False,
            ),
        ],
    )


class TestResourceContainmentAndBudgets:
    """Verifies that orchestration respects budgets and deadlines without runaway executions."""

    def test_workflow_budget_tracker_timeout(self) -> None:
        """When elapsed time exceeds max_timeout_seconds, tracker reports timeout."""
        settings = Settings()
        tracker = WorkflowBudgetTracker(
            settings=settings,
            max_total_timeout_seconds=0.5,  # 500 milliseconds
            max_llm_calls=3,
            max_corrections=2,
        )
        assert tracker.is_timed_out() is False
        assert tracker.can_make_llm_call() is True

        time.sleep(0.55)
        assert tracker.is_timed_out() is True
        assert tracker.can_make_llm_call() is False
        assert tracker.can_attempt_correction() is False

    def test_workflow_budget_llm_call_limits(self) -> None:
        """Exceeding max LLM calls exhausts budget."""
        settings = Settings()
        tracker = WorkflowBudgetTracker(
            settings=settings,
            max_total_timeout_seconds=60.0,
            max_llm_calls=2,
            max_corrections=2,
        )
        assert tracker.can_make_llm_call() is True
        tracker.record_llm_call()
        assert tracker.can_make_llm_call() is True
        tracker.record_llm_call()
        assert tracker.can_make_llm_call() is False
        assert tracker.can_attempt_correction() is False

    def test_workflow_budget_step_limits(self) -> None:
        """Step counter increments and flags when max_steps is reached."""
        settings = Settings()
        tracker = WorkflowBudgetTracker(
            settings=settings,
            max_total_timeout_seconds=60.0,
            max_steps=3,
        )
        assert tracker.increment_step() is True
        assert tracker.increment_step() is True
        assert tracker.increment_step() is True
        assert tracker.increment_step() is False

    @pytest.mark.asyncio
    async def test_concurrency_semaphore_releases_on_exception(self) -> None:
        """If execution crashes or gets cancelled, admission ticket is released."""
        service = OrchestrationService(llm_provider=AsyncMock())
        initial_active = service.admission.active_count

        # Simulate task cancellation or error
        user_uuid = uuid.uuid4()
        with patch.object(
            service, "_execute_workflow_internal", side_effect=asyncio.CancelledError()
        ):
            with pytest.raises(asyncio.CancelledError):
                await service.execute_workflow(
                    dataset=AsyncMock(id="ds-1", owner_id=user_uuid),
                    question="test",
                    user_id=user_uuid,
                )

        # Admission ticket must be fully restored
        assert service.admission.active_count == initial_active
