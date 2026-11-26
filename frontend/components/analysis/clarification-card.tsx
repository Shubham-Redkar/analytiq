"use client";

import React from "react";
import type { ClarificationOutput } from "../../lib/analysis-types";
import { HelpCircle } from "lucide-react";

interface ClarificationCardProps {
  clarification: ClarificationOutput;
  onSelectOption: (optionText: string) => void;
  disabled?: boolean;
}

export function ClarificationCard({
  clarification,
  onSelectOption,
  disabled = false,
}: ClarificationCardProps) {
  if (!clarification.needs_clarification) return null;

  return (
    <div className="p-4 border border-blue-500/30 rounded-xl bg-blue-500/5 space-y-3 my-2">
      <div className="flex items-start gap-2.5">
        <HelpCircle className="h-5 w-5 text-blue-500 shrink-0 mt-0.5" />
        <div className="space-y-1">
          <span className="font-semibold text-sm text-foreground block">Clarification Needed</span>
          <p className="text-xs text-foreground/90 leading-relaxed">
            {clarification.question || "Please clarify your analytical question:"}
          </p>
        </div>
      </div>

      {clarification.options && clarification.options.length > 0 && (
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 pt-1">
          {clarification.options.map((opt) => (
            <button
              key={opt.key}
              onClick={() => onSelectOption(opt.label)}
              disabled={disabled}
              className="text-left p-2.5 rounded-lg border bg-card hover:border-primary hover:bg-muted/50 transition text-xs disabled:opacity-50"
            >
              <div className="font-semibold text-foreground">{opt.label}</div>
              {opt.description && (
                <div className="text-muted-foreground text-[11px] mt-0.5 line-clamp-2">
                  {opt.description}
                </div>
              )}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
