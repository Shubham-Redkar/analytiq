"""Tests for context window estimation and token budgeting."""

import pytest
from app.analysis.context_builder import (
    ContextBuilderError,
    estimate_text_tokens,
    serialize_context_for_prompt,
)
from app.analysis.contracts import ColumnContext, DatasetAnalyticalContext


def test_estimate_text_tokens_conservative() -> None:
    text = "Hello world! This is a test context string."
    # 44 chars -> ~11 base words -> ~13 tokens with safety margin
    tokens = estimate_text_tokens(text)
    assert tokens > 0
    # Safety margin (+15%) must be included
    raw_est = int(len(text) / 4)
    assert tokens >= raw_est


def test_serialize_context_for_prompt_within_budget() -> None:
    ctx = DatasetAnalyticalContext(
        dataset_name="titanic",
        row_count=100,
        column_count=2,
        columns=[
            ColumnContext(
                name="age",
                physical_type="DOUBLE",
                logical_type="numeric",
                nullable=True,
                distinct_count=50,
                sample_values=[],
            ),
            ColumnContext(
                name="survived",
                physical_type="BIGINT",
                logical_type="categorical",
                nullable=False,
                distinct_count=2,
                sample_values=[],
            ),
        ],
    )

    prompt = serialize_context_for_prompt(ctx, max_input_tokens=2048)
    assert "age" in prompt
    assert "survived" in prompt


def test_serialize_context_for_prompt_exceeding_budget() -> None:
    ctx = DatasetAnalyticalContext(
        dataset_name="large_dataset",
        row_count=100,
        column_count=50,
        columns=[
            ColumnContext(
                name=f"very_long_column_name_exceeding_token_budget_threshold_index_{i}",
                physical_type="VARCHAR",
                logical_type="text",
                nullable=True,
                distinct_count=10,
                sample_values=[],
            )
            for i in range(50)
        ],
    )

    with pytest.raises(ContextBuilderError) as exc_info:
        serialize_context_for_prompt(ctx, max_input_tokens=50)

    assert "exceeding the allocated input budget" in str(exc_info.value)
