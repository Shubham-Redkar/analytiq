"""Deterministic schema grounding node for AnalytIQ multi-agent workflow.

Inspects the dataset columns, metrics, and question terms to detect schema mismatches,
missing targets, subjective terms, or missing time grains deterministically BEFORE LLM calls.
"""

import re

from app.analysis.contracts import DatasetAnalyticalContext
from app.orchestration.contracts import ClarificationType
from app.orchestration.state import GroundingAnalysis

# Terms indicating subjective comparisons without criteria
SUBJECTIVE_PATTERNS = [
    r"\bbest\b",
    r"\bworst\b",
    r"\btop\s+performing\b",
    r"\bpoor\b",
    r"\bgreat\b",
    r"\bsuccessful\b",
    r"\bfavorite\b",
]

# Patterns requesting an average without naming a specific numeric column
BARE_AVERAGE_PATTERNS = [
    r"^(what\s+is\s+the\s+)?average\s+(of\s+|for\s+)?(this\s+|the\s+)?dataset\??$",
    r"^(what\s+is\s+the\s+)?mean\s+(of\s+|for\s+)?(this\s+|the\s+)?dataset\??$",
    r"^calculate\s+(the\s+)?average\??$",
    r"^calculate\s+(the\s+)?mean\??$",
    r"^give\s+me\s+(the\s+)?average\??$",
    r"^give\s+me\s+(the\s+)?mean\??$",
]

# Patterns requesting temporal trends or over time analysis
TREND_PATTERNS = [
    r"\btrend\b",
    r"\bover\s+time\b",
    r"\btime\s+series\b",
    r"\bgrowth\s+rate\b",
    r"\bmonthly\s+or\s+yearly\b",
]


