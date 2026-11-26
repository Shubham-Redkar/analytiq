/**
 * AnalytIQ Deterministic Chart Recommendation Engine (M6).
 *
 * Principle: Charts must be derived exclusively from deterministic result data.
 * No LLM hallucinations or guessing values.
 */

import type { AnalyticalResultColumn } from "./analysis-types";

export type ChartType = "metric" | "bar" | "horizontal-bar" | "line" | "pie" | "table";

export interface ChartRecommendation {
  type: ChartType;
  title: string;
  dimensionColumn?: string;
  metricColumn?: string;
  additionalMetricColumns?: string[];
  isEligible: boolean;
  reason?: string;
}

export function recommendChart(
  columns: AnalyticalResultColumn[],
  rows: (string | number | boolean | null)[][],
  returnedRowCount: number,
  truncated: boolean
): ChartRecommendation {
  if (returnedRowCount === 0 || rows.length === 0 || columns.length === 0) {
    return {
      type: "table",
      title: "Tabular View",
      isEligible: false,
      reason: "No result rows returned to visualize.",
    };
  }

  // 1. Single scalar metric check (1 row, 1 numeric column)
  if (rows.length === 1 && columns.length === 1) {
    const col = columns[0];
    const val = rows[0][0];
    const colType = (col.duckdb_type || col.type || "").toLowerCase();
    if (
      typeof val === "number" ||
      colType.includes("int") ||
      colType.includes("float") ||
      colType.includes("double")
    ) {
      return {
        type: "metric",
        title: col.name,
        metricColumn: col.name,
        isEligible: true,
      };
    }
  }

  // Identify column types
  const numericCols: string[] = [];
  const textCols: string[] = [];
  const dateCols: string[] = [];

  columns.forEach((col) => {
    const t = (col.duckdb_type || col.type || "").toLowerCase();
    const isNum =
      t.includes("int") ||
      t.includes("float") ||
      t.includes("double") ||
      t.includes("decimal") ||
      t.includes("numeric");
    const isDate = t.includes("date") || t.includes("timestamp") || t.includes("time");

    if (isNum) {
      numericCols.push(col.name);
    } else if (isDate) {
      dateCols.push(col.name);
    } else {
      textCols.push(col.name);
    }
  });

  // 2. Temporal aggregation -> Line Chart
  if (dateCols.length >= 1 && numericCols.length >= 1) {
    return {
      type: "line",
      title: `${numericCols[0]} over ${dateCols[0]}`,
      dimensionColumn: dateCols[0],
      metricColumn: numericCols[0],
      additionalMetricColumns: numericCols.slice(1),
      isEligible: true,
    };
  }

  // 3. Categorical + Numeric Metric -> Bar or Horizontal Bar
  if (textCols.length >= 1 && numericCols.length >= 1) {
    const dimCol = textCols[0];
    const metricCol = numericCols[0];

    // Check average label length
    let maxLen = 0;
    const colIdx = columns.findIndex((c) => c.name === dimCol);
    rows.forEach((r) => {
      const v = String(r[colIdx] ?? "");
      if (v.length > maxLen) maxLen = v.length;
    });

    const isHorizontal = maxLen > 15;
    return {
      type: isHorizontal ? "horizontal-bar" : "bar",
      title: `${metricCol} by ${dimCol}`,
      dimensionColumn: dimCol,
      metricColumn: metricCol,
      isEligible: true,
      reason: truncated ? "Chart displays returned top subset." : undefined,
    };
  }

  // 4. Default to standard table
  return {
    type: "table",
    title: "Result Table",
    isEligible: false,
    reason: "Tabular structure without clear categorical or temporal metric grouping.",
  };
}
