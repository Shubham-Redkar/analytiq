"""CLI Runner for Reusable Analytical Model & Orchestration Evaluation Benchmark.

Provides reproducible, per-case evaluation with failure classification,
strict aggregation statistics, and machine-readable JSON reporting.
Supports both Direct M3 AnalysisService and M4 Multi-Agent Orchestration workflows.
"""

import argparse
import asyncio
import json
import logging
import math
import os
import sys
import tempfile
import time
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pyarrow.parquet as pq
from app.analysis.benchmark import (
    BENCHMARK_CASES,
    BENCHMARK_VERSION,
    HOLDOUT_BENCHMARK_CASES,
    create_benchmark_synthetic_dataset,
)
from app.analysis.orchestration_benchmark import ORCHESTRATION_BENCHMARK_CASES
from app.analysis.prompts import PROMPT_VERSION
from app.analysis.service import AnalysisService
from app.core.config import get_settings
from app.llm.contracts import LLMProvider
from app.llm.factory import create_llm_provider
from app.models.dataset import Dataset
from app.orchestration.service import OrchestrationService

logger = logging.getLogger(__name__)


def classify_failure(
    expected_status: str,
    actual_status: str,
    validator_passed: bool,
    error_message: str | None,
) -> str:
    """Classify failure mode deterministically into a machine-readable category."""
    if actual_status == "needs_clarification" and expected_status != "needs_clarification":
        return "incorrect_clarification"
    if actual_status != "needs_clarification" and expected_status == "needs_clarification":
        return "missing_clarification"
    if actual_status == "unsupported" and expected_status != "unsupported":
        return "unsupported_request_misclassification"
    if actual_status in ("query_rejected", "prohibited", "validation_rejected"):
        if expected_status in ("unsupported", "prohibited_statement", "unauthorized_relation"):
            return "security_policy_enforced"
        return "sql_validation_rejection"
    if actual_status == "execution_error":
        return "sql_execution_failure"
    if actual_status == "timeout":
        return "provider_or_execution_timeout"
    if actual_status == "completed" and not validator_passed:
        return "incorrect_numerical_or_shape_result"
    if actual_status == "failed":
        return "internal_workflow_or_agent_failure"
    return "unexpected_status_discrepancy"


