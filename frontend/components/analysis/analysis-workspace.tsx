"use client";

import React, { useState, useEffect, useMemo, useRef } from "react";
import type { Dataset } from "../../lib/types";
import type {
  WorkflowAnalysisResponse,
  AnalysisSessionSummary,
  StreamProgressEvent,
  ConversationTurn,
} from "../../lib/analysis-types";
import { api, ApiError } from "../../lib/api";
import { QuestionComposer } from "./question-composer";
import { AnalysisResponseCard } from "./analysis-response-card";
import { WorkflowProgress } from "./workflow-progress";
import { AnalysisHistorySidebar } from "./analysis-history-sidebar";
import { generateSuggestedQuestions } from "../../lib/suggested-questions";
import { Database, PanelLeftClose, PanelLeftOpen, AlertCircle, RotateCcw } from "lucide-react";
import { cn } from "cn";
import {
  Select,
  SelectTrigger,
  SelectValue,
  SelectPortal,
  SelectPositioner,
  SelectPopup,
  SelectItem,
} from "../ui/select";

function mapErrorToUserFriendlyMessage(status: number, message: string): string {
  if (status === 401) {
    return "Your session has expired. Please sign in again.";
  }
  if (status === 404) {
    return "This dataset is no longer available for analysis.";
  }
  if (status === 429) {
    return "The analysis service is busy. Please try again shortly.";
  }
  if (status >= 500) {
    return "Unable to complete this analysis. Please try again.";
  }
  if (message.toLowerCase().includes("network") || message.toLowerCase().includes("connection")) {
    return "The connection to the analysis service was interrupted. Please try again.";
  }
  return message || "Unable to complete this analysis. Please try again.";
}

interface AnalysisWorkspaceProps {
  initialDatasets: Dataset[];
  selectedDatasetId?: string | null;
}

