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
    <div className="flex h-[calc(100vh-4rem)] overflow-hidden bg-background">
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
      <main className="flex-1 flex flex-col h-full overflow-hidden">
        {/* Workspace Top Header */}
        <header className="border-b px-6 py-3.5 flex items-center justify-between bg-card/40 shrink-0">
          <div className="flex items-center gap-3">
            <button
              onClick={() => setShowHistory(!showHistory)}
              className="p-1.5 rounded-lg border hover:bg-muted text-muted-foreground transition hidden md:flex items-center"
              title={showHistory ? "Collapse history" : "Expand history"}
            >
              {showHistory ? <PanelLeftClose className="h-4 w-4" /> : <PanelLeftOpen className="h-4 w-4" />}
            </button>

            <div className="flex items-center gap-2">
              <Database className="h-4 w-4 text-primary" />
              <select
                value={activeDatasetId}
                onChange={(e) => {
                  setActiveDatasetId(e.target.value);
                  handleNewSession();
                }}
                className="font-semibold text-sm bg-transparent border-0 focus:ring-0 text-foreground cursor-pointer pr-2"
              >
                {datasets.map((d) => (
                  <option key={d.id} value={d.id} disabled={d.status !== "ready"}>
                    {d.name} {d.status !== "ready" ? `(${d.status})` : ""}
                  </option>
                ))}
              </select>
            </div>
          </div>

          {activeDataset && (
            <div className="text-xs text-muted-foreground flex items-center gap-3">
              <span>{activeDataset.row_count?.toLocaleString() ?? 0} rows</span>
              <span>·</span>
              <span>{activeDataset.column_count ?? 0} cols</span>
            </div>
          )}
        </header>

        {/* Conversation Feed */}
        <div className="flex-1 overflow-y-auto p-6 space-y-6">
          {generalError && (
            <div className="p-4 rounded-xl border border-rose-500/30 bg-rose-500/10 text-xs text-rose-500 flex items-center justify-between gap-2">
              <div className="flex items-center gap-2">
                <AlertCircle className="h-4 w-4 shrink-0" />
                <span>{generalError}</span>
              </div>
              <button
                onClick={() => setGeneralError(null)}
                className="p-1 hover:text-foreground text-rose-400"
              >
                Dismiss
              </button>
            </div>
          )}

          {responses.length === 0 && !isRunning && (
            <div className="max-w-xl mx-auto my-12 text-center space-y-3">
              <div className="h-12 w-12 rounded-2xl bg-primary/10 text-primary flex items-center justify-center mx-auto mb-2">
                <Database className="h-6 w-6" />
              </div>
              <h2 className="text-lg font-semibold text-foreground">
                Intelligent Analysis. Verified Insights.
              </h2>
              <p className="text-xs text-muted-foreground leading-relaxed">
                Ask analytical questions in natural language. AnalytIQ formulates verified DuckDB queries, validates analytical claims, and cross-checks results against deterministic execution evidence.
              </p>
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
        <footer className="border-t p-4 bg-background/80 backdrop-blur-xs shrink-0 max-w-4xl w-full mx-auto">
          <QuestionComposer
            onSubmit={handleSubmitQuestion}
            onCancel={handleCancel}
            isRunning={isRunning}
            disabled={!activeDataset || activeDataset.status !== "ready"}
            suggestedQuestions={responses.length === 0 ? suggestedQuestions : []}
          />
        </footer>
      </main>
    </div>
  );
}
