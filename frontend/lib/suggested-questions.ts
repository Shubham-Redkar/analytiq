/**
 * AnalytIQ Semantic Schema-Aware Suggested Questions Generator (M6.1).
 *
 * Deterministically constructs high-quality starter analytical questions from actual dataset columns.
 * Distinguishes semantic column roles:
 * - Identifiers (PassengerId, Id, UUID) -> excluded from SUM/AVG/trend, used only for counts
 * - High-cardinality descriptive text (Name, Description, URL) -> excluded from grouping
 * - Numeric measures (Age, Fare, Revenue, Price, Quantity) -> candidates for AVG/SUM
 * - Categorical dimensions (Sex, Pclass, Region, Category, Department) -> candidates for GROUP BY
 * - Binary outcomes (Survived, Approved, Completed) -> candidates for rate/percentage comparisons
 * - Temporal dimensions (Date, Timestamp, CreatedAt) -> candidates for trends
 */

import type { DatasetSchema, ColumnSchema } from "./types";

export interface SemanticColumnRole {
  name: string;
  role: "identifier" | "measure" | "categorical" | "binary_outcome" | "temporal" | "free_text" | "unknown";
}

export function classifyColumn(col: ColumnSchema): SemanticColumnRole["role"] {
  const nameLower = col.name.toLowerCase().trim();
  const typeLower = col.duckdb_type.toLowerCase();

  // 1. Identifiers
  if (
    nameLower.endsWith("id") ||
    nameLower.startsWith("id_") ||
    nameLower === "id" ||
    nameLower.includes("uuid") ||
    nameLower.includes("guid") ||
    nameLower.includes("ssn")
  ) {
    return "identifier";
  }

  // 2. Binary outcomes
  if (
    nameLower === "survived" ||
    nameLower === "active" ||
    nameLower === "is_active" ||
    nameLower === "approved" ||
    nameLower === "completed" ||
    nameLower === "success" ||
    nameLower === "churned"
  ) {
    return "binary_outcome";
  }

  // 3. Temporal
  if (
    typeLower.includes("date") ||
    typeLower.includes("timestamp") ||
    typeLower.includes("time") ||
    nameLower.includes("date") ||
    nameLower.includes("year") ||
    nameLower.includes("month")
  ) {
    return "temporal";
  }

  // 4. Free text / high-cardinality descriptions
  if (
    nameLower === "name" ||
    nameLower.includes("full_name") ||
    nameLower.includes("first_name") ||
    nameLower.includes("last_name") ||
    nameLower.includes("description") ||
    nameLower.includes("comment") ||
    nameLower.includes("address") ||
    nameLower.includes("email") ||
    nameLower.includes("phone") ||
    nameLower.includes("ticket")
  ) {
    return "free_text";
  }

  // 5. Categorical
  if (
    nameLower === "pclass" ||
    nameLower === "class" ||
    nameLower === "sex" ||
    nameLower === "gender" ||
    nameLower === "region" ||
    nameLower === "country" ||
    nameLower === "state" ||
    nameLower === "city" ||
    nameLower === "status" ||
    nameLower === "category" ||
    nameLower === "department" ||
    nameLower === "tier" ||
    nameLower === "embarked" ||
    nameLower.endsWith("_type") ||
    nameLower.endsWith("_status")
  ) {
    return "categorical";
  }

  // 6. Numeric measures
  const isNumeric =
    typeLower.includes("int") ||
    typeLower.includes("float") ||
    typeLower.includes("double") ||
    typeLower.includes("decimal") ||
    typeLower.includes("numeric") ||
    typeLower.includes("real");

  if (isNumeric) {
    return "measure";
  }

  // Fallback string/varchar to categorical if not classified as free_text
  if (typeLower.includes("varchar") || typeLower.includes("text") || typeLower.includes("string")) {
    return "categorical";
  }

  return "unknown";
}

export function generateSuggestedQuestions(schema?: DatasetSchema | null, datasetName?: string): string[] {
  if (!schema || !schema.columns || schema.columns.length === 0) {
    return [
      "How many total records are in this dataset?",
      "Which columns have missing values?",
    ];
  }

  const columns = schema.columns;
  const classified: SemanticColumnRole[] = columns.map((c) => ({
    name: c.name,
    role: classifyColumn(c),
  }));

  const measures = classified.filter((c) => c.role === "measure");
  const categoricals = classified.filter((c) => c.role === "categorical");
  const outcomes = classified.filter((c) => c.role === "binary_outcome");
  const temporals = classified.filter((c) => c.role === "temporal");

  const suggestions: string[] = [];

  // Entity phrasing based on dataset name
  const isTitanic = datasetName?.toLowerCase().includes("titanic");
  const entityName = isTitanic ? "passengers" : "records";

  // 1. Overall record count
  suggestions.push(`How many ${entityName} are in this dataset?`);

  // 2. Binary outcome comparison (e.g. survival rate by gender/class)
  if (outcomes.length > 0 && categoricals.length > 0) {
    const outcomeCol = outcomes[0].name;
    const catCol = categoricals[0].name;
    suggestions.push(`Compare ${outcomeCol.toLowerCase()} rates by ${catCol}.`);
  }

  // 3. Measure comparison grouped by categorical (e.g. average fare by passenger class)
  if (measures.length > 0 && categoricals.length > 0) {
    const measureCol = measures[0].name;
    const catCol = categoricals.length > 1 ? categoricals[1].name : categoricals[0].name;
    suggestions.push(`What is the average ${measureCol} by ${catCol}?`);
  } else if (measures.length > 0) {
    suggestions.push(`What is the average ${measures[0].name}?`);
  }

  // 4. Distribution / count by category
  if (categoricals.length > 0) {
    const catCol = categoricals[0].name;
    suggestions.push(`How many ${entityName} belong to each ${catCol}?`);
  }

  // 5. Temporal trend if temporal column exists
  if (temporals.length > 0 && measures.length > 0) {
    suggestions.push(`Show trend of ${measures[0].name} over ${temporals[0].name}.`);
  }

  // 6. Data quality / missing values
  suggestions.push("Which columns contain missing values?");

  // Return top 4 distinct questions
  return Array.from(new Set(suggestions)).slice(0, 4);
}
