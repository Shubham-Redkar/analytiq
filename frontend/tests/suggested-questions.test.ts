import { describe, it, expect } from "vitest";
import {
  classifyColumn,
  formatColumnLabel,
  generateSuggestedQuestions,
} from "../lib/suggested-questions";

describe("Semantic Suggested Questions & Formatter (M6.1)", () => {
  it("formats column labels into natural human-readable text", () => {
    expect(formatColumnLabel("pclass")).toBe("passenger class");
    expect(formatColumnLabel("Pclass")).toBe("passenger class");
    expect(formatColumnLabel("survived")).toBe("survival");
    expect(formatColumnLabel("Sex")).toBe("gender");
    expect(formatColumnLabel("order_date")).toBe("order date");
    expect(formatColumnLabel("TotalRevenue")).toBe("total revenue");
    expect(formatColumnLabel("customer_lifetime_value")).toBe("customer lifetime value");
  });

  it("classifies column roles correctly across schemas", () => {
    expect(
      classifyColumn({
        name: "PassengerId",
        duckdb_type: "BIGINT",
        logical_type: "integer",
        nullable: false,
      })
    ).toBe("identifier");
    expect(
      classifyColumn({
        name: "user_uuid",
        duckdb_type: "VARCHAR",
        logical_type: "string",
        nullable: false,
      })
    ).toBe("identifier");
    expect(
      classifyColumn({
        name: "survived",
        duckdb_type: "BIGINT",
        logical_type: "integer",
        nullable: false,
      })
    ).toBe("binary_outcome");
    expect(
      classifyColumn({
        name: "Pclass",
        duckdb_type: "BIGINT",
        logical_type: "integer",
        nullable: false,
      })
    ).toBe("categorical");
    expect(
      classifyColumn({
        name: "Name",
        duckdb_type: "VARCHAR",
        logical_type: "string",
        nullable: false,
      })
    ).toBe("free_text");
    expect(
      classifyColumn({
        name: "Fare",
        duckdb_type: "DOUBLE",
        logical_type: "float",
        nullable: false,
      })
    ).toBe("measure");
    expect(
      classifyColumn({
        name: "created_at",
        duckdb_type: "TIMESTAMP",
        logical_type: "datetime",
        nullable: false,
      })
    ).toBe("temporal");
  });

  it("generates natural question phrasing for Titanic dataset without raw column artifacts", () => {
    const titanicSchema = {
      row_count: 891,
      column_count: 5,
      columns: [
        { name: "PassengerId", duckdb_type: "BIGINT", logical_type: "integer", nullable: false },
        { name: "Survived", duckdb_type: "BIGINT", logical_type: "integer", nullable: false },
        { name: "Pclass", duckdb_type: "BIGINT", logical_type: "integer", nullable: false },
        { name: "Name", duckdb_type: "VARCHAR", logical_type: "string", nullable: false },
        { name: "Fare", duckdb_type: "DOUBLE", logical_type: "float", nullable: false },
      ],
    };

    const questions = generateSuggestedQuestions(titanicSchema, "Titanic Passengers");
    expect(questions.length).toBeGreaterThan(0);
    expect(questions).toContain("How many passengers are in this dataset?");
    expect(questions.some((q) => q.includes("survival rates by passenger class"))).toBe(true);
    expect(questions.some((q) => q.includes("average fare by passenger class"))).toBe(true);
    // Ensure identifiers and free text are not suggested as measures
    expect(questions.some((q) => q.toLowerCase().includes("average passengerid"))).toBe(false);
    expect(questions.some((q) => q.toLowerCase().includes("by name"))).toBe(false);
  });

  it("generates natural question phrasing for generic e-commerce schema", () => {
    const salesSchema = {
      row_count: 5000,
      column_count: 4,
      columns: [
        { name: "order_id", duckdb_type: "VARCHAR", logical_type: "string", nullable: false },
        { name: "region", duckdb_type: "VARCHAR", logical_type: "string", nullable: false },
        { name: "revenue", duckdb_type: "DOUBLE", logical_type: "float", nullable: false },
        { name: "order_date", duckdb_type: "DATE", logical_type: "date", nullable: false },
      ],
    };

    const questions = generateSuggestedQuestions(salesSchema, "Q4 Sales Data");
    expect(questions).toContain("How many records are in this dataset?");
    expect(questions.some((q) => q.includes("average revenue by region"))).toBe(true);
    expect(questions.some((q) => q.includes("trend of revenue over order date"))).toBe(true);
  });
});
