"""Comprehensive end-to-end analytical query service for AnalytIQ."""

import asyncio
import logging
import time
import uuid
from typing import Any

from app.analysis.context_builder import build_dataset_context
from app.analysis.contracts import (
    AnalyticalQueryResult,
    AnalyticalResultColumn,
    PlanStatus,
    SQLValidationCategory,
)
from app.analysis.evidence import build_execution_evidence
from app.analysis.planner import AnalyticalPlanner
from app.analysis.prompts import PROMPT_VERSION
from app.analysis.query_executor import (
    QueryExecutionError,
    QueryResourceLimitError,
    QueryTimeoutError,
    RestrictedQueryExecutor,
)
from app.analysis.sql_validator import SQLSecurityValidator
from app.core.config import Settings, get_settings
from app.llm.contracts import LLMProvider
from app.llm.exceptions import LLMError
from app.models.dataset import Dataset
from app.services.storage import StorageService, storage_service

logger = logging.getLogger(__name__)


class AnalysisService:
    """Coordinates context building, planning, validation, execution, and evidence."""

    def __init__(
        self,
        llm_provider: LLMProvider,
        settings: Settings | None = None,
        storage_svc: StorageService | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.storage = storage_svc or storage_service
        self.llm_provider = llm_provider

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

        # Global concurrency semaphore per process
        self._concurrency_semaphore = asyncio.Semaphore(
            self.settings.analysis_max_concurrent_requests
        )

    async def run_analysis(
        self,
        dataset: Dataset,
        question: str,
    ) -> AnalyticalQueryResult:
        """Execute complete analytical query workflow."""
        start_time = time.perf_counter()
        request_id = str(uuid.uuid4())
        trimmed_question = question.strip()

        # Enforce concurrency boundary
        async with self._concurrency_semaphore:
            # 1. Dataset Lifecycle & Readiness Check
            if dataset.status != "ready":
                return AnalyticalQueryResult(
                    request_id=request_id,
                    dataset_id=dataset.id,
                    status="failed",
                    question=trimmed_question,
                    intent="Dataset not ready",
                    error_message=(
                        f"Dataset is currently in '{dataset.status}' status (must be 'ready')."
                    ),
                )

            # 2. Build Bounded Context
            try:
                context = build_dataset_context(dataset)
            except Exception as e:
                return AnalyticalQueryResult(
                    request_id=request_id,
                    dataset_id=dataset.id,
                    status="failed",
                    question=trimmed_question,
                    intent="Context construction",
                    error_message=f"Failed to build schema context: {e}",
                )

            # 3. Initial Analytical Planning
            correction_attempts = 0
            plan_meta: dict[str, Any] = {}
            try:
                plan, plan_meta = await self.planner.plan(trimmed_question, context)
            except LLMError as le:
                return AnalyticalQueryResult(
                    request_id=request_id,
                    dataset_id=dataset.id,
                    status="provider_unavailable"
                    if "unavailable" in le.__class__.__name__.lower()
                    else "generation_failed",
                    question=trimmed_question,
                    intent="Analytical planning",
                    error_message=le.message,
                )

            # 4. Handle Non-Executable Plans (Clarification / Unsupported)
            if plan.status == PlanStatus.NEEDS_CLARIFICATION:
                return AnalyticalQueryResult(
                    request_id=request_id,
                    dataset_id=dataset.id,
                    status="needs_clarification",
                    question=trimmed_question,
                    intent=plan.intent,
                    clarification_question=plan.clarification_question
                    or "Please clarify your question.",
                )

            if plan.status == PlanStatus.UNSUPPORTED:
                return AnalyticalQueryResult(
                    request_id=request_id,
                    dataset_id=dataset.id,
                    status="unsupported",
                    question=trimmed_question,
                    intent=plan.intent,
                    unsupported_reason=plan.unsupported_reason
                    or "This operation is not supported.",
                )

            proposed_sql = plan.sql or ""

            # 5. Deterministic SQL Validation & Security Policy
            val_result = self.validator.validate(proposed_sql, context)

            # 6. Bounded Correction Loop (at most analysis_max_correction_attempts)
            if (
                not val_result.is_valid
                and val_result.category
                in (
                    SQLValidationCategory.SYNTAX_ERROR,
                    SQLValidationCategory.UNKNOWN_COLUMN,
                )
                and self.settings.analysis_max_correction_attempts > 0
            ):
                correction_attempts += 1
                try:
                    corrected_plan, plan_meta = await self.planner.correct_plan(
                        trimmed_question,
                        context,
                        failed_sql=proposed_sql,
                        error_feedback=val_result.error_message
                        or "Invalid syntax or column reference.",
                    )
                    if corrected_plan.status == PlanStatus.READY and corrected_plan.sql:
                        proposed_sql = corrected_plan.sql
                        val_result = self.validator.validate(proposed_sql, context)
                except Exception as ce:
                    logger.warning("Correction attempt failed: %s", ce)

            # If still invalid, reject safely
            if not val_result.is_valid:
                return AnalyticalQueryResult(
                    request_id=request_id,
                    dataset_id=dataset.id,
                    status="query_rejected",
                    question=trimmed_question,
                    intent=plan.intent,
                    error_message=(
                        f"Query rejected ({val_result.category.value}): {val_result.error_message}"
                    ),
                )

            approved_sql = val_result.normalized_sql or proposed_sql

            # 7. Resolve Parquet Path
            try:
                parquet_path = self.storage.get_parquet_file_path(dataset.id)
            except Exception as se:
                return AnalyticalQueryResult(
                    request_id=request_id,
                    dataset_id=dataset.id,
                    status="failed",
                    question=trimmed_question,
                    intent=plan.intent,
                    error_message=f"Could not locate dataset parquet file: {se}",
                )

            # 8. Execute in Restricted DuckDB
            try:
                col_names, col_types, rows, query_duration_ms = await self.executor.execute_query(
                    parquet_path=parquet_path,
                    approved_sql=approved_sql,
                )
            except QueryTimeoutError as qte:
                return AnalyticalQueryResult(
                    request_id=request_id,
                    dataset_id=dataset.id,
                    status="execution_timed_out",
                    question=trimmed_question,
                    intent=plan.intent,
                    executed_sql=approved_sql,
                    error_message=str(qte),
                )
            except (QueryResourceLimitError, QueryExecutionError) as qee:
                return AnalyticalQueryResult(
                    request_id=request_id,
                    dataset_id=dataset.id,
                    status="execution_failed",
                    question=trimmed_question,
                    intent=plan.intent,
                    executed_sql=approved_sql,
                    error_message=str(qee),
                )

            total_duration_ms = (time.perf_counter() - start_time) * 1000.0

            # 9. Build Verifiable Execution Evidence
            is_truncated = len(rows) >= self.settings.analysis_max_result_rows
            token_usage = {
                "input_tokens": plan_meta.get("input_tokens"),
                "output_tokens": plan_meta.get("output_tokens"),
            }

            evidence = build_execution_evidence(
                dataset_id=dataset.id,
                schema_json=dataset.schema_json,
                executed_sql=approved_sql,
                columns=col_names,
                rows=rows,
                query_duration_ms=query_duration_ms,
                total_duration_ms=total_duration_ms,
                provider=plan_meta.get("provider", "unknown"),
                model=plan_meta.get("model", self.settings.llm_model),
                prompt_version=PROMPT_VERSION,
                truncated=is_truncated,
                correction_attempts=correction_attempts,
                token_usage=token_usage,
            )

            result_columns = [
                AnalyticalResultColumn(name=name, type=col_type)
                for name, col_type in zip(col_names, col_types, strict=False)
            ]

            return AnalyticalQueryResult(
                request_id=request_id,
                dataset_id=dataset.id,
                status="completed",
                question=trimmed_question,
                intent=plan.intent,
                executed_sql=approved_sql,
                columns=result_columns,
                rows=rows,
                returned_row_count=len(rows),
                total_row_count=dataset.row_count,
                truncated=is_truncated,
                evidence=evidence,
            )
