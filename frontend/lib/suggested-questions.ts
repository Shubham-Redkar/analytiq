/**
 * AnalytIQ Schema-Aware Suggested Questions Generator (M6).
 *
 * Deterministically constructs starter analytical questions from actual dataset columns.
 * Never invents nonexistent columns.
 */

import type { DatasetSchema } from "./types";

export function generateSuggestedQuestions(schema?: DatasetSchema | null): string[] {
  if (!schema || !schema.columns || schema.columns.length === 0) {
    return [
      "How many total records are in this dataset?",
      "Which columns have missing values?",
    ];
  }

  const suggestions: string[] = [
    `How many records are in this dataset?`,
  ];

  const columns = schema.columns;
  const numCol = columns.find((c) => {
    const t = c.duckdb_type.toLowerCase();
    return t.includes("int") || t.includes("float") || t.includes("double") || t.includes("decimal");
  });

  const catCol = columns.find((c) => {
    const t = c.duckdb_type.toLowerCase();
    return t.includes("varchar") || t.includes("text") || t.includes("string");
  });

  const dateCol = columns.find((c) => {
    const t = c.duckdb_type.toLowerCase();
    return t.includes("date") || t.includes("timestamp");
  });

  if (numCol && catCol) {
    suggestions.push(`What is the average ${numCol.name} grouped by ${catCol.name}?`);
    suggestions.push(`Show total ${numCol.name} by ${catCol.name}.`);
  } else if (numCol) {
    suggestions.push(`What is the average ${numCol.name}?`);
  }

  if (dateCol && numCol) {
    suggestions.push(`Show trend of ${numCol.name} over time.`);
  }

  if (catCol) {
    suggestions.push(`What are the distinct values in ${catCol.name}?`);
  }

  suggestions.push("Which columns contain the highest missing rate?");

  return suggestions.slice(0, 5);
}
