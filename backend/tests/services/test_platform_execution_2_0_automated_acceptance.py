"""2.0 automated acceptance — B/G/F/K/L/M/H/I/J-A without customer data."""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from app.connectors.action_catalog.registry import get_action_spec
from app.connectors.google_vendor_oauth import google_vendor_authorize_url
from app.services.canonical_cognitive_resolution import should_skip_unified_live_for_compiled_read
from app.services.cognitive_outcome_loop import bias_from_outcomes, record_closed_loop
from app.services.connector_certification_scorecard import (
    scorecard_from_availability_rows,
)
from app.services.gravitre_e2e_test_org import (
    E2E_ORG_ID,
    FORBIDDEN_OPERATOR_ORG_ID,
    e2e_org_policy,
    seed_test_customer_alpha,
)
from app.services.multi_source_diagnostic import (
    build_multi_source_diagnostic_plan,
    conclude_diagnostic,
    match_diagnostic_recipe,
)
from app.services.outcome_learning_service import tool_success_is_business_impact
from app.services.proactive_business_operator import evaluate_business_signals
from app.services.reasoning_evidence_pipeline import (
    parallel_safe_steps,
    plan_entity_join_for_reads,
)
from app.services.task_continuity import decide_task_continuity
from app.services.text_voice_semantic_parity import typed_matches_spoken
from app.services.voice_protocol_proof import (
    KNOWN_PCM_FIXTURE,
    classify_voice_proof,
    known_pcm_websocket_roundtrip,
    protocol_roundtrip_ok,
)


def _deals_state() -> dict:
    return {
        "execution_plan": {
            "plan_id": "plan-deals-1",
            "capability_id": "sales.pipeline.health",
            "objective": "Show my deals.",
            "terminal_status": "completed",
            "steps": [
                {
                    "step_id": "s1",
                    "kind": "read",
                    "action_key": "hubspot.deals.list",
                    "status": "completed",
                }
            ],
        },
        "compiled_task": {
            "plan_id": "plan-deals-1",
            "capability_id": "sales.pipeline.health",
            "objective_text": "Show my deals.",
        },
    }


def test_e2e_org_is_not_operator_workspace() -> None:
    policy = e2e_org_policy()
    assert policy["org_id"] == E2E_ORG_ID
    assert policy["never_customer_visible"] is True
    assert policy["forbidden_operator_org"] == FORBIDDEN_OPERATOR_ORG_ID
    assert policy["org_id"] != FORBIDDEN_OPERATOR_ORG_ID


def test_b_unique_bind_alpha_survives_into_join_plan() -> None:
    from app.services.gravitre_e2e_test_org import ALPHA_ENTITY_ID

    entity = seed_test_customer_alpha()
    assert entity.id == ALPHA_ENTITY_ID
    assert entity.org_id == E2E_ORG_ID
    assert {b.system for b in entity.bindings} == {"hubspot", "quickbooks", "zendesk"}
    join = plan_entity_join_for_reads(
        entity=entity,
        store_available=True,
        read_vendors=["hubspot", "zendesk", "quickbooks"],
    )
    assert join["join"] is True
    assert join["entity_id"] == entity.id
    assert len(join["systems"]) >= 2


def test_b_ambiguous_name_only_refused() -> None:
    from app.services.business_entity_fabric import EntityBinding, EntityEvidence, join_provider_bindings

    left = EntityBinding(
        system="hubspot",
        resource_type="company",
        resource_id="hs-x",
        confidence=0.95,
        evidence=(EntityEvidence(kind="legal_name", value="Alpha", source="hubspot"),),
    )
    right = EntityBinding(
        system="zendesk",
        resource_type="organization",
        resource_id="zd-x",
        confidence=0.95,
        evidence=(EntityEvidence(kind="legal_name", value="Alpha", source="zendesk"),),
    )
    decision = join_provider_bindings(
        org_id=E2E_ORG_ID,
        display_name="Alpha",
        kind="company",
        left=left,
        right=right,
    )
    assert decision.status == "refused_ambiguous"


