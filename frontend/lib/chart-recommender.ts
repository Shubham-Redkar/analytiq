/**
 * AnalytIQ Deterministic Chart Recommendation Engine (M6 / M7.1).
 *
 * Principle: Charts must be derived exclusively from deterministic result data.
 * No LLM hallucinations or guessing values.
 *
 * M7.1 fix: numeric categorical detection.
 * Integer columns used as grouping dimensions (e.g. pclass=1,2,3) have low cardinality
 * in the result rows. When an integer column appears first and the result has 2–50 distinct
 * values across ≤50 rows, treat it as a categorical dimension rather than a metric.
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
  /** True when the metric values are proportions (0–1 range) → format as % */
  metricIsProportion?: boolean;
  reason?: string;
}

/** Known categorical column name patterns even when stored as integers. */
const KNOWN_CATEGORICAL_NAMES = new Set([
  "pclass",
  "class",
  "passenger_class",
  "sex",
  "gender",
  "embarked",
  "embarkation",
  "survived",
  "survival",
  "rating",
  "score",
  "grade",
  "rank",
  "priority",
  "level",
  "category",
  "cat",
  "type",
  "status",
  "flag",
  "group",
  "region",
  "zone",
  "segment",
  "tier",
  "bin",
  "bucket",
]);

/** Known metric keywords that should never be converted into categorical dimensions. */
const KNOWN_METRIC_PATTERNS = [
  /count/i,
  /sum/i,
  /avg/i,
  /average/i,
  /total/i,
  /rate/i,
  /ratio/i,
  /pct/i,
  /percent/i,
  /fare/i,
  /price/i,
  /amount/i,
  /revenue/i,
  /cost/i,
  /profit/i,
  /score/i,
  /correlation/i,
  /corr/i,
];

/** Returns true when a column should be treated as a categorical dimension. */
function isCategoricalDimension(
  col: AnalyticalResultColumn,
  colIdx: number,
  rows: (string | number | boolean | null)[][],
  numericMetricCandidates: number
): boolean {
  const nameLower = col.name.toLowerCase().replace(/[^a-z0-9_]/g, "");
  const t = (col.duckdb_type || col.type || "").toLowerCase();

  // If the column name explicitly matches known metric patterns, it is a metric, NEVER a dimension
  if (KNOWN_METRIC_PATTERNS.some((pat) => pat.test(col.name))) {
    return false;
  }

  // Always treat text/varchar columns as categorical
  if (
    !t.includes("int") &&
    !t.includes("float") &&
    !t.includes("double") &&
    !t.includes("decimal")
  ) {
    return false; // handled by textCols already
  }

  // If the column name matches a known categorical pattern
  if (KNOWN_CATEGORICAL_NAMES.has(nameLower)) return true;

  // Heuristic: low-cardinality INTEGER column where every value is distinct in a small result
  // Only apply to true integers (not floats/doubles which are metrics)
  const isIntType =
    t.includes("int") || t.includes("bigint") || t.includes("tinyint") || t.includes("smallint");
  if (!isIntType) return false; // floats are always metrics, never categorical dims

  if (numericMetricCandidates < 1) return false;
  if (rows.length < 2 || rows.length > 50) return false;

  const distinctValues = new Set<unknown>();
  for (const row of rows) {
    distinctValues.add(row[colIdx]);
  }
  const cardinality = distinctValues.size;

  // Low cardinality relative to result size indicates it's a grouping dimension
  const isLowCardinality = cardinality <= 20 && cardinality === rows.length;
  return isLowCardinality;
}

/** Detect whether metric values represent proportions (all between 0 and 1). */
function detectProportion(
  col: AnalyticalResultColumn,
  colIdx: number,
  rows: (string | number | boolean | null)[][]
): boolean {
  const nameLower = col.name.toLowerCase();
  const looksLikeRate =
    nameLower.includes("rate") ||
    nameLower.includes("ratio") ||
    nameLower.includes("proportion") ||
    nameLower.includes("pct") ||
    nameLower.includes("percent") ||
    nameLower.includes("share");

  if (!looksLikeRate) return false;

  // Verify all numeric values are in [0, 1]
  for (const row of rows) {
    const val = row[colIdx];
    if (val === null || val === undefined) continue;
    const n = typeof val === "number" ? val : Number(val);
    if (isNaN(n) || n < 0 || n > 1) return false;
  }
  return true;
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

  // Classify column types
  const numericCols: string[] = [];
  const textCols: string[] = [];
  const dateCols: string[] = [];

  // First pass: identify all numeric columns (potential metrics)
  columns.forEach((col) => {
    const t = (col.duckdb_type || col.type || "").toLowerCase();
    const isNum =
      t.includes("int") ||
      t.includes("float") ||
      t.includes("double") ||
      t.includes("decimal") ||
      t.includes("numeric");
    const isDate = t.includes("date") || t.includes("timestamp") || t.includes("time");

    if (isDate) {
      dateCols.push(col.name);
    } else if (!isNum) {
      textCols.push(col.name);
    }
    // numeric columns: defer until after categorical detection
  });

  // Second pass: separate numeric columns into categoricalDims vs metricCols
  // A numeric column is a categorical dimension if it passes isCategoricalDimension()
  const categoricalDimsFromNumeric: string[] = [];

  columns.forEach((col, colIdx) => {
    const t = (col.duckdb_type || col.type || "").toLowerCase();
    const isNum =
      t.includes("int") ||
      t.includes("float") ||
      t.includes("double") ||
      t.includes("decimal") ||
      t.includes("numeric");
    if (!isNum) return;

    // Count how many OTHER numeric columns exist (potential metrics)
    const otherNumerics = columns.filter((c, i) => {
      if (i === colIdx) return false;
      const ct = (c.duckdb_type || c.type || "").toLowerCase();
      return (
        ct.includes("int") ||
        ct.includes("float") ||
        ct.includes("double") ||
        ct.includes("decimal") ||
        ct.includes("numeric")
      );
    }).length;

    if (isCategoricalDimension(col, colIdx, rows, otherNumerics)) {
      categoricalDimsFromNumeric.push(col.name);
    } else {
      numericCols.push(col.name);
    }
  });

  // Merge text + promoted categorical dims into dimensions pool
  const allDims = [...textCols, ...categoricalDimsFromNumeric];

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

  // 3. Categorical/Dimension + Numeric Metric -> Bar or Horizontal Bar
  if (allDims.length >= 1 && numericCols.length >= 1) {
    const dimCol = allDims[0];
    const metricCol = numericCols[0];

    // Find column indices for label length check
    const dimIdx = columns.findIndex((c) => c.name === dimCol);
    const metricIdx = columns.findIndex((c) => c.name === metricCol);

    let maxLen = 0;
    rows.forEach((r) => {
      const v = String(r[dimIdx] ?? "");
      if (v.length > maxLen) maxLen = v.length;
    });

    const isHorizontal = maxLen > 15;
    const metricIsProportion =
      metricIdx >= 0 ? detectProportion(columns[metricIdx], metricIdx, rows) : false;

    return {
      type: isHorizontal ? "horizontal-bar" : "bar",
      title: `${metricCol} by ${dimCol}`,
      dimensionColumn: dimCol,
      metricColumn: metricCol,
      isEligible: true,
      metricIsProportion,
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
