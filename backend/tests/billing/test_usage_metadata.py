"""Tests for real-token AI usage metadata."""
from __future__ import annotations

from app.billing.service import (
    build_ai_usage_metadata_from_tokens,
    compute_ai_credits,
)


def test_metadata_uses_real_tokens_and_model():
    meta = build_ai_usage_metadata_from_tokens(
        input_tokens=1200,
        output_tokens=300,
        model_name="gpt-5.5",
        source="model_call",
        source_id="mc-1",
    )
    assert meta["input_tokens"] == 1200
    assert meta["output_tokens"] == 300
    assert meta["model_name"] == "gpt-5.5"
    assert meta["source_id"] == "mc-1"
    # credits match the real-token computation (gpt-5.5 multiplier applied)
    assert meta["credits"] == compute_ai_credits(1200, 300, "gpt-5.5")
    assert meta["credits"] >= 1


def test_metadata_floors_to_at_least_one_credit():
    meta = build_ai_usage_metadata_from_tokens(0, 0, "gpt-5.4-mini", "model_call", "mc-2")
    assert meta["credits"] >= 1


def test_metadata_clamps_negatives():
    meta = build_ai_usage_metadata_from_tokens(-5, -10, None, "model_call", None)
    assert meta["input_tokens"] == 0
    assert meta["output_tokens"] == 0
