"""Phase 6 (conversational-realism): real per-stage voice latency sample writes.

Confirms record_voice_llm_stage_sample / record_voice_e2e_latency_sample write
through the exact same write_audit_event helper the rest of the platform's
live signals use (unified_turn.live.completed, platform.deploy_smoke, ...),
that they pass a real user_id as actor_id (audit_events.actor_id FKs
auth.users(id) — org_id is never a valid stand-in and every write silently
23503'd until this was fixed; see the live-verified root cause note in
voice_latency_metrics.py), and that a write failure never raises out into the
live voice turn it is reporting on (fire-and-forget contract).
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

from app.services.pipecat_voice import voice_latency_metrics as mod


def test_llm_stage_sample_writes_via_write_audit_event_with_expected_shape():
    """MUTATION PROOF: wrong action name or payload shape would break the
    golden_signals_service reducer, which reads these exact field names.
    """
    client = MagicMock()
    with (
        patch("app.workflows.repository.get_supabase_client", return_value=client),
        patch("app.workflows.audit.write_audit_event") as write,
    ):
        mod.record_voice_llm_stage_sample(
            object(),
            org_id="11111111-1111-1111-1111-111111111111",
            user_id="33333333-3333-3333-3333-333333333333",
            conversation_id="22222222-2222-2222-2222-222222222222",
            llm_first_token_ms=650,
            llm_first_speakable_chunk_ms=900,
            tts_requested_ms=910,
        )

    assert write.call_count == 1
    args = write.call_args.args
    assert args[0] is client
    assert args[1] == "11111111-1111-1111-1111-111111111111"
    # MUTATION PROOF: actor_id (args[2]) must be the real user_id, never the
    # org_id — audit_events.actor_id FKs auth.users(id), not orgs.
    assert args[2] == "33333333-3333-3333-3333-333333333333"
    assert args[3] == mod.LLM_STAGE_ACTION == "voice.turn_latency.llm_stage"
    assert args[4] == "conversation"
    assert args[5] == "22222222-2222-2222-2222-222222222222"
    payload = args[6]
    assert payload == {
        "llm_first_token_ms": 650,
        "llm_first_speakable_chunk_ms": 900,
        "tts_requested_ms": 910,
    }


def test_e2e_sample_writes_via_write_audit_event_with_expected_shape():
    client = MagicMock()
    with (
        patch("app.workflows.repository.get_supabase_client", return_value=client),
        patch("app.workflows.audit.write_audit_event") as write,
    ):
        mod.record_voice_e2e_latency_sample(
            object(),
            org_id="11111111-1111-1111-1111-111111111111",
            user_id="33333333-3333-3333-3333-333333333333",
            conversation_id=None,
            end_to_end_ms=4200,
            user_turn_finalization_ms=1100,
            ttfb_by_processor_ms={"GravitreCognitiveLLMService": 650, "ElevenLabsTTSService": 180},
        )

    assert write.call_count == 1
    args = write.call_args.args
    assert args[2] == "33333333-3333-3333-3333-333333333333"
    assert args[3] == mod.E2E_ACTION == "voice.turn_latency.e2e"
    # conversation_id falls back to org_id (same UUID-fallback convention as
    # unified_turn_reasoning_service.emit_unified_turn_shadow_audit) so the
    # audit_events resource_id NOT NULL constraint is never violated.
    assert args[5] == "11111111-1111-1111-1111-111111111111"
    payload = args[6]
    assert payload["end_to_end_ms"] == 4200
    assert payload["user_turn_finalization_ms"] == 1100
    assert payload["ttfb_by_processor_ms"] == {
        "GravitreCognitiveLLMService": 650,
        "ElevenLabsTTSService": 180,
    }


def test_no_org_id_skips_write_entirely():
    with patch("app.workflows.audit.write_audit_event") as write:
        mod.record_voice_e2e_latency_sample(
            object(),
            org_id="",
            user_id="33333333-3333-3333-3333-333333333333",
            conversation_id=None,
            end_to_end_ms=1000,
            user_turn_finalization_ms=None,
            ttfb_by_processor_ms={},
        )
    write.assert_not_called()


def test_no_user_id_skips_write_entirely():
    """MUTATION PROOF (live root cause): a missing/blank user_id must skip
    the write, not silently fall back to org_id as actor_id — that fallback
    is exactly what caused every Phase 6 sample to 23503 in production.
    """
    with patch("app.workflows.audit.write_audit_event") as write:
        mod.record_voice_llm_stage_sample(
            object(),
            org_id="11111111-1111-1111-1111-111111111111",
            user_id=None,
            conversation_id=None,
            llm_first_token_ms=1,
            llm_first_speakable_chunk_ms=1,
            tts_requested_ms=1,
        )
    write.assert_not_called()


def test_write_failure_is_swallowed_never_raises():
    """MUTATION PROOF: a live voice turn must never crash because a
    best-effort latency sample failed to persist.
    """
    with (
        patch(
            "app.workflows.repository.get_supabase_client",
            side_effect=RuntimeError("db down"),
        ),
    ):
        mod.record_voice_llm_stage_sample(
            object(),
            org_id="11111111-1111-1111-1111-111111111111",
            user_id="33333333-3333-3333-3333-333333333333",
            conversation_id=None,
            llm_first_token_ms=1,
            llm_first_speakable_chunk_ms=1,
            tts_requested_ms=1,
        )
    # Reaching here (no exception propagated) is the assertion.
