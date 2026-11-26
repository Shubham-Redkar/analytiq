"""Validation of evidence references against trusted execution evidence."""

from typing import Any

from app.analysis.contracts import ExecutionEvidence
from app.verification.contracts import EvidenceReference
from app.verification.derived_metrics import numbers_match


class EvidenceReferenceError(Exception):
    """Raised when an evidence reference is malformed or invalid."""


def validate_evidence_reference(
    ref: EvidenceReference,
    evidence: ExecutionEvidence,
    columns: list[str],
    rows: list[list[Any]],
    current_request_id: str | None = None,
) -> tuple[bool, str, Any]:
    """Validate that an evidence reference points to a valid cell in the current execution evidence.

    Enforces:
    1. Cryptographic result fingerprint verification.
    2. Scope isolation: if dataset_id is present, it must match evidence.dataset_id.
    3. Request isolation: if request_id is present, it must match current_request_id.
    4. Row index non-negative bounds checking.
    5. Column existence against schema columns.
    6. Expected value validation using strict type-aware numerical comparison.

    Returns:
        (is_valid, reason_code, actual_cell_value)
    """
    # 1. Dataset identity & isolation check
    if ref.dataset_id is not None and ref.dataset_id != evidence.dataset_id:
        return False, "DATASET_MISMATCH", None

    # 2. Request identity & isolation check
    if ref.request_id is not None and current_request_id is not None:
        if ref.request_id != current_request_id:
            return False, "REQUEST_MISMATCH", None

    # 3. Fingerprint verification
    if ref.result_fingerprint != evidence.result_fingerprint:
        return False, "FINGERPRINT_MISMATCH", None

    # 4. Row index bounds
    if ref.row_index < 0 or ref.row_index >= len(rows):
        return False, "ROW_INDEX_OUT_OF_BOUNDS", None

    # 5. Column existence
    target_row = rows[ref.row_index]
    col_name_lower = ref.column_name.lower().strip()
    col_indices = [i for i, c in enumerate(columns) if c.lower().strip() == col_name_lower]

    if not col_indices:
        return False, "UNKNOWN_COLUMN", None

    col_idx = col_indices[0]
    if col_idx >= len(target_row):
        return False, "COLUMN_INDEX_OUT_OF_BOUNDS", None

    actual_value = target_row[col_idx]

    # 6. Type-aware expected value comparison
    if ref.expected_value is not None:
        # Check booleans strictly
        if isinstance(ref.expected_value, bool) or isinstance(actual_value, bool):
            if not (isinstance(ref.expected_value, bool) and isinstance(actual_value, bool)):
                return False, "TYPE_MISMATCH", actual_value
            if ref.expected_value is not actual_value:
                return False, "VALUE_MISMATCH", actual_value
        is_numeric = isinstance(ref.expected_value, (int, float)) and isinstance(
            actual_value, (int, float)
        )
        if is_numeric:
            if not numbers_match(ref.expected_value, actual_value):
                return False, "VALUE_MISMATCH", actual_value
        else:
            if str(ref.expected_value).strip().lower() != str(actual_value).strip().lower():
                return False, "VALUE_MISMATCH", actual_value

    return True, "VALID_REFERENCE", actual_value
