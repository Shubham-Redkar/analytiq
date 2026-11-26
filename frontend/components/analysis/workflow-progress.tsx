"use client";

import React from "react";
import type { StreamProgressEvent } from "../../lib/analysis-types";
import { Loader2, Square } from "lucide-react";

interface WorkflowProgressProps {
  currentEvent: StreamProgressEvent | null;
  onCancel?: () => void;
  canCancel?: boolean;
}

export function WorkflowProgress({
  currentEvent,
  onCancel,
  canCancel = true,
}: WorkflowProgressProps) {
  if (!currentEvent) return null;

  const isTerminal =
    currentEvent.event_type === "completed" ||
    currentEvent.event_type === "result" ||
    currentEvent.event_type === "cancelled" ||
    currentEvent.event_type === "error";

  if (isTerminal) return null;

  return (
    <div className="p-3 border rounded-xl bg-card/80 flex items-center justify-between gap-3 shadow-xs animate-in fade-in duration-200 my-2">
      <div className="flex items-center gap-3">
        <Loader2 className="h-4 w-4 animate-spin text-primary shrink-0" />
        <div className="space-y-0.5">
          <div className="text-xs font-semibold text-foreground flex items-center gap-2">
            <span>{currentEvent.stage_name || "Executing analytical workflow..."}</span>
            <span className="text-[10px] text-muted-foreground font-mono">
              {(currentEvent.elapsed_ms / 1000).toFixed(1)}s
            </span>
          </div>
          {currentEvent.stage && (
            <div className="text-[11px] text-muted-foreground">
              Stage: <span className="font-mono">{currentEvent.stage}</span>
            </div>
          )}
        </div>
      </div>

      {canCancel && onCancel && (
        <button
          onClick={onCancel}
          className="flex items-center gap-1.5 px-2.5 py-1 text-xs font-medium rounded-md border border-rose-500/30 text-rose-500 hover:bg-rose-500/10 transition"
        >
          <Square className="h-3 w-3 fill-current" />
          <span>Stop</span>
        </button>
      )}
    </div>
  );
}
