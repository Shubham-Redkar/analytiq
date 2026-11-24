"""CLI Runner for the Reusable Analytical Model Evaluation Benchmark.

Provides reproducible, per-case model evaluation with failure classification,
strict aggregation statistics, and machine-readable JSON reporting.
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
from app.analysis.prompts import PROMPT_VERSION
from app.analysis.service import AnalysisService
from app.core.config import get_settings
from app.llm.contracts import LLMProvider
from app.llm.factory import create_llm_provider
from app.models.dataset import Dataset

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
    if actual_status == "query_rejected":
        if expected_status in ("unsupported", "prohibited_statement", "unauthorized_relation"):
            return "security_policy_enforced"
        return "sql_validation_rejection"
    if actual_status == "execution_error":
        return "sql_execution_failure"
    if actual_status == "timeout":
        return "provider_or_execution_timeout"
    if actual_status == "completed" and not validator_passed:
        return "incorrect_numerical_or_shape_result"
    return "unexpected_application_failure"


async def run_benchmark(
    provider_name: str = "ollama",
    model_name: str | None = None,
    suite: str = "all",
    output_json: Path | None = None,
) -> dict[str, Any]:
    """Run all benchmark cases against the requested LLM provider."""
    settings = get_settings()
    target_model = model_name or settings.llm_model

    print("=" * 80)
    print("ANALYTIQ M3.1 ANALYTICAL EVALUATION BENCHMARK")
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

    # 2. Instantiate provider and service
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

    service = AnalysisService(
        llm_provider=provider,
        settings=settings,
    )
    # Ensure planner uses the target model rather than settings default
    service.planner.model = target_model
    # Redirect parquet lookup to our temporary benchmark file
    service.storage.get_parquet_file_path = lambda did: parquet_path  # type: ignore[method-assign]

    if suite == "base":
        cases_to_run = BENCHMARK_CASES
    elif suite == "holdout":
        cases_to_run = HOLDOUT_BENCHMARK_CASES
    else:
        cases_to_run = BENCHMARK_CASES + HOLDOUT_BENCHMARK_CASES

    case_records: list[dict[str, Any]] = []
    latencies: list[float] = []

    print(f"{'ID':<7} | {'Macro Category':<24} | {'Status':<18} | {'Latency':<8} | {'Result':<6}")
    print("-" * 80)

    for case in cases_to_run:
        suite_name = "baseline" if case.id.startswith("TC") else "holdout"
        t0 = time.perf_counter()
        res = await service.run_analysis(dataset, case.question)
        dur_ms = (time.perf_counter() - t0) * 1000.0
        latencies.append(dur_ms)

        status_matches = res.status == case.expected_status
        validator_passes = True
        if case.result_validator is not None:
            validator_passes = case.result_validator(res.rows, res.error_message)

        is_success = status_matches and validator_passes
        outcome = "PASS" if is_success else "FAIL"
        failure_reason = (
            None
            if is_success
            else classify_failure(
                case.expected_status, res.status, validator_passes, res.error_message
            )
        )

        print(
            f"{case.id:<7} | {case.macro_category[:24]:<24} | {res.status:<18} | "
            f"{dur_ms:>6.1f}ms | {outcome:<6}"
        )

        record: dict[str, Any] = {
            "id": case.id,
            "suite": suite_name,
            "category": case.category,
            "macro_category": case.macro_category,
            "question": case.question,
            "expected_status": case.expected_status,
            "actual_status": res.status,
            "validator_passed": validator_passes,
            "executed_sql": res.executed_sql,
            "row_count": len(res.rows) if res.rows is not None else 0,
            "sample_rows": res.rows[:3] if res.rows is not None else None,
            "latency_ms": round(dur_ms, 1),
            "outcome": outcome,
            "failure_reason": failure_reason,
            "error_message": res.error_message,
        }
        case_records.append(record)

    # 3. Derive strictly consistent aggregation statistics from individual records
    total_cases = len(case_records)
    passed_cases = sum(1 for r in case_records if r["outcome"] == "PASS")
    failed_cases = sum(1 for r in case_records if r["outcome"] == "FAIL")

    base_cases = [r for r in case_records if r["suite"] == "baseline"]
    base_passed = sum(1 for r in base_cases if r["outcome"] == "PASS")
    hold_cases = [r for r in case_records if r["suite"] == "holdout"]
    hold_passed = sum(1 for r in hold_cases if r["outcome"] == "PASS")

    # Macro category aggregation (mutually exclusive partition)
    macro_categories = sorted({r["macro_category"] for r in case_records})
    macro_breakdown: dict[str, dict[str, int]] = {}
    for mc in macro_categories:
        mc_records = [r for r in case_records if r["macro_category"] == mc]
        mc_passed = sum(1 for r in mc_records if r["outcome"] == "PASS")
        macro_breakdown[mc] = {
            "total": len(mc_records),
            "passed": mc_passed,
            "failed": len(mc_records) - mc_passed,
        }

    # Failure classifications breakdown
    failed_records = [r for r in case_records if r["outcome"] == "FAIL"]
    failure_breakdown: dict[str, int] = {}
    for r in failed_records:
        reason = r["failure_reason"] or "unclassified"
        failure_breakdown[reason] = failure_breakdown.get(reason, 0) + 1

    sorted_latencies = sorted(latencies)
    mean_latency = sum(latencies) / len(latencies) if latencies else 0.0
    median_latency = sorted_latencies[len(sorted_latencies) // 2] if sorted_latencies else 0.0
    p95_index = min(math.ceil(0.95 * len(sorted_latencies)) - 1, len(sorted_latencies) - 1)
    p95_latency = sorted_latencies[p95_index] if sorted_latencies else 0.0

    # Strict check: macro breakdown sum must equal total cases
    assert sum(d["total"] for d in macro_breakdown.values()) == total_cases
    assert sum(d["passed"] for d in macro_breakdown.values()) == passed_cases
    assert sum(d["failed"] for d in macro_breakdown.values()) == failed_cases

    base_pct = round((base_passed / len(base_cases)) * 100.0, 1) if base_cases else 0.0
    hold_pct = round((hold_passed / len(hold_cases)) * 100.0, 1) if hold_cases else 0.0
    overall_pct = round((passed_cases / total_cases) * 100.0, 1) if total_cases else 0.0

    summary: dict[str, Any] = {
        "benchmark_version": BENCHMARK_VERSION,
        "prompt_version": PROMPT_VERSION,
        "provider": provider_name,
        "model": target_model,
        "timestamp": datetime.now(UTC).isoformat(),
        "total_cases": total_cases,
        "passed_cases": passed_cases,
        "failed_cases": failed_cases,
        "accuracy_pct": overall_pct,
        "baseline": {
            "total": len(base_cases),
            "passed": base_passed,
            "accuracy_pct": base_pct,
        },
        "holdout": {
            "total": len(hold_cases),
            "passed": hold_passed,
            "accuracy_pct": hold_pct,
        },
        "latency_ms": {
            "mean": round(mean_latency, 1),
            "median": round(median_latency, 1),
            "p95": round(p95_latency, 1),
        },
        "macro_categories": macro_breakdown,
        "failure_modes": failure_breakdown,
        "failed_case_ids": [r["id"] for r in failed_records],
        "case_records": case_records,
    }

    print("=" * 80)
    print(f"TOTAL CASES: {total_cases} | PASSED: {passed_cases} | FAILED: {failed_cases}")
    print(
        f"OVERALL ACCURACY: {overall_pct}% | "
        f"BASELINE: {base_passed}/{len(base_cases)} ({base_pct}%) | "
        f"HOLDOUT: {hold_passed}/{len(hold_cases)} ({hold_pct}%)"
    )
    print(
        f"LATENCY: Mean={round(mean_latency, 1)}ms | "
        f"Median={round(median_latency, 1)}ms | "
        f"P95={round(p95_latency, 1)}ms"
    )
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
    parser.add_argument("--suite", default="all", choices=["all", "base", "holdout"])
    parser.add_argument("--output-json", default=None, help="Output JSON path")
    args = parser.parse_args()

    out_path = Path(args.output_json) if args.output_json else None
    asyncio.run(
        run_benchmark(
            provider_name=args.provider,
            model_name=args.model,
            suite=args.suite,
            output_json=out_path,
        )
    )


if __name__ == "__main__":
    main()
