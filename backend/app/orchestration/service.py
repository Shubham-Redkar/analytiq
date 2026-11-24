"""High-level Orchestration Service coordinating LangGraph execution."""

import asyncio
import logging
import time
import uuid

from app.analysis.context_builder import build_dataset_context
from app.analysis.planner import AnalyticalPlanner
from app.analysis.query_executor import RestrictedQueryExecutor
from app.analysis.sql_validator import SQLSecurityValidator
from app.core.config import Settings, get_settings
from app.llm.contracts import LLMProvider
from app.models.dataset import Dataset
from app.orchestration.agents.clarification import ClarificationAgent
from app.orchestration.agents.interpreter import ResultInterpreterAgent
from app.orchestration.agents.supervisor import SupervisorAgent
from app.orchestration.budgets import WorkflowBudgetTracker
from app.orchestration.contracts import (
    IntentCategory,
    OrchestrationResult,
    OrchestrationStatus,
)
from app.orchestration.graph import build_analytical_workflow_graph
from app.orchestration.state import WorkflowState
from app.orchestration.tracing import WorkflowTracer
from app.services.storage import StorageService, storage_service

logger = logging.getLogger(__name__)


class OrchestrationService:
    """Manages the lifecycle and execution of LangGraph multi-agent analytical workflows."""

    def __init__(
        self,
        llm_provider: LLMProvider,
        settings: Settings | None = None,
        storage_svc: StorageService | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.storage = storage_svc or storage_service
        self.llm_provider = llm_provider

        # Sub-agents and deterministic tools
        self.supervisor = SupervisorAgent(
            provider=self.llm_provider,
            model=self.settings.llm_model,
            temperature=self.settings.llm_temperature,
            timeout_seconds=self.settings.llm_request_timeout_seconds,
        )
        self.clarification_agent = ClarificationAgent()
        self.planner = AnalyticalPlanner(
            provider=self.llm_provider,
            model=self.settings.llm_model,
            temperature=self.settings.llm_temperature,
            max_tokens=self.settings.llm_max_output_tokens,
            timeout_seconds=self.settings.llm_request_timeout_seconds,
        )
        self.validator = SQLSecurityValidator(
            max_result_rows=self.settings.analysis_max_result_rows,
        )
        self.executor = RestrictedQueryExecutor(
            memory_limit=self.settings.analysis_duckdb_memory_limit,
            threads=self.settings.analysis_duckdb_threads,
            query_timeout_seconds=self.settings.analysis_query_timeout_seconds,
            max_result_rows=self.settings.analysis_max_result_rows,
            max_result_bytes=self.settings.analysis_max_result_bytes,
        )
        self.interpreter = ResultInterpreterAgent(
            provider=self.llm_provider,
            model=self.settings.llm_model,
            temperature=self.settings.llm_temperature,
            timeout_seconds=self.settings.llm_request_timeout_seconds,
        )

    async def execute_workflow(
        self,
        dataset: Dataset,
        question: str,
        user_id: uuid.UUID,
        request_id: str | None = None,
    ) -> OrchestrationResult:
        """Run the end-to-end multi-agent LangGraph workflow."""
        req_id = request_id or str(uuid.uuid4())
        start_time = time.monotonic()

        # 1. Initialize budget tracker and event tracer
        budget = WorkflowBudgetTracker(
            settings=self.settings,
            max_total_timeout_seconds=self.settings.llm_request_timeout_seconds * 1.5,
            max_llm_calls=5,
            max_corrections=self.settings.analysis_max_correction_attempts + 1,
        )
        tracer = WorkflowTracer(max_events=50)

        # 2. Resolve dataset parquet path and build context
        try:
            parquet_path = self.storage.get_parquet_file_path(dataset.id)
        except Exception:
            parquet_path = self.storage.get_parquet_dir(dataset.id) / "data.parquet"

        context = build_dataset_context(dataset=dataset)

        # 3. Compile LangGraph workflow
        compiled_graph = build_analytical_workflow_graph(
            llm_provider=self.llm_provider,
            settings=self.settings,
            supervisor=self.supervisor,
            clarification_agent=self.clarification_agent,
            planner=self.planner,
            validator=self.validator,
            executor=self.executor,
            interpreter=self.interpreter,
            tracer=tracer,
            budget=budget,
        )

        initial_state: WorkflowState = {
            "request_id": req_id,
            "dataset_id": str(dataset.id),
            "user_id": str(user_id),
            "question": question,
            "dataset_context": context,
            "dataset_parquet_path": str(parquet_path),
            "status": OrchestrationStatus.COMPLETED,
            "intent": IntentCategory.ANALYTICAL_QUERY,
            "step_count": 0,
            "llm_call_count": 0,
            "correction_count": 0,
            "total_start_monotonic": start_time,
            "deadline_monotonic": start_time + budget.max_timeout_seconds,
            "timed_out": False,
            "error_message": None,
            "unsupported_reason": None,
            "query_columns": [],
            "query_rows": [],
            "returned_row_count": 0,
            "dataset_row_count": context.row_count,
            "total_row_count": None,
            "truncated": False,
            "trace_events": [],
        }

        # 4. Execute graph asynchronously with deadline guard
        try:
            final_state = await asyncio.wait_for(
                compiled_graph.ainvoke(initial_state),
                timeout=budget.remaining_seconds,
            )
        except TimeoutError:
            tracer.record(
                node="workflow",
                action="workflow_timeout",
                duration_ms=(time.monotonic() - start_time) * 1000,
                status="timeout",
            )
            return OrchestrationResult(
                request_id=req_id,
                dataset_id=dataset.id,
                status=OrchestrationStatus.TIMEOUT,
                question=question,
                intent="Analytical query timed out.",
                error_message="Workflow execution exceeded configured deadline.",
                trace_events=tracer.get_events(),
                total_duration_ms=round((time.monotonic() - start_time) * 1000, 2),
            )
        except Exception as e:
            logger.exception("Unexpected LangGraph execution error: %s", e)
            return OrchestrationResult(
                request_id=req_id,
                dataset_id=dataset.id,
                status=OrchestrationStatus.FAILED,
                question=question,
                intent="Analytical query failed.",
                error_message=f"Workflow failed: {e}",
                trace_events=tracer.get_events(),
                total_duration_ms=round((time.monotonic() - start_time) * 1000, 2),
            )

        total_duration_ms = round((time.monotonic() - start_time) * 1000, 2)
        final_status = final_state.get("status", OrchestrationStatus.COMPLETED)
        plan = final_state.get("plan")
        intent_desc = (
            plan.intent
            if plan
            else (final_state.get("unsupported_reason") or "Analytical query processing")
        )

        return OrchestrationResult(
            request_id=req_id,
            dataset_id=dataset.id,
            status=final_status,
            question=question,
            intent=intent_desc,
            clarification=final_state.get("clarification"),
            interpretation=final_state.get("interpretation"),
            executed_sql=final_state.get("validated_sql"),
            columns=final_state.get("query_columns", []),
            rows=final_state.get("query_rows", []),
            returned_row_count=final_state.get("returned_row_count", 0),
            dataset_row_count=final_state.get("dataset_row_count"),
            total_row_count=final_state.get("total_row_count"),
            truncated=final_state.get("truncated", False),
            unsupported_reason=final_state.get("unsupported_reason"),
            error_message=final_state.get("error_message"),
            evidence=final_state.get("evidence"),
            trace_events=final_state.get("trace_events", tracer.get_events()),
            total_llm_calls=budget.llm_call_count,
            correction_attempts=budget.correction_count,
            total_duration_ms=total_duration_ms,
        )
