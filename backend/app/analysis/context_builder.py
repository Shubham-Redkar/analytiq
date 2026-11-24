"""Context builder that serializes data-minimized, prompt-injection-safe schema context."""

import json
from typing import Any

from app.analysis.contracts import ColumnContext, DatasetAnalyticalContext
from app.models.dataset import Dataset

MAX_CONTEXT_COLUMNS = 200
MAX_CATEGORICAL_VALUES_PER_COL = 5
MAX_CATEGORICAL_VALUE_LEN = 30
CATEGORICAL_DISTINCT_CEILING = 10


class ContextBuilderError(Exception):
    """Raised when analytical context cannot be constructed."""


def build_dataset_context(
    dataset: Dataset,
    include_samples: bool = False,
    include_categories: bool = True,
) -> DatasetAnalyticalContext:
    """Build a deterministic, data-minimized analytical context from dataset metadata.

    Security & Privacy rules:
    - Never leaks internal storage paths or physical disk locations.
    - Strictly maps the table relation name to the fixed logical identifier 'dataset'.
    - Binds exact column names, logical types, physical types, and nullability.
    - Excludes raw sample values by default to prevent data leakage and prompt contamination.
    - Categorical context: bounded to low-cardinality discrete columns (distinct_count <= 10)
      with sanitized representation (max 5 distinct categories, truncated to 30 chars).
    - Treats all dataset strings (name, column names) as untrusted metadata.
    """
    if dataset.status != "ready":
        raise ContextBuilderError(
            f"Cannot build analytical context: dataset status is '{dataset.status}' "
            "(must be 'ready')."
        )

    schema_json: dict[str, Any] = dataset.schema_json or {}
    columns_raw: list[dict[str, Any]] = schema_json.get("columns", [])

    if len(columns_raw) > MAX_CONTEXT_COLUMNS:
        raise ContextBuilderError(
            f"Dataset has {len(columns_raw)} columns, exceeding maximum analytical context "
            f"ceiling of {MAX_CONTEXT_COLUMNS}."
        )

    columns: list[ColumnContext] = []
    for col in columns_raw:
        col_name = str(col.get("name", "")).strip()
        if not col_name:
            continue

        distinct_cnt = col.get("distinct_count")
        logical_type = str(col.get("logical_type", "string")).lower()

        safe_samples: list[Any] = []
        # Privacy policy: Only include discrete categories if explicitly requested,
        # column is categorical/string, and distinct count is within small ceiling.
        if include_samples:
            raw_samples = col.get("sample_values", [])
            if isinstance(raw_samples, list):
                for s in raw_samples[:MAX_CATEGORICAL_VALUES_PER_COL]:
                    if s is None:
                        continue
                    s_str = str(s)
                    if len(s_str) > MAX_CATEGORICAL_VALUE_LEN:
                        s_str = s_str[:MAX_CATEGORICAL_VALUE_LEN] + "..."
                    safe_samples.append(s_str)
        elif (
            include_categories
            and distinct_cnt is not None
            and distinct_cnt <= CATEGORICAL_DISTINCT_CEILING
            and logical_type in ("string", "category", "boolean")
        ):
            raw_samples = col.get("sample_values", [])
            if isinstance(raw_samples, list):
                for s in raw_samples[:MAX_CATEGORICAL_VALUES_PER_COL]:
                    if s is None:
                        continue
                    s_str = str(s)
                    if len(s_str) > MAX_CATEGORICAL_VALUE_LEN:
                        s_str = s_str[:MAX_CATEGORICAL_VALUE_LEN] + "..."
                    safe_samples.append(s_str)

        columns.append(
            ColumnContext(
                name=col_name,
                physical_type=str(col.get("physical_type", "VARCHAR")),
                logical_type=logical_type,
                nullable=bool(col.get("nullable", True)),
                distinct_count=distinct_cnt,
                sample_values=safe_samples,
            )
        )

    return DatasetAnalyticalContext(
        relation_name="dataset",
        dataset_name=dataset.name,
        row_count=dataset.row_count or 0,
        column_count=len(columns),
        columns=columns,
        dialect="duckdb",
    )


def serialize_context_for_prompt(context: DatasetAnalyticalContext) -> str:
    """Serialize DatasetAnalyticalContext as a structured JSON string for LLM injection."""
    dict_repr = {
        "relation_name": context.relation_name,
        "dataset_name": context.dataset_name,
        "row_count": context.row_count,
        "columns": [
            {
                "name": c.name,
                "type": c.physical_type,
                "logical_type": c.logical_type,
                "nullable": c.nullable,
                "sample_values": c.sample_values,
            }
            for c in context.columns
        ],
    }
    return json.dumps(dict_repr, indent=2)