def test_g_deals_plus_tickets_does_not_need_ga() -> None:
    message = "Which open deals have customers with recent support tickets?"
    assert match_diagnostic_recipe(message) == "sales.pipeline.health"
    plan = build_multi_source_diagnostic_plan(
        message,
        connected_integrations=["hubspot", "zendesk"],
    )
    assert plan is not None
    vendors = {str(s.connector_id or "") for s in plan.steps}
    assert "zendesk" in vendors
    assert "google_analytics" not in vendors
    parallel = parallel_safe_steps(plan)
    assert all(s.kind != "write" for s in parallel)
    conclusion = conclude_diagnostic(plan, [])
    assert conclusion["sufficient"] is False
    assert "enough live system evidence" in conclusion["message"]


def test_h_expanded_continuity_phrases() -> None:
    state = _deals_state()
    for message in (
        "Only the large ones.",
        "Last week instead.",
        "Only the top three.",
        "Who owns those?",
        "Draft a summary.",
    ):
        assert decide_task_continuity(message, state) == "continue", message
        assert should_skip_unified_live_for_compiled_read(message, state, ["hubspot"])


@pytest.mark.asyncio
async def test_f_draft_email_compiles_without_send() -> None:
    from app.services.governed_write_compile import try_governed_write_compile_turn

    spec = get_action_spec("gmail.drafts.create")
    assert spec is not None
    proof = MagicMock(
        ok=True,
        error_class=None,
        safe_parameter_summary=lambda: {"to": "ops@alpha.test.gravitre.app"},
        user_message=lambda: "",
    )
    with patch(
        "app.services.governed_write_compile.preflight_write_action",
        return_value=proof,
    ) as mock_pf:
        turn = await try_governed_write_compile_turn(
            message="Draft an email.",
            org_id=E2E_ORG_ID,
            client=object(),
            settings=MagicMock(),
            connected_integrations=["gmail"],
            task_state={},
        )
    assert turn is not None
    assert turn["selected_action"] == "gmail.drafts.create"
    assert turn["workflow_status"] == "waiting_for_approval"
    assert "sent" in turn["message"].lower()
    pending = turn["task_state"]["pending_action"]
    assert pending["action"] == "gmail.drafts.create"
    assert pending["write_allowed"] is False
    mock_pf.assert_called_once()
    assert mock_pf.call_args.kwargs["context"]["action_key"] == "gmail.drafts.create"


@pytest.mark.asyncio
async def test_k_tool_success_then_business_outcome_biases_plan() -> None:
    assert tool_success_is_business_impact("workflow_executed") is False
    rec_id = str(uuid4())
    with patch(
        "app.services.outcome_learning_service.get_outcome_learning_service"
    ) as mock_svc:
        mock_svc.return_value.record_recommendation_outcome = AsyncMock()
        recorded = await record_closed_loop(
            org_id=E2E_ORG_ID,
            recommendation_id=rec_id,
            outcome_event="workflow_executed",
            settings=SimpleNamespace(),
        )
        assert recorded["ok"] is True
        mock_svc.return_value.record_recommendation_outcome.assert_called()
        assert mock_svc.return_value.record_recommendation_outcome.call_args[0][2] == "workflow_executed"

    rows = [
        {"outcome_event": "workflow_executed", "entity_id": "alpha", "recommendation_id": rec_id},
        {
            "outcome_event": "business_metric_improved",
            "entity_id": "alpha-completion",
            "recommendation_id": rec_id,
        },
    ]
    client = MagicMock()
    client.table.return_value.select.return_value.eq.return_value.order.return_value.limit.return_value.execute.return_value = SimpleNamespace(
        data=rows
    )
    bias = bias_from_outcomes(client, E2E_ORG_ID, "alpha", SimpleNamespace())
    notes = " ".join(bias["bias_notes"])
    assert "workflow_executed" not in notes
    assert "business_metric_improved" in notes
    assert bias["weight_delta"] > 0


