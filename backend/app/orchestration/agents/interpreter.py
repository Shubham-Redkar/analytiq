"""Evidence-linked Result Interpreter Agent for AnalytIQ multi-agent workflow.

Interprets actual computed DuckDB query results, strictly bound to verifiable
execution evidence, with deterministic fallback if the LLM fails or is unavailable.
"""

import json
import logging
import re
from typing import Any

from app.analysis.contracts import AnalyticalResultColumn, ExecutionEvidence
from app.llm.contracts import ChatMessage, LLMProvider, LLMRequest, MessageRole
from app.orchestration.budgets import WorkflowBudgetTracker
from app.orchestration.contracts import InterpretationOutput

logger = logging.getLogger(__name__)

INTERPRETER_SYSTEM_PROMPT = """You are an Analytical Result Interpreter for AnalytIQ.
Your role is to explain the computed tabular data clearly and factually.

STRICT CONSTRAINTS:
1. ONLY make claims supported by the returned rows and columns.
2. DO NOT hallucinate numbers, trends, or external facts.
3. Every numeric value mentioned MUST appear in the provided rows or evidence.
4. Output MUST be valid JSON conforming to:
{
  "summary": "Concise 1-2 sentence direct answer to the user's question.",
  "key_findings": ["Finding 1 with exact data point", "Finding 2"],
  "data_points": {"metric_name": value},
  "caveats": ["Any limitation, e.g., truncated result, missing values"]
}
"""


