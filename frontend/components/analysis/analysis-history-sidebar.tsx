"use client";

import React, { useState } from "react";
import type { AnalysisSessionSummary } from "../../lib/analysis-types";
import { Plus, MessageSquare, Trash2, Edit2, Check, X } from "lucide-react";

interface AnalysisHistorySidebarProps {
  sessions: AnalysisSessionSummary[];
  currentSessionId?: string | null;
  onSelectSession: (sessionId: string) => void;
  onNewSession: () => void;
  onRenameSession: (sessionId: string, newTitle: string) => void;
  onDeleteSession: (sessionId: string) => void;
}

export function AnalysisHistorySidebar({
  sessions,
  currentSessionId,
  onSelectSession,
  onNewSession,
  onRenameSession,
  onDeleteSession,
}: AnalysisHistorySidebarProps) {
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editTitle, setEditTitle] = useState("");

  const startRename = (s: AnalysisSessionSummary) => {
    setEditingId(s.id);
    setEditTitle(s.title);
  };

  const saveRename = (sessionId: string) => {
    if (editTitle.trim()) {
      onRenameSession(sessionId, editTitle.trim());
    }
    setEditingId(null);
  };

  return (
    <div className="flex flex-col h-full space-y-3.5">
      <div className="flex items-center justify-between pb-3 border-b border-border">
        <h2 className="text-sm font-semibold tracking-tight text-foreground">
          Analysis History
        </h2>
        <button
          onClick={onNewSession}
          className="flex items-center gap-1.5 text-xs font-medium px-3 h-8 rounded-lg bg-primary text-primary-foreground hover:bg-primary/90 transition shadow-2xs cursor-pointer"
        >
          <Plus className="h-3.5 w-3.5" />
          <span>New analysis</span>
        </button>
      </div>

      <div className="flex-1 overflow-y-auto space-y-1 pr-0.5">
        {sessions.length === 0 ? (
          <div className="text-center py-10 px-3 space-y-1.5">
            <p className="text-sm font-medium text-foreground/80">No analyses yet</p>
            <p className="text-[13px] text-muted-foreground leading-relaxed">
              Your analytical sessions will appear here.
            </p>
          </div>
        ) : (
          sessions.map((s) => {
            const isSelected = s.id === currentSessionId;
            const isEditing = s.id === editingId;

            return (
              <div
                key={s.id}
                onClick={() => !isEditing && onSelectSession(s.id)}
                className={`group p-2.5 rounded-xl text-sm cursor-pointer transition flex items-center justify-between gap-2 border ${
                  isSelected
                    ? "bg-accent border-primary/40 font-medium text-accent-foreground shadow-2xs"
                    : "border-transparent hover:bg-muted/60 text-muted-foreground hover:text-foreground"
                }`}
              >
                <div className="flex items-center gap-2.5 overflow-hidden flex-1 min-w-0">
                  <MessageSquare className="h-4 w-4 text-muted-foreground shrink-0" />
                  {isEditing ? (
                    <input
                      type="text"
                      value={editTitle}
                      onChange={(e) => setEditTitle(e.target.value)}
                      onClick={(e) => e.stopPropagation()}
                      onKeyDown={(e) => {
                        if (e.key === "Enter") saveRename(s.id);
                        if (e.key === "Escape") setEditingId(null);
                      }}
                      className="px-2 py-1 border rounded-lg text-sm bg-background text-foreground w-full focus:outline-none focus:ring-1 focus:ring-primary"
                      autoFocus
                    />
                  ) : (
                    <div className="truncate min-w-0">
                      <div className="truncate text-sm text-foreground">{s.title}</div>
                      {s.dataset_name && (
                        <div className="text-xs text-muted-foreground truncate mt-0.5">
                          {s.dataset_name} · {s.run_count} {s.run_count === 1 ? "query" : "queries"}
                        </div>
                      )}
                    </div>
                  )}
                </div>

                <div className="flex items-center gap-1 shrink-0 opacity-0 group-hover:opacity-100 transition">
                  {isEditing ? (
                    <>
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          saveRename(s.id);
                        }}
                        className="p-1.5 hover:text-emerald-500 text-muted-foreground cursor-pointer"
                        title="Save title"
                      >
                        <Check className="h-4 w-4" />
                      </button>
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          setEditingId(null);
                        }}
                        className="p-1.5 hover:text-rose-500 text-muted-foreground cursor-pointer"
                        title="Cancel"
                      >
                        <X className="h-4 w-4" />
                      </button>
                    </>
                  ) : (
                    <>
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          startRename(s);
                        }}
                        className="p-1.5 hover:text-foreground text-muted-foreground rounded-md hover:bg-muted transition cursor-pointer"
                        title="Rename"
                      >
                        <Edit2 className="h-3.5 w-3.5" />
                      </button>
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          onDeleteSession(s.id);
                        }}
                        className="p-1.5 hover:text-rose-500 text-muted-foreground rounded-md hover:bg-muted transition cursor-pointer"
                        title="Delete"
                      >
                        <Trash2 className="h-3.5 w-3.5" />
                      </button>
                    </>
                  )}
                </div>
              </div>
            );
          })
        )}
      </div>
    </div>
  );
}
