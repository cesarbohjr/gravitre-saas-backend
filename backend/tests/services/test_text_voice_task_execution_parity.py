"""Standing CI: canned shortcuts and spoken lite-path cannot diverge task execution.

Typed chat (assistant.py) and spoken (Pipecat / spoken_mode=True) must reach the
same kernel/LIVE gates for real operator jobs. Conversational chitchat may still
use spoken latency shortcuts.
"""

from __future__ import annotations

from app.routers import assistant as assistant_module
from app.services.conversational_turn_gate import (
    ambiguous_open_clarify_reply,
    definition_brief_reply,
    heuristic_turn_shape,
    is_human_moment_venting_no_ask,
)
from app.services.frontend_ia_nav_faq import match_frontend_ia_nav_faq
from app.services.operator_task_intent import (
    should_keep_full_reasoning_for_spoken,
    should_skip_unified_live_guards,
    use_spoken_lite_path,
)
from tests.services.task_execution_parity_fixtures import (
    AMBIGUOUS_CLARIFY,
    CONNECTOR_LOOKUP,
    GOOGLE_ADS_CAMPAIGN_BRIEF,
    MULTI_PARAM_WRITE,
    SEO_PLUS_GOOGLE_ADS,
    VENTING_PLUS_GOOGLE_ADS,
)


def _assert_reaches_reasoning(message: str) -> None:
    assert match_frontend_ia_nav_faq(message) is None
    assert ambiguous_open_clarify_reply(message) is None
    assert definition_brief_reply(message) is None
    assert is_human_moment_venting_no_ask(message) is False
    assert not assistant_module._response_cache_eligible(message)
    assert should_keep_full_reasoning_for_spoken(message)
    assert not use_spoken_lite_path(
        spoken_mode=True,
        routing_tier="simple",
        message=message,
    )
    assert not should_skip_unified_live_guards(
        spoken_mode=True,
        reasoning_depth="conversational",
        has_pending=False,
        message=message,
    )
    assert not should_skip_unified_live_guards(
        spoken_mode=False,
        reasoning_depth="full",
        has_pending=False,
        message=message,
    )


def test_google_ads_brief_reaches_reasoning_typed_and_spoken() -> None:
    _assert_reaches_reasoning(GOOGLE_ADS_CAMPAIGN_BRIEF)


def test_connector_lookup_reaches_reasoning_typed_and_spoken() -> None:
    _assert_reaches_reasoning(CONNECTOR_LOOKUP)


def test_multi_param_write_reaches_reasoning_typed_and_spoken() -> None:
    _assert_reaches_reasoning(MULTI_PARAM_WRITE)


def test_seo_prefix_plus_google_ads_is_not_canned_clarify() -> None:
    """Mutation of the FAQ-class bug: prefix keyword + real job must fall through."""
    assert ambiguous_open_clarify_reply(AMBIGUOUS_CLARIFY) is not None
    assert ambiguous_open_clarify_reply(SEO_PLUS_GOOGLE_ADS) is None
    _assert_reaches_reasoning(SEO_PLUS_GOOGLE_ADS)


def test_venting_plus_google_ads_is_not_human_moment_canned() -> None:
    assert is_human_moment_venting_no_ask("ugh this is so frustrating today") is True
    assert is_human_moment_venting_no_ask(VENTING_PLUS_GOOGLE_ADS) is False
    decision = heuristic_turn_shape(VENTING_PLUS_GOOGLE_ADS)
    assert decision is None or decision.shape != "conversational" or decision.reason != "human_moment_venting_no_ask"
    _assert_reaches_reasoning(VENTING_PLUS_GOOGLE_ADS)


def test_narrow_ambiguous_open_still_clarifies() -> None:
    reply = ambiguous_open_clarify_reply(AMBIGUOUS_CLARIFY)
    assert reply is not None
    assert "?" in reply


def test_spoken_and_typed_share_full_depth_for_operator_tasks() -> None:
    for message in (GOOGLE_ADS_CAMPAIGN_BRIEF, CONNECTOR_LOOKUP, MULTI_PARAM_WRITE):
        typed_skip = should_skip_unified_live_guards(
            spoken_mode=False,
            reasoning_depth="full",
            has_pending=False,
            message=message,
        )
        spoken_skip = should_skip_unified_live_guards(
            spoken_mode=True,
            reasoning_depth="full",
            has_pending=False,
            message=message,
        )
        assert typed_skip is False
        assert spoken_skip is False
        assert should_keep_full_reasoning_for_spoken(message)
