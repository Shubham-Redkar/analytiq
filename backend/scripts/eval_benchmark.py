"""CLI Runner for the Reusable Analytical Model Evaluation Benchmark."""

import asyncio
import logging
import os
import sys
import tempfile
import time
import uuid
from pathlib import Path
from typing import Any

import pyarrow.parquet as pq
from app.analysis.benchmark import (
    BENCHMARK_CASES,
    HOLDOUT_BENCHMARK_CASES,
    create_benchmark_synthetic_dataset,
)
from app.analysis.service import AnalysisService
from app.core.config import get_settings
from app.llm.contracts import LLMProvider
from app.llm.factory import create_llm_provider
from app.models.dataset import Dataset

logger = logging.getLogger(__name__)


async def run_benchmark(
    provider_name: str = "ollama",
    model_name: str | None = None,
    suite: str = "all",
) -> None:
    """Run all benchmark cases against the requested LLM provider."""
    settings = get_settings()
    target_model = model_name or settings.llm_model

    print("=" * 80)
    print("ANALYTIQ M3 ANALYTICAL EVALUATION BENCHMARK")
    print(f"Provider: {provider_name.upper()} | Model: {target_model}")
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

    passed_count = 0
    failed_count = 0
    total_duration_ms = 0.0

    print(f"{'ID':<7} | {'Category':<22} | {'Status':<18} | {'Latency':<8} | {'Result':<6}")
    print("-" * 80)

    results_table: list[dict[str, Any]] = []

    for case in cases_to_run:
        t0 = time.perf_counter()
        res = await service.run_analysis(dataset, case.question)
        dur_ms = (time.perf_counter() - t0) * 1000.0
        total_duration_ms += dur_ms

        status_matches = res.status == case.expected_status
        validator_passes = True
        if case.result_validator is not None:
            validator_passes = case.result_validator(res.rows, res.error_message)

        is_success = status_matches and validator_passes

        if is_success:
            passed_count += 1
            outcome = "PASS"
        else:
            failed_count += 1
            outcome = "FAIL"

        print(
            f"{case.id:<7} | {case.category[:22]:<22} | {res.status:<18} | "
            f"{dur_ms:>6.1f}ms | {outcome:<6}"
        )

        results_table.append(
            {
                "id": case.id,
                "category": case.category,
                "question": case.question,
                "expected_status": case.expected_status,
                "actual_status": res.status,
                "executed_sql": res.executed_sql,
                "latency_ms": round(dur_ms, 1),
                "outcome": outcome,
                "error": res.error_message,
            }
        )

    print("=" * 80)
    accuracy = (passed_count / len(cases_to_run)) * 100.0
    print(
        f"TOTAL CASES: {len(cases_to_run)} | PASSED: {passed_count} | "
        f"FAILED: {failed_count} | ACCURACY: {accuracy:.1f}% | "
        f"AVG LATENCY: {(total_duration_ms / len(cases_to_run)):.1f}ms"
    )
    print("=" * 80)

    # Cleanup temp file
    try:
        parquet_path.unlink(missing_ok=True)
    except Exception as ex:
        logger.debug("Failed to remove temp parquet benchmark file: %s", ex)


if __name__ == "__main__":
    prov = sys.argv[1] if len(sys.argv) > 1 else "ollama"
    mod = sys.argv[2] if len(sys.argv) > 2 else None
    s = sys.argv[3] if len(sys.argv) > 3 else "all"
    asyncio.run(run_benchmark(provider_name=prov, model_name=mod, suite=s))
