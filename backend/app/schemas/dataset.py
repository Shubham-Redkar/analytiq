"""AnalytIQ Schemas - Dataset request and response contracts."""

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class DatasetProfileSummary(BaseModel):
    """Deterministic factual quality indicators summary."""

    total_rows: int = 0
    total_columns: int = 0
    duplicate_rows: int = 0
    missing_cells: int = 0
    missing_percentage: float = 0.0
    columns_with_missing: int = 0
    all_null_columns_count: int = 0
    constant_columns_count: int = 0


class ColumnMissingBreakdown(BaseModel):
    """Per-column missing values breakdown."""

    name: str
    logical_type: str
    null_count: int
    null_percentage: float
    distinct_count: int


class DatasetResponse(BaseModel):
    """Sanitized dataset response contract (never exposes internal storage paths)."""

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: uuid.UUID
    name: str
    original_filename: str
    file_format: str
    file_size_bytes: int
    row_count: int | None = None
    column_count: int | None = None
    status: str
    created_at: datetime
    updated_at: datetime
    schema_metadata: dict[str, Any] | None = Field(
        default=None,
        alias="schema_json",
        serialization_alias="schema_json",
    )
    quality_summary: DatasetProfileSummary | None = None


class DatasetListResponse(BaseModel):
    """Paginated dataset listing response."""

    items: list[DatasetResponse]
    total: int
    page: int
    page_size: int
    total_pages: int


class DatasetPreviewResponse(BaseModel):
    """Bounded dataset row preview."""

    columns: list[dict[str, Any]]
    rows: list[dict[str, Any]]
    total_rows: int
    offset: int
    limit: int
    has_next: bool = False
    has_previous: bool = False


class DatasetProfileResponse(BaseModel):
    """Deterministic column statistics and summaries."""

    summary: dict[str, Any]
    columns: list[dict[str, Any]]


class DatasetQualityResponse(BaseModel):
    """Deterministic data-quality findings and metrics."""

    summary: DatasetProfileSummary
    quality_findings: list[dict[str, Any]]
    columns_breakdown: list[ColumnMissingBreakdown] = Field(default_factory=list)


class DatasetDeleteResponse(BaseModel):
    """Dataset deletion status response."""

    status: str = "ok"
    message: str = "Dataset deleted successfully."
    dataset_id: uuid.UUID