def test_l_scorecard_mixed_states_no_customer_badge() -> None:
    rows = [
        {
            "vendor": "hubspot",
            "configured": True,
            "connected": True,
            "authenticated": True,
            "token_valid": True,
            "scopes_valid": True,
            "execution_available": True,
            "last_success_at": "2026-09-21T06:21:00Z",
            "test_verified": True,
        },
        {
            "vendor": "google_analytics",
            "configured": True,
            "connected": False,
            "authenticated": False,
            "token_valid": False,
            "scopes_valid": False,
            "execution_available": False,
        },
        {
            "vendor": "google_search_console",
            "configured": True,
            "connected": True,
            "authenticated": False,
            "token_valid": False,
            "scopes_valid": True,
            "execution_available": False,
        },
    ]
    card = scorecard_from_availability_rows(
        rows,
        action_keys=["hubspot.deals.list", "google_analytics.reports.run", "google_search_console.searchAnalytics.query"],
        production_verified_keys=frozenset({"hubspot.deals.list"}),
    )
    assert card["customer_facing_certification"] is False
    by_action = {item["action_key"]: item for item in card["items"]}
    assert by_action["hubspot.deals.list"]["layers"]["production_verified"] is True
    assert by_action["google_analytics.reports.run"]["layers"]["authorized"] is False
    assert all(item["customer_badge"] is None for item in card["items"])


def test_m_proactive_dedupes_and_never_writes() -> None:
    recs = evaluate_business_signals(
        [
            {
                "id": "ga-auth",
                "kind": "pending_auth",
                "connector": "google_analytics",
                "evidence": ["pending_auth"],
            },
            {
                "id": "ga-auth",
                "kind": "pending_auth",
                "connector": "google_analytics",
                "evidence": ["pending_auth"],
            },
        ]
    )
    assert len(recs) == 1
    assert recs[0].notify is True
    assert recs[0].write_allowed is False


def test_i_text_voice_skip_live_parity() -> None:
    state = _deals_state()
    connected = ["hubspot"]
    assert typed_matches_spoken(
        "Only the large ones.",
        "Only the large ones.",
        state,
        connected,
    )
    assert typed_matches_spoken(
        "Which open deals have customers with recent support tickets?",
        "Which open deals have customers with recent support tickets?",
        {},
        ["hubspot", "zendesk"],
    )


def test_j_voice_a_protocol_is_not_human_device() -> None:
    assert classify_voice_proof(
        used_known_pcm_fixture=True,
        used_virtual_loopback=False,
        used_physical_microphone=False,
    ) == "VOICE_A_PROTOCOL"
    assert protocol_roundtrip_ok(KNOWN_PCM_FIXTURE, KNOWN_PCM_FIXTURE)
    assert classify_voice_proof(
        used_known_pcm_fixture=False,
        used_virtual_loopback=True,
        used_physical_microphone=False,
    ) == "VOICE_B_VIRTUAL_AUDIO"
    assert classify_voice_proof(
        used_known_pcm_fixture=False,
        used_virtual_loopback=False,
        used_physical_microphone=True,
    ) == "VOICE_C_HUMAN_DEVICE"


@pytest.mark.asyncio
async def test_j_voice_a_known_pcm_serializer_roundtrip() -> None:
    recovered = await known_pcm_websocket_roundtrip(KNOWN_PCM_FIXTURE)
    assert recovered == KNOWN_PCM_FIXTURE
    from app.services.voice_protocol_proof import virtual_audio_path_timings

    timings = await virtual_audio_path_timings(KNOWN_PCM_FIXTURE)
    assert timings["proof_class"] == "VOICE_B_VIRTUAL_AUDIO"
    assert timings["roundtrip_ok"] is True
    assert timings["physical_microphone"] is False
    assert timings["first_pcm_available_ms"] >= timings["speech_end_ms"]


def test_isolated_reconnect_may_force_consent_default_does_not() -> None:
    default = google_vendor_authorize_url(
        "google_search_console",
        "cid",
        "https://gravitre.app/api/connectors/oauth/google/callback",
        "st",
    )
    forced = google_vendor_authorize_url(
        "google_search_console",
        "cid",
        "https://gravitre.app/api/connectors/oauth/google/callback",
        "st",
        force_consent=True,
    )
    assert "prompt=select_account" in default
    assert "prompt=consent" in forced