def ground_question_in_schema(
    question: str,
    context: DatasetAnalyticalContext,
) -> GroundingAnalysis:
    """Analyze question against schema metadata deterministically."""
    clean_q = question.strip().lower()

    col_names = [col.name.lower() for col in context.columns]
    {col.name.lower(): col for col in context.columns}

    numeric_cols = [
        col.name
        for col in context.columns
        if any(
            t in col.physical_type.lower()
            for t in ["int", "float", "double", "decimal", "numeric", "real"]
        )
    ]
    date_cols = [
        col.name
        for col in context.columns
        if any(t in col.physical_type.lower() for t in ["date", "time", "timestamp"])
    ]
    categorical_cols = [
        col.name
        for col in context.columns
        if col.name not in numeric_cols and col.name not in date_cols
    ]

    # 1. Check for bare average / aggregate without specified target column
    has_avg_request = any(re.search(pat, clean_q) for pat in BARE_AVERAGE_PATTERNS) or (
        bool(re.search(r"\b(average|mean|avg)\b", clean_q))
        and not any(
            col.lower() in clean_q or col.lower().replace("_", " ") in clean_q
            for col in numeric_cols
        )
    )
    if has_avg_request:
        num_cols_msg = ", ".join(numeric_cols)
        return GroundingAnalysis(
            is_grounded=False,
            ambiguity_detected=True,
            ambiguity_type=ClarificationType.MISSING_TARGET_METRIC.value,
            ambiguity_reason=(
                "The query asks for an average/mean without specifying a numeric metric."
            ),
            referenced_columns=[],
            missing_columns=[],
            candidate_metrics=numeric_cols,
            candidate_dimensions=categorical_cols,
            suggested_clarification=(
                f"Please specify which metric to average. Available columns: {num_cols_msg}."
            ),
        )

    # 2. Check for subjective ranking / superlatives without metric criteria
    for pat in SUBJECTIVE_PATTERNS:
        if re.search(pat, clean_q):
            # Check if an explicit metric is mentioned alongside the subjective word
            # e.g., "best orders by total_amount" is grounded, but "best orders" is not
            has_metric_qualifier = any(metric.lower() in clean_q for metric in numeric_cols) or (
                "by" in clean_q and any(col in clean_q for col in col_names)
            )

            if not has_metric_qualifier:
                rank_col_hint = ", ".join(numeric_cols[:3]) if numeric_cols else "a specific column"
                return GroundingAnalysis(
                    is_grounded=False,
                    ambiguity_detected=True,
                    ambiguity_type=ClarificationType.SUBJECTIVE_RANKING.value,
                    ambiguity_reason=(
                        "Subjective ranking term used without specifying the evaluation metric."
                    ),
                    referenced_columns=[],
                    missing_columns=[],
                    candidate_metrics=numeric_cols,
                    candidate_dimensions=categorical_cols,
                    suggested_clarification=(
                        f"Please specify the ranking criteria or metric (e.g. by {rank_col_hint})."
                    ),
                )

    # 3. Check for trend analysis when date column or grain is missing
    for pat in TREND_PATTERNS:
        if re.search(pat, clean_q):
            if not date_cols:
                return GroundingAnalysis(
                    is_grounded=False,
                    ambiguity_detected=True,
                    ambiguity_type=ClarificationType.MISSING_TIME_GRAIN.value,
                    ambiguity_reason=(
                        "Trend analysis requested but no date column exists in the dataset."
                    ),
                    referenced_columns=[],
                    missing_columns=["date_or_timestamp"],
                    candidate_metrics=numeric_cols,
                    candidate_dimensions=categorical_cols,
                    suggested_clarification=(
                        "Trend analysis requires a date column, but none was found in this dataset."
                    ),
                )
            # Date col exists, but check if time grain (daily, monthly, yearly) is missing
            has_grain = any(
                g in clean_q
                for g in [
                    "daily",
                    "day",
                    "weekly",
                    "week",
                    "monthly",
                    "month",
                    "yearly",
                    "year",
                    "quarterly",
                    "quarter",
                ]
            )
            if not has_grain:
                return GroundingAnalysis(
                    is_grounded=False,
                    ambiguity_detected=True,
                    ambiguity_type=ClarificationType.MISSING_TIME_GRAIN.value,
                    ambiguity_reason=(
                        "Trend analysis requested without specifying the time granularity."
                    ),
                    referenced_columns=[d for d in date_cols if d.lower() in clean_q]
                    or date_cols[:1],
                    missing_columns=[],
                    candidate_metrics=numeric_cols,
                    candidate_dimensions=date_cols,
                    suggested_clarification=(
                        "Please specify the time granularity for the trend "
                        f"(daily, monthly, yearly) using column '{date_cols[0]}'."
                    ),
                )

    # 4. Check for requested columns that do not exist (e.g., "profit", "margin", "cost")
    # Especially "most profitable" when profit column is missing
    profit_requested = bool(re.search(r"\bprofit\b|\bprofitable\b|\bmargins?\b", clean_q))
    if profit_requested:
        profit_cols = [c for c in col_names if "profit" in c or "margin" in c]
        if not profit_cols:
            alt_candidates = [
                c for c in ["total_amount", "revenue", "sales", "price", "amount"] if c in col_names
            ]
            alt_hint = alt_candidates[0] if alt_candidates else "another column"
            return GroundingAnalysis(
                is_grounded=False,
                ambiguity_detected=True,
                ambiguity_type=ClarificationType.UNAVAILABLE_METRIC.value,
                ambiguity_reason=(
                    "The question asks about profitability, but no profit column is present."
                ),
                referenced_columns=[],
                missing_columns=["profit"],
                candidate_metrics=alt_candidates or numeric_cols,
                candidate_dimensions=categorical_cols,
                suggested_clarification=(
                    f"The dataset does not contain a 'profit' column. "
                    f"Would you like to evaluate by {alt_hint} instead?"
                ),
            )

    # Identify recognized referenced columns
    found_cols = [col.name for col in context.columns if col.name.lower() in clean_q]

    return GroundingAnalysis(
        is_grounded=True,
        ambiguity_detected=False,
        ambiguity_type=None,
        ambiguity_reason=None,
        referenced_columns=found_cols,
        missing_columns=[],
        candidate_metrics=numeric_cols,
        candidate_dimensions=categorical_cols,
        suggested_clarification=None,
    )