class ResultInterpreterAgent:
    """Interprets deterministic analytical query results with verifiable grounding."""

    def __init__(
        self,
        provider: LLMProvider,
        model: str,
        temperature: float = 0.0,
        timeout_seconds: float = 30.0,
    ) -> None:
        self.provider = provider
        self.model = model
        self.temperature = temperature
        self.timeout_seconds = timeout_seconds

    def _verify_numerical_grounding(
        self,
        summary: str,
        data_points: dict[str, Any],
        rows: list[list[Any]],
    ) -> bool:
        """Verify that numeric claims in summary and data points are present in computed rows."""
        # Collect all numeric values present in the computed result rows
        valid_numbers: set[float] = set()
        for row in rows:
            for cell in row:
                if isinstance(cell, (int, float)):
                    valid_numbers.add(float(cell))
                elif isinstance(cell, str):
                    try:
                        valid_numbers.add(float(cell))
                    except ValueError:
                        pass

        # If the query produced rows but has no numbers, skip check
        if not valid_numbers:
            return True

        # Check explicit data_points
        for val in data_points.values():
            if isinstance(val, (int, float)):
                f_val = float(val)
                # Allow row count as valid observation
                if f_val == len(rows):
                    continue
                if not any(abs(f_val - target) < 0.001 for target in valid_numbers):
                    return False

        # Extract numeric tokens from summary
        summary_numbers = re.findall(r"\b\d+(?:\.\d+)?\b", summary)
        for num_str in summary_numbers:
            f_num = float(num_str)
            # Allow common sentence counts like "1 record", "2 rows", or years >= 1900
            if f_num in (len(rows), 0.0, 1.0) or f_num >= 1900:
                continue
            # If a cited number is not in the computed results, fail grounding
            if not any(abs(f_num - target) < 0.01 for target in valid_numbers):
                return False

        return True

    def _build_deterministic_fallback(
        self,
        question: str,
        columns: list[AnalyticalResultColumn],
        rows: list[list[Any]],
        evidence: ExecutionEvidence | None,
    ) -> InterpretationOutput:
        """Deterministic, rule-based summary when LLM interpretation is unavailable or skipped."""
        col_names = [c.name for c in columns]
        row_count = len(rows)

        if row_count == 0:
            return InterpretationOutput(
                summary="The analytical query returned zero rows matching the criteria.",
                key_findings=["No records met the query conditions."],
                data_points={"row_count": 0},
                caveats=[],
                is_fallback=True,
            )

        # Single scalar result (e.g. SELECT COUNT(*) or SELECT AVG(x))
        if row_count == 1 and len(col_names) == 1:
            val = rows[0][0]
            summary = f"The query calculated {col_names[0]} as {val}."
            return InterpretationOutput(
                summary=summary,
                key_findings=[f"{col_names[0]}: {val}"],
                data_points={col_names[0]: val},
                caveats=[],
                is_fallback=True,
            )

        # Single row multiple columns
        if row_count == 1:
            points = {col_names[i]: rows[0][i] for i in range(len(col_names))}
            first_items = list(points.items())[:3]
            pairs = ", ".join(f"{k}={v}" for k, v in first_items)
            summary = f"Analysis returned 1 record: {pairs}."
            return InterpretationOutput(
                summary=summary,
                key_findings=[f"{k}: {v}" for k, v in points.items()],
                data_points=points,
                caveats=[],
                is_fallback=True,
            )

        # Multiple rows
        summary = f"Analysis returned {row_count} rows across columns ({', '.join(col_names[:4])})."
        key_findings = [f"Top record: {col_names[0]} = {rows[0][0]}"]
        if len(col_names) > 1:
            key_findings.append(f"Value: {col_names[1]} = {rows[0][1]}")

        caveats = []
        if evidence and evidence.truncated:
            caveats.append(f"Results are truncated at {evidence.returned_row_count} rows.")

        return InterpretationOutput(
            summary=summary,
            key_findings=key_findings,
            data_points={"returned_rows": row_count},
            caveats=caveats,
            is_fallback=True,
        )

    async def interpret(
        self,
        question: str,
        columns: list[AnalyticalResultColumn],
        rows: list[list[Any]],
        evidence: ExecutionEvidence | None,
        budget: WorkflowBudgetTracker,
    ) -> InterpretationOutput:
        """Interpret analytical results with LLM or fallback."""
        # Check budget first
        if not budget.can_make_llm_call():
            logger.info(
                "Interpreter: Budget or timeout prevents LLM call; using deterministic fallback."
            )
            return self._build_deterministic_fallback(question, columns, rows, evidence)

        # Minimize payload sent to LLM (sample up to top 15 rows)
        sample_rows = rows[:15]
        col_names = [c.name for c in columns]

        user_prompt = f"""Question: {question}
Result Columns: {json.dumps(col_names)}
Returned Rows (sample of {len(sample_rows)} rows):
{json.dumps(sample_rows, default=str)}
Total Rows: {len(rows)}
Truncated: {evidence.truncated if evidence else False}

Provide a factual summary of these results adhering strictly to the JSON schema."""

        try:
            timeout = min(self.timeout_seconds, budget.remaining_seconds)
            if timeout <= 1.0:
                return self._build_deterministic_fallback(question, columns, rows, evidence)

            request = LLMRequest(
                messages=[
                    ChatMessage(role=MessageRole.SYSTEM, content=INTERPRETER_SYSTEM_PROMPT),
                    ChatMessage(role=MessageRole.USER, content=user_prompt),
                ],
                model=self.model,
                temperature=self.temperature,
                max_tokens=600,
            )

            budget.record_llm_call()
            response = await self.provider.generate(request)

            raw_dict = response.structured_data
            if not raw_dict and response.content:
                try:
                    loaded = json.loads(response.content)
                    if isinstance(loaded, dict):
                        raw_dict = loaded
                except Exception:
                    raw_dict = None

            if isinstance(raw_dict, dict) and "summary" in raw_dict:
                pts = raw_dict.get("data_points")
                data_points: dict[str, Any] = pts if isinstance(pts, dict) else {}
                summary_str = str(raw_dict.get("summary", ""))
                findings_list = [str(f) for f in raw_dict.get("key_findings", [])]

                # Numerical Grounding Check:
                # Any explicit numbers cited in the summary or data_points must be verified against
                # the actual computed query rows to prevent ungrounded or hallucinated claims.
                is_grounded = self._verify_numerical_grounding(summary_str, data_points, rows)
                if not is_grounded:
                    logger.warning(
                        "Interpreter: LLM generated ungrounded numeric claims; falling back."
                    )
                    return self._build_deterministic_fallback(question, columns, rows, evidence)

                return InterpretationOutput(
                    summary=summary_str,
                    key_findings=findings_list,
                    data_points=data_points,
                    caveats=[str(c) for c in raw_dict.get("caveats", [])],
                    is_fallback=False,
                )
        except Exception as e:
            logger.warning(
                "Interpreter LLM generation failed: %s; falling back to deterministic.", e
            )

        return self._build_deterministic_fallback(question, columns, rows, evidence)
