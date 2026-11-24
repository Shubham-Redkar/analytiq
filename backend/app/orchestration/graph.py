"""LangGraph StateGraph assembly for the AnalytIQ Multi-Agent Analytical Architecture."""

import logging
import time
from pathlib import Path
from typing import Any, cast

from langgraph.graph import END, StateGraph

from app.analysis.contracts import (
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
from app.core.config import Settings
from app.llm.contracts import LLMProvider
from app.orchestration.agents.clarification import ClarificationAgent
from app.orchestration.agents.interpreter import ResultInterpreterAgent
from app.orchestration.agents.supervisor import SupervisorAgent
from app.orchestration.budgets import WorkflowBudgetTracker
from app.orchestration.contracts import (
    IntentCategory,
    OrchestrationStatus,
    WorkflowNodeName,
)
from app.orchestration.grounding import ground_question_in_schema
from app.orchestration.state import WorkflowState
from app.orchestration.tracing import WorkflowTracer

logger = logging.getLogger(__name__)


def build_analytical_workflow_graph(
    llm_provider: LLMProvider,
    settings: Settings,
    supervisor: SupervisorAgent,
    clarification_agent: ClarificationAgent,
    planner: AnalyticalPlanner,
    validator: SQLSecurityValidator,
    executor: RestrictedQueryExecutor,
    interpreter: ResultInterpreterAgent,
    tracer: WorkflowTracer,
    budget: WorkflowBudgetTracker,
) -> Any:
    """Build and compile the LangGraph StateGraph workflow."""

    # -------------------------------------------------------------
    # Node Implementations
    # -------------------------------------------------------------

    async def supervisor_node(state: WorkflowState) -> dict[str, Any]:
        t0 = time.monotonic()
        budget.increment_step()
        question = state["question"]
        ctx = state["dataset_context"]

        intent, reason = await supervisor.classify_intent(question, ctx, budget)
        duration_ms = (time.monotonic() - t0) * 1000

        tracer.record(
            node=WorkflowNodeName.SUPERVISOR,
            action="classify_intent",
            duration_ms=duration_ms,
            details={"intent": intent.value, "reason": reason},
        )

        update: dict[str, Any] = {
            "intent": intent,
            "step_count": state.get("step_count", 0) + 1,
            "trace_events": tracer.get_events(),
        }
        if reason:
            update["unsupported_reason"] = reason
            if intent == IntentCategory.PROHIBITED:
                update["status"] = OrchestrationStatus.PROHIBITED
            elif intent == IntentCategory.UNSUPPORTED:
                update["status"] = OrchestrationStatus.UNSUPPORTED
        return update

    async def schema_grounding_node(state: WorkflowState) -> dict[str, Any]:
        t0 = time.monotonic()
        budget.increment_step()
        question = state["question"]
        ctx = state["dataset_context"]

        grounding = ground_question_in_schema(question, ctx)
        duration_ms = (time.monotonic() - t0) * 1000

        tracer.record(
            node=WorkflowNodeName.SCHEMA_GROUNDING,
            action="ground_schema",
            duration_ms=duration_ms,
            details={
                "is_grounded": grounding["is_grounded"],
                "ambiguity_detected": grounding["ambiguity_detected"],
                "ambiguity_type": grounding.get("ambiguity_type"),
            },
        )

        update: dict[str, Any] = {
            "grounding": grounding,
            "step_count": state.get("step_count", 0) + 1,
            "trace_events": tracer.get_events(),
        }

        if grounding["ambiguity_detected"]:
            update["status"] = OrchestrationStatus.NEEDS_CLARIFICATION
            update["intent"] = IntentCategory.NEEDS_CLARIFICATION

        return update

    async def clarification_node(state: WorkflowState) -> dict[str, Any]:
        t0 = time.monotonic()
        budget.increment_step()
        question = state["question"]
        ctx = state["dataset_context"]
        grounding = state.get("grounding")
        if not grounding:
            grounding = ground_question_in_schema(question, ctx)

        clarification_out = clarification_agent.formulate_clarification(question, ctx, grounding)
        duration_ms = (time.monotonic() - t0) * 1000

        tracer.record(
            node=WorkflowNodeName.CLARIFICATION,
            action="formulate_clarification",
            duration_ms=duration_ms,
            details={
                "clarification_type": clarification_out.clarification_type.value,
                "options_count": len(clarification_out.options),
            },
        )

        return {
            "clarification": clarification_out,
            "status": OrchestrationStatus.NEEDS_CLARIFICATION,
            "step_count": state.get("step_count", 0) + 1,
            "trace_events": tracer.get_events(),
        }

    async def planner_node(state: WorkflowState) -> dict[str, Any]:
        t0 = time.monotonic()
        budget.increment_step()
        question = state["question"]
        ctx = state["dataset_context"]

        validation_result = state.get("validation_result")
        feedback = None
        if validation_result and not validation_result.is_valid:
            feedback = (
                f"Previous query was rejected: {validation_result.error_message}. "
                "Please generate a compliant read-only DuckDB SQL query."
            )

        if not budget.can_make_llm_call():
            tracer.record(
                node=WorkflowNodeName.PLANNER,
                action="plan_aborted_budget",
                duration_ms=0.0,
                status="budget_exceeded",
            )
            return {
                "status": OrchestrationStatus.TIMEOUT
                if budget.is_timed_out()
                else OrchestrationStatus.FAILED,
                "error_message": "LLM call budget or request deadline exceeded.",
                "trace_events": tracer.get_events(),
            }

        budget.record_llm_call()
        try:
            curr_plan = state.get("plan")
            if feedback and curr_plan and curr_plan.sql:
                plan, _meta = await planner.correct_plan(
                    question=question,
                    context=ctx,
                    failed_sql=curr_plan.sql,
                    error_feedback=feedback,
                )
            else:
                plan, _meta = await planner.plan(
                    question=question,
                    context=ctx,
                )
        except Exception as e:
            duration_ms = (time.monotonic() - t0) * 1000
            tracer.record(
                node=WorkflowNodeName.PLANNER,
                action="generate_plan_error",
                duration_ms=duration_ms,
                status="error",
                details={"error": str(e)},
            )
            return {
                "status": OrchestrationStatus.FAILED,
                "error_message": f"Analytical planner failed: {e}",
                "trace_events": tracer.get_events(),
            }

        duration_ms = (time.monotonic() - t0) * 1000
        tracer.record(
            node=WorkflowNodeName.PLANNER,
            action="generate_plan",
            duration_ms=duration_ms,
            llm_called=True,
            details={"plan_status": plan.status.value, "has_sql": bool(plan.sql)},
        )

        update: dict[str, Any] = {
            "plan": plan,
            "llm_call_count": state.get("llm_call_count", 0) + 1,
            "step_count": state.get("step_count", 0) + 1,
            "trace_events": tracer.get_events(),
        }

        if plan.status == PlanStatus.NEEDS_CLARIFICATION:
            update["status"] = OrchestrationStatus.NEEDS_CLARIFICATION
        elif plan.status == PlanStatus.UNSUPPORTED:
            update["status"] = OrchestrationStatus.UNSUPPORTED
            update["unsupported_reason"] = (
                plan.unsupported_reason or "The requested analysis is unsupported."
            )

        return update

    async def validator_node(state: WorkflowState) -> dict[str, Any]:
        t0 = time.monotonic()
        budget.increment_step()
        plan = state.get("plan")
        ctx = state["dataset_context"]

        if not plan or not plan.sql:
            return {
                "status": OrchestrationStatus.FAILED,
                "error_message": "No analytical SQL provided for validation.",
                "trace_events": tracer.get_events(),
            }

        val_result = validator.validate(sql=plan.sql, context=ctx)
        duration_ms = (time.monotonic() - t0) * 1000

        tracer.record(
            node=WorkflowNodeName.VALIDATOR,
            action="validate_sql",
            duration_ms=duration_ms,
            status="valid" if val_result.is_valid else "invalid",
            details={
                "category": val_result.category.value,
                "is_valid": val_result.is_valid,
                "error": val_result.error_message,
            },
        )

        update: dict[str, Any] = {
            "validation_result": val_result,
            "step_count": state.get("step_count", 0) + 1,
            "trace_events": tracer.get_events(),
        }

        if val_result.is_valid:
            update["validated_sql"] = val_result.normalized_sql or plan.sql
        else:
            update["status"] = OrchestrationStatus.VALIDATION_REJECTED
            update["error_message"] = val_result.error_message

        return update

    async def executor_node(state: WorkflowState) -> dict[str, Any]:
        t0 = time.monotonic()
        budget.increment_step()
        sql = state.get("validated_sql")
        parquet_path_str = state["dataset_parquet_path"]
        ctx = state["dataset_context"]
        dataset_id = state["dataset_id"]

        if not sql:
            return {
                "status": OrchestrationStatus.FAILED,
                "error_message": "No validated SQL available for execution.",
                "trace_events": tracer.get_events(),
            }

        remaining_time = min(settings.analysis_query_timeout_seconds, budget.remaining_seconds)
        if remaining_time <= 0.5:
            return {
                "status": OrchestrationStatus.TIMEOUT,
                "error_message": "Request deadline exceeded prior to query execution.",
                "trace_events": tracer.get_events(),
            }

        try:
            (
                col_names,
                col_types,
                rows,
                query_duration_ms,
                is_truncated,
            ) = await executor.execute_query(
                parquet_path=Path(parquet_path_str),
                approved_sql=sql,
                timeout_seconds=remaining_time,
            )
            duration_ms = (time.monotonic() - t0) * 1000

            col_defs = [
                AnalyticalResultColumn(name=col_names[i], type=col_types[i])
                for i in range(len(col_names))
            ]

            # Build execution evidence
            import uuid as uuid_mod

            d_id = uuid_mod.UUID(dataset_id) if isinstance(dataset_id, str) else dataset_id

            evidence = build_execution_evidence(
                dataset_id=d_id,
                schema_json=None,
                executed_sql=sql,
                columns=col_names,
                rows=rows,
                query_duration_ms=query_duration_ms,
                total_duration_ms=duration_ms,
                provider=settings.llm_provider,
                model=settings.llm_model,
                prompt_version=PROMPT_VERSION,
                dataset_row_count=ctx.row_count,
                truncated=is_truncated,
                correction_attempts=state.get("correction_count", 0),
            )

            tracer.record(
                node=WorkflowNodeName.EXECUTOR,
                action="execute_query",
                duration_ms=duration_ms,
                status="success",
                details={
                    "returned_rows": len(rows),
                    "truncated": is_truncated,
                },
            )

            return {
                "query_columns": col_defs,
                "query_rows": rows,
                "returned_row_count": len(rows),
                "dataset_row_count": ctx.row_count,
                "total_row_count": len(rows),
                "truncated": is_truncated,
                "evidence": evidence,
                "status": OrchestrationStatus.COMPLETED,
                "step_count": state.get("step_count", 0) + 1,
                "trace_events": tracer.get_events(),
            }

        except QueryTimeoutError as e:
            duration_ms = (time.monotonic() - t0) * 1000
            tracer.record(
                node=WorkflowNodeName.EXECUTOR,
                action="execute_timeout",
                duration_ms=duration_ms,
                status="timeout",
                details={"error": str(e)},
            )
            return {
                "status": OrchestrationStatus.TIMEOUT,
                "error_message": str(e),
                "trace_events": tracer.get_events(),
            }
        except QueryResourceLimitError as e:
            duration_ms = (time.monotonic() - t0) * 1000
            tracer.record(
                node=WorkflowNodeName.EXECUTOR,
                action="execute_resource_limit",
                duration_ms=duration_ms,
                status="resource_limit_exceeded",
                details={"error": str(e)},
            )
            return {
                "status": OrchestrationStatus.FAILED,
                "error_message": str(e),
                "trace_events": tracer.get_events(),
            }
        except (QueryExecutionError, Exception) as e:
            duration_ms = (time.monotonic() - t0) * 1000
            tracer.record(
                node=WorkflowNodeName.EXECUTOR,
                action="execute_error",
                duration_ms=duration_ms,
                status="error",
                details={"error": str(e)},
            )
            return {
                "status": OrchestrationStatus.FAILED,
                "error_message": str(e),
                "trace_events": tracer.get_events(),
            }

    async def interpreter_node(state: WorkflowState) -> dict[str, Any]:
        t0 = time.monotonic()
        budget.increment_step()
        question = state["question"]
        columns = state.get("query_columns", [])
        rows = state.get("query_rows", [])
        evidence = state.get("evidence")

        interpretation = await interpreter.interpret(
            question=question,
            columns=columns,
            rows=rows,
            evidence=evidence,
            budget=budget,
        )
        duration_ms = (time.monotonic() - t0) * 1000

        tracer.record(
            node=WorkflowNodeName.INTERPRETER,
            action="interpret_results",
            duration_ms=duration_ms,
            details={
                "is_fallback": interpretation.is_fallback,
                "findings_count": len(interpretation.key_findings),
            },
        )

        return {
            "interpretation": interpretation,
            "step_count": state.get("step_count", 0) + 1,
            "trace_events": tracer.get_events(),
        }

    async def refusal_node(state: WorkflowState) -> dict[str, Any]:
        time.monotonic()
        budget.increment_step()
        reason = (
            state.get("unsupported_reason") or state.get("error_message") or "Operation refused."
        )
        tracer.record(
            node=WorkflowNodeName.REFUSAL,
            action="refusal",
            duration_ms=0.5,
            details={"reason": reason},
        )
        return {
            "step_count": state.get("step_count", 0) + 1,
            "trace_events": tracer.get_events(),
        }

    # -------------------------------------------------------------
    # Conditional Edges & Routing
    # -------------------------------------------------------------

    def route_after_supervisor(state: WorkflowState) -> str:
        intent = state.get("intent")
        if intent in (IntentCategory.PROHIBITED, IntentCategory.UNSUPPORTED):
            return WorkflowNodeName.REFUSAL.value
        return WorkflowNodeName.SCHEMA_GROUNDING.value

    def route_after_grounding(state: WorkflowState) -> str:
        grounding = state.get("grounding", {})
        if grounding.get("ambiguity_detected"):
            return WorkflowNodeName.CLARIFICATION.value
        return WorkflowNodeName.PLANNER.value

    def route_after_planner(state: WorkflowState) -> str:
        plan = state.get("plan")
        if not plan:
            return END
        if plan.status == PlanStatus.NEEDS_CLARIFICATION:
            return WorkflowNodeName.CLARIFICATION.value
        if plan.status == PlanStatus.UNSUPPORTED:
            return WorkflowNodeName.REFUSAL.value
        if plan.status == PlanStatus.READY and plan.sql:
            return WorkflowNodeName.VALIDATOR.value
        return END

    def route_after_validator(state: WorkflowState) -> str:
        val_result = state.get("validation_result")
        if not val_result:
            return END
        if val_result.is_valid:
            return WorkflowNodeName.EXECUTOR.value

        eligible_for_correction = val_result.category in (
            SQLValidationCategory.SYNTAX_ERROR,
            SQLValidationCategory.UNKNOWN_COLUMN,
            SQLValidationCategory.UNAPPROVED_FUNCTION,
        )
        if eligible_for_correction and budget.can_attempt_correction():
            budget.record_correction()
            logger.info("Validator rejected query; routing back to Planner for bounded correction.")
            return WorkflowNodeName.PLANNER.value

        if val_result.category in (
            SQLValidationCategory.PROHIBITED_STATEMENT,
            SQLValidationCategory.UNAUTHORIZED_RELATION,
        ):
            return WorkflowNodeName.REFUSAL.value

        return END

    def route_after_executor(state: WorkflowState) -> str:
        status = state.get("status")
        if status == OrchestrationStatus.COMPLETED:
            return WorkflowNodeName.INTERPRETER.value
        return END

    # -------------------------------------------------------------
    # StateGraph Construction
    # -------------------------------------------------------------

    # Note: cast to Any resolves IDE language server (Pyrefly/Pylance) strict
    # protocol bound check against LangGraph's internal StateLike union.
    workflow = StateGraph(cast(Any, WorkflowState))

    workflow.add_node(WorkflowNodeName.SUPERVISOR.value, supervisor_node)
    workflow.add_node(WorkflowNodeName.SCHEMA_GROUNDING.value, schema_grounding_node)
    workflow.add_node(WorkflowNodeName.CLARIFICATION.value, clarification_node)
    workflow.add_node(WorkflowNodeName.PLANNER.value, planner_node)
    workflow.add_node(WorkflowNodeName.VALIDATOR.value, validator_node)
    workflow.add_node(WorkflowNodeName.EXECUTOR.value, executor_node)
    workflow.add_node(WorkflowNodeName.INTERPRETER.value, interpreter_node)
    workflow.add_node(WorkflowNodeName.REFUSAL.value, refusal_node)

    workflow.set_entry_point(WorkflowNodeName.SUPERVISOR.value)

    workflow.add_conditional_edges(
        WorkflowNodeName.SUPERVISOR.value,
        route_after_supervisor,
        {
            WorkflowNodeName.REFUSAL.value: WorkflowNodeName.REFUSAL.value,
            WorkflowNodeName.SCHEMA_GROUNDING.value: WorkflowNodeName.SCHEMA_GROUNDING.value,
        },
    )

    workflow.add_conditional_edges(
        WorkflowNodeName.SCHEMA_GROUNDING.value,
        route_after_grounding,
        {
            WorkflowNodeName.CLARIFICATION.value: WorkflowNodeName.CLARIFICATION.value,
            WorkflowNodeName.PLANNER.value: WorkflowNodeName.PLANNER.value,
        },
    )

    workflow.add_edge(WorkflowNodeName.CLARIFICATION.value, END)

    workflow.add_conditional_edges(
        WorkflowNodeName.PLANNER.value,
        route_after_planner,
        {
            WorkflowNodeName.CLARIFICATION.value: WorkflowNodeName.CLARIFICATION.value,
            WorkflowNodeName.REFUSAL.value: WorkflowNodeName.REFUSAL.value,
            WorkflowNodeName.VALIDATOR.value: WorkflowNodeName.VALIDATOR.value,
            END: END,
        },
    )

    workflow.add_conditional_edges(
        WorkflowNodeName.VALIDATOR.value,
        route_after_validator,
        {
            WorkflowNodeName.EXECUTOR.value: WorkflowNodeName.EXECUTOR.value,
            WorkflowNodeName.PLANNER.value: WorkflowNodeName.PLANNER.value,
            WorkflowNodeName.REFUSAL.value: WorkflowNodeName.REFUSAL.value,
            END: END,
        },
    )

    workflow.add_conditional_edges(
        WorkflowNodeName.EXECUTOR.value,
        route_after_executor,
        {
            WorkflowNodeName.INTERPRETER.value: WorkflowNodeName.INTERPRETER.value,
            END: END,
        },
    )

    workflow.add_edge(WorkflowNodeName.INTERPRETER.value, END)
    workflow.add_edge(WorkflowNodeName.REFUSAL.value, END)

    return workflow.compile()
