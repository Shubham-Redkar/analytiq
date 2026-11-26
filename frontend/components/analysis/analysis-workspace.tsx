"use client";

import React, { useState, useEffect, useMemo, useRef } from "react";
import type { Dataset } from "../../lib/types";
import type {
  WorkflowAnalysisResponse,
  AnalysisSessionSummary,
  StreamProgressEvent,
} from "../../lib/analysis-types";
import { api } from "../../lib/api";
import { QuestionComposer } from "./question-composer";
import { AnalysisResponseCard } from "./analysis-response-card";
import { WorkflowProgress } from "./workflow-progress";
import { AnalysisHistorySidebar } from "./analysis-history-sidebar";
import { generateSuggestedQuestions } from "../../lib/suggested-questions";
import { Database, PanelLeftClose, PanelLeftOpen, AlertCircle } from "lucide-react";
import {
  Select,
  SelectTrigger,
  SelectValue,
  SelectPortal,
  SelectPositioner,
  SelectPopup,
  SelectItem,
} from "../ui/select";

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
  const [responses, setResponses] = useState<WorkflowAnalysisResponse[]>([]);
  const [isRunning, setIsRunning] = useState<boolean>(false);
  const [currentProgressEvent, setCurrentProgressEvent] = useState<StreamProgressEvent | null>(null);
  const [showHistory, setShowHistory] = useState<boolean>(true);
  const [generalError, setGeneralError] = useState<string | null>(null);

  const activeDataset = useMemo(() => {
    return datasets.find((d) => d.id === activeDatasetId);
  }, [datasets, activeDatasetId]);

  const suggestedQuestions = useMemo(() => {
    return generateSuggestedQuestions(activeDataset?.schema_json);
  }, [activeDataset]);

  const activeRequestIdRef = useRef<string | null>(null);

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
      const session = await api.getAnalysisSession(sessionId);
      setActiveSessionId(session.id);
      if (session.dataset_id !== activeDatasetId) {
        setActiveDatasetId(session.dataset_id);
      }

      // Reconstruct WorkflowAnalysisResponse array from saved runs
      const reconstructed: WorkflowAnalysisResponse[] = session.runs.map((r) => ({
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
      }));
      setResponses(reconstructed);
    } catch (e: unknown) {
      setGeneralError(e instanceof Error ? e.message : "Failed to load session history.");
    }
  };

  const handleNewSession = () => {
    setActiveSessionId(null);
    setResponses([]);
    setCurrentProgressEvent(null);
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
      await api.deleteAnalysisSession(sessionId);
      if (activeSessionId === sessionId) {
        handleNewSession();
      }
      loadSessions();
    } catch {
      // Ignored
    }
  };

  // Submit analytical question via SSE Streaming
  const handleSubmitQuestion = async (question: string) => {
    if (!activeDatasetId) {
      setGeneralError("Please select a ready dataset before submitting questions.");
      return;
    }

    setIsRunning(true);
    setGeneralError(null);
    setCurrentProgressEvent({
      request_id: "init",
      seq: 0,
      event_type: "accepted",
      stage_name: "Submitting analytical question to workflow...",
      status: "queued",
      timestamp: new Date().toISOString(),
      elapsed_ms: 0,
    });

    try {
      // Fetch authenticated SSE stream
      const response = await fetch(`/api/v1/datasets/${activeDatasetId}/analysis/stream`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        credentials: "include",
        body: JSON.stringify({
          question,
          session_id: activeSessionId || undefined,
        }),
      });

      if (!response.ok) {
        const errJson = await response.json().catch(() => ({}));
        throw new Error(errJson.detail || `Server error ${response.status}`);
      }

      if (!response.body) {
        throw new Error("No readable response stream received.");
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder("utf-8");
      let buffer = "";

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
                setResponses((prev) => [...prev, event.result!]);
                loadSessions();
              } else if (event.event_type === "error") {
                const msg = (event.payload?.detail as string) || "Workflow encountered an error.";
                setGeneralError(msg);
              }
            } catch {
              // Parse error
            }
          }
        }
      }
    } catch (err: unknown) {
      setGeneralError(err instanceof Error ? err.message : "Analytical query execution failed.");
    } finally {
      setIsRunning(false);
      setCurrentProgressEvent(null);
      activeRequestIdRef.current = null;
    }
  };

  const handleCancel = async () => {
    if (activeRequestIdRef.current && activeDatasetId) {
      try {
        await api.cancelAnalysis(activeDatasetId, activeRequestIdRef.current);
      } catch {
        // Ignored
      }
    }
    setIsRunning(false);
    setCurrentProgressEvent(null);
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
              {showHistory ? <PanelLeftClose className="h-4 w-4" /> : <PanelLeftOpen className="h-4 w-4" />}
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
                <SelectTrigger className="h-9 min-w-[220px] max-w-[320px] gap-2.5 font-medium text-sm">
                  <Database className="h-4 w-4 text-primary shrink-0" />
                  <SelectValue placeholder="Select dataset...">
                    {activeDataset?.name || "Select dataset..."}
                  </SelectValue>
                </SelectTrigger>
                <SelectPortal>
                  <SelectPositioner>
                    <SelectPopup className="min-w-[280px]">
                      {datasets.map((d) => (
                        <SelectItem
                          key={d.id}
                          value={d.id}
                          disabled={d.status !== "ready"}
                        >
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
        <div className="flex-1 min-h-0 overflow-y-auto p-6 space-y-6">
          {generalError && (
            <div className="p-4 rounded-xl border border-rose-500/30 bg-rose-500/10 text-xs text-rose-500 flex items-center justify-between gap-2">
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

          {responses.length === 0 && !isRunning && (
            <div className="max-w-2xl mx-auto my-auto py-8 text-center space-y-5">
              <div className="h-14 w-14 rounded-2xl bg-primary/10 text-primary flex items-center justify-center mx-auto mb-2 shadow-2xs">
                <Database className="h-7 w-7" />
              </div>
              <h2 className="text-2xl font-semibold tracking-tight text-foreground">
                What would you like to explore?
              </h2>
              <p className="text-[15px] text-muted-foreground leading-relaxed max-w-lg mx-auto">
                {activeDataset
                  ? `Ask questions about ${activeDataset.name}, explore your data, and discover insights backed by evidence.`
                  : "Select an uploaded dataset to begin exploring insights backed by deterministic evidence."}
              </p>

              {suggestedQuestions.length > 0 && (
                <div className="pt-3 text-left">
                  <h3 className="text-sm font-medium text-foreground/80 mb-3">
                    Suggested questions
                  </h3>
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                    {suggestedQuestions.map((q, idx) => (
                      <button
                        key={idx}
                        onClick={() => handleSubmitQuestion(q)}
                        className="text-left text-sm p-3.5 min-h-[52px] rounded-xl border border-border bg-card hover:bg-muted/50 hover:border-primary/40 focus-visible:ring-2 focus-visible:ring-ring transition-all text-card-foreground shadow-2xs group flex items-start justify-between gap-2.5 cursor-pointer"
                      >
                        <span className="line-clamp-2 leading-relaxed font-normal">{q}</span>
                        <span className="text-primary opacity-0 group-hover:opacity-100 transition-opacity text-base shrink-0 mt-0.5">&rarr;</span>
                      </button>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}

          {responses.map((resp, idx) => (
            <AnalysisResponseCard
              key={`${resp.request_id}-${idx}`}
              response={resp}
              onClarify={(opt) => handleSubmitQuestion(opt)}
            />
          ))}

          {isRunning && (
            <WorkflowProgress
              currentEvent={currentProgressEvent}
              onCancel={handleCancel}
            />
          )}
        </div>

        {/* Sticky Question Composer Footer */}
        <footer className="border-t p-4 bg-background/95 backdrop-blur-xs shrink-0 max-w-4xl w-full mx-auto">
          <QuestionComposer
            onSubmit={handleSubmitQuestion}
            onCancel={handleCancel}
            isRunning={isRunning}
            disabled={!activeDataset || activeDataset.status !== "ready"}
            suggestedQuestions={responses.length === 0 ? [] : suggestedQuestions}
          />
        </footer>
      </main>
    </div>
  );
}
