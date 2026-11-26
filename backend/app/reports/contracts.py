"""AnalytIQ Reports - Strongly typed versioned report document contracts."""

import uuid
from datetime import datetime
from enum import StrEnum
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class ReportBlockType(StrEnum):
    """Supported report document block types."""

    HEADING = "heading"
    PARAGRAPH = "paragraph"
    VERIFIED_FINDING = "verified_finding"
    SCALAR_METRIC = "scalar_metric"
    CHART = "chart"
    RESULT_TABLE = "result_table"
    DATASET_OVERVIEW = "dataset_overview"
    LIMITATION_NOTICE = "limitation_notice"
    EVIDENCE_REFERENCE = "evidence_reference"
    METHODOLOGY_NOTE = "methodology_note"


class ChartType(StrEnum):
    """Supported report chart types."""

    BAR = "bar"
    HORIZONTAL_BAR = "horizontal_bar"
    LINE = "line"
    PIE = "pie"
    SCATTER = "scatter"
    HISTOGRAM = "histogram"
    KPI_CARD = "kpi_card"
    TABLE = "table"


class ReportStatus(StrEnum):
    """Lifecycle status of a generated analytical report."""

    DRAFT = "draft"
    GENERATING = "generating"
    READY = "ready"
    FAILED = "failed"


# --- Individual Typed Blocks ---


class BaseReportBlock(BaseModel):
    """Base class for all report document content blocks."""

    model_config = ConfigDict(extra="forbid")

    id: str = Field(default_factory=lambda: f"blk_{uuid.uuid4().hex[:8]}")
    display_order: int = 0
    source_run_id: str | None = None


class HeadingBlock(BaseReportBlock):
    block_type: Literal[ReportBlockType.HEADING] = ReportBlockType.HEADING
    level: int = Field(ge=1, le=4, default=2)
    text: str = Field(max_length=200)


class ParagraphBlock(BaseReportBlock):
    block_type: Literal[ReportBlockType.PARAGRAPH] = ReportBlockType.PARAGRAPH
    text: str = Field(max_length=3000)
    is_user_note: bool = False


class VerifiedFindingBlock(BaseReportBlock):
    block_type: Literal[ReportBlockType.VERIFIED_FINDING] = ReportBlockType.VERIFIED_FINDING
    finding_text: str = Field(max_length=1000)
    claim_id: str | None = None
    metric_name: str | None = None
    claimed_value: Any = None
    verified: bool = True
    reason_code: str | None = None
    evidence_fingerprint: str | None = None


class ScalarMetricBlock(BaseReportBlock):
    block_type: Literal[ReportBlockType.SCALAR_METRIC] = ReportBlockType.SCALAR_METRIC
    label: str = Field(max_length=100)
    value: Any
    unit: str | None = None
    verified: bool = True
    evidence_fingerprint: str | None = None


class ChartSeriesSpec(BaseModel):
    data_key: str
    name: str
    color: str | None = None


class ChartSpec(BaseModel):
    chart_type: ChartType
    title: str = Field(max_length=200)
    description: str | None = Field(default=None, max_length=500)
    x_axis_key: str | None = None
    y_axis_key: str | None = None
    series: list[ChartSeriesSpec] = Field(default_factory=list)
    data: list[dict[str, Any]] = Field(default_factory=list)
    units: str | None = None
    truncated: bool = False
    evidence_fingerprint: str | None = None


class ChartBlock(BaseReportBlock):
    block_type: Literal[ReportBlockType.CHART] = ReportBlockType.CHART
    spec: ChartSpec


class ResultTableColumn(BaseModel):
    name: str
    type: str


class ResultTableBlock(BaseReportBlock):
    block_type: Literal[ReportBlockType.RESULT_TABLE] = ReportBlockType.RESULT_TABLE
    title: str = Field(max_length=200)
    columns: list[ResultTableColumn]
    rows: list[list[Any]]
    returned_row_count: int
    total_row_count: int | None = None
    truncated: bool = False
    evidence_fingerprint: str | None = None


class DatasetOverviewBlock(BaseReportBlock):
    block_type: Literal[ReportBlockType.DATASET_OVERVIEW] = ReportBlockType.DATASET_OVERVIEW
    dataset_name: str
    row_count: int
    column_count: int
    columns: list[str]


class LimitationNoticeBlock(BaseReportBlock):
    block_type: Literal[ReportBlockType.LIMITATION_NOTICE] = ReportBlockType.LIMITATION_NOTICE
    notice_text: str = Field(max_length=1000)


class EvidenceReferenceBlock(BaseReportBlock):
    block_type: Literal[ReportBlockType.EVIDENCE_REFERENCE] = ReportBlockType.EVIDENCE_REFERENCE
    request_id: str
    executed_sql: str | None = None
    result_fingerprint: str | None = None
    dataset_fingerprint: str | None = None
    verification_status: str | None = None


class MethodologyNoteBlock(BaseReportBlock):
    block_type: Literal[ReportBlockType.METHODOLOGY_NOTE] = ReportBlockType.METHODOLOGY_NOTE
    note: str = Field(max_length=2000)


# Discriminated Union of all supported blocks
ReportBlock = Annotated[
    HeadingBlock
    | ParagraphBlock
    | VerifiedFindingBlock
    | ScalarMetricBlock
    | ChartBlock
    | ResultTableBlock
    | DatasetOverviewBlock
    | LimitationNoticeBlock
    | EvidenceReferenceBlock
    | MethodologyNoteBlock,
    Field(discriminator="block_type"),
]


class ReportSection(BaseModel):
    """Structured report section grouping related content blocks."""

    id: str = Field(default_factory=lambda: f"sec_{uuid.uuid4().hex[:8]}")
    title: str = Field(max_length=200)
    source_question: str | None = None
    source_run_id: str | None = None
    blocks: list[ReportBlock] = Field(default_factory=list)
    visible: bool = True
    display_order: int = 0


class ReportMetadata(BaseModel):
    """Metadata describing the origin, timestamps, and authorship of a report."""

    report_id: str
    title: str = Field(max_length=120)
    description: str | None = Field(default=None, max_length=1000)
    dataset_id: str
    dataset_name: str
    analysis_session_id: str
    schema_version: str = "1.0.0"
    created_at: datetime
    updated_at: datetime
    generated_at: datetime


class ReportDocument(BaseModel):
    """Full strongly typed, versioned analytical report document."""

    model_config = ConfigDict(extra="forbid")

    schema_version: str = "1.0.0"
    metadata: ReportMetadata
    executive_summary: str = Field(max_length=3000)
    dataset_overview: DatasetOverviewBlock
    sections: list[ReportSection] = Field(default_factory=list)
    methodology: MethodologyNoteBlock | None = None
    limitations: list[LimitationNoticeBlock] = Field(default_factory=list)
    evidence_appendix: list[EvidenceReferenceBlock] = Field(default_factory=list)
