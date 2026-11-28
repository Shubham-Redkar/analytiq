import React from "react";
import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { QuestionComposer } from "../components/analysis/question-composer";
import { recommendChart } from "../lib/chart-recommender";
import { ChartContainer } from "../components/analysis/chart-container";
import { AnalysisResponseCard } from "../components/analysis/analysis-response-card";
import { formatDisplayHeader, generateSuggestedQuestions } from "../lib/suggested-questions";
import type { WorkflowAnalysisResponse } from "../lib/analysis-types";

describe("Phase 1: QuestionComposer Draft Preservation & Interaction", () => {
  it("allows typing and editing draft while analysis is running", () => {
    const handleSubmit = vi.fn();
    const handleCancel = vi.fn();

    render(<QuestionComposer onSubmit={handleSubmit} onCancel={handleCancel} isRunning={true} />);

    const textarea = screen.getByPlaceholderText(
      "Prepare your next question while analysis is running..."
    ) as HTMLTextAreaElement;
    expect(textarea).not.toBeDisabled();

    // Type draft while running
    fireEvent.change(textarea, { target: { value: "What is the average age by gender?" } });
    expect(textarea.value).toBe("What is the average age by gender?");

    // Enter key does NOT submit while running
    fireEvent.keyDown(textarea, { key: "Enter", shiftKey: false });
    expect(handleSubmit).not.toHaveBeenCalled();

    // Stop button is present and clickable
    const stopBtn = screen.getByTitle("Stop analysis");
    expect(stopBtn).toBeInTheDocument();
    fireEvent.click(stopBtn);
    expect(handleCancel).toHaveBeenCalledTimes(1);

    // Draft remains intact
    expect(textarea.value).toBe("What is the average age by gender?");
  });

  it("enables send button and preserves draft when analysis finishes", () => {
    const handleSubmit = vi.fn();

    const { rerender } = render(<QuestionComposer onSubmit={handleSubmit} isRunning={true} />);

    const textarea = screen.getByPlaceholderText(
      "Prepare your next question while analysis is running..."
    ) as HTMLTextAreaElement;
    fireEvent.change(textarea, { target: { value: "Next analytical question" } });

    // Transition isRunning to false
    rerender(<QuestionComposer onSubmit={handleSubmit} isRunning={false} />);

    // Text remains intact
    expect(textarea.value).toBe("Next analytical question");

    // Send button is available and enabled
    const sendBtn = screen.getByTitle("Submit analytical question");
    expect(sendBtn).not.toBeDisabled();

    // Submitting clears text and invokes callback
    fireEvent.click(sendBtn);
    expect(handleSubmit).toHaveBeenCalledWith("Next analytical question");
    expect(textarea.value).toBe("");
  });
});

