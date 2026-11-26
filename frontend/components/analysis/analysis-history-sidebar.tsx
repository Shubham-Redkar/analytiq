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
    <div className="flex flex-col h-full space-y-3">
      <div className="flex items-center justify-between pb-2 border-b">
        <span className="text-xs font-semibold text-foreground uppercase tracking-wider">
          Analysis History
        </span>
        <button
          onClick={onNewSession}
          className="flex items-center gap-1 text-xs px-2 py-1 rounded-md bg-primary text-primary-foreground hover:bg-primary/90 transition"
        >
          <Plus className="h-3.5 w-3.5" />
          <span>New</span>
        </button>
      </div>

      <div className="flex-1 overflow-y-auto space-y-1">
        {sessions.length === 0 ? (
          <div className="text-center py-8 text-xs text-muted-foreground">
            No previous sessions. Start an analysis to persist history.
          </div>
        ) : (
          sessions.map((s) => {
            const isSelected = s.id === currentSessionId;
            const isEditing = s.id === editingId;

            return (
              <div
                key={s.id}
                onClick={() => !isEditing && onSelectSession(s.id)}
                className={`group p-2 rounded-lg text-xs cursor-pointer transition flex items-center justify-between gap-1 border ${
                  isSelected
                    ? "bg-accent border-primary/40 font-medium"
                    : "border-transparent hover:bg-muted/50"
                }`}
              >
                <div className="flex items-center gap-2 overflow-hidden flex-1">
                  <MessageSquare className="h-3.5 w-3.5 text-muted-foreground shrink-0" />
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
                      className="px-1 py-0.5 border rounded text-xs bg-background text-foreground w-full focus:outline-none"
                      autoFocus
                    />
                  ) : (
                    <div className="truncate">
                      <div className="truncate text-foreground">{s.title}</div>
                      {s.dataset_name && (
                        <div className="text-[10px] text-muted-foreground truncate">
                          {s.dataset_name} · {s.run_count} runs
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
                        className="p-1 hover:text-emerald-500 text-muted-foreground"
                      >
                        <Check className="h-3.5 w-3.5" />
                      </button>
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          setEditingId(null);
                        }}
                        className="p-1 hover:text-rose-500 text-muted-foreground"
                      >
                        <X className="h-3.5 w-3.5" />
                      </button>
                    </>
                  ) : (
                    <>
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          startRename(s);
                        }}
                        className="p-1 hover:text-foreground text-muted-foreground"
                        title="Rename"
                      >
                        <Edit2 className="h-3 w-3" />
                      </button>
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          onDeleteSession(s.id);
                        }}
                        className="p-1 hover:text-rose-500 text-muted-foreground"
                        title="Delete"
                      >
                        <Trash2 className="h-3 w-3" />
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
