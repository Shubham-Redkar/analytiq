"""Deterministic verified response assembler and renderer."""

from app.analysis.contracts import AnalyticalResultColumn
from app.verification.contracts import (
    ClaimVerificationResult,
    VerificationSummary,
)


def render_verified_claim_prose(res: ClaimVerificationResult) -> str:
    """Render a verified structured claim into deterministic factual prose."""
    return res.explanation


def assemble_verified_explanation(
    summary: VerificationSummary,
    columns: list[AnalyticalResultColumn],
    rows: list[list[object]],
) -> str:
    """Build a factual narrative from only verified claims and table evidence."""
    verified = summary.verified_claims

    # If no claims were verified or none provided, produce safe deterministic fallback
    if not verified:
        row_count = len(rows)
        col_names = [c.name for c in columns]
        if row_count == 0:
            return "The analytical query returned zero rows matching the criteria."
        elif row_count == 1 and len(col_names) == 1:
            val = rows[0][0]
            return f"The calculated result for {col_names[0]} is {val}."
        elif row_count == 1:
            pairs = ", ".join(f"{col_names[i]}: {rows[0][i]}" for i in range(len(col_names)))
            return f"Analysis returned 1 record: {pairs}."
        else:
            return f"Analysis returned {row_count} rows across columns ({', '.join(col_names)})."

    # If we have verified claims, assemble them into clear prose
    narratives: list[str] = []
    for c in verified:
        narratives.append(render_verified_claim_prose(c))

    explanation = " ".join(narratives)

    # Note any limitations or truncated population
    if summary.limitations:
        lim_str = " Limitations: " + "; ".join(summary.limitations)
        explanation += lim_str

    return explanation
