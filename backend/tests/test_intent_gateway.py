"""Intent Gateway: one threshold, one operator-task scope, identical text/voice."""

from __future__ import annotations

import pytest

from app.services.intent_gateway import (
    INTENT_GATEWAY_THRESHOLD,
    CandidateVerdict,
    GatewayContext,
    evaluate_intent_gateway,
    response_cache_clear,
    response_cache_put,
)
from tests.services.task_execution_parity_fixtures import (
    AMBIGUOUS_CLARIFY,
    GOOGLE_ADS_CAMPAIGN_BRIEF,
    SEO_PLUS_GOOGLE_ADS,
    VENTING_PLUS_GOOGLE_ADS,
)

NAV_FAQ = (
    "In the Gravitre sidebar, which primary nav item holds Enterprise, Federation, and Environments?"
)


@pytest.fixture(autouse=True)
def _clear_gateway_cache() -> None:
    response_cache_clear()
    yield
    response_cache_clear()


def test_threshold_is_uniform_and_high() -> None:
    assert INTENT_GATEWAY_THRESHOLD == 0.92


@pytest.mark.asyncio
async def test_operator_task_is_ineligible_even_if_a_candidate_would_hit(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_faq(_ctx: GatewayContext) -> CandidateVerdict:
        return CandidateVerdict(candidate_id="ia_nav_faq", confidence=0.99, answer="FAQ hijack")

    monkeypatch.setattr(
        "app.services.intent_gateway._SYNC_CANDIDATES",
        (fake_faq,),
    )

    async def _none(_ctx: GatewayContext):
        return None

    monkeypatch.setattr("app.services.intent_gateway._propose_channel_override", _none)
    monkeypatch.setattr("app.services.intent_gateway._propose_meta_capability", _none)

    for spoken in (False, True):
        decision = await evaluate_intent_gateway(
            GatewayContext(message=GOOGLE_ADS_CAMPAIGN_BRIEF, spoken_mode=spoken, org_id="org")
        )
        assert decision.action == "fallthrough"
        assert decision.reason == "operator_task_shaped"
        assert decision.answer is None


@pytest.mark.asyncio
async def test_below_threshold_always_falls_through(monkeypatch: pytest.MonkeyPatch) -> None:
    def weak(_ctx: GatewayContext) -> CandidateVerdict:
        return CandidateVerdict(
            candidate_id="weak",
            confidence=INTENT_GATEWAY_THRESHOLD - 0.01,
            answer="should not serve",
        )

    monkeypatch.setattr("app.services.intent_gateway._SYNC_CANDIDATES", (weak,))

    async def _none(_ctx: GatewayContext):
        return None

    monkeypatch.setattr("app.services.intent_gateway._propose_channel_override", _none)
    monkeypatch.setattr("app.services.intent_gateway._propose_meta_capability", _none)

    decision = await evaluate_intent_gateway(
        GatewayContext(message="hey, how's it going", org_id="org")
    )
    assert decision.action == "fallthrough"
    assert decision.reason == "below_threshold"


@pytest.mark.asyncio
async def test_hello_there_and_capability_one_liner_shortcut_at_threshold() -> None:
    """Calibration: these are high-confidence social/meta, not a reason to lower 0.92."""
    hello = await evaluate_intent_gateway(GatewayContext(message="hello there", org_id="org"))
    capability = await evaluate_intent_gateway(
        GatewayContext(message="what can you help with in one sentence", org_id="org")
    )
    assert hello.action == "shortcut"
    assert hello.candidate_id == "phrase_bank"
    assert hello.confidence is not None and hello.confidence >= INTENT_GATEWAY_THRESHOLD
    assert capability.action == "shortcut"
    assert capability.candidate_id in {"phrase_bank", "meta_capability"}
    assert capability.confidence is not None and capability.confidence >= INTENT_GATEWAY_THRESHOLD
    job = await evaluate_intent_gateway(
        GatewayContext(message="What can you help with for our SEO campaign this quarter?", org_id="org")
    )
    assert job.action == "fallthrough"
    typed = await evaluate_intent_gateway(GatewayContext(message=NAV_FAQ, spoken_mode=False, org_id="org"))
    spoken = await evaluate_intent_gateway(GatewayContext(message=NAV_FAQ, spoken_mode=True, org_id="org"))
    assert typed.action == "shortcut"
    assert spoken.action == "shortcut"
    assert typed.candidate_id == spoken.candidate_id == "ia_nav_faq"
    assert typed.answer == spoken.answer
    assert typed.confidence is not None and typed.confidence >= INTENT_GATEWAY_THRESHOLD


@pytest.mark.asyncio
async def test_narrow_seo_clarify_shortcuts_but_seo_plus_ads_falls_through() -> None:
    clarify = await evaluate_intent_gateway(GatewayContext(message=AMBIGUOUS_CLARIFY, org_id="org"))
    mixed = await evaluate_intent_gateway(GatewayContext(message=SEO_PLUS_GOOGLE_ADS, org_id="org"))
    assert clarify.action == "shortcut"
    assert clarify.candidate_id == "ambiguous_open_clarify"
    assert mixed.action == "fallthrough"
    assert mixed.reason == "operator_task_shaped"


@pytest.mark.asyncio
async def test_venting_plus_operator_task_falls_through() -> None:
    vent_only = await evaluate_intent_gateway(
        GatewayContext(message="ugh this is so frustrating today", org_id="org")
    )
    mixed = await evaluate_intent_gateway(GatewayContext(message=VENTING_PLUS_GOOGLE_ADS, org_id="org"))
    assert vent_only.action == "shortcut"
    assert vent_only.candidate_id == "venting_no_ask"
    assert mixed.action == "fallthrough"


@pytest.mark.asyncio
async def test_response_cache_is_a_candidate_not_an_independent_answer() -> None:
    msg = "status ping for the lobby coffee machine"
    response_cache_put("org", "conv", msg, "cached hello", ["next"])
    typed = await evaluate_intent_gateway(
        GatewayContext(
            message=msg,
            org_id="org",
            conversation_id="conv",
            spoken_mode=False,
        )
    )
    spoken = await evaluate_intent_gateway(
        GatewayContext(
            message=msg,
            org_id="org",
            conversation_id="conv",
            spoken_mode=True,
        )
    )
    assert typed.action == spoken.action == "shortcut"
    assert typed.candidate_id == spoken.candidate_id == "response_cache"
    assert typed.answer == spoken.answer == "cached hello"
