"""AnalytIQ Schema Inference - Deterministic logical data type inference."""

import re
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any

# Date formats accepted deterministically without locale ambiguity
DATE_PATTERNS = [
    re.compile(r"^\d{4}-\d{2}-\d{2}$"),  # YYYY-MM-DD
    re.compile(r"^\d{4}/\d{2}/\d{2}$"),  # YYYY/MM/DD
]

TIMESTAMP_PATTERNS = [
    re.compile(r"^\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}:\d{2}(\.\d+)?(Z|[+-]\d{2}:?\d{2})?$"),
    re.compile(r"^\d{4}/\d{2}/\d{2}[ T]\d{2}:\d{2}:\d{2}(\.\d+)?$"),
]

BOOLEAN_STRINGS = {"true", "false", "t", "f", "yes", "no", "1", "0"}


@dataclass(frozen=True)
class ColumnSchema:
    """Metadata describing a single dataset column."""

    name: str
    logical_type: str  # string, integer, float, boolean, date, timestamp
    duckdb_type: str
    nullable: bool


class SchemaInferenceError(Exception):
    """Raised when schema validation or inference fails."""


def is_leading_zero_identifier(val: str) -> bool:
    """Check if a string looks like a numeric identifier with preserving leading zeros.

    E.g. '01234' (US ZIP code) must NOT be coerced to integer 1234.
    """
    if len(val) > 1 and val.startswith("0") and val.isdigit():
        return True
    return False


def infer_value_type(val: Any) -> str:
    """Infer the logical type of an individual non-null value."""
    if val is None or val == "":
        return "null"

    if isinstance(val, bool):
        return "boolean"
    if isinstance(val, int):
        return "integer"
    if isinstance(val, float):
        return "float"
    if isinstance(val, datetime):
        return "timestamp"
    if isinstance(val, date):
        return "date"

    s_val = str(val).strip()
    if not s_val:
        return "null"

    # Leading-zero numbers like '007' or '02138' must remain string identifiers
    if is_leading_zero_identifier(s_val):
        return "string"

    # Boolean strings
    if s_val.lower() in {"true", "false"}:
        return "boolean"

    # Integer
    if re.match(r"^[-+]?\d+$", s_val):
        return "integer"

    # Floating point
    if re.match(r"^[-+]?\d+\.\d+([eE][-+]?\d+)?$", s_val):
        return "float"

    # Date
    for pattern in DATE_PATTERNS:
        if pattern.match(s_val):
            try:
                date.fromisoformat(s_val.replace("/", "-"))
                return "date"
            except ValueError:
                pass

    # Timestamp
    for pattern in TIMESTAMP_PATTERNS:
        if pattern.match(s_val):
            try:
                datetime.fromisoformat(s_val.replace("/", "-"))
                return "timestamp"
            except ValueError:
                pass

    return "string"


def resolve_column_type(types_seen: set[str]) -> str:
    """Deterministically resolve a single column logical type from observed sample types."""
    non_null_types = types_seen - {"null"}
    if not non_null_types:
        return "string"

    if len(non_null_types) == 1:
        return next(iter(non_null_types))

    # If mixed integers and floats, coerce to float
    if non_null_types == {"integer", "float"}:
        return "float"

    # Any other mixed combination falls back safely to string
    return "string"


def map_logical_to_duckdb_type(logical_type: str) -> str:
    """Map logical type to corresponding DuckDB column type."""
    mapping = {
        "integer": "BIGINT",
        "float": "DOUBLE",
        "boolean": "BOOLEAN",
        "date": "DATE",
        "timestamp": "TIMESTAMP",
        "string": "VARCHAR",
    }
    return mapping.get(logical_type, "VARCHAR")
