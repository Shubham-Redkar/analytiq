"""Evidence-linked Result Interpreter Agent for AnalytIQ multi-agent workflow.

Generates structured analytical claims and preliminary interpretation adhering strictly to
verifiable execution evidence, with deterministic fallback when LLM is unavailable or skipped.
"""

import json
import logging
import re
from typing import Any

from app.analysis.contracts import AnalyticalResultColumn, ExecutionEvidence
from app.llm.contracts import ChatMessage, LLMProvider, LLMRequest, MessageRole
from app.orchestration.budgets import WorkflowBudgetTracker
from app.orchestration.contracts import InterpretationOutput
from app.verification.contracts import (
    AnalyticalClaim,
    ClaimType,
    ComparisonClaim,
    ComparisonOperator,
    DifferenceClaim,
    DimensionAssociatedValueClaim,
    EmptyResultObservationClaim,
    EvidenceReference,
    ExtremumClaim,
    ExtremumType,
    MissingValueObservationClaim,
    PercentageChangeClaim,
    ProportionClaim,
    RankingClaim,
    RowCountClaim,
    ScalarValueClaim,
)
from app.verification.derived_metrics import safe_float

logger = logging.getLogger(__name__)

INTERPRETER_SYSTEM_PROMPT = """You are an Analytical Result Interpreter for AnalytIQ.
Your role is to explain computed tabular results and propose structured factual claims.

STRICT CONSTRAINTS:
1. ONLY make claims supported by the returned rows and columns.
2. DO NOT hallucinate numbers, trends, or external facts.
3. Every claim MUST be represented in the structured "claims" array with exact values.
4. Output MUST be valid JSON conforming to:
{
  "summary": "Concise 1-2 sentence direct factual answer to the question.",
  "key_findings": ["Finding 1 with exact data point", "Finding 2"],
  "data_points": {"metric_name": value},
  "caveats": ["Any limitation, e.g., truncated result, missing values"],
  "claims": [
    {
      "claim_type": "scalar_value | dimension_associated_value | row_count",
      ...specific fields...
    }
  ]
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

        if not valid_numbers:
            return True

        for val in data_points.values():
            if isinstance(val, (int, float)):
                f_val = float(val)
                if f_val == len(rows):
                    continue
                if not any(abs(f_val - target) < 0.001 for target in valid_numbers):
                    return False

        summary_numbers = re.findall(r"\b\d+(?:\.\d+)?\b", summary)
        for num_str in summary_numbers:
            f_num = float(num_str)
            if f_num in (len(rows), 0.0, 1.0) or f_num >= 1900:
                continue
            if not any(abs(f_num - target) < 0.01 for target in valid_numbers):
                return False

        return True

    def _build_deterministic_fallback(
        self,
        question: str,
        columns: list[AnalyticalResultColumn],
        rows: list[list[Any]],
        evidence: ExecutionEvidence | None,
    ) -> tuple[InterpretationOutput, list[AnalyticalClaim]]:
        """Deterministic, rule-based summary and claims when LLM interpretation is unavailable."""
        col_names = [c.name for c in columns]
        row_count = len(rows)
        fingerprint = evidence.result_fingerprint if evidence else ""
        claims: list[AnalyticalClaim] = []

        if row_count == 0:
            claims.append(EmptyResultObservationClaim(evidence_references=[]))
            return (
                InterpretationOutput(
                    summary="The analytical query returned zero rows matching the criteria.",
                    key_findings=["No records met the query conditions."],
                    data_points={"row_count": 0},
                    caveats=[],
                    is_fallback=True,
                ),
                claims,
            )

        # Single scalar result (e.g. SELECT COUNT(*) or SELECT AVG(x))
        if row_count == 1 and len(col_names) == 1:
            val = rows[0][0]
            summary = f"The query calculated {col_names[0]} as {val}."
            claims.append(
                ScalarValueClaim(
                    metric_name=col_names[0],
                    claimed_value=val,
                    evidence_references=[
                        EvidenceReference(
                            result_fingerprint=fingerprint,
                            row_index=0,
                            column_name=col_names[0],
                            expected_value=val,
                        )
                    ],
                )
            )
            return (
                InterpretationOutput(
                    summary=summary,
                    key_findings=[f"{col_names[0]}: {val}"],
                    data_points={col_names[0]: val},
                    caveats=[],
                    is_fallback=True,
                ),
                claims,
            )

        # Single row multiple columns
        if row_count == 1:
            points = {col_names[i]: rows[0][i] for i in range(len(col_names))}
            first_items = list(points.items())[:3]
            pairs = ", ".join(f"{k}={v}" for k, v in first_items)
            summary = f"Analysis returned 1 record: {pairs}."
            for col_idx, col_name in enumerate(col_names):
                claims.append(
                    ScalarValueClaim(
                        metric_name=col_name,
                        claimed_value=rows[0][col_idx],
                        evidence_references=[
                            EvidenceReference(
                                result_fingerprint=fingerprint,
                                row_index=0,
                                column_name=col_name,
                                expected_value=rows[0][col_idx],
                            )
                        ],
                    )
                )
            return (
                InterpretationOutput(
                    summary=summary,
                    key_findings=[f"{k}: {v}" for k, v in points.items()],
                    data_points=points,
                    caveats=[],
                    is_fallback=True,
                ),
                claims,
            )

        # Multiple rows: generate dimension-associated claims for top records
        summary = f"Analysis returned {row_count} rows across columns ({', '.join(col_names[:4])})."
        key_findings = [f"Top record: {col_names[0]} = {rows[0][0]}"]
        if len(col_names) > 1:
            key_findings.append(f"Value: {col_names[1]} = {rows[0][1]}")

        caveats = []
        if evidence and evidence.truncated:
            caveats.append(f"Results are truncated at {evidence.returned_row_count} rows.")

        claims.append(RowCountClaim(claimed_count=row_count, is_dataset_total=False))

        # Add dimension-associated claims for first 5 rows if at least 2 columns
        if len(col_names) >= 2:
            dim_col = col_names[0]
            metric_col = col_names[1]
            for r_idx, r in enumerate(rows[:5]):
                claims.append(
                    DimensionAssociatedValueClaim(
                        dimension_name=dim_col,
                        dimension_value=r[0],
                        metric_name=metric_col,
                        claimed_value=r[1],
                        evidence_references=[
                            EvidenceReference(
                                result_fingerprint=fingerprint,
                                row_index=r_idx,
                                column_name=metric_col,
                                expected_value=r[1],
                            )
                        ],
                    )
                )

        return (
            InterpretationOutput(
                summary=summary,
                key_findings=key_findings,
                data_points={"returned_rows": row_count},
                caveats=caveats,
                is_fallback=True,
            ),
            claims,
        )

    def _parse_structured_claims(
        self,
        raw_claims: list[dict[str, Any]],
        fingerprint: str,
    ) -> list[AnalyticalClaim]:
        """Parse untrusted LLM claim dicts into strongly typed AnalyticalClaim instances."""
        parsed: list[AnalyticalClaim] = []
        for c in raw_claims:
            if not isinstance(c, dict):
                continue
            ctype = c.get("claim_type")
            try:
                # Ensure evidence references have fingerprint if omitted
                refs_data = c.get("evidence_references", [])
                refs: list[EvidenceReference] = []
                for r in refs_data:
                    if isinstance(r, dict):
                        refs.append(
                            EvidenceReference(
                                evidence_id=r.get("evidence_id"),
                                result_fingerprint=r.get("result_fingerprint") or fingerprint,
                                row_index=int(r.get("row_index", 0)),
                                column_name=str(r.get("column_name", "")),
                                expected_value=r.get("expected_value"),
                            )
                        )

                if ctype == ClaimType.SCALAR_VALUE:
                    parsed.append(
                        ScalarValueClaim(
                            metric_name=str(c.get("metric_name", "")),
                            claimed_value=c.get("claimed_value"),
                            aggregation=c.get("aggregation"),
                            unit=c.get("unit"),
                            evidence_references=refs,
                        )
                    )
                elif ctype == ClaimType.DIMENSION_ASSOCIATED_VALUE:
                    parsed.append(
                        DimensionAssociatedValueClaim(
                            dimension_name=str(c.get("dimension_name", "")),
                            dimension_value=c.get("dimension_value"),
                            metric_name=str(c.get("metric_name", "")),
                            claimed_value=c.get("claimed_value"),
                            unit=c.get("unit"),
                            evidence_references=refs,
                        )
                    )
                elif ctype == ClaimType.ROW_COUNT:
                    parsed.append(
                        RowCountClaim(
                            claimed_count=int(c.get("claimed_count", 0)),
                            is_dataset_total=bool(c.get("is_dataset_total", False)),
                            evidence_references=refs,
                        )
                    )
                elif ctype == ClaimType.COMPARISON:
                    op_str = c.get("operator", ">")
                    op = (
                        ComparisonOperator(op_str)
                        if op_str in ComparisonOperator
                        else ComparisonOperator.GREATER_THAN
                    )
                    parsed.append(
                        ComparisonClaim(
                            left_entity=str(c.get("left_entity", "")),
                            left_value=float(c.get("left_value", 0.0)),
                            operator=op,
                            right_entity=str(c.get("right_entity", "")),
                            right_value=float(c.get("right_value", 0.0)),
                            metric_name=str(c.get("metric_name", "")),
                            evidence_references=refs,
                        )
                    )
                elif ctype == ClaimType.DIFFERENCE:
                    parsed.append(
                        DifferenceClaim(
                            target_entity=str(c.get("target_entity", "")),
                            baseline_entity=str(c.get("baseline_entity", "")),
                            metric_name=str(c.get("metric_name", "")),
                            claimed_difference=float(c.get("claimed_difference", 0.0)),
                            is_absolute=bool(c.get("is_absolute", False)),
                            evidence_references=refs,
                        )
                    )
                elif ctype == ClaimType.PERCENTAGE_CHANGE:
                    parsed.append(
                        PercentageChangeClaim(
                            baseline_entity=str(c.get("baseline_entity", "")),
                            target_entity=str(c.get("target_entity", "")),
                            metric_name=str(c.get("metric_name", "")),
                            claimed_percent_change=float(c.get("claimed_percent_change", 0.0)),
                            evidence_references=refs,
                        )
                    )
                elif ctype == ClaimType.PROPORTION:
                    parsed.append(
                        ProportionClaim(
                            part_entity=str(c.get("part_entity", "")),
                            whole_entity=str(c.get("whole_entity", "total")),
                            metric_name=str(c.get("metric_name", "")),
                            claimed_proportion_pct=float(c.get("claimed_proportion_pct", 0.0)),
                            evidence_references=refs,
                        )
                    )
                elif ctype == ClaimType.RANKING:
                    parsed.append(
                        RankingClaim(
                            entity_name=str(c.get("entity_name", "")),
                            metric_name=str(c.get("metric_name", "")),
                            claimed_rank=int(c.get("claimed_rank", 1)),
                            descending=bool(c.get("descending", True)),
                            scope_is_global=bool(c.get("scope_is_global", False)),
                            evidence_references=refs,
                        )
                    )
                elif ctype == ClaimType.EXTREMUM:
                    ext_str = str(c.get("extremum", "maximum")).lower()
                    ext = ExtremumType.MINIMUM if "min" in ext_str else ExtremumType.MAXIMUM
                    parsed.append(
                        ExtremumClaim(
                            extremum=ext,
                            entity_name=str(c.get("entity_name", "")),
                            metric_name=str(c.get("metric_name", "")),
                            claimed_value=safe_float(c.get("claimed_value")),
                            scope_is_global=bool(c.get("scope_is_global", False)),
                            evidence_references=refs,
                        )
                    )
                elif ctype == ClaimType.MISSING_VALUE_OBSERVATION:
                    parsed.append(
                        MissingValueObservationClaim(
                            column_name=str(c.get("column_name", "")),
                            missing_count=int(c.get("missing_count", 0)),
                            evidence_references=refs,
                        )
                    )
                elif ctype == ClaimType.EMPTY_RESULT_OBSERVATION:
                    parsed.append(
                        EmptyResultObservationClaim(
                            filter_criteria=c.get("filter_criteria"),
                            evidence_references=refs,
                        )
                    )
            except Exception as e:
                logger.debug("Could not parse claim %s: %s", c, e)
        return parsed

    async def interpret(
        self,
        question: str,
        columns: list[AnalyticalResultColumn],
        rows: list[list[Any]],
        evidence: ExecutionEvidence | None,
        budget: WorkflowBudgetTracker,
    ) -> tuple[InterpretationOutput, list[AnalyticalClaim]]:
        """Interpret results with LLM or fallback, returning interpretation and claims."""
        fingerprint = evidence.result_fingerprint if evidence else ""

        # Check budget first
        if not budget.can_make_llm_call():
            logger.info("Interpreter: Budget prevents LLM call; using deterministic fallback.")
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

                # Parse claims
                raw_claims = raw_dict.get("claims", [])
                parsed_claims = (
                    self._parse_structured_claims(raw_claims, fingerprint)
                    if isinstance(raw_claims, list)
                    else []
                )

                # Grounding check: verify that numbers in summary are supported
                is_grounded = self._verify_numerical_grounding(summary_str, data_points, rows)
                if not is_grounded:
                    logger.warning(
                        "Interpreter: LLM generated ungrounded numeric claims; falling back."
                    )
                    return self._build_deterministic_fallback(question, columns, rows, evidence)

                # If no claims produced by LLM, generate basic fallback claims
                if not parsed_claims:
                    _, parsed_claims = self._build_deterministic_fallback(
                        question, columns, rows, evidence
                    )

                return (
                    InterpretationOutput(
                        summary=summary_str,
                        key_findings=findings_list,
                        data_points=data_points,
                        caveats=[str(c) for c in raw_dict.get("caveats", [])],
                        is_fallback=False,
                    ),
                    parsed_claims,
                )
        except Exception as e:
            logger.warning(
                "Interpreter LLM generation failed: %s; falling back to deterministic.", e
            )

        return self._build_deterministic_fallback(question, columns, rows, evidence)
