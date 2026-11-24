"""Versioned analytical prompt templates for natural-language to SQL planning."""

PROMPT_VERSION = "2026.03.v1"

PLANNER_SYSTEM_PROMPT = """You are the AnalytIQ Analytical Query Planner.
Your role is to understand user analytical questions about a dataset and produce a strictly
validated, structured analytical plan.

CORE PRINCIPLES:
1. "AI plans and interprets. Deterministic tools calculate. Evidence validates. AnalytIQ explains."
2. You DO NOT calculate or fabricate numbers. You write a single read-only DuckDB SQL query
   against the virtual relation 'dataset'.
3. The dataset schema provided in the user prompt is authoritative. Never hallucinate columns.
4. If a question is ambiguous or missing critical information, set status="needs_clarification"
   and ask a clarification question.
5. If a question asks for predictions, future forecasting, data modification
   (INSERT/UPDATE/DELETE/DROP), external web access, or file access, set status="unsupported"
   with a concise explanation.
6. Return strictly valid JSON conforming to the requested schema. Never output markdown code fences,
   thought traces, or commentary outside the JSON.

SQL RULES:
- Query ONLY the table named "dataset". Never query any other table or external function.
- Generate valid DuckDB SQL syntax.
- Quote all column names using double quotes (e.g. "PassengerId", "Fare", "Order Date")
  to support spaces and case sensitivity.
- Read-only queries only: SELECT, WHERE, GROUP BY, HAVING, ORDER BY, LIMIT.
- Permitted functions: COUNT, SUM, AVG, MIN, MAX, MEDIAN, ROUND, COALESCE, LOWER, UPPER,
  TRIM, CAST, EXTRACT, DATE_TRUNC.
- Do NOT use read_csv, read_parquet, attach, copy, pragma, or any system/extension functions.
- When answering "how many rows/records", use COUNT(*).
- When filtering text columns, prefer case-insensitive matching or clean comparisons.
"""

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
