export interface User {
  id: string;
  email: string;
  display_name: string;
  is_active: boolean;
  created_at: string;
}

export interface ApiErrorResponse {
  detail: string;
}

export interface ColumnSchema {
  name: string;
  logical_type: string;
  duckdb_type: string;
  nullable: boolean;
}

export interface DatasetSchema {
  columns: ColumnSchema[];
  row_count: number;
  column_count: number;
}

export interface Dataset {
  id: string;
  name: string;
  original_filename: string;
  file_format: string;
  file_size_bytes: number;
  row_count: number | null;
  column_count: number | null;
  status: string;
  created_at: string;
  updated_at: string;
  schema_json?: DatasetSchema | null;
  quality_summary?: DatasetProfileSummary | null;
}

export interface DatasetListResponse {
  items: Dataset[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}

export interface DatasetPreviewResponse {
  columns: { name: string; duckdb_type: string; logical_type?: string }[];
  rows: Record<string, unknown>[];
  total_rows: number;
  offset: number;
  limit: number;
}

export interface ColumnProfile {
  name: string;
  logical_type: string;
  null_count: number;
  null_percentage: number;
  distinct_count: number;
  min: number | string | null;
  max: number | string | null;
  mean: number | null;
  top_values: { value: string; count: number }[];
  is_discrete?: boolean;
  is_high_cardinality?: boolean;
}

export interface DatasetProfileSummary {
  total_rows: number;
  total_columns: number;
  duplicate_rows: number;
  missing_cells: number;
  missing_percentage: number;
  columns_with_missing: number;
  all_null_columns_count: number;
  constant_columns_count: number;
}

export interface QualityFinding {
  type: string;
  severity: "info" | "warning";
  message: string;
}

export interface ColumnMissingBreakdown {
  name: string;
  logical_type: string;
  null_count: number;
  null_percentage: number;
  distinct_count: number;
}

export interface DatasetProfileResponse {
  summary: DatasetProfileSummary;
  columns: ColumnProfile[];
}

export interface DatasetQualityResponse {
  summary: DatasetProfileSummary;
  quality_findings: QualityFinding[];
  columns_breakdown?: ColumnMissingBreakdown[];
}

