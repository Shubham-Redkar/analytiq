"use client";

import React, { useEffect, useState } from "react";
import type { StreamProgressEvent } from "../../lib/analysis-types";
import { Loader2 } from "lucide-react";

interface WorkflowProgressProps {
  currentEvent: StreamProgressEvent | null;
  startedAt?: number | null;
}

const STAGE_LABELS: Record<string, { label: string; desc: string }> = {
  admission: {
    label: "Waiting to start analysis",
    desc: "Acquiring analytical execution permit...",
  },
  supervisor: {
    label: "Understanding your question",
    desc: "Analyzing intent and parameters...",
  },
  schema_grounding: {
    label: "Checking dataset information",
    desc: "Grounding question against dataset columns...",
  },
  planner: {
    label: "Preparing the analytical query",
    desc: "Formulating deterministic SQL query...",
  },
  validator: {
    label: "Validating the query",
    desc: "Ensuring query safety and structural validity...",
  },
  executor: {
    label: "Analyzing your data",
    desc: "Executing query in DuckDB engine...",
  },
  interpreter: {
    label: "Preparing the findings",
    desc: "Interpreting results and extracting factual claims...",
  },
  verifier: {
    label: "Verifying the results",
    desc: "Validating claims against computed evidence...",
  },
  persistence: {
    label: "Saving your analysis",
    desc: "Recording verified session history...",
  },
};

export function WorkflowProgress({ currentEvent, startedAt }: WorkflowProgressProps) {
  const [elapsedSeconds, setElapsedSeconds] = useState<number>(0);

  useEffect(() => {
    if (!startedAt) {
      return;
    }

    const interval = setInterval(() => {
      setElapsedSeconds(Math.max(0, (Date.now() - startedAt) / 1000));
    }, 100);

    return () => clearInterval(interval);
  }, [startedAt]);

  if (!currentEvent && !startedAt) return null;

  const isTerminal =
    currentEvent?.event_type === "completed" ||
    currentEvent?.event_type === "result" ||
    currentEvent?.event_type === "cancelled" ||
    currentEvent?.event_type === "error";

  if (isTerminal) return null;

  const stageKey = currentEvent?.stage || "supervisor";
  const mapped = STAGE_LABELS[stageKey] || {
    label: currentEvent?.stage_name || "Executing analytical workflow",
    desc: "Processing your analytical question...",
  };

  return (
    <div className="w-full max-w-2xl mx-auto p-4 border border-border/80 rounded-2xl bg-card/90 shadow-2xs animate-in fade-in duration-200">
      <div className="flex items-center gap-3.5">
        <Loader2 className="h-5 w-5 animate-spin text-primary shrink-0" />
        <div className="space-y-1 flex-1 min-w-0">
          <div className="flex items-center justify-between gap-2">
            <span className="text-sm font-medium text-foreground tracking-tight">
              {mapped.label}
            </span>
            <span className="text-xs text-muted-foreground font-mono tabular-nums">
              {elapsedSeconds.toFixed(1)}s
            </span>
          </div>
          <p className="text-xs text-muted-foreground truncate">{mapped.desc}</p>
        </div>
      </div>
    </div>
  );
}
