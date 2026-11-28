"""Versioned analytical prompt templates for natural-language to SQL planning."""

PROMPT_VERSION = "2026.03.v2"

PLANNER_SYSTEM_PROMPT = """You are the AnalytIQ Analytical Query Planner.
Your role is to write a single read-only DuckDB SQL query answering user questions
about the 'dataset' relation.

When a query can be answered using SQL on 'dataset', ALWAYS set status="ready"
and provide the SQL query.

GUIDELINES:
- Query ONLY the table named "dataset". Never query filesystem paths or other tables.
- Return ONLY valid DuckDB SQL syntax. Quote column names using double quotes
  (e.g. "order_id", "revenue").
- Permitted functions: COUNT, SUM, AVG, MIN, MAX, MEDIAN, STDDEV, ROUND, COALESCE,
  CORR, LOWER, UPPER, TRIM.
- When answering "how many rows/records/orders", use COUNT(*).
- When asked for the relationship or correlation between two numerical variables,
  calculate Pearson correlation:
  SELECT CORR("col1", "col2") AS correlation, COUNT(*) AS valid_pairs
  FROM dataset WHERE NOT "col1" IS NULL AND NOT "col2" IS NULL.
- When asked for averages by gender/sex, map to the gender/sex column (e.g. "Sex") and group by it:
  SELECT "Sex" AS gender, AVG("Age") AS average_age
  FROM dataset WHERE NOT "Age" IS NULL GROUP BY "Sex".
- Only set status="unsupported" if the user explicitly asks for future forecasting,
  machine learning predictions, or data mutation (INSERT/UPDATE/DELETE/DROP).
- Only set status="needs_clarification" if the question is completely ambiguous and does
  not mention any column or metric.
- Respond strictly in JSON format matching the schema."""

PLAN_JSON_SCHEMA = {
    "type": "object",
    "properties": {
        "status": {
            "type": "string",
            "enum": ["ready", "needs_clarification", "unsupported"],
        },
        "intent": {
            "type": "string",
            "description": "Concise summary of analytical intent",
        },
        "operation": {
            "type": "string",
            "enum": [
                "aggregation",
                "grouped_aggregation",
                "filtering",
                "sorting",
                "ranking",
                "distribution",
                "distinct_values",
                "descriptive_statistics",
                "time_series",
                "comparison",
                "general_query",
            ],
        },
        "referenced_columns": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Exact dataset column names referenced",
        },
        "sql": {
            "type": "string",
            "description": "DuckDB SQL querying 'dataset' (required if status=ready)",
        },
        "assumptions": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Explicit assumptions made",
        },
        "clarification_question": {
            "type": "string",
            "description": "Question if status=needs_clarification",
        },
        "unsupported_reason": {
            "type": "string",
            "description": "Reason if status=unsupported",
        },
    },
    "required": ["status", "intent"],
}


def build_planner_user_message(context_json: str, user_question: str) -> str:
    """Format structured user message separating untrusted dataset metadata from instructions."""
    return f"""DATASET SCHEMA:
{context_json}

USER QUESTION:
{user_question}

Produce a structured analytical plan conforming to the required JSON schema."""


def build_correction_user_message(
    context_json: str,
    user_question: str,
    failed_sql: str | None,
    error_feedback: str,
) -> str:
    """Format prompt for bounded SQL correction."""
    return f"""DATASET SCHEMA:
{context_json}

ORIGINAL QUESTION:
{user_question}

PREVIOUS PROPOSED SQL:
{failed_sql or "(None)"}

VALIDATION / EXECUTION ERROR:
{error_feedback}

Correct the SQL query to resolve the error. Ensure all columns match the schema exactly
and only the 'dataset' relation is queried. Return the revised structured plan."""