async def run_benchmark(
    provider_name: str = "ollama",
    model_name: str | None = None,
    suite: str = "all",
    mode: str = "direct",
    output_json: Path | None = None,
) -> dict[str, Any]:
    """Run evaluation cases against the requested LLM provider in direct or orchestration mode."""
    settings = get_settings()
    target_model = model_name or settings.llm_model

    print("=" * 80)
    print(f"ANALYTIQ EVALUATION BENCHMARK — MODE: {mode.upper()}")
    print(f"Benchmark Version: {BENCHMARK_VERSION} | Prompt Version: {PROMPT_VERSION}")
    print(f"Provider: {provider_name.upper()} | Target Model: {target_model}")
    print("=" * 80)

    # 1. Setup synthetic dataset in temp file
    table, schema_json = create_benchmark_synthetic_dataset()
    tf = tempfile.NamedTemporaryFile(suffix=".parquet", delete=False)
    pq.write_table(table, tf.name)
    parquet_path = Path(tf.name)

    dataset_id = uuid.uuid4()
    dataset = Dataset(
        id=dataset_id,
        owner_id=uuid.uuid4(),
        name="Benchmark Sales Dataset",
        original_filename="benchmark_sales.parquet",
        file_format="csv",
        file_size_bytes=os.path.getsize(parquet_path),
        storage_key=f"benchmark-{dataset_id}",
        row_count=table.num_rows,
        column_count=table.num_columns,
        status="ready",
        schema_json=schema_json,
    )

    # 2. Instantiate provider
    provider: LLMProvider = create_llm_provider(
        settings=settings,
        provider=provider_name,
        model=target_model,
    )

    # Verify health first
    health = await provider.health_check()
    if not health.available and provider_name != "mock":
        print(f"ERROR: LLM Provider '{provider_name}' is not ready: {health.error}")
        print("Benchmark aborted.")
        sys.exit(1)

    # 3. Instantiate Direct or Orchestration Service
    direct_service = None
    orch_service = None

    if mode == "orchestration":
        orch_service = OrchestrationService(
            llm_provider=provider,
            settings=settings,
        )
        orch_service.planner.model = target_model
        orch_service.supervisor.model = target_model
        orch_service.interpreter.model = target_model
        orch_service.storage.get_parquet_file_path = lambda did: parquet_path  # type: ignore[method-assign]
        orch_service.storage.resolve_raw_path = lambda p: parquet_path  # type: ignore[method-assign]
    else:
        direct_service = AnalysisService(
            llm_provider=provider,
            settings=settings,
        )
        direct_service.planner.model = target_model
        direct_service.storage.get_parquet_file_path = lambda did: parquet_path  # type: ignore[method-assign]
        direct_service.storage.resolve_raw_path = lambda p: parquet_path  # type: ignore[method-assign]

    if suite == "base":
        cases_to_run = BENCHMARK_CASES
    elif suite == "holdout":
        cases_to_run = HOLDOUT_BENCHMARK_CASES
    elif suite == "orchestration":
        cases_to_run = ORCHESTRATION_BENCHMARK_CASES
    else:
        cases_to_run = BENCHMARK_CASES + HOLDOUT_BENCHMARK_CASES

    case_records: list[dict[str, Any]] = []
    latencies: list[float] = []

    print(f"{'ID':<10} | {'Macro Category':<22} | {'Status':<18} | {'Latency':<8} | {'Result':<6}")
    print("-" * 80)

    for case in cases_to_run:
        suite_name = (
            "orchestration"
            if case.id.startswith("M4")
            else ("baseline" if case.id.startswith("TC") else "holdout")
        )
        t0 = time.perf_counter()

        if mode == "orchestration" and orch_service is not None:
            orch_res = await orch_service.execute_workflow(dataset, case.question, dataset.owner_id)
            res = orch_res.to_legacy_query_result()
        elif direct_service is not None:
            res = await direct_service.run_analysis(dataset, case.question)
        else:
            raise RuntimeError("No active analysis or orchestration service.")

        duration_s = time.perf_counter() - t0
        latencies.append(duration_s)

        # Evaluate correctness
        validator_passed = True
        status_matched = False

        if case.expected_status == "completed":
            status_matched = res.status == "completed"
            if status_matched and case.result_validator:
                validator_passed = case.result_validator(res.rows, res.executed_sql)
            passed = status_matched and validator_passed
        elif case.expected_status in (
            "unsupported",
            "prohibited_statement",
            "unauthorized_relation",
            "query_rejected",
        ):
            # Safe refusal check
            passed = res.status in (
                "unsupported",
                "query_rejected",
                "prohibited",
                "validation_rejected",
            )
            status_matched = passed
        else:
            passed = res.status == case.expected_status
            status_matched = passed

        failure_class = None
        if not passed:
            failure_class = classify_failure(
                expected_status=case.expected_status,
                actual_status=res.status,
                validator_passed=validator_passed,
                error_message=res.error_message or res.unsupported_reason,
            )

        status_str = f"{res.status}"
        res_tag = "PASS" if passed else "FAIL"
        line_out = (
            f"{case.id:<10} | {case.macro_category:<22} | "
            f"{status_str:<18} | {duration_s:>6.2f}s | {res_tag:<6}"
        )
        print(line_out)

        record = {
            "case_id": case.id,
            "suite": suite_name,
            "category": case.category,
            "macro_category": case.macro_category,
            "question": case.question,
            "expected_status": case.expected_status,
            "actual_status": res.status,
            "passed": passed,
            "status_matched": status_matched,
            "validator_passed": validator_passed,
            "failure_classification": failure_class,
            "latency_ms": round(duration_s * 1000, 2),
            "executed_sql": res.executed_sql,
            "rows_returned": res.returned_row_count,
            "error_message": res.error_message or res.unsupported_reason,
        }
        case_records.append(record)

    total_cases = len(case_records)
    passed_cases = sum(1 for r in case_records if r["passed"])
    pass_rate = (passed_cases / total_cases) * 100.0 if total_cases > 0 else 0.0

    latencies_sorted = sorted(latencies)
    mean_lat = sum(latencies) / total_cases if total_cases > 0 else 0.0

    def percentile(p: float) -> float:
        if not latencies_sorted:
            return 0.0
        idx = math.ceil(p * len(latencies_sorted)) - 1
        return latencies_sorted[max(0, min(idx, len(latencies_sorted) - 1))]

    p50_lat = percentile(0.50)
    p95_lat = percentile(0.95)

    macro_breakdown: dict[str, dict[str, int]] = {}
    for r in case_records:
        mc = r["macro_category"]
        if mc not in macro_breakdown:
            macro_breakdown[mc] = {"total": 0, "passed": 0}
        macro_breakdown[mc]["total"] += 1
        if r["passed"]:
            macro_breakdown[mc]["passed"] += 1

    summary = {
        "timestamp": datetime.now(UTC).isoformat(),
        "benchmark_version": BENCHMARK_VERSION,
        "prompt_version": PROMPT_VERSION,
        "mode": mode,
        "provider": provider_name,
        "model": target_model,
        "total_cases": total_cases,
        "passed_cases": passed_cases,
        "pass_rate_pct": round(pass_rate, 2),
        "mean_latency_ms": round(mean_lat * 1000, 2),
        "p50_latency_ms": round(p50_lat * 1000, 2),
        "p95_latency_ms": round(p95_lat * 1000, 2),
        "macro_category_breakdown": macro_breakdown,
        "cases": case_records,
    }

    print("=" * 80)
    print("BENCHMARK EXECUTION SUMMARY")
    print(f"Overall Pass Rate: {passed_cases}/{total_cases} ({pass_rate:.1f}%)")
    mean_str = f"{mean_lat * 1000:.1f}ms"
    p50_str = f"{p50_lat * 1000:.1f}ms"
    p95_str = f"{p95_lat * 1000:.1f}ms"
    print(f"Mean Latency: {mean_str} | P50: {p50_str} | P95: {p95_str}")
    print("-" * 80)
    print("MACRO CATEGORIES:")
    for mc, stats in macro_breakdown.items():
        pct = (stats["passed"] / stats["total"]) * 100.0 if stats["total"] else 0.0
        print(f"  {mc:<28}: {stats['passed']:>2}/{stats['total']:<2} ({pct:>5.1f}%)")
    print("=" * 80)

    if output_json is not None:
        output_json.parent.mkdir(parents=True, exist_ok=True)
        with open(output_json, "w", encoding="utf-8") as f:
            json.dump(summary, f, indent=2)
        print(f"Saved evaluation report to: {output_json}")

    # Cleanup temp file
    try:
        parquet_path.unlink(missing_ok=True)
    except Exception as ex:
        logger.debug("Failed to remove temp parquet benchmark file: %s", ex)

    await provider.close()
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="AnalytIQ Benchmark Runner")
    parser.add_argument("--provider", default="ollama", help="LLM provider name")
    parser.add_argument("--model", default=None, help="LLM model tag")
    suite_choices = ["all", "base", "holdout", "orchestration"]
    parser.add_argument("--suite", default="all", choices=suite_choices)
    parser.add_argument("--mode", default="direct", choices=["direct", "orchestration"])
    parser.add_argument("--output-json", default=None, help="Output JSON path")
    args = parser.parse_args()

    out_path = Path(args.output_json) if args.output_json else None
    asyncio.run(
        run_benchmark(
            provider_name=args.provider,
            model_name=args.model,
            suite=args.suite,
            mode=args.mode,
            output_json=out_path,
        )
    )


if __name__ == "__main__":
    main()