export function AnalysisWorkspace({
  initialDatasets,
  selectedDatasetId: defaultDatasetId,
}: AnalysisWorkspaceProps) {
  const [datasets] = useState<Dataset[]>(initialDatasets);
  const [activeDatasetId, setActiveDatasetId] = useState<string>(
    defaultDatasetId || (initialDatasets.find((d) => d.status === "ready")?.id ?? "")
  );

  const [sessions, setSessions] = useState<AnalysisSessionSummary[]>([]);
  const [activeSessionId, setActiveSessionId] = useState<string | null>(null);
  const [turns, setTurns] = useState<ConversationTurn[]>([]);
  const [isRunning, setIsRunning] = useState<boolean>(false);
  const [currentProgressEvent, setCurrentProgressEvent] = useState<StreamProgressEvent | null>(
    null
  );
  const [activeTurnId, setActiveTurnId] = useState<string | null>(null);
  const [showHistory, setShowHistory] = useState<boolean>(true);
  const [generalError, setGeneralError] = useState<string | null>(null);

  const activeDataset = useMemo(() => {
    return datasets.find((d) => d.id === activeDatasetId);
  }, [datasets, activeDatasetId]);

  const suggestedQuestions = useMemo(() => {
    return generateSuggestedQuestions(activeDataset?.schema_json);
  }, [activeDataset]);

  const activeRequestIdRef = useRef<string | null>(null);
  const abortControllerRef = useRef<AbortController | null>(null);

  // Load sessions for active dataset
  const loadSessions = React.useCallback(async () => {
    try {
      const res = await api.listAnalysisSessions(activeDatasetId || undefined);
      setSessions(res.items);
    } catch {
      // Non-blocking history load
    }
  }, [activeDatasetId]);

  useEffect(() => {
    let ignore = false;
    async function fetchSessions() {
      try {
        const res = await api.listAnalysisSessions(activeDatasetId || undefined);
        if (!ignore) {
          setSessions(res.items);
        }
      } catch {
        // Non-blocking
      }
    }
    if (activeDatasetId) {
      fetchSessions();
    }
    return () => {
      ignore = true;
    };
  }, [activeDatasetId]);

  // Load historical session runs
  const handleSelectSession = async (sessionId: string) => {
    try {
      setIsRunning(false);
      setGeneralError(null);
      setCurrentProgressEvent(null);
      setActiveTurnId(null);
      const session = await api.getAnalysisSession(sessionId);
      setActiveSessionId(session.id);
      if (session.dataset_id !== activeDatasetId) {
        setActiveDatasetId(session.dataset_id);
      }

      // Reconstruct ConversationTurn array from saved runs
      const reconstructed: ConversationTurn[] = session.runs.map((r) => {
        const resp: WorkflowAnalysisResponse = {
          request_id: r.request_id,
          dataset_id: session.dataset_id,
          status: r.status,
          question: r.question,
          intent: r.intent,
          executed_sql: r.executed_sql,
          columns: r.columns,
          rows: r.rows,
          returned_row_count: r.returned_row_count,
          dataset_row_count: r.dataset_row_count,
          total_row_count: r.total_row_count,
          truncated: r.truncated,
          unsupported_reason: r.unsupported_reason,
          error_message: r.error_message,
          evidence: r.evidence,
          verification: r.verification,
          clarification: r.clarification,
          trace_events: [],
          total_llm_calls: 0,
          correction_attempts: 0,
          total_duration_ms: 0,
        };
        return {
          id: r.request_id || r.id,
          question: r.question,
          status: r.status === "failed" ? "failed" : "completed",
          response: resp,
          errorMessage: r.error_message,
        };
      });
      setTurns(reconstructed);
    } catch (e: unknown) {
      setGeneralError(e instanceof Error ? e.message : "Failed to load session history.");
    }
  };

  const handleNewSession = () => {
    setActiveSessionId(null);
    setTurns([]);
    setCurrentProgressEvent(null);
    setActiveTurnId(null);
    setGeneralError(null);
  };

  const handleRenameSession = async (sessionId: string, title: string) => {
    try {
      await api.updateAnalysisSession(sessionId, title);
      loadSessions();
    } catch {
      // Ignored
    }
  };

  const handleDeleteSession = async (sessionId: string) => {
    try {
      // If the session being deleted is currently active and running, abort active request
      if (activeSessionId === sessionId) {
        if (abortControllerRef.current) {
          abortControllerRef.current.abort();
        }
        setIsRunning(false);
      }
      await api.deleteAnalysisSession(sessionId);
      if (activeSessionId === sessionId) {
        handleNewSession();
      }
      await loadSessions();
      setGeneralError(null);
      return true;
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Failed to delete analysis session.";
      setGeneralError(msg);
      return false;
    }
  };

  // Submit analytical question via SSE Streaming with optimistic user message
  const handleSubmitQuestion = React.useCallback(
    async (question: string, retryTurnId?: string) => {
      if (!activeDatasetId) {
        setGeneralError("Please select a ready dataset before submitting questions.");
        return;
      }

      const turnId = retryTurnId || `turn_${Date.now()}`;
      const startTime = Date.now();

      if (retryTurnId) {
        setTurns((prev) =>
          prev.map((t) =>
            t.id === retryTurnId
              ? { ...t, status: "processing", errorMessage: null, startedAt: startTime }
              : t
          )
        );
      } else {
        const newTurn: ConversationTurn = {
          id: turnId,
          question,
          status: "processing",
          startedAt: startTime,
        };
        setTurns((prev) => [...prev, newTurn]);
      }

      setIsRunning(true);
      setActiveTurnId(turnId);
      setGeneralError(null);
      setCurrentProgressEvent({
        request_id: "init",
        seq: 0,
        event_type: "accepted",
        stage: "supervisor",
        stage_name: "Submitting analytical question to workflow...",
        status: "queued",
        timestamp: new Date().toISOString(),
        elapsed_ms: 0,
      });

      const abortController = new AbortController();
      abortControllerRef.current = abortController;

      try {
        // Fetch authenticated SSE stream
        const response = await fetch(`/api/v1/datasets/${activeDatasetId}/analysis/stream`, {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
          credentials: "include",
          signal: abortController.signal,
          body: JSON.stringify({
            question,
            session_id: activeSessionId || undefined,
          }),
        });

        if (!response.ok) {
          const errJson = await response.json().catch(() => ({}));
          const userMsg = mapErrorToUserFriendlyMessage(
            response.status,
            errJson.detail || `Server error ${response.status}`
          );
          throw new ApiError(userMsg, response.status);
        }

        if (!response.body) {
          throw new Error("No readable response stream received.");
        }

        const reader = response.body.getReader();
        const decoder = new TextDecoder("utf-8");
        let buffer = "";
        let receivedResult: WorkflowAnalysisResponse | null = null;

        while (true) {
          const { value, done } = await reader.read();
          if (done) break;

          buffer += decoder.decode(value, { stream: true });
          const lines = buffer.split("\n\n");
          buffer = lines.pop() || "";

          for (const line of lines) {
            const trimmed = line.trim();
            if (trimmed.startsWith("data:")) {
              const jsonStr = trimmed.replace(/^data:\s*/, "");
              try {
                const event: StreamProgressEvent = JSON.parse(jsonStr);
                activeRequestIdRef.current = event.request_id;
                setCurrentProgressEvent(event);

                if (event.event_type === "result" && event.result) {
                  receivedResult = event.result;
                  setTurns((prev) =>
                    prev.map((t) =>
                      t.id === turnId
                        ? {
                            ...t,
                            status: "completed",
                            response: event.result!,
                            errorMessage: null,
                          }
                        : t
                    )
                  );
                  loadSessions();
                } else if (event.event_type === "cancelled") {
                  setTurns((prev) =>
                    prev.map((t) =>
                      t.id === turnId
                        ? { ...t, status: "cancelled", errorMessage: "Analysis cancelled by user." }
                        : t
                    )
                  );
                } else if (event.event_type === "error") {
                  const msg = (event.payload?.detail as string) || "Workflow encountered an error.";
                  setTurns((prev) =>
                    prev.map((t) =>
                      t.id === turnId ? { ...t, status: "failed", errorMessage: msg } : t
                    )
                  );
                }
              } catch {
                // Parse error
              }
            }
          }
        }

        // If stream ended without error and without receiving result (unexpected termination)
        if (!receivedResult) {
          setTurns((prev) =>
            prev.map((t) => {
              if (t.id === turnId && t.status === "processing") {
                return {
                  ...t,
                  status: "failed",
                  errorMessage: "The connection was interrupted before the analysis completed.",
                };
              }
              return t;
            })
          );
        }
      } catch (err: unknown) {
        if (err instanceof Error && err.name === "AbortError") {
          setTurns((prev) =>
            prev.map((t) =>
              t.id === turnId
                ? { ...t, status: "cancelled", errorMessage: "Analysis cancelled by user." }
                : t
            )
          );
        } else {
          const errorMsg =
            err instanceof ApiError
              ? err.message
              : err instanceof Error
                ? mapErrorToUserFriendlyMessage(0, err.message)
                : "Unable to complete this analysis. Please try again.";
          setTurns((prev) =>
            prev.map((t) =>
              t.id === turnId ? { ...t, status: "failed", errorMessage: errorMsg } : t
            )
          );
        }
      } finally {
        setIsRunning(false);
        setCurrentProgressEvent(null);
        setActiveTurnId(null);
        activeRequestIdRef.current = null;
        abortControllerRef.current = null;
      }
    },
    [activeDatasetId, activeSessionId, loadSessions]
  );

  const handleCancel = async () => {
    if (activeRequestIdRef.current && activeDatasetId) {
      try {
        await api.cancelAnalysis(activeDatasetId, activeRequestIdRef.current);
      } catch {
        // Ignored
      }
    }
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
    }
    if (activeTurnId) {
      setTurns((prev) =>
        prev.map((t) =>
          t.id === activeTurnId
            ? { ...t, status: "cancelled", errorMessage: "Analysis cancelled by user." }
            : t
        )
      );
    }
    setIsRunning(false);
    setCurrentProgressEvent(null);
    setActiveTurnId(null);
    activeRequestIdRef.current = null;
    abortControllerRef.current = null;
  };

  return (
    <div className="flex h-full overflow-hidden bg-background">
      {/* Left Sidebar: Analysis Sessions & History */}
      {showHistory && (
        <aside className="w-64 border-r p-4 bg-muted/10 shrink-0 hidden md:block">
          <AnalysisHistorySidebar
            sessions={sessions}
            currentSessionId={activeSessionId}
            onSelectSession={handleSelectSession}
            onNewSession={handleNewSession}
            onRenameSession={handleRenameSession}
            onDeleteSession={handleDeleteSession}
          />
        </aside>
      )}

      {/* Main Workspace */}
      <main className="flex-1 flex flex-col h-full min-h-0 overflow-hidden">
        {/* Workspace Top Header */}
        <header className="border-b px-6 py-3 flex items-center justify-between bg-card/50 shrink-0">
          <div className="flex items-center gap-3">
            <button
              onClick={() => setShowHistory(!showHistory)}
              className="p-2 rounded-lg border hover:bg-muted text-muted-foreground transition hidden md:flex items-center cursor-pointer"
              title={showHistory ? "Collapse history" : "Expand history"}
            >
              {showHistory ? (
                <PanelLeftClose className="h-4 w-4" />
              ) : (
                <PanelLeftOpen className="h-4 w-4" />
              )}
            </button>

            <div className="flex items-center gap-2">
              <Select
                value={activeDatasetId}
                onValueChange={(val: string | null) => {
                  if (val && val !== activeDatasetId) {
                    setActiveDatasetId(val);
                    handleNewSession();
                  }
                }}
              >
                <SelectTrigger className="h-9 min-w-[220px] max-w-[320px] font-medium text-sm">
                  <Database className="h-4 w-4 text-primary shrink-0" />
                  <SelectValue
                    placeholder="Select dataset..."
                    className="truncate text-left font-medium"
                  >
                    {activeDataset?.name || "Select dataset..."}
                  </SelectValue>
                </SelectTrigger>
                <SelectPortal>
                  <SelectPositioner>
                    <SelectPopup className="min-w-[280px]">
                      {datasets.map((d) => (
                        <SelectItem key={d.id} value={d.id} disabled={d.status !== "ready"}>
                          <div className="flex flex-col gap-0.5">
                            <span className="font-medium text-sm text-foreground">{d.name}</span>
                            <span className="text-xs text-muted-foreground">
                              {d.status === "ready"
                                ? `${d.row_count?.toLocaleString() ?? 0} rows · ${d.column_count ?? 0} columns`
                                : `Status: ${d.status}`}
                            </span>
                          </div>
                        </SelectItem>
                      ))}
                    </SelectPopup>
                  </SelectPositioner>
                </SelectPortal>
              </Select>
            </div>
          </div>

          {activeDataset && (
            <div className="text-[13px] text-muted-foreground flex items-center gap-3">
              <span>{activeDataset.row_count?.toLocaleString() ?? 0} rows</span>
              <span>·</span>
              <span>{activeDataset.column_count ?? 0} columns</span>
            </div>
          )}
        </header>

        {/* Conversation Feed */}
        <div
          className={cn(
            "flex-1 min-h-0 overflow-y-auto p-6",
            turns.length === 0 && !isRunning
              ? "flex flex-col justify-center items-center pb-12"
              : "space-y-6"
          )}
        >
          {generalError && (
            <div className="w-full max-w-2xl mx-auto p-4 mb-4 rounded-xl border border-rose-500/30 bg-rose-500/10 text-xs text-rose-500 flex items-center justify-between gap-2">
              <div className="flex items-center gap-2">
                <AlertCircle className="h-4 w-4 shrink-0" />
                <span>{generalError}</span>
              </div>
              <button
                onClick={() => setGeneralError(null)}
                className="p-1 hover:text-foreground text-rose-400 cursor-pointer"
              >
                Dismiss
              </button>
            </div>
          )}

          {turns.length === 0 && !isRunning && (
            <div className="w-full max-w-2xl mx-auto text-center space-y-6">
              <div className="h-14 w-14 rounded-2xl bg-primary/10 text-primary flex items-center justify-center mx-auto mb-2 shadow-2xs">
                <Database className="h-7 w-7" />
              </div>
              <div className="space-y-2">
                <h2 className="text-2xl font-semibold tracking-tight text-foreground">
                  What would you like to explore?
                </h2>
                <p className="text-[15px] text-muted-foreground leading-relaxed max-w-lg mx-auto">
                  {activeDataset
                    ? `Ask questions about ${activeDataset.name}, explore your data, and discover insights backed by evidence.`
                    : "Select an uploaded dataset to begin exploring insights backed by deterministic evidence."}
                </p>
              </div>

              {suggestedQuestions.length > 0 && (
                <div className="pt-2 text-left space-y-3">
                  <h3 className="text-sm font-medium text-foreground/80">Suggested questions</h3>
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                    {suggestedQuestions.map((q, idx) => (
                      <button
                        key={idx}
                        onClick={() => handleSubmitQuestion(q)}
                        className="text-left text-sm p-3.5 min-h-[52px] rounded-xl border border-border bg-card hover:bg-muted/50 hover:border-primary/40 focus-visible:ring-2 focus-visible:ring-ring transition-all text-card-foreground shadow-2xs group flex items-start justify-between gap-2.5 cursor-pointer"
                      >
                        <span className="line-clamp-2 leading-relaxed font-normal">{q}</span>
                        <span className="text-primary opacity-0 group-hover:opacity-100 transition-opacity text-base shrink-0 mt-0.5">
                          &rarr;
                        </span>
                      </button>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}

          {/* Conversation turns */}
          {turns.map((turn) => (
            <div key={turn.id} className="space-y-4 max-w-4xl mx-auto">
              {/* User question bubble */}
              <div className="flex justify-end">
                <div className="max-w-[85%] sm:max-w-[75%] rounded-2xl bg-primary text-primary-foreground px-4 py-3 text-[15px] leading-relaxed shadow-2xs font-normal">
                  {turn.question}
                </div>
              </div>

              {/* Turn states */}
              {turn.status === "processing" && (
                <WorkflowProgress currentEvent={currentProgressEvent} startedAt={turn.startedAt} />
              )}

              {turn.status === "completed" && turn.response && (
                <AnalysisResponseCard
                  response={turn.response}
                  onClarify={(opt) => handleSubmitQuestion(opt)}
                />
              )}

              {turn.status === "failed" && (
                <div className="border border-border/80 rounded-2xl bg-card p-5 space-y-3.5 shadow-xs">
                  <div className="flex items-center gap-2 text-rose-500 font-medium text-sm">
                    <AlertCircle className="h-4 w-4 shrink-0" />
                    <span>Unable to complete analysis</span>
                  </div>
                  <p className="text-sm text-muted-foreground leading-relaxed">
                    {turn.errorMessage || "The connection was interrupted. Please try again."}
                  </p>
                  <div>
                    <button
                      onClick={() => handleSubmitQuestion(turn.question, turn.id)}
                      disabled={isRunning}
                      className="inline-flex items-center gap-1.5 text-xs font-medium px-3 py-1.5 rounded-lg border border-border bg-card hover:bg-muted text-foreground transition cursor-pointer disabled:opacity-50"
                    >
                      <RotateCcw className="h-3.5 w-3.5" />
                      <span>Retry analysis</span>
                    </button>
                  </div>
                </div>
              )}

              {turn.status === "cancelled" && (
                <div className="border border-border/80 rounded-2xl bg-card/60 p-4 text-xs text-muted-foreground flex items-center justify-between gap-2 shadow-2xs">
                  <span>Analysis cancelled by user.</span>
                  <button
                    onClick={() => handleSubmitQuestion(turn.question, turn.id)}
                    disabled={isRunning}
                    className="inline-flex items-center gap-1 text-xs text-foreground hover:underline cursor-pointer"
                  >
                    <RotateCcw className="h-3 w-3" />
                    <span>Retry</span>
                  </button>
                </div>
              )}
            </div>
          ))}
        </div>

        {/* Sticky Question Composer Footer */}
        <footer className="border-t p-4 bg-background/95 backdrop-blur-xs shrink-0 max-w-4xl w-full mx-auto">
          <QuestionComposer
            onSubmit={handleSubmitQuestion}
            onCancel={handleCancel}
            isRunning={isRunning}
            disabled={!activeDataset || activeDataset.status !== "ready"}
            suggestedQuestions={turns.length === 0 ? [] : suggestedQuestions}
          />
        </footer>
      </main>
    </div>
  );
}
