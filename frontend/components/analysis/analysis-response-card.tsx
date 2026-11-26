"use client";

import React, { useState } from "react";
import type { WorkflowAnalysisResponse } from "../../lib/analysis-types";
import { ResultTable } from "./result-table";
import { ChartContainer } from "./chart-container";
import { EvidencePanel } from "./evidence-panel";
import { ClarificationCard } from "./clarification-card";
import {
  CheckCircle2,
  AlertTriangle,
  ChevronDown,
  ChevronRight,
  BarChart2,
  Table as TableIcon,
  ShieldAlert,
} from "lucide-react";

interface AnalysisResponseCardProps {
  response: WorkflowAnalysisResponse;
  onClarify?: (option: string) => void;
}

export function AnalysisResponseCard({ response, onClarify }: AnalysisResponseCardProps) {
  const [activeTab, setActiveTab] = useState<"visual" | "table">("visual");
  const [showEvidence, setShowEvidence] = useState(false);
  const [highlightCoords, setHighlightCoords] = useState<{ row: number; colName: string } | null>(
    null
  );

  // Authoritative verified answer
  const answer =
    response.verification?.verified_explanation ||
    response.interpretation?.summary ||
    (response.returned_row_count > 0
      ? "Results computed successfully from analytical query."
      : null);

  const isUnsupported = Boolean(response.unsupported_reason);
  const isFailed = response.status === "failed" || Boolean(response.error_message);

  return (
    <div className="border rounded-2xl bg-card p-5 space-y-4 shadow-xs">
      {/* 1. Header with Status and Question */}
      <div className="flex items-start justify-between gap-3 border-b border-border pb-3.5">
        <div className="space-y-1.5">
          <div className="flex items-center gap-2">
            <span className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
              Analytical Insight
            </span>
            {response.verification?.status === "verified" && (
              <span className="flex items-center gap-1 text-xs px-2.5 py-0.5 rounded-full bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 font-medium border border-emerald-500/20">
                <CheckCircle2 className="h-3.5 w-3.5" /> Verified
              </span>
            )}
            {response.verification?.status === "partially_verified" && (
              <span className="flex items-center gap-1 text-xs px-2.5 py-0.5 rounded-full bg-amber-500/10 text-amber-600 dark:text-amber-400 font-medium border border-amber-500/20">
                <AlertTriangle className="h-3.5 w-3.5" /> Partial
              </span>
            )}
            {isUnsupported && (
              <span className="text-xs px-2.5 py-0.5 rounded-full bg-muted text-muted-foreground font-medium">
                Unsupported
              </span>
            )}
          </div>
          <h3 className="text-base sm:text-lg font-semibold text-foreground leading-snug">
            {response.question}
          </h3>
        </div>

        <button
          onClick={() => setShowEvidence(!showEvidence)}
          className={`flex items-center gap-1.5 text-xs font-medium px-3 py-1.5 rounded-lg border transition shrink-0 cursor-pointer ${
            showEvidence
              ? "bg-primary text-primary-foreground border-primary"
              : "bg-card hover:bg-muted text-foreground border-border"
          }`}
        >
          <span>Evidence</span>
          {showEvidence ? (
            <ChevronDown className="h-4 w-4" />
          ) : (
            <ChevronRight className="h-4 w-4" />
          )}
        </button>
      </div>

      {/* 2. Clarification Needed */}
      {response.clarification?.needs_clarification && onClarify && (
        <ClarificationCard clarification={response.clarification} onSelectOption={onClarify} />
      )}

      {/* 3. Authoritative Verified Explanation */}
      {answer && (
        <div className="text-[15px] text-foreground leading-relaxed bg-muted/20 p-4 rounded-xl border border-border/80">
          {answer}
        </div>
      )}

      {/* 4. Unsupported or Failure Notice */}
      {isUnsupported && (
        <div className="flex items-start gap-2.5 p-3 rounded-xl border border-amber-500/30 bg-amber-500/5 text-xs text-foreground">
          <AlertTriangle className="h-4 w-4 text-amber-500 shrink-0 mt-0.5" />
          <span>{response.unsupported_reason}</span>
        </div>
      )}

      {isFailed && (
        <div className="flex items-start gap-2.5 p-3 rounded-xl border border-rose-500/30 bg-rose-500/5 text-xs text-rose-500">
          <ShieldAlert className="h-4 w-4 text-rose-500 shrink-0 mt-0.5" />
          <span>
            {response.error_message || "Analytical execution encountered an unrecoverable error."}
          </span>
        </div>
      )}

      {/* 5. Result Viewers (Chart & Dynamic Table) */}
      {response.rows && response.rows.length > 0 && (
        <div className="space-y-3 pt-2">
          <div className="flex items-center gap-2 border-b pb-2">
            <button
              onClick={() => setActiveTab("visual")}
              className={`flex items-center gap-1.5 text-xs px-3 py-1 rounded-md transition font-medium ${
                activeTab === "visual"
                  ? "bg-accent text-foreground shadow-xs"
                  : "text-muted-foreground hover:text-foreground"
              }`}
            >
              <BarChart2 className="h-3.5 w-3.5" />
              <span>Chart</span>
            </button>
            <button
              onClick={() => setActiveTab("table")}
              className={`flex items-center gap-1.5 text-xs px-3 py-1 rounded-md transition font-medium ${
                activeTab === "table"
                  ? "bg-accent text-foreground shadow-xs"
                  : "text-muted-foreground hover:text-foreground"
              }`}
            >
              <TableIcon className="h-3.5 w-3.5" />
              <span>Table</span>
            </button>
          </div>

          {activeTab === "visual" && (
            <ChartContainer
              columns={response.columns}
              rows={response.rows}
              returnedRowCount={response.returned_row_count}
              truncated={response.truncated}
            />
          )}

          <div className={activeTab === "visual" ? "pt-2" : ""}>
            <ResultTable
              columns={response.columns}
              rows={response.rows}
              totalRowCount={response.total_row_count}
              datasetRowCount={response.dataset_row_count}
              truncated={response.truncated}
              highlightCoordinates={highlightCoords}
            />
          </div>
        </div>
      )}

      {/* 6. Collapsible Evidence Inspection Drawer */}
      {showEvidence && (
        <div className="pt-3 border-t">
          <EvidencePanel
            evidence={response.evidence}
            verification={response.verification}
            executedSql={response.executed_sql}
            traceEvents={response.trace_events}
            onHighlightEvidence={(coords) => {
              setHighlightCoords(coords);
              setActiveTab("table");
            }}
          />
        </div>
      )}
    </div>
  );
}
