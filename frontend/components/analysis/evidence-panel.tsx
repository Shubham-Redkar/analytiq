"use client";

import React, { useState } from "react";
import type {
  ExecutionEvidence,
  VerificationSummary,
  WorkflowTraceEvent,
} from "../../lib/analysis-types";
import { CheckCircle2, AlertTriangle, XCircle, Code, Clock, ShieldCheck, ChevronDown, ChevronRight, Copy, Check } from "lucide-react";

interface EvidencePanelProps {
  evidence?: ExecutionEvidence | null;
  verification?: VerificationSummary | null;
  executedSql?: string | null;
  traceEvents?: WorkflowTraceEvent[];
  onHighlightEvidence?: (coords: { row: number; colName: string }) => void;
}

export function EvidencePanel({
  evidence,
  verification,
  executedSql,
  traceEvents = [],
  onHighlightEvidence,
}: EvidencePanelProps) {
  const [copiedSql, setCopiedSql] = useState(false);
  const [showSql, setShowSql] = useState(true);
  const [showTrace, setShowTrace] = useState(false);

  const copySql = () => {
    if (!executedSql) return;
    navigator.clipboard.writeText(executedSql);
    setCopiedSql(true);
    setTimeout(() => setCopiedSql(false), 2000);
  };

  return (
    <div className="space-y-4 text-sm">
      {/* 1. Verification Summary Card */}
      <div className="p-3.5 border border-border rounded-xl bg-card/60 space-y-2.5">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2 font-semibold text-foreground text-sm">
            <ShieldCheck className="h-4 w-4 text-primary" />
            <span>Analytical Verification</span>
          </div>
          {verification?.status === "verified" && (
            <span className="flex items-center gap-1 text-emerald-500 font-medium text-xs">
              <CheckCircle2 className="h-4 w-4" /> Verified
            </span>
          )}
          {verification?.status === "partially_verified" && (
            <span className="flex items-center gap-1 text-amber-500 font-medium text-xs">
              <AlertTriangle className="h-4 w-4" /> Partially Verified
            </span>
          )}
          {verification?.status === "contradicted" && (
            <span className="flex items-center gap-1 text-rose-500 font-medium text-xs">
              <XCircle className="h-4 w-4" /> Contradicted
            </span>
          )}
        </div>

        <div className="grid grid-cols-2 gap-2 pt-1 border-t border-border/80 text-muted-foreground text-xs">
          <div>
            <span>Verified claims:</span>{" "}
            <span className="font-semibold text-foreground">
              {verification?.verified_claims_count ?? 0}
            </span>
          </div>
          <div>
            <span>Proposed claims:</span>{" "}
            <span className="font-semibold text-foreground">
              {verification?.total_claims_proposed ?? 0}
            </span>
          </div>
        </div>

        {verification?.verification_notes && (
          <p className="text-muted-foreground italic text-xs pt-1">
            {verification.verification_notes}
          </p>
        )}
      </div>

      {/* 2. Verified Claims List with Evidence Coordinates */}
      {verification?.verified_claims && verification.verified_claims.length > 0 && (
        <div className="space-y-2">
          <span className="font-semibold text-foreground text-sm block">Verified Claims</span>
          <div className="space-y-1.5">
            {verification.verified_claims.map((claim) => (
              <div
                key={claim.claim_id}
                className="p-3 border border-border rounded-xl bg-card hover:bg-muted/40 transition flex items-start justify-between gap-3 shadow-2xs"
              >
                <div className="space-y-1">
                  <div className="flex items-center gap-2 font-medium text-sm text-foreground">
                    <CheckCircle2 className="h-4 w-4 text-emerald-500 shrink-0" />
                    <span>{claim.claim_text}</span>
                  </div>
                  {claim.actual_value !== undefined && (
                    <div className="text-muted-foreground font-mono text-xs pl-6">
                      Value: {String(claim.actual_value)}
                    </div>
                  )}
                </div>

                {claim.evidence_reference && onHighlightEvidence && (
                  <button
                    onClick={() => {
                      const ref = claim.evidence_reference;
                      if (ref && ref.row_indices.length > 0 && ref.column_names.length > 0) {
                        onHighlightEvidence({
                          row: ref.row_indices[0],
                          colName: ref.column_names[0],
                        });
                      }
                    }}
                    className="text-xs font-medium text-primary hover:underline px-2.5 py-1 rounded-md border border-primary/30 shrink-0 cursor-pointer"
                  >
                    Inspect Cell
                  </button>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* 3. Executed SQL Inspector */}
      {executedSql && (
        <div className="border border-border rounded-xl bg-card/60 overflow-hidden shadow-2xs">
          <div
            onClick={() => setShowSql(!showSql)}
            className="flex items-center justify-between p-3 bg-muted/40 cursor-pointer select-none border-b border-border"
          >
            <div className="flex items-center gap-2 font-semibold text-sm text-foreground">
              <Code className="h-4 w-4 text-muted-foreground" />
              <span>Executed DuckDB SQL</span>
            </div>
            <div className="flex items-center gap-2">
              <button
                onClick={(e) => {
                  e.stopPropagation();
                  copySql();
                }}
                className="p-1.5 hover:text-foreground text-muted-foreground transition rounded cursor-pointer"
                title="Copy SQL"
              >
                {copiedSql ? (
                  <Check className="h-4 w-4 text-emerald-500" />
                ) : (
                  <Copy className="h-4 w-4" />
                )}
              </button>
              {showSql ? <ChevronDown className="h-4 w-4" /> : <ChevronRight className="h-4 w-4" />}
            </div>
          </div>

          {showSql && (
            <div className="p-3.5 bg-muted/20 overflow-x-auto">
              <pre className="font-mono text-[13px] text-foreground leading-relaxed">
                {executedSql}
              </pre>
            </div>
          )}
        </div>
      )}

      {/* 4. Execution Metadata */}
      {evidence && (
        <div className="p-3 border rounded-lg bg-card/40 space-y-1.5 text-[11px] text-muted-foreground">
          <span className="font-semibold text-foreground block text-xs mb-1">
            Execution Metadata
          </span>
          <div className="flex justify-between">
            <span>Duration:</span>
            <span className="font-mono text-foreground">
              {evidence.execution_duration_ms.toFixed(1)} ms
            </span>
          </div>
          <div className="flex justify-between">
            <span>Result Fingerprint:</span>
            <span className="font-mono text-foreground text-[10px] truncate max-w-[150px]">
              {evidence.result_fingerprint}
            </span>
          </div>
          <div className="flex justify-between">
            <span>Returned Rows:</span>
            <span className="font-mono text-foreground">{evidence.returned_row_count}</span>
          </div>
        </div>
      )}

      {/* 5. Workflow Trace Events */}
      {traceEvents.length > 0 && (
        <div className="border rounded-lg bg-card/60 overflow-hidden">
          <div
            onClick={() => setShowTrace(!showTrace)}
            className="flex items-center justify-between p-2.5 bg-muted/40 cursor-pointer select-none"
          >
            <div className="flex items-center gap-1.5 font-semibold text-foreground">
              <Clock className="h-3.5 w-3.5 text-muted-foreground" />
              <span>Workflow Trace ({traceEvents.length} events)</span>
            </div>
            {showTrace ? <ChevronDown className="h-3.5 w-3.5" /> : <ChevronRight className="h-3.5 w-3.5" />}
          </div>

          {showTrace && (
            <div className="p-2 space-y-1 bg-muted/20 border-t max-h-48 overflow-y-auto">
              {traceEvents.map((t, idx) => (
                <div key={idx} className="flex items-center justify-between text-[11px] py-1 border-b last:border-0">
                  <span className="font-medium text-foreground">{t.node}: {t.action}</span>
                  <span className="font-mono text-muted-foreground">{t.duration_ms.toFixed(0)}ms</span>
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
