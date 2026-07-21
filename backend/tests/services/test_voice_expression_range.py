"""Module D expression range — selection + fact consistency."""
from __future__ import annotations

import pytest

from app.services.gravitree_voice import format_operator_message
from app.services.voice_expression_range import (
    EXPRESSION_BANKS,
    EXPRESSION_EXCLUDED,
    assert_fact_tokens_consistent,
    all_expressions,
    bind_voice_expression_state,
    next_variant_index,
    pick_expression,
    reset_voice_expression_state,
    voice_expression_state_snapshot,
)


def test_next_variant_index_rotates_deterministically():
    assert next_variant_index(6, None) == 0
    assert next_variant_index(6, 0) == 1
    assert next_variant_index(6, 5) == 0
    assert next_variant_index(6, 99) == 0


def test_unbound_state_always_returns_first_variant():
    a = format_operator_message("connector_connect_to_run", integration="slack")
    b = format_operator_message("connector_connect_to_run", integration="slack")
    assert a == b == EXPRESSION_BANKS["connector_connect_to_run"][0].format(integration="Slack")


def test_bound_state_avoids_immediate_repeat():
    token = bind_voice_expression_state({})
    try:
        first = format_operator_message("connector_connect_to_run", integration="slack")
        second = format_operator_message("connector_connect_to_run", integration="slack")
        third = format_operator_message("connector_connect_to_run", integration="slack")
        assert first != second
        assert second != third
        assert "Slack" in first and "Slack" in second and "/connectors" in third
        snap = voice_expression_state_snapshot()
        assert snap["connector_connect_to_run"] == 2
    finally:
        reset_voice_expression_state(token)


def test_same_history_reproduces_same_selection():
    token1 = bind_voice_expression_state({"voice_expression_last": {"connector_connect_to_run": 1}})
    try:
        a = format_operator_message("connector_connect_to_run", integration="gmail")
    finally:
        reset_voice_expression_state(token1)
    token2 = bind_voice_expression_state({"voice_expression_last": {"connector_connect_to_run": 1}})
    try:
        b = format_operator_message("connector_connect_to_run", integration="gmail")
    finally:
        reset_voice_expression_state(token2)
    assert a == b
    # After last=1, next is index 2
    expected = EXPRESSION_BANKS["connector_connect_to_run"][2].format(integration="Gmail")
    assert a == expected


def test_excluded_categories_do_not_vary():
    assert "write_approval" in EXPRESSION_EXCLUDED
    token = bind_voice_expression_state({})
    try:
        a = format_operator_message(
            "write_approval",
            vendor="HubSpot",
            label="Create deal",
            details={"amount": "100"},
        )
        b = format_operator_message(
            "write_approval",
            vendor="HubSpot",
            label="Create deal",
            details={"amount": "100"},
        )
        assert a == b
        assert "Reply **yes**" in a
        assert pick_expression("write_approval") is None
        c = format_operator_message("canvas_write_blocked")
        d = format_operator_message("canvas_write_blocked")
        assert c == d
        e = format_operator_message(
            "tool_error",
            error_code="write_approval_required",
            integration="slack",
        )
        f = format_operator_message(
            "tool_error",
            error_code="write_approval_required",
            integration="slack",
        )
        assert e == f == "This write needs your approval before it runs."
    finally:
        reset_voice_expression_state(token)


@pytest.mark.parametrize(
    "category,ctx,tokens",
    [
        (
            "connector_connect_to_run",
            {"integration": "Slack"},
            ["Slack", "/connectors"],
        ),
        (
            "tool_error.connector_not_connected",
            {"integration": "Slack", "action_suffix": ""},
            ["Slack", "Connected", "/connectors", "yes"],
        ),
        (
            "tool_error.validation_error",
            {"integration": "HubSpot", "action_suffix": " (hubspot.deals.create)"},
            ["HubSpot", "hubspot.deals.create"],
        ),
        (
            "tool_error.rate_limited",
            {"integration": "Apollo", "action_suffix": ""},
            ["Apollo"],
        ),
        (
            "correction_ack",
            {"correction": "HubSpot instead of Apollo"},
            ["HubSpot instead of Apollo"],
        ),
        (
            "blocked_generic",
            {"blocker": "auth expired", "next_action": "Reconnect at /connectors."},
            ["auth expired", "Reconnect at /connectors"],
        ),
    ],
)
def test_fact_consistency_across_all_variants(category, ctx, tokens):
    variants = all_expressions(category, ctx=ctx)
    assert len(variants) >= 5
    assert_fact_tokens_consistent(variants, tokens)
    # Distinct constructions — not synonym-padded duplicates
    assert len(set(variants)) == len(variants)


def test_every_bank_has_maintainable_size():
    for key, bank in EXPRESSION_BANKS.items():
        assert 5 <= len(bank) <= 8, key
        assert len(set(bank)) == len(bank), f"duplicate variants in {key}"
