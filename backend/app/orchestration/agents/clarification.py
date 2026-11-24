"""Clarification Agent for resolving analytical ambiguities with schema grounding."""

from app.analysis.contracts import DatasetAnalyticalContext
from app.orchestration.contracts import (
    ClarificationOption,
    ClarificationOutput,
    ClarificationType,
)
from app.orchestration.state import GroundingAnalysis


class ClarificationAgent:
    """Formulates clear, actionable, schema-grounded clarification prompts."""

    def formulate_clarification(
        self,
        question: str,
        context: DatasetAnalyticalContext,
        grounding: GroundingAnalysis,
    ) -> ClarificationOutput:
        """Construct structured clarification based on grounding findings."""
        ambiguity_type_val = (
            grounding.get("ambiguity_type") or ClarificationType.GENERAL_AMBIGUITY.value
        )
        ambiguity_type = ClarificationType(ambiguity_type_val)

        numeric_cols = grounding.get("candidate_metrics") or []
        all_col_names = [col.name for col in context.columns]

        if ambiguity_type == ClarificationType.MISSING_TARGET_METRIC:
            options = [
                ClarificationOption(
                    label=f"Average {col}",
                    description=f"Calculate the average / mean of column '{col}'.",
                    suggested_column=col,
                )
                for col in numeric_cols[:4]
            ]
            q_text = (
                grounding.get("suggested_clarification")
                or "Which numeric column would you like to calculate the average for?"
            )
            return ClarificationOutput(
                clarification_type=ambiguity_type,
                question=q_text,
                options=options,
                available_columns=numeric_cols,
            )

        if ambiguity_type == ClarificationType.SUBJECTIVE_RANKING:
            options = [
                ClarificationOption(
                    label=f"Rank by {col}",
                    description=f"Rank records descending by '{col}'.",
                    suggested_column=col,
                )
                for col in numeric_cols[:3]
            ]
            q_text = (
                grounding.get("suggested_clarification")
                or "Please specify the criteria to determine the ranking."
            )
            return ClarificationOutput(
                clarification_type=ambiguity_type,
                question=q_text,
                options=options,
                available_columns=numeric_cols,
            )

        if ambiguity_type == ClarificationType.MISSING_TIME_GRAIN:
            date_col = next(
                (
                    c.name
                    for c in context.columns
                    if "date" in c.physical_type.lower() or "time" in c.physical_type.lower()
                ),
                None,
            )
            options = [
                ClarificationOption(
                    label="Monthly Trend",
                    description=f"Aggregate metrics by month using '{date_col}'.",
                    suggested_column=date_col,
                    suggested_filter="date_trunc('month', ...)",
                ),
                ClarificationOption(
                    label="Daily Trend",
                    description=f"Aggregate metrics daily using '{date_col}'.",
                    suggested_column=date_col,
                    suggested_filter="date_trunc('day', ...)",
                ),
                ClarificationOption(
                    label="Yearly Trend",
                    description=f"Aggregate metrics yearly using '{date_col}'.",
                    suggested_column=date_col,
                    suggested_filter="date_trunc('year', ...)",
                ),
            ]
            q_text = (
                grounding.get("suggested_clarification")
                or "What time interval should be used for the trend?"
            )
            return ClarificationOutput(
                clarification_type=ambiguity_type,
                question=q_text,
                options=options,
                available_columns=[date_col] if date_col else [],
            )

        if ambiguity_type == ClarificationType.UNAVAILABLE_METRIC:
            candidates = grounding.get("candidate_metrics") or []
            options = [
                ClarificationOption(
                    label=f"Analyze by {col}",
                    description=f"Use '{col}' as the primary metric.",
                    suggested_column=col,
                )
                for col in candidates[:3]
            ]
            q_text = (
                grounding.get("suggested_clarification")
                or "The requested metric is not present in this dataset."
            )
            return ClarificationOutput(
                clarification_type=ambiguity_type,
                question=q_text,
                options=options,
                available_columns=all_col_names,
            )

        # General ambiguity fallback
        q_text = (
            grounding.get("suggested_clarification") or "Could you please clarify your question?"
        )
        return ClarificationOutput(
            clarification_type=ClarificationType.GENERAL_AMBIGUITY,
            question=q_text,
            options=[],
            available_columns=all_col_names,
        )
