"""Validation of evidence references against trusted execution evidence."""

from typing import Any

from app.analysis.contracts import ExecutionEvidence
from app.verification.contracts import EvidenceReference


class EvidenceReferenceError(Exception):
    """Raised when an evidence reference is malformed or invalid."""


def validate_evidence_reference(
    ref: EvidenceReference,
    evidence: ExecutionEvidence,
    columns: list[str],
    rows: list[list[Any]],
) -> tuple[bool, str, Any]:
    """Validate that an evidence reference points to a valid cell in the current execution evidence.

    Returns:
        (is_valid, reason_code, actual_cell_value)
    """
    # 1. Fingerprint verification
    if ref.result_fingerprint != evidence.result_fingerprint:
        return False, "FINGERPRINT_MISMATCH", None

    # 2. Row index bounds
    if ref.row_index < 0 or ref.row_index >= len(rows):
        return False, "ROW_INDEX_OUT_OF_BOUNDS", None

    # 3. Column existence
    target_row = rows[ref.row_index]
    col_name_lower = ref.column_name.lower().strip()
    col_indices = [i for i, c in enumerate(columns) if c.lower().strip() == col_name_lower]

    if not col_indices:
        return False, "UNKNOWN_COLUMN", None

    col_idx = col_indices[0]
    if col_idx >= len(target_row):
        return False, "COLUMN_INDEX_OUT_OF_BOUNDS", None

    actual_value = target_row[col_idx]

    # 4. If reference specifies expected_value, verify value match
    if ref.expected_value is not None:
        if isinstance(ref.expected_value, (int, float)) and isinstance(actual_value, (int, float)):
            if abs(float(ref.expected_value) - float(actual_value)) > 0.001:
                return False, "VALUE_MISMATCH", actual_value
        elif str(ref.expected_value).strip().lower() != str(actual_value).strip().lower():
            return False, "VALUE_MISMATCH", actual_value

    return True, "VALID_REFERENCE", actual_value
