"""Integration tests covering M7.1 analytical correctness and acceptance corrections."""

import pytest
from app.analysis.contracts import ColumnContext, DatasetAnalyticalContext
from app.analysis.sql_validator import SQLSecurityValidator
from app.orchestration.agents.clarification import ClarificationAgent
from app.orchestration.agents.supervisor import SupervisorAgent
from app.orchestration.contracts import ClarificationType, IntentCategory
from app.orchestration.grounding import ground_question_in_schema


@pytest.fixture
def titanic_context() -> DatasetAnalyticalContext:
    cols = [
        ColumnContext(name="PassengerId", physical_type="BIGINT", logical_type="integer"),
        ColumnContext(name="Survived", physical_type="BIGINT", logical_type="integer"),
        ColumnContext(name="Pclass", physical_type="BIGINT", logical_type="integer"),
        ColumnContext(name="Name", physical_type="VARCHAR", logical_type="string"),
        ColumnContext(name="Sex", physical_type="VARCHAR", logical_type="string"),
        ColumnContext(name="Age", physical_type="DOUBLE", logical_type="float"),
        ColumnContext(name="SibSp", physical_type="BIGINT", logical_type="integer"),
        ColumnContext(name="Parch", physical_type="BIGINT", logical_type="integer"),
        ColumnContext(name="Ticket", physical_type="VARCHAR", logical_type="string"),
        ColumnContext(name="Fare", physical_type="DOUBLE", logical_type="float"),
        ColumnContext(name="Cabin", physical_type="VARCHAR", logical_type="string"),
        ColumnContext(name="Embarked", physical_type="VARCHAR", logical_type="string"),
    ]
    return DatasetAnalyticalContext(
        relation_name="dataset",
        dataset_name="Titanic",
        row_count=418,
        column_count=len(cols),
        columns=cols,
        dialect="duckdb",
    )


def test_grounding_average_age_by_gender(titanic_context: DatasetAnalyticalContext):
    """Grounded query with Age and Sex recognized, no false ambiguity."""
    analysis = ground_question_in_schema("What is the average age by gender?", titanic_context)
    assert analysis["is_grounded"] is True
    assert analysis["ambiguity_detected"] is False
    assert analysis["ambiguity_type"] is None


def test_grounding_bare_average_requests_clarification(titanic_context: DatasetAnalyticalContext):
    """Bare 'What is the average?' triggers MISSING_TARGET_METRIC clarification with options."""
    analysis = ground_question_in_schema("What is the average?", titanic_context)
    assert analysis["is_grounded"] is False
    assert analysis["ambiguity_detected"] is True
    assert analysis["ambiguity_type"] == ClarificationType.MISSING_TARGET_METRIC.value

    agent = ClarificationAgent()
    clarification = agent.formulate_clarification("What is the average?", titanic_context, analysis)
    assert clarification.needs_clarification is True
    assert len(clarification.options) > 0
    assert any(opt.suggested_column in ("Age", "Fare") for opt in clarification.options)


def test_sql_validator_approves_correlation(titanic_context: DatasetAnalyticalContext):
    """SQL validator approves CORR with non-null constraints."""
    validator = SQLSecurityValidator()
    sql = (
        'SELECT CORR("Age", "Fare") AS correlation, COUNT(*) AS valid_pairs '
        'FROM dataset WHERE NOT "Age" IS NULL AND NOT "Fare" IS NULL'
    )
    result = validator.validate(sql, titanic_context)
    assert result.is_valid is True
    assert result.error_message is None


def test_supervisor_deterministic_safety_and_refusal():
    """Supervisor immediately rejects prohibited mutations and unsupported ML predictions."""

    class DummyProvider:
        pass

    supervisor = SupervisorAgent(provider=DummyProvider(), model="test")  # type: ignore[arg-type]

    # Prohibited mutating statement
    intent, reason = supervisor.check_deterministic_safety("Delete all passenger records")
    assert intent == IntentCategory.PROHIBITED
    assert "strictly prohibited" in (reason or "").lower()

    # Unsupported prediction
    intent, reason = supervisor.check_deterministic_safety("Predict future passenger survival")
    assert intent == IntentCategory.UNSUPPORTED
    assert "unsupported" in (reason or "").lower()
