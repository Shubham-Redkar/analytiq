"""Supervisor / Intent Classifier Agent for AnalytIQ multi-agent workflow.

Classifies question intent early, enforces safety and resource boundaries,
and routes requests toward clarification, planning, or safe rejection.
"""

import re

from app.analysis.contracts import DatasetAnalyticalContext
from app.llm.contracts import LLMProvider
from app.orchestration.budgets import WorkflowBudgetTracker
from app.orchestration.contracts import IntentCategory

# Prohibited mutation or administration keywords that can be immediately rejected
PROHIBITED_MUTATION_PATTERNS = [
    r"\bdrop\s+(table|view|schema|database)\b",
    r"\bdelete\s+(from\b|all\b)",
    r"\btruncate\s+(table)?\b",
    r"\bupdate\s+\w+\s+set\b",
    r"\binsert\s+into\b",
    r"\balter\s+table\b",
    r"\bgrant\s+",
    r"\brevoke\s+",
    r"\bcopy\s+.*\s+to\b",
    r"\bpg_catalog\b",
    r"\binformation_schema\b",
]

# Unsupported queries (e.g., ML modeling, causal inference, external web lookups)
UNSUPPORTED_DOMAINS = [
    r"\bpredict\b",
    r"\bforecast\b",
    r"\bmachine\s+learning\b",
    r"\btrain\s+model\b",
    r"\bcausal\s+inference\b",
    r"\bweather\s+in\b",
    r"\bstock\s+price\s+tomorrow\b",
    r"\bwrite\s+(an?\s+)?essay\b",
    r"\bwrite\s+(a\s+)?story\b",
    r"\bessay\b",
]


class SupervisorAgent:
    """Supervises analytical intent and guards against dangerous or unsupported operations."""

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

    def check_deterministic_safety(self, question: str) -> tuple[IntentCategory, str | None]:
        """Check for hard security policy or scope violations without invoking LLM."""
        clean_q = question.strip().lower()

        # 1. Prohibited statements
        for pat in PROHIBITED_MUTATION_PATTERNS:
            if re.search(pat, clean_q):
                return (
                    IntentCategory.PROHIBITED,
                    "Mutating, administrative, and export operations are strictly prohibited.",
                )

        # 2. Unsupported domains
        for pat in UNSUPPORTED_DOMAINS:
            if re.search(pat, clean_q):
                return (
                    IntentCategory.UNSUPPORTED,
                    "Predictive modeling, external lookups, and text tasks are unsupported.",
                )

        return (IntentCategory.ANALYTICAL_QUERY, None)

    async def classify_intent(
        self,
        question: str,
        context: DatasetAnalyticalContext,
        budget: WorkflowBudgetTracker,
    ) -> tuple[IntentCategory, str | None]:
        """Classify user intent with deterministic pre-filter and fallback."""
        # 1. Check deterministic rules first
        intent, reason = self.check_deterministic_safety(question)
        if intent != IntentCategory.ANALYTICAL_QUERY:
            return intent, reason

        # Avoid unnecessary LLM calls when deterministic check passes
        return IntentCategory.ANALYTICAL_QUERY, None
