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
  role:
    | "identifier"
    | "measure"
    | "categorical"
    | "binary_outcome"
    | "temporal"
    | "free_text"
    | "unknown";
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

/**
 * Format a database column name into a natural human-readable label.
 * Handles snake_case, camelCase, PascalCase, and common analytical aliases.
 */
export function formatColumnLabel(colName: string): string {
  const trimmed = colName.trim();
  const lower = trimmed.toLowerCase();

  // Normalize: strip underscores/camelCase and lowercase for alias lookup
  const normalized = lower.replace(/[_-]/g, "").replace(/\s+/g, "");

  // Known domain-specific semantic mappings (lowercase for sentence flow)
  const aliases: Record<string, string> = {
    pclass: "passenger class",
    passengerclass: "passenger class",
    fare: "fare",
    age: "age",
    sex: "gender",
    gender: "gender",
    survived: "survival",
    survival: "survival",
    survivalrate: "survival rate",
    embarked: "port of embarkation",
    sibsp: "siblings/spouses aboard",
    parch: "parents/children aboard",
    revenue: "revenue",
    sales: "sales",
    profit: "profit",
    price: "price",
    cost: "cost",
    quantity: "quantity",
    discount: "discount",
    region: "region",
    country: "country",
    state: "state",
    city: "city",
    department: "department",
    category: "category",
    sub_category: "sub-category",
    order_date: "order date",
    orderdate: "order date",
    ship_date: "ship date",
    shipdate: "ship date",
    totalcount: "total count",
    total_revenue: "total revenue",
    totalrevenue: "total revenue",
    customer_lifetime_value: "customer lifetime value",
  };

  if (aliases[normalized]) {
    return aliases[normalized];
  }

  if (aliases[lower]) {
    return aliases[lower];
  }

  // Decompose snake_case or kebab-case
  if (trimmed.includes("_") || trimmed.includes("-")) {
    return trimmed
      .split(/[_-]+/)
      .map((part) => part.toLowerCase())
      .join(" ");
  }

  // Decompose camelCase / PascalCase
  const words = trimmed.replace(/([a-z])([A-Z])/g, "$1 $2").toLowerCase();
  return words;
}

/**
 * Format a database column name into a human-readable header label with title case and units.
 * Examples:
 *   "pclass" -> "Passenger class"
 *   "survival_rate" / "SURVIVALRATE" -> "Survival rate (%)"
 *   "fare" -> "Fare"
 */
export function formatDisplayHeader(colName: string): string {
  const trimmed = colName.trim();
  const lower = trimmed.toLowerCase();
  const normalized = lower.replace(/[_\s\-()]/g, "");

  // Special aggregate operations
  if (normalized === "count*" || normalized === "countstar" || normalized === "count") {
    return "Total records";
  }
  if (normalized.startsWith("count(") || normalized.startsWith("count_")) {
    const inner = colName.replace(/count[(_\s]+([a-zA-Z0-9_]+)[)\s]*/i, "$1");
    return `Count of ${formatColumnLabel(inner)}`;
  }
  if (
    normalized.startsWith("avg(") ||
    normalized.startsWith("average_") ||
    normalized.startsWith("avg_")
  ) {
    const inner = colName.replace(/(avg|average)[(_\s]+([a-zA-Z0-9_]+)[)\s]*/i, "$2");
    return `Average ${formatColumnLabel(inner)}`;
  }
  if (
    normalized.startsWith("sum(") ||
    normalized.startsWith("total_") ||
    normalized.startsWith("sum_")
  ) {
    const inner = colName.replace(/(sum|total)[(_\s]+([a-zA-Z0-9_]+)[)\s]*/i, "$2");
    return `Total ${formatColumnLabel(inner)}`;
  }
  if (normalized === "correlation" || normalized === "corr") {
    return "Correlation";
  }
  if (normalized === "validpairs" || normalized === "valid_pairs") {
    return "Valid pairs";
  }

  if (normalized === "survivalrate") {
    return "Survival rate (%)";
  }
  if (normalized === "pclass" || normalized === "passengerclass") {
    return "Passenger class";
  }

  const base = formatColumnLabel(colName);
  return base.charAt(0).toUpperCase() + base.slice(1);
}

export function generateSuggestedQuestions(
  schema?: DatasetSchema | null,
  datasetName?: string,
  submittedQuestions?: string[]
): string[] {
  if (!schema || !schema.columns || schema.columns.length === 0) {
    return ["How many total records are in this dataset?", "Which columns have missing values?"];
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

  // 2. Binary outcome comparison (e.g. survival rate by passenger class / gender)
  if (outcomes.length > 0 && categoricals.length > 0) {
    const outcomeCol = outcomes[0].name;
    const catCol = categoricals[0].name;
    const outcomeLabel = formatColumnLabel(outcomeCol);
    const catLabel = formatColumnLabel(catCol);

    // Natural outcome rate phrasing
    if (outcomeLabel === "survival" || outcomeLabel === "survived") {
      suggestions.push(`Compare survival rates by ${catLabel}.`);
    } else {
      suggestions.push(`Compare ${outcomeLabel} rates by ${catLabel}.`);
    }
  }

  // 3. Measure comparison grouped by categorical (e.g. average fare by passenger class / age by gender)
  if (measures.length > 0 && categoricals.length > 0) {
    const measureCol = measures[0].name;
    const catCol = categoricals.length > 1 ? categoricals[1].name : categoricals[0].name;
    const measureLabel = formatColumnLabel(measureCol);
    const catLabel = formatColumnLabel(catCol);
    suggestions.push(`What is the average ${measureLabel} by ${catLabel}?`);
  } else if (measures.length > 0) {
    const measureLabel = formatColumnLabel(measures[0].name);
    suggestions.push(`What is the average ${measureLabel}?`);
  }

  // 4. Distribution / count by category
  if (categoricals.length > 0) {
    const catCol = categoricals[0].name;
    const catLabel = formatColumnLabel(catCol);
    suggestions.push(`How many ${entityName} are in each ${catLabel}?`);
  }

  // 5. Temporal trend if temporal column exists
  if (temporals.length > 0 && measures.length > 0) {
    const measureLabel = formatColumnLabel(measures[0].name);
    const tempLabel = formatColumnLabel(temporals[0].name);
    suggestions.push(`Show trend of ${measureLabel} over ${tempLabel}.`);
  }

  // 6. Data quality / missing values
  suggestions.push("Which columns contain missing values?");

  // Semantic normalization function for question comparison
  const normalizeQuestionSemantics = (q: string): string => {
    return q
      .toLowerCase()
      .replace(/[?!.,;:'"()]/g, "")
      .replace(/\b(passengers|rows|records|people|items|entries)\b/g, "entities")
      .replace(/\b(dataset|table|data)\b/g, "dataset")
      .replace(/\b(in each|by each|grouped by|per)\b/g, "by")
      .replace(/\s+/g, " ")
      .trim();
  };

  // Deduplicate against already-submitted questions (semantic and exact)
  const submittedExact = new Set((submittedQuestions ?? []).map((q) => q.toLowerCase().trim()));
  const submittedSemantic = new Set((submittedQuestions ?? []).map(normalizeQuestionSemantics));

  // Return top 4 distinct questions not already submitted
  return Array.from(new Set(suggestions))
    .filter((q) => {
      const exact = q.toLowerCase().trim();
      const sem = normalizeQuestionSemantics(q);
      return !submittedExact.has(exact) && !submittedSemantic.has(sem);
    })
    .slice(0, 4);
}
