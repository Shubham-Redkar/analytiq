"use client";

import React, { useState, useMemo } from "react";
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
import { recommendChart } from "../../lib/chart-recommender";
import { formatColumnLabel, formatDisplayHeader } from "../../lib/suggested-questions";

interface AnalysisResponseCardProps {
  response: WorkflowAnalysisResponse;
  onClarify?: (option: string) => void;
}

/**
 * Build a human-readable verified insight from deterministic result data.
 * Produces clear analytical findings (e.g. ranking comparisons, rate percentages, totals)
 * while keeping technical verification statements (row count match, exact claim proofs)
 * segregated inside the Evidence Panel.
 */
function buildHumanReadableInsight(response: WorkflowAnalysisResponse): string | null {
  if (response.unsupported_reason) return response.unsupported_reason;
  if (response.status === "failed" && response.error_message) return response.error_message;

  const { columns, rows, returned_row_count } = response;
  if (!columns || columns.length === 0 || !rows || rows.length === 0) {
    return returned_row_count > 0
      ? "Results computed successfully from analytical query."
      : "The analytical query completed with 0 matching records.";
  }

  // 1. Single scalar metric result (1 row, 1 column)
  if (rows.length === 1 && columns.length === 1) {
    const col = columns[0];
    const val = rows[0][0];
    const label = formatDisplayHeader(col.name);
    const formatted =
      typeof val === "number"
        ? val.toLocaleString(undefined, { maximumFractionDigits: 4 })
        : String(val);
    return `${label}: ${formatted}`;
  }

  // 2. Grouped Categorical Comparison (2 columns: Dimension + Metric, ≥ 2 rows)
  if (columns.length === 2 && rows.length >= 2) {
    const dimCol = columns[0];
    const metricCol = columns[1];
    const metricNameLower = metricCol.name.toLowerCase();
    const isProportion =
      metricNameLower.includes("rate") ||
      metricNameLower.includes("ratio") ||
      metricNameLower.includes("proportion") ||
      metricNameLower.includes("pct") ||
      metricNameLower.includes("percent") ||
      metricNameLower.includes("share");

    // Format metric values nicely
    const formatMetricVal = (v: unknown): string => {
      if (typeof v === "number") {
        if (isProportion && v >= 0 && v <= 1) {
          return `${(v * 100).toFixed(2)}%`;
        }
        return v.toLocaleString(undefined, { maximumFractionDigits: 2 });
      }
      return String(v ?? "");
    };

    // Format dimension values nicely (e.g. pclass: 1 -> "Class 1")
    const formatDimVal = (dimName: string, val: unknown): string => {
      const dLower = dimName.toLowerCase();
      const sVal = String(val ?? "");
      if (dLower === "pclass" || dLower === "class" || dLower === "passenger_class") {
        if (sVal === "1") return "Class 1";
        if (sVal === "2") return "Class 2";
        if (sVal === "3") return "Class 3";
        return `Class ${sVal}`;
      }
      return sVal;
    };

    // Sort rows descending by metric value
    const sorted = [...rows].sort((a, b) => {
      const va = typeof a[1] === "number" ? a[1] : Number(a[1]) || 0;
      const vb = typeof b[1] === "number" ? b[1] : Number(b[1]) || 0;
      return vb - va;
    });

    const metricLabel = formatColumnLabel(metricCol.name);
    const isClassDim = dimCol.name.toLowerCase().includes("class");
    const entitySuffix = isClassDim ? " passengers" : "";

    if (sorted.length === 2) {
      const [top, second] = sorted;
      const topDim = formatDimVal(dimCol.name, top[0]);
      const secDim = formatDimVal(dimCol.name, second[0]);
      const topVal = formatMetricVal(top[1]);
      const secVal = formatMetricVal(second[1]);

      if (top[1] === second[1]) {
        return `${topDim} and ${secDim} tied for ${metricLabel} at ${topVal}.`;
      }
      return `${topDim}${entitySuffix} had the higher ${metricLabel} at ${topVal}, compared to ${secDim} at ${secVal}.`;
    }

    if (sorted.length >= 3) {
      const top = sorted[0];
      const topDim = formatDimVal(dimCol.name, top[0]);
      const topVal = formatMetricVal(top[1]);

      // Check if top is tied
      if (sorted[0][1] === sorted[1][1]) {
        const tiedDims = sorted
          .filter((r) => r[1] === top[1])
          .map((r) => formatDimVal(dimCol.name, r[0]));
        return `${tiedDims.join(" and ")} tied for the highest ${metricLabel} at ${topVal}.`;
      }

      // Format remaining items
      const rest = sorted
        .slice(1)
        .map((r) => `${formatDimVal(dimCol.name, r[0])} at ${formatMetricVal(r[1])}`);
      let restPhrase = "";
      if (rest.length === 2) {
        restPhrase = `${rest[0]} and ${rest[1]}`;
      } else {
        restPhrase = `${rest.slice(0, -1).join(", ")}, and ${rest[rest.length - 1]}`;
      }

      return `${topDim}${entitySuffix} had the highest ${metricLabel} at ${topVal}, followed by ${restPhrase}.`;
    }
  }

  // Fallback to interpretation or cleaned non-technical summary
  const raw = response.interpretation?.summary || response.verification?.verified_explanation;
  if (
    raw &&
    !raw.startsWith("Returned row count") &&
    !raw.startsWith("Analysis returned") &&
    !raw.includes("Verified ")
  ) {
    return raw.replace(/\b(0\.\d{4,})\b/g, (match) => {
      const val = parseFloat(match);
      return val >= 0 && val <= 1 ? `${(val * 100).toFixed(2)}%` : match;
    });
  }

  return `Results computed successfully for ${returned_row_count} records.`;
}

export function AnalysisResponseCard({ response, onClarify }: AnalysisResponseCardProps) {
  // Determine default tab: show chart tab if data is chart-eligible, otherwise table
  const rec = useMemo(() => {
    if (!response.columns || !response.rows) return null;
    return recommendChart(
      response.columns,
      response.rows,
      response.returned_row_count,
      response.truncated ?? false
    );
  }, [response]);

  const [activeTab, setActiveTab] = useState<"visual" | "table">(
    rec?.isEligible ? "visual" : "table"
  );
  const [showEvidence, setShowEvidence] = useState(false);
  const [highlightCoords, setHighlightCoords] = useState<{ row: number; colName: string } | null>(
    null
  );

  const answer = buildHumanReadableInsight(response);

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

          {activeTab === "table" && (
            <ResultTable
              columns={response.columns}
              rows={response.rows}
              totalRowCount={response.total_row_count}
              datasetRowCount={response.dataset_row_count}
              truncated={response.truncated}
              highlightCoordinates={highlightCoords}
            />
          )}
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
