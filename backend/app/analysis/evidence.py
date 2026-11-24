"""Evidence and provenance calculation for verified analytical results."""

import hashlib
import json
import uuid
from datetime import UTC, datetime
from typing import Any

from app.analysis.contracts import ExecutionEvidence


def compute_sha256(data: str) -> str:
    """Compute standard SHA-256 hex digest for input string."""
    return hashlib.sha256(data.encode("utf-8")).hexdigest()


def compute_result_fingerprint(columns: list[str], rows: list[list[Any]]) -> str:
    """Deterministic canonical fingerprint of result columns and rows."""
    canonical_payload = {
        "columns": columns,
        "rows": rows,
    }
    dumped = json.dumps(canonical_payload, sort_keys=True, default=str)
    return compute_sha256(dumped)


def build_execution_evidence(
    dataset_id: uuid.UUID,
    schema_json: dict[str, Any] | None,
    executed_sql: str,
    columns: list[str],
    rows: list[list[Any]],
    query_duration_ms: float,
    total_duration_ms: float,
    provider: str,
    model: str,
    prompt_version: str,
    truncated: bool = False,
    correction_attempts: int = 0,
    token_usage: dict[str, int | None] | None = None,
) -> ExecutionEvidence:
    """Build strongly typed, verifiable ExecutionEvidence contract."""
    # Deterministic fingerprint of schema definition
    schema_str = json.dumps(schema_json or {}, sort_keys=True)
    schema_fingerprint = compute_sha256(schema_str)

    # Result fingerprint
    res_fingerprint = compute_result_fingerprint(columns, rows)

    return ExecutionEvidence(
        dataset_id=dataset_id,
        dataset_fingerprint=compute_sha256(str(dataset_id)),
        schema_fingerprint=schema_fingerprint,
        executed_sql=executed_sql,
        executed_at=datetime.now(UTC),
        row_count=len(rows),
        column_count=len(columns),
        truncated=truncated,
        result_fingerprint=res_fingerprint,
        query_duration_ms=round(query_duration_ms, 2),
        total_duration_ms=round(total_duration_ms, 2),
        provider=provider,
        model=model,
        prompt_version=prompt_version,
        correction_attempts=correction_attempts,
        token_usage=token_usage or {},
    )
