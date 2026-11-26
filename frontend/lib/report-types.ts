/**
 * Type definitions for AnalytIQ Report Generation, Management, and Export.
 */

export type ReportBlockType =
  | "heading"
  | "paragraph"
  | "verified_finding"
  | "scalar_metric"
  | "chart"
  | "result_table"
  | "dataset_overview"
  | "limitation_notice"
  | "evidence_reference"
  | "methodology_note";

export type ChartType =
  "bar" | "horizontal_bar" | "line" | "pie" | "scatter" | "histogram" | "kpi_card" | "table";

export interface ChartSeriesSpec {
  data_key: string;
  name: string;
  color?: string | null;
}

export interface ChartSpec {
  chart_type: ChartType;
  title: string;
  description?: string | null;
  x_axis_key?: string | null;
  y_axis_key?: string | null;
  series: ChartSeriesSpec[];
  data: Record<string, unknown>[];
  units?: string | null;
  truncated: boolean;
  evidence_fingerprint?: string | null;
}

export interface ResultTableColumn {
  name: string;
  type: string;
}

export interface BaseReportBlock {
  id: string;
  display_order: number;
  source_run_id?: string | null;
}

export interface HeadingBlock extends BaseReportBlock {
  block_type: "heading";
  level: number;
  text: string;
}

export interface ParagraphBlock extends BaseReportBlock {
  block_type: "paragraph";
  text: string;
  is_user_note: boolean;
}

export interface VerifiedFindingBlock extends BaseReportBlock {
  block_type: "verified_finding";
  finding_text: string;
  claim_id?: string | null;
  metric_name?: string | null;
  claimed_value?: unknown;
  verified: boolean;
  reason_code?: string | null;
  evidence_fingerprint?: string | null;
}

export interface ScalarMetricBlock extends BaseReportBlock {
  block_type: "scalar_metric";
  label: string;
  value: unknown;
  unit?: string | null;
  verified: boolean;
  evidence_fingerprint?: string | null;
}

export interface ChartBlock extends BaseReportBlock {
  block_type: "chart";
  spec: ChartSpec;
}

export interface ResultTableBlock extends BaseReportBlock {
  block_type: "result_table";
  title: string;
  columns: ResultTableColumn[];
  rows: unknown[][];
  returned_row_count: number;
  total_row_count?: number | null;
  truncated: boolean;
  evidence_fingerprint?: string | null;
}

export interface DatasetOverviewBlock extends BaseReportBlock {
  block_type: "dataset_overview";
  dataset_name: string;
  row_count: number;
  column_count: number;
  columns: string[];
}

export interface LimitationNoticeBlock extends BaseReportBlock {
  block_type: "limitation_notice";
  notice_text: string;
}

export interface EvidenceReferenceBlock extends BaseReportBlock {
  block_type: "evidence_reference";
  request_id: string;
  executed_sql?: string | null;
  result_fingerprint?: string | null;
  dataset_fingerprint?: string | null;
  verification_status?: string | null;
}

export interface MethodologyNoteBlock extends BaseReportBlock {
  block_type: "methodology_note";
  note: string;
}

export type ReportBlock =
  | HeadingBlock
  | ParagraphBlock
  | VerifiedFindingBlock
  | ScalarMetricBlock
  | ChartBlock
  | ResultTableBlock
  | DatasetOverviewBlock
  | LimitationNoticeBlock
  | EvidenceReferenceBlock
  | MethodologyNoteBlock;

export interface ReportSection {
  id: string;
  title: string;
  source_question?: string | null;
  source_run_id?: string | null;
  blocks: ReportBlock[];
  visible: boolean;
  display_order: number;
}

export interface ReportMetadata {
  report_id: string;
  title: string;
  description?: string | null;
  dataset_id: string;
  dataset_name: string;
  analysis_session_id: string;
  schema_version: string;
  created_at: string;
  updated_at: string;
  generated_at: string;
}

export interface ReportDocument {
  schema_version: string;
  metadata: ReportMetadata;
  executive_summary: string;
  dataset_overview: DatasetOverviewBlock;
  sections: ReportSection[];
  methodology?: MethodologyNoteBlock | null;
  limitations: LimitationNoticeBlock[];
  evidence_appendix: EvidenceReferenceBlock[];
}

export interface ReportSummary {
  id: string;
  dataset_id: string;
  dataset_name?: string | null;
  analysis_session_id: string;
  title: string;
  description?: string | null;
  status: string;
  revision: number;
  created_at: string;
  updated_at: string;
}

export interface ReportDetail extends ReportSummary {
  schema_version: string;
  document: ReportDocument;
  generated_at: string;
}

export interface ReportListResponse {
  items: ReportSummary[];
  total: number;
  page: number;
  page_size: number;
  pages: number;
}

export interface CreateReportPayload {
  analysis_session_id: string;
  title?: string | null;
  description?: string | null;
  run_ids?: string[] | null;
}

export interface UpdateReportPayload {
  title?: string | null;
  description?: string | null;
  document?: Record<string, unknown> | null;
  revision: number;
}
