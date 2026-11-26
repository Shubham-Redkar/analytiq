"use client";

import React, { useState } from "react";
import type { AnalysisSessionSummary } from "../../lib/analysis-types";
import { Plus, MessageSquare, Trash2, Edit2, Check, X, AlertCircle } from "lucide-react";
import {
  AlertDialog,
  AlertDialogPopup,
  AlertDialogHeader,
  AlertDialogFooter,
  AlertDialogTitle,
  AlertDialogDescription,
} from "../ui/alert-dialog";
import { Button } from "../ui/button";

interface AnalysisHistorySidebarProps {
  sessions: AnalysisSessionSummary[];
  currentSessionId?: string | null;
  onSelectSession: (sessionId: string) => void;
  onNewSession: () => void;
  onRenameSession: (sessionId: string, newTitle: string) => void;
  onDeleteSession: (sessionId: string) => Promise<boolean | void> | void;
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
  const [sessionToDelete, setSessionToDelete] = useState<AnalysisSessionSummary | null>(null);
  const [isDeleting, setIsDeleting] = useState(false);
  const [deleteError, setDeleteError] = useState<string | null>(null);

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

  const promptDelete = (s: AnalysisSessionSummary) => {
    setDeleteError(null);
    setSessionToDelete(s);
  };

  const handleConfirmDelete = async () => {
    if (!sessionToDelete || isDeleting) return;
    setIsDeleting(true);
    setDeleteError(null);
    try {
      const result = await onDeleteSession(sessionToDelete.id);
      if (result === false) {
        setDeleteError("Failed to delete analysis session. Please try again.");
      } else {
        setSessionToDelete(null);
      }
    } catch (err: unknown) {
      setDeleteError(
        err instanceof Error ? err.message : "Failed to delete analysis session. Please try again."
      );
    } finally {
      setIsDeleting(false);
    }
  };

  return (
    <>
      <div className="flex flex-col h-full space-y-4">
        {/* Full-width New Analysis button above header */}
        <button
          onClick={onNewSession}
          className="flex items-center justify-center gap-2 w-full h-10 px-4 rounded-xl bg-primary text-primary-foreground hover:bg-primary/90 text-sm font-medium transition shadow-2xs cursor-pointer shrink-0"
        >
          <Plus className="h-4 w-4" />
          <span>New analysis</span>
        </button>

        {/* Analysis history section title */}
        <div className="flex items-center justify-between pb-2 border-b border-border">
          <h2 className="text-sm font-semibold tracking-tight text-foreground">Analysis history</h2>
          {sessions.length > 0 && (
            <span className="text-xs text-muted-foreground font-mono">{sessions.length}</span>
          )}
        </div>

        <div className="flex-1 overflow-y-auto space-y-1.5 pr-0.5">
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
                            {s.dataset_name} · {s.run_count}{" "}
                            {s.run_count === 1 ? "query" : "queries"}
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
                            promptDelete(s);
                          }}
                          className="p-1.5 hover:text-rose-500 text-muted-foreground rounded-md hover:bg-muted transition cursor-pointer"
                          title="Delete"
                          aria-label={`Delete ${s.title}`}
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

      {/* Accessible Confirmation Dialog */}
      <AlertDialog
        open={!!sessionToDelete}
        onOpenChange={(open) => {
          if (!open && !isDeleting) {
            setSessionToDelete(null);
            setDeleteError(null);
          }
        }}
      >
        <AlertDialogPopup>
          <AlertDialogHeader>
            <AlertDialogTitle>Delete analysis?</AlertDialogTitle>
            <AlertDialogDescription>
              This will permanently delete &apos;{sessionToDelete?.title}&apos; and its associated
              conversation history and analytical results. This action cannot be undone.
            </AlertDialogDescription>
          </AlertDialogHeader>

          {deleteError && (
            <div className="mt-4 rounded-lg bg-destructive/10 p-3 text-xs text-destructive flex items-center gap-2">
              <AlertCircle className="h-4 w-4 shrink-0" />
              <span>{deleteError}</span>
            </div>
          )}

          <AlertDialogFooter>
            <Button
              variant="outline"
              disabled={isDeleting}
              onClick={() => {
                setSessionToDelete(null);
                setDeleteError(null);
              }}
              autoFocus
              className="cursor-pointer"
            >
              Cancel
            </Button>
            <Button
              variant="destructive"
              disabled={isDeleting}
              onClick={() => void handleConfirmDelete()}
              className="cursor-pointer font-semibold"
            >
              {isDeleting ? "Deleting..." : "Delete analysis"}
            </Button>
          </AlertDialogFooter>
        </AlertDialogPopup>
      </AlertDialog>
    </>
  );
}
