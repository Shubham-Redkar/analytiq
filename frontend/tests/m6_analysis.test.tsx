import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import React from "react";
import { ResultTable } from "../components/analysis/result-table";
import { ClarificationCard } from "../components/analysis/clarification-card";
import { WorkflowProgress } from "../components/analysis/workflow-progress";
import { QuestionComposer } from "../components/analysis/question-composer";
import { recommendChart } from "../lib/chart-recommender";
import { generateSuggestedQuestions } from "../lib/suggested-questions";
import type { StreamProgressEvent } from "../lib/analysis-types";

describe("M6 Analysis Frontend Components & Helpers", () => {
  it("generates deterministic schema-aware suggested questions", () => {
    const schema = {
      row_count: 100,
      column_count: 3,
      columns: [
        { name: "revenue", duckdb_type: "DOUBLE", logical_type: "float", nullable: false },
        { name: "region", duckdb_type: "VARCHAR", logical_type: "string", nullable: false },
        { name: "order_date", duckdb_type: "DATE", logical_type: "date", nullable: false },
      ],
    };

    const questions = generateSuggestedQuestions(schema);
    expect(questions.length).toBeGreaterThan(0);
    expect(questions[0]).toContain("How many records");
    expect(questions.some((q) => q.includes("revenue"))).toBe(true);
    expect(questions.some((q) => q.includes("region"))).toBe(true);
  });

  it("recommends line chart for temporal aggregations", () => {
    const columns = [
      { name: "month", duckdb_type: "DATE", python_type: "str", nullable: false },
      { name: "sales", duckdb_type: "DOUBLE", python_type: "float", nullable: false },
    ];
    const rows = [
      ["2026-01-01", 100],
      ["2026-02-01", 150],
    ];

    const rec = recommendChart(columns, rows, 2, false);
    expect(rec.isEligible).toBe(true);
    expect(rec.type).toBe("line");
    expect(rec.dimensionColumn).toBe("month");
    expect(rec.metricColumn).toBe("sales");
  });

  it("recommends bar chart for categorical aggregations", () => {
    const columns = [
      { name: "region", duckdb_type: "VARCHAR", python_type: "str", nullable: false },
      { name: "count", duckdb_type: "BIGINT", python_type: "int", nullable: false },
    ];
    const rows = [
      ["North", 45],
      ["South", 60],
    ];

    const rec = recommendChart(columns, rows, 2, false);
    expect(rec.isEligible).toBe(true);
    expect(rec.type).toBe("bar");
    expect(rec.dimensionColumn).toBe("region");
    expect(rec.metricColumn).toBe("count");
  });

  it("recommends single metric display for 1x1 scalar result", () => {
    const columns = [
      { name: "total_revenue", duckdb_type: "DOUBLE", python_type: "float", nullable: false },
    ];
    const rows = [[1250000.5]];

    const rec = recommendChart(columns, rows, 1, false);
    expect(rec.isEligible).toBe(true);
    expect(rec.type).toBe("metric");
    expect(rec.metricColumn).toBe("total_revenue");
  });

  it("renders ResultTable with dynamic columns and formatting", () => {
    const columns = [
      { name: "Category", duckdb_type: "VARCHAR", python_type: "str", nullable: false },
      { name: "Amount", duckdb_type: "DOUBLE", python_type: "float", nullable: true },
    ];
    const rows = [
      ["Books", 120.5],
      ["Electronics", null],
    ];

    render(<ResultTable columns={columns} rows={rows} totalRowCount={2} datasetRowCount={100} />);

    expect(screen.getByText("Category")).toBeDefined();
    expect(screen.getByText("Amount")).toBeDefined();
    expect(screen.getByText("Books")).toBeDefined();
    expect(screen.getByText("NULL")).toBeDefined();
  });

  it("renders ClarificationCard and triggers callback on selection", () => {
    const onSelect = vi.fn();
    const clarification = {
      needs_clarification: true,
      question: "Which metric would you like to average?",
      options: [
        { key: "rev", label: "Revenue", description: "Gross recorded revenue" },
        { key: "qty", label: "Quantity", description: "Units sold" },
      ],
    };

    render(<ClarificationCard clarification={clarification} onSelectOption={onSelect} />);

    expect(screen.getByText("Clarification Needed")).toBeDefined();
    expect(screen.getByText("Revenue")).toBeDefined();

    fireEvent.click(screen.getByText("Revenue"));
    expect(onSelect).toHaveBeenCalledWith("Revenue");
  });

  it("WorkflowProgress renders user-friendly stage labels and single progress container", () => {
    const event: StreamProgressEvent = {
      request_id: "test-req",
      seq: 2,
      event_type: "stage_started",
      stage: "supervisor",
      stage_name: "Classifying analytical question",
      status: "running",
      timestamp: new Date().toISOString(),
      elapsed_ms: 50,
    };

    render(<WorkflowProgress currentEvent={event} startedAt={Date.now()} />);

    expect(screen.getByText("Understanding your question")).toBeDefined();
    expect(screen.getByText("Analyzing intent and parameters...")).toBeDefined();
    expect(screen.queryByText("Stage: supervisor")).toBeNull();
    // Confirms no duplicate Stop button in progress card
    expect(screen.queryByText("Stop")).toBeNull();
  });

  it("QuestionComposer renders single Stop control during active processing", () => {
    const onCancel = vi.fn();
    const onSubmit = vi.fn();

    render(
      <QuestionComposer onSubmit={onSubmit} onCancel={onCancel} isRunning={true} disabled={false} />
    );

    const stopButton = screen.getByLabelText("Stop analysis");
    expect(stopButton).toBeDefined();
    fireEvent.click(stopButton);
    expect(onCancel).toHaveBeenCalled();
  });
});
