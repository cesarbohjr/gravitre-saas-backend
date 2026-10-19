"""LIVE chat answers explain their sources in plain language, with no made-up confidence.

The context engine records which sources it selected and which it left out
(``contextRanking``). That record used to stop at the audit trace; the user saw
nothing under "Why this answer?" and a hard-coded 0.9 confidence.
"""
from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from app.operators.assistant_sse import sse_intelligence_metadata
from app.operators.stream_events import AssistantStreamComplete
from app.services.context_sources_summary import (
    build_user_context_sources,
    freshness_words,
)

NOW = datetime(2026, 10, 19, 12, 0, tzinfo=UTC)


def _knowledge_meta() -> dict:
    return {
        "competing_crm_hits_dropped": 1,
        "contextRanking": {
            "mode": "active",
            "freshnessApplied": True,
            "selectedSources": [
                {"id": "rag:9f2c1a7b3e4d5f60", "type": "rag", "label": "Pricing FAQ 2026"},
                {"id": "rag:0a1b2c3d4e5f6a7b", "type": "rag", "label": "Discount policy"},
                {
                    "id": "kernel:conversation_memory",
                    "type": "conversation_memory",
                    "label": "Conversation and agent memory",
                },
                {
                    "id": "graph:abc",
                    "type": "graph",
                    "label": "org business graph (deal:7d1e0c4a-1111-2222-3333-444455556666)",
                },
                {"id": "rag:1234", "type": "rag", "label": "7d1e0c4a-1111-2222-3333-444455556666"},
            ],
            "selectedSourcesAsOf": [
                (NOW - timedelta(hours=2)).isoformat(),
                (NOW - timedelta(days=40)).isoformat(),
                None,
                None,
                None,
            ],
            "excludedSources": [
                {"id": "rag:old", "type": "rag", "reason": "expired"},
                {"id": "rag:old2", "type": "rag", "reason": "superseded"},
                {"id": "rag:dup", "type": "rag", "reason": "duplicate", "duplicateOf": "rag:x"},
                {"id": "rag:none", "type": "rag", "reason": "empty"},
            ],
        },
    }


def test_summary_names_sources_freshness_and_skips_in_plain_words() -> None:
    out = build_user_context_sources(_knowledge_meta(), now=NOW)
    assert out is not None
    used = {row["name"]: row for row in out["used"]}
    assert used["Pricing FAQ 2026"]["kind"] == "Your knowledge"
    assert used["Pricing FAQ 2026"]["freshness"] == "updated 2 hours ago"
    assert used["Discount policy"]["freshness"] == "updated 5 weeks ago"
    assert "freshness" not in used["Conversation and agent memory"]
    skipped = {row["reason"]: row["count"] for row in out["skipped"]}
    assert skipped == {"out_of_date": 2, "repeated": 1, "not_connected": 1}
    summary = out["summary"]
    assert summary.startswith("Used ")
    assert "2 out-of-date sources" in summary
    assert "1 source from a tool that isn't connected" in summary
    assert summary.endswith(".")


def test_summary_never_shows_internal_ids() -> None:
    out = build_user_context_sources(_knowledge_meta(), now=NOW)
    blob = repr(out)
    assert "7d1e0c4a" not in blob
    assert "rag:" not in blob
    assert "kernel:" not in blob
    assert "deal:" not in blob


def test_nothing_recorded_means_nothing_claimed() -> None:
    assert build_user_context_sources(None) is None
    assert build_user_context_sources({}) is None
    no_hits = build_user_context_sources({"skipped": "no_hits"})
    assert no_hits is not None and no_hits["used"] == [] and no_hits["skipped"] == []


def test_freshness_words_only_from_real_dates() -> None:
    assert freshness_words(None, now=NOW) is None
    assert freshness_words("not a date", now=NOW) is None
    assert freshness_words((NOW - timedelta(minutes=5)).isoformat(), now=NOW) == "updated 5 minutes ago"
    assert freshness_words("2026-10-19", now=NOW) == "updated today"
    assert freshness_words((NOW + timedelta(days=1)).isoformat(), now=NOW) is None


def test_sse_frame_carries_context_sources() -> None:
    sources = build_user_context_sources(_knowledge_meta(), now=NOW)
    event = sse_intelligence_metadata(
        message_id="m1",
        confidence={"needs_clarification": False},
        answer_explanation="Unified turn live (final_answer)",
        context_explanation=sources["summary"],
        context_sources=sources,
    )
    data = event.payload["data"]
    assert data["contextSources"]["used"][0]["name"] == "Pricing FAQ 2026"
    assert data["contextExplanation"] == sources["summary"]
    assert "score" not in data["confidence"]
    # Frames without a record do not invent one.
    bare = sse_intelligence_metadata(message_id="m2", confidence=None, answer_explanation=None)
    assert bare.payload["data"]["contextSources"] is None


@pytest.mark.asyncio
async def test_live_turn_streams_context_sources_and_no_fake_confidence() -> None:
    from tests.operators.test_typed_live_streaming import _run_typed_turn

    meta = _knowledge_meta()

    async def fake_live(**_kwargs):
        return {
            "stop_pipeline": True,
            "message": "The Pro plan is listed at the price in your pricing FAQ.",
            "dialogue_mode": "answer",
            "latency_breakdown": {"unifiedTurnKnowledge": meta},
        }

    timeline = await _run_typed_turn(fake_live, streaming=False)
    frames = [
        event.payload["data"]
        for _, event in timeline
        if getattr(event, "sse_type", "") == "data-intelligence"
    ]
    live = [f for f in frames if (f.get("routing") or {}).get("unifiedTurnLive")]
    assert live, "LIVE answer sent no data-intelligence frame"
    frame = live[0]
    assert frame["contextSources"] is not None
    names = [row["name"] for row in frame["contextSources"]["used"]]
    assert "Pricing FAQ 2026" in names
    assert frame["contextExplanation"] == frame["contextSources"]["summary"]
    assert "score" not in (frame["confidence"] or {})
    complete = next(e for _, e in timeline if isinstance(e, AssistantStreamComplete))
    assert "score" not in (complete.confidence or {})
