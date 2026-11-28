/**
 * M7.1 Regression Tests — Visualization, Formatting & Deduplication
 *
 * Covers:
 * - Numeric categorical dimension detection (pclass-like BIGINT columns)
 * - Proportion detection and % formatting in chart recommender
 * - Suggested question deduplication
 * - Column label formatting
 */

import { describe, it, expect, vi } from "vitest";
import React from "react";
import { render, screen, fireEvent } from "@testing-library/react";
import { recommendChart } from "../lib/chart-recommender";
import {
  generateSuggestedQuestions,
  formatColumnLabel,
  formatDisplayHeader,
} from "../lib/suggested-questions";
import { api, ApiError } from "../lib/api";
import { AnalysisResponseCard } from "../components/analysis/analysis-response-card";
import type { WorkflowAnalysisResponse } from "../lib/analysis-types";

// ---------------------------------------------------------------------------
// 1. Chart Recommender — Numeric Categorical Detection
// ---------------------------------------------------------------------------

describe("recommendChart — numeric categorical dimension (M7.1)", () => {
  const pclassCol = { name: "pclass", duckdb_type: "BIGINT", python_type: "int", nullable: false };
  const survivalRateCol = {
    name: "survival_rate",
    duckdb_type: "DOUBLE",
    python_type: "float",
    nullable: false,
  };

  it("promotes pclass (BIGINT, known categorical name) to dimension → bar chart", () => {
    const columns = [pclassCol, survivalRateCol];
    const rows: (string | number | boolean | null)[][] = [
      [1, 0.6296296],
      [2, 0.4728],
      [3, 0.2423],
    ];
    const rec = recommendChart(columns, rows, 3, false);
    expect(rec.isEligible).toBe(true);
    expect(rec.type).toBe("bar");
    expect(rec.dimensionColumn).toBe("pclass");
    expect(rec.metricColumn).toBe("survival_rate");
  });

  it("detects survival_rate as proportion (0–1 range with rate in name)", () => {
    const columns = [pclassCol, survivalRateCol];
    const rows: (string | number | boolean | null)[][] = [
      [1, 0.629],
      [2, 0.472],
      [3, 0.242],
    ];
    const rec = recommendChart(columns, rows, 3, false);
    expect(rec.metricIsProportion).toBe(true);
  });

  it("does NOT detect proportion when values are outside 0–1", () => {
    const countCol = {
      name: "survival_rate",
      duckdb_type: "BIGINT",
      python_type: "int",
      nullable: false,
    };
    const columns = [pclassCol, countCol];
    const rows: (string | number | boolean | null)[][] = [
      [1, 123],
      [2, 95],
      [3, 200],
    ];
    const rec = recommendChart(columns, rows, 3, false);
    expect(rec.metricIsProportion).toBeFalsy();
  });

  it("recommends bar chart for text dimension + numeric metric", () => {
    const columns = [
      { name: "sex", duckdb_type: "VARCHAR", python_type: "str", nullable: false },
      { name: "avg_fare", duckdb_type: "DOUBLE", python_type: "float", nullable: false },
    ];
    const rows: (string | number | boolean | null)[][] = [
      ["male", 25.5],
      ["female", 44.8],
    ];
    const rec = recommendChart(columns, rows, 2, false);
    expect(rec.isEligible).toBe(true);
    expect(rec.type).toBe("bar");
    expect(rec.dimensionColumn).toBe("sex");
  });

  it("recommends line chart for temporal + numeric", () => {
    const columns = [
      { name: "month", duckdb_type: "DATE", python_type: "str", nullable: false },
      { name: "revenue", duckdb_type: "DOUBLE", python_type: "float", nullable: false },
    ];
    const rows: (string | number | boolean | null)[][] = [
      ["2026-01-01", 100],
      ["2026-02-01", 150],
    ];
    const rec = recommendChart(columns, rows, 2, false);
    expect(rec.isEligible).toBe(true);
    expect(rec.type).toBe("line");
  });

  it("returns metric type for single scalar row", () => {
    const columns = [
      { name: "total_count", duckdb_type: "BIGINT", python_type: "int", nullable: false },
    ];
    const rows: (string | number | boolean | null)[][] = [[418]];
    const rec = recommendChart(columns, rows, 1, false);
    expect(rec.isEligible).toBe(true);
    expect(rec.type).toBe("metric");
    expect(rec.metricColumn).toBe("total_count");
  });

  it("falls back to table for two pure numeric metric columns (no categorical)", () => {
    const columns = [
      { name: "age", duckdb_type: "DOUBLE", python_type: "float", nullable: false },
      { name: "fare", duckdb_type: "DOUBLE", python_type: "float", nullable: false },
    ];
    // Many rows of continuous data — no clear categorical dimension
    const rows: (string | number | boolean | null)[][] = Array.from({ length: 30 }, (_, i) => [
      20 + i,
      5 + i * 2,
    ]);
    const rec = recommendChart(columns, rows, 30, false);
    // age could be classified as categorical if cardinality === rows.length and rows ≤ 50
    // but age values are unique so cardinality check passes; name does NOT match known categorical names
    // so it should NOT be promoted — stays as numericCol → table fallback
    expect(rec.isEligible).toBe(false);
    expect(rec.type).toBe("table");
  });

  it("returns table when no rows are present", () => {
    const columns = [
      { name: "pclass", duckdb_type: "BIGINT", python_type: "int", nullable: false },
    ];
    const rec = recommendChart(columns, [], 0, false);
    expect(rec.isEligible).toBe(false);
    expect(rec.type).toBe("table");
  });
});

