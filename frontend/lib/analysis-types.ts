/**
 * AnalytIQ Frontend Types - Interactive Analytical Workspace Contracts (M6).
 */

export interface AnalyticalResultColumn {
  name: string;
  duckdb_type: string;
  python_type: string;
  nullable: boolean;
}

export interface ExecutionEvidence {
  request_id: string;
  dataset_id: string;
  dataset_snapshot_id: string;
  result_fingerprint: string;
  execution_duration_ms: number;
  returned_row_count: number;
  column_names: string[];
  row_count_accurate: boolean;
  truncated: boolean;
}

export interface EvidenceReference {
  claim_id: string;
  evidence_id: string;
  result_fingerprint: string;
  row_indices: number[];
  column_names: string[];
  aggregation_applied?: string | null;
  request_id?: string | null;
  dataset_id?: string | null;
}

export interface VerifiedClaim {
  claim_id: string;
  claim_text: string;
  status: "verified" | "contradicted" | "unverifiable";
  claim_type: string;
  claimed_value?: string | number | boolean | null;
  actual_value?: string | number | boolean | null;
  tolerance_applied?: number | null;
  evidence_reference?: EvidenceReference | null;
  verification_notes?: string | null;
}

export interface VerificationSummary {
  status: "verified" | "partially_verified" | "contradicted" | "unverified";
  total_claims_proposed: number;
  verified_claims_count: number;
  contradicted_claims_count: number;
  unverifiable_claims_count: number;
  verified_claims: VerifiedClaim[];
  contradicted_claims: VerifiedClaim[];
  unverifiable_claims: VerifiedClaim[];
  verified_explanation?: string | null;
  verification_notes?: string | null;
}

export interface ClarificationOption {
  key: string;
  label: string;
  description: string;
}

export interface ClarificationOutput {
  needs_clarification: boolean;
  question?: string | null;
  options: ClarificationOption[];
  ambiguity_type?: string | null;
}

export interface InterpretationOutput {
  summary: string;
  key_takeaways: string[];
  limitations: string[];
}

export interface WorkflowTraceEvent {
  node: string;
  action: string;
  duration_ms: number;
  timestamp: string;
  llm_called: boolean;
  tokens_used: number;
  status: string;
  details?: Record<string, unknown>;
}

export interface WorkflowAnalysisResponse {
  request_id: string;
  dataset_id: string;
  status: string;
  question: string;
  intent: string;
  clarification?: ClarificationOutput | null;
  interpretation?: InterpretationOutput | null;
  executed_sql?: string | null;
  columns: AnalyticalResultColumn[];
  rows: (string | number | boolean | null)[][];
  returned_row_count: number;
  dataset_row_count?: number | null;
  total_row_count?: number | null;
  truncated: boolean;
  unsupported_reason?: string | null;
  error_message?: string | null;
  evidence?: ExecutionEvidence | null;
  verification?: VerificationSummary | null;
  trace_events: WorkflowTraceEvent[];
  total_llm_calls: number;
  correction_attempts: number;
  total_duration_ms: number;
}

export interface AnalysisSessionSummary {
  id: string;
  dataset_id: string;
  dataset_name?: string | null;
  title: string;
  run_count: number;
  last_question?: string | null;
  created_at: string;
  updated_at: string;
}

export interface AnalysisSessionListResponse {
  items: AnalysisSessionSummary[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}

export interface AnalysisRunDetail {
  id: string;
  session_id: string;
  request_id: string;
  question: string;
  intent: string;
  status: string;
  authoritative_answer?: string | null;
  executed_sql?: string | null;
  columns: AnalyticalResultColumn[];
  rows: (string | number | boolean | null)[][];
  returned_row_count: number;
  dataset_row_count?: number | null;
  total_row_count?: number | null;
  truncated: boolean;
  unsupported_reason?: string | null;
  error_message?: string | null;
  evidence?: ExecutionEvidence | null;
  verification?: VerificationSummary | null;
  clarification?: ClarificationOutput | null;
  created_at: string;
  completed_at?: string | null;
}

export interface AnalysisSessionResponse {
  id: string;
  user_id: string;
  dataset_id: string;
  dataset_name?: string | null;
  title: string;
  created_at: string;
  updated_at: string;
  runs: AnalysisRunDetail[];
}

export interface StreamProgressEvent {
  request_id: string;
  seq: number;
  event_type:
    | "accepted"
    | "stage_started"
    | "stage_completed"
    | "result"
    | "error"
    | "cancelled"
    | "completed";
  stage?: string | null;
  stage_name?: string | null;
  status: string;
  timestamp: string;
  elapsed_ms: number;
  payload?: Record<string, unknown> | null;
  result?: WorkflowAnalysisResponse | null;
}
