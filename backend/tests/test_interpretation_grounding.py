"""Tests for numerical interpretation grounding and hallucination prevention."""

from unittest.mock import MagicMock

from app.orchestration.agents.interpreter import ResultInterpreterAgent


def test_interpreter_numerical_grounding_valid_data() -> None:
    mock_provider = MagicMock()
    agent = ResultInterpreterAgent(provider=mock_provider, model="test-model")

    rows = [[342, 891]]
    summary = "A total of 342 passengers survived out of 891 individuals."
    data_points = {"survived_count": 342, "total_passengers": 891}

    # Should pass grounding check since 342 and 891 exist in rows
    assert agent._verify_numerical_grounding(summary, data_points, rows) is True


def test_interpreter_numerical_grounding_rejects_hallucination() -> None:
    mock_provider = MagicMock()
    agent = ResultInterpreterAgent(provider=mock_provider, model="test-model")

    rows = [[342, 891]]

    # 540 is not in computed rows
    summary_with_hallucination = "A total of 540 passengers survived out of 891 individuals."
    data_points = {"survived_count": 342}

    assert agent._verify_numerical_grounding(summary_with_hallucination, data_points, rows) is False

    # Ungrounded data_point
    data_points_with_hallucination = {"survived_count": 342, "unverified_metric": 99.9}
    summary_clean = "A total of 342 passengers survived out of 891 individuals."
    assert (
        agent._verify_numerical_grounding(summary_clean, data_points_with_hallucination, rows)
        is False
    )