// ---------------------------------------------------------------------------
// 2. Column Label & Display Header Formatting
// ---------------------------------------------------------------------------

describe("formatColumnLabel & formatDisplayHeader (M7.1)", () => {
  it("formats 'pclass' to lowercase label and capitalized display header", () => {
    expect(formatColumnLabel("pclass")).toBe("passenger class");
    expect(formatDisplayHeader("pclass")).toBe("Passenger class");
  });

  it("formats 'survival_rate' to rate label and 'Survival rate (%)' header", () => {
    expect(formatColumnLabel("survival_rate")).toBe("survival rate");
    expect(formatDisplayHeader("survival_rate")).toBe("Survival rate (%)");
  });

  it("formats 'SURVIVALRATE' (all-caps merged) via normalized alias", () => {
    expect(formatColumnLabel("SURVIVALRATE")).toBe("survival rate");
    expect(formatDisplayHeader("SURVIVALRATE")).toBe("Survival rate (%)");
  });

  it("formats 'avg_fare' — snake_case decomposition", () => {
    expect(formatColumnLabel("avg_fare")).toContain("fare");
    expect(formatDisplayHeader("avg_fare")).toMatch(/^[A-Z]/);
  });

  it("preserves already-readable label like 'Revenue'", () => {
    expect(formatColumnLabel("revenue")).toBe("revenue");
    expect(formatDisplayHeader("revenue")).toBe("Revenue");
  });
});

// ---------------------------------------------------------------------------
// 3. Suggested Questions Deduplication
// ---------------------------------------------------------------------------

describe("generateSuggestedQuestions — deduplication (M7.1)", () => {
  const titanicSchema = {
    row_count: 418,
    column_count: 5,
    columns: [
      { name: "pclass", duckdb_type: "BIGINT", logical_type: "int", nullable: false },
      { name: "sex", duckdb_type: "VARCHAR", logical_type: "string", nullable: false },
      { name: "survived", duckdb_type: "BIGINT", logical_type: "int", nullable: false },
      { name: "age", duckdb_type: "DOUBLE", logical_type: "float", nullable: false },
      { name: "fare", duckdb_type: "DOUBLE", logical_type: "float", nullable: false },
    ],
  };

  it("returns suggestions without deduplication when submittedQuestions is absent", () => {
    const qs = generateSuggestedQuestions(titanicSchema, "titanic");
    expect(qs.length).toBeGreaterThan(0);
  });

  it("filters out already-submitted questions (case-insensitive)", () => {
    const all = generateSuggestedQuestions(titanicSchema, "titanic");
    const submitted = [all[0]]; // simulate user already asked the first suggestion
    const filtered = generateSuggestedQuestions(titanicSchema, "titanic", submitted);
    expect(filtered).not.toContain(all[0]);
    expect(filtered.every((q) => q !== all[0])).toBe(true);
  });

  it("filters case-insensitively", () => {
    const all = generateSuggestedQuestions(titanicSchema, "titanic");
    const submittedUpperCase = [all[0].toUpperCase()];
    const filtered = generateSuggestedQuestions(titanicSchema, "titanic", submittedUpperCase);
    expect(filtered).not.toContain(all[0]);
  });

  it("returns at most 1 remaining suggestion when all top-4 have been submitted", () => {
    const all = generateSuggestedQuestions(titanicSchema, "titanic");
    expect(all.length).toBe(4);
    // Submit all 4 → only the 5th fallback ("Which columns…") can remain
    const filtered = generateSuggestedQuestions(titanicSchema, "titanic", all);
    expect(filtered.length).toBeLessThanOrEqual(1);
  });

  it("returns at most 4 suggestions", () => {
    const qs = generateSuggestedQuestions(titanicSchema, "titanic");
    expect(qs.length).toBeLessThanOrEqual(4);
  });
});

// ---------------------------------------------------------------------------
// 4. API Client Response Contracts (M7.1 Section 13)
// ---------------------------------------------------------------------------