describe("Phase 4 & 5: Generalized Chart Recommender & Bar Scaling", () => {
  it("recommends a bar chart for grouped integer counts (e.g. Pclass + record_count)", () => {
    const rec = recommendChart(
      [
        { name: "Pclass", type: "BIGINT", duckdb_type: "BIGINT" },
        { name: "record_count", type: "BIGINT", duckdb_type: "BIGINT" },
      ],
      [
        [1, 107],
        [2, 93],
        [3, 218],
      ],
      3,
      false
    );

    expect(rec.isEligible).toBe(true);
    expect(rec.type).toBe("bar");
    expect(rec.dimensionColumn).toBe("Pclass");
    expect(rec.metricColumn).toBe("record_count");
  });

  it("recommends a horizontal bar chart for top-5 ranking with long category names", () => {
    const rec = recommendChart(
      [
        { name: "Name", type: "VARCHAR", duckdb_type: "VARCHAR" },
        { name: "Fare", type: "DOUBLE", duckdb_type: "DOUBLE" },
      ],
      [
        ["Cardeza, Mrs. James Warburton Martinez (Charlotte Wardle Drake)", 512.33],
        ["Fortune, Miss. Ethel Flora", 263.0],
        ["Fortune, Mrs. Mark (Mary McDougald)", 263.0],
        ["Ryerson, Mrs. Arthur Larned (Emily Maria Borie)", 262.38],
        ["Ryerson, Master. John Borie", 262.38],
      ],
      5,
      false
    );

    expect(rec.isEligible).toBe(true);
    expect(rec.type).toBe("horizontal-bar");
    expect(rec.dimensionColumn).toBe("Name");
    expect(rec.metricColumn).toBe("Fare");
  });

  it("renders zero-based linear scale for top-5 fare chart without collapsing relative bar lengths", () => {
    const { container } = render(
      <ChartContainer
        columns={[
          { name: "Name", type: "VARCHAR", duckdb_type: "VARCHAR" },
          { name: "Fare", type: "DOUBLE", duckdb_type: "DOUBLE" },
        ]}
        rows={[
          ["Cardeza, Mrs. James Warburton Martinez (Charlotte Wardle Drake)", 512.33],
          ["Fortune, Miss. Ethel Flora", 263.0],
          ["Fortune, Mrs. Mark (Mary McDougald)", 263.0],
          ["Ryerson, Mrs. Arthur Larned (Emily Maria Borie)", 262.38],
          ["Ryerson, Master. John Borie", 262.38],
        ]}
        returnedRowCount={5}
      />
    );

    expect(container).toBeInTheDocument();
    expect(screen.getByText("Fare by Name")).toBeInTheDocument();
  });
});

describe("Phase 6: Operation-Aware Scalar Labels", () => {
  it("formats COUNT(*) and COUNT_STAR aliases cleanly into Total records", () => {
    expect(formatDisplayHeader("COUNT(*)")).toBe("Total records");
    expect(formatDisplayHeader("countstar")).toBe("Total records");
    expect(formatDisplayHeader("count(*) ")).toBe("Total records");
  });

  it("formats correlation and valid pairs cleanly", () => {
    expect(formatDisplayHeader("correlation")).toBe("Correlation");
    expect(formatDisplayHeader("valid_pairs")).toBe("Valid pairs");
  });

  it("renders human-readable findings for record count and correlation responses", () => {
    const countResponse: WorkflowAnalysisResponse = {
      request_id: "req-count",
      dataset_id: "d-1",
      status: "completed",
      question: "How many records are in this dataset?",
      intent: "Count records",
      columns: [{ name: "COUNT(*)", type: "BIGINT" }],
      rows: [[418]],
      returned_row_count: 1,
      truncated: false,
      trace_events: [],
      total_llm_calls: 1,
      correction_attempts: 0,
      total_duration_ms: 120,
    };

    render(<AnalysisResponseCard response={countResponse} />);
    expect(screen.getByText("The dataset contains 418 records.")).toBeInTheDocument();
  });
});

describe("Phase 8: Semantic Suggested Question Deduplication", () => {
  it("filters out semantic equivalents of already answered questions", () => {
    const schema = {
      row_count: 418,
      column_count: 6,
      columns: [
        { name: "PassengerId", duckdb_type: "BIGINT", logical_type: "integer", nullable: false },
        { name: "Survived", duckdb_type: "BIGINT", logical_type: "integer", nullable: false },
        { name: "Pclass", duckdb_type: "BIGINT", logical_type: "integer", nullable: false },
        { name: "Sex", duckdb_type: "VARCHAR", logical_type: "string", nullable: false },
        { name: "Age", duckdb_type: "DOUBLE", logical_type: "float", nullable: true },
        { name: "Fare", duckdb_type: "DOUBLE", logical_type: "float", nullable: true },
      ],
    };

    // Asked "How many records are in this dataset?"
    // Should suppress "How many passengers are in this dataset?"
    const suggestions = generateSuggestedQuestions(schema, "Titanic", [
      "How many records are in this dataset?",
    ]);

    expect(suggestions).not.toContain("How many passengers are in this dataset?");
  });
});