describe("API Client — Void vs JSON contract separation (M7.1)", () => {
  it("deleteAnalysisSession returns void on 204 No Content without error", async () => {
    const fetchSpy = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValueOnce(new Response(null, { status: 204 }));

    await expect(api.deleteAnalysisSession("test-session-id")).resolves.toBeUndefined();
    expect(fetchSpy).toHaveBeenCalled();
    fetchSpy.mockRestore();
  });

  it("deleteReport returns void on 204 No Content without error", async () => {
    const fetchSpy = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValueOnce(new Response(null, { status: 204 }));

    await expect(api.deleteReport("test-report-id")).resolves.toBeUndefined();
    expect(fetchSpy).toHaveBeenCalled();
    fetchSpy.mockRestore();
  });

  it("getReport rejects when server returns unexpected 204 on JSON endpoint", async () => {
    const fetchSpy = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValue(new Response(null, { status: 204 }));

    await expect(api.getReport("test-report-id")).rejects.toThrow(ApiError);
    await expect(api.getReport("test-report-id").catch((e) => e.message)).resolves.toContain(
      "Expected JSON response"
    );
    fetchSpy.mockRestore();
  });

  it("getReport rejects when server returns empty body on JSON endpoint", async () => {
    const fetchSpy = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValueOnce(new Response("", { status: 200 }));

    await expect(api.getReport("test-report-id")).rejects.toThrow(ApiError);
    fetchSpy.mockRestore();
  });
});

// ---------------------------------------------------------------------------
// 5. AnalysisResponseCard — Tab Isolation & Human-Readable Insights (M7.1)
// ---------------------------------------------------------------------------

describe("AnalysisResponseCard — Tab Isolation & Insights (M7.1)", () => {
  const survivalResponse: WorkflowAnalysisResponse = {
    request_id: "req-1",
    dataset_id: "ds-1",
    intent: "aggregation",
    question: "Compare survival rates by passenger class.",
    status: "completed",
    trace_events: [],
    total_llm_calls: 1,
    correction_attempts: 0,
    total_duration_ms: 120,
    columns: [
      { name: "pclass", duckdb_type: "BIGINT", python_type: "int" },
      { name: "survival_rate", duckdb_type: "DOUBLE", python_type: "float" },
    ],
    rows: [
      [1, 0.4672897196261682],
      [2, 0.3225806451612903],
      [3, 0.3302752293577982],
    ],
    total_row_count: 3,
    returned_row_count: 3,
    dataset_row_count: 418,
    truncated: false,
    executed_sql: "SELECT pclass, AVG(survived) as survival_rate FROM dataset GROUP BY pclass",
    interpretation: {
      summary: "Comparison of survival rates across passenger classes.",
      key_takeaways: [],
      limitations: [],
    },
    verification: {
      status: "verified",
      verified_claims_count: 2,
      total_claims_proposed: 2,
      contradicted_claims_count: 0,
      unverifiable_claims_count: 0,
      verified_explanation:
        "Returned row count 3 matches query output. Verified SurvivalRate = 0.4672897196261682 for Pclass = 1.",
      verified_claims: [],
      contradicted_claims: [],
      unverifiable_claims: [],
      verification_notes: null,
    },
  };

  it("renders human-readable insight for categorical comparison (not raw verification text)", () => {
    render(<AnalysisResponseCard response={survivalResponse} />);

    // Primary insight should be human-readable and describe findings with percentage formatting
    expect(
      screen.getByText(
        /Class 1 passengers had the highest survival rate at 46\.73%, followed by Class 3 at 33\.03% and Class 2 at 32\.26%\./i
      )
    ).toBeInTheDocument();

    // Raw technical verification text should NOT be in the main insight card
    expect(
      screen.queryByText(/Returned row count 3 matches query output/i)
    ).not.toBeInTheDocument();
  });

  it("enforces Chart/Table tab isolation: Chart tab does NOT render table", () => {
    render(<AnalysisResponseCard response={survivalResponse} />);

    // By default for eligible chart data, Chart tab is active
    // Table content should NOT be rendered in the document
    expect(screen.queryByText("Showing 1–3 of 3 returned rows")).not.toBeInTheDocument();
  });

  it("switching to Table tab renders table and hides chart", () => {
    render(<AnalysisResponseCard response={survivalResponse} />);

    const tableTabBtn = screen.getByRole("button", { name: /table/i });
    fireEvent.click(tableTabBtn);

    // Now table is rendered
    expect(screen.getByText("Showing 1–3 of 3 returned rows")).toBeInTheDocument();
    // Headers should use formatDisplayHeader
    expect(screen.getByText("Passenger class")).toBeInTheDocument();
    expect(screen.getByText("Survival rate (%)")).toBeInTheDocument();
    // Cell value formatted as %
    expect(screen.getByText("46.73%")).toBeInTheDocument();
  });

  it("evidence drawer reveals technical verification details without cluttering main view", () => {
    render(<AnalysisResponseCard response={survivalResponse} />);

    const evidenceBtn = screen.getByRole("button", { name: /evidence/i });
    fireEvent.click(evidenceBtn);

    // Technical verification statement is now visible inside Evidence panel
    expect(screen.getByText(/Returned row count 3 matches query output/i)).toBeInTheDocument();
  });
});
