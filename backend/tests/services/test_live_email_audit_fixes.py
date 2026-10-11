"""Live email test audit (2026-10-11): F1-F4 regressions.

Cesar asked voice to email Stephanie on Gmail. Production sent the request,
"Gmail." and even "Sorry." to public web search; "try again, the email now?"
got "I don't have a matching prior write"; and two state paths could lose or
add data after the turn moved on.

F1  Thin internal context alone must not web-search actions, slot answers,
    retries, apologies or small talk. Real questions and explicit research
    still search.
F2  A retry or a mention of "the email" continues the task in progress; only
    real status questions about a finished write are answered from the log,
    and an uncertain earlier send is never resent blind.
F3  A failed state read must not turn into an empty state that replaces the
    stored pending task and memory.
F4  A memory promotion cancelled during its lookup/embedding writes nothing.
"""
from __future__ import annotations

import ast
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest.mock import patch

import pytest

from app.services.action_lifecycle import recent_write_status_turn
from app.services.adaptive_research_cascade import (
    ResearchScope,
    auto_internet_research_blocked,
    should_run_internet_research,
)
from app.services.conversation_state_service import ConversationStateService
from app.services.turn_cancellation import TurnCancellation, bound_turn_cancellation
from tests.services.fake_supabase_db import FakeSupabaseDB

ORG = "11111111-1111-4111-8111-111111111111"
USER = "22222222-2222-4222-8222-222222222222"
CONV = "33333333-3333-4333-8333-333333333333"

_INTERNET_ON = SimpleNamespace(
    internet_research_enabled=True,
    tavily_api_key="tvly-test",
    gemini_api_key="",
    web_research_provider="tavily",
    web_research_fallback_tavily=True,
    google_genai_use_vertexai=False,
    google_cloud_project="",
    google_cloud_location="us-central1",
)


def _thin_search(query: str) -> bool:
    return should_run_internet_research(
        ResearchScope.INTERNAL_ONLY.value,
        settings=_INTERNET_ON,
        internal_thin=True,
        query=query,
    )


# --- F1: no public research for the email conversation -----------------------------


@pytest.mark.parametrize(
    "utterance",
    [
        "Send an email to Stephanie.",
        "Can you send an email to Stephanie on Gmail?",
        "Gmail.",
        "No.",
        "Sorry.",
        "Sorry about that.",
        "Try again... the email now?",
        "Okay, draft it and send it to her.",
        "Thanks!",
    ],
)
def test_the_email_conversation_never_searches_the_web(utterance: str) -> None:
    assert auto_internet_research_blocked(utterance)
    assert not _thin_search(utterance)


@pytest.mark.parametrize(
    "utterance",
    [
        "What's the average open rate for B2B cold email?",
        "How are other MSPs pricing managed backup these days?",
        "Research Stephanie's company online before I email her.",
        "Search the web for the latest Gmail sending limits.",
    ],
)
def test_real_information_needs_still_search_when_internal_context_is_thin(utterance: str) -> None:
    assert _thin_search(utterance)


def test_a_chosen_internet_scope_still_searches_whatever_was_said() -> None:
    assert should_run_internet_research(
        ResearchScope.INTERNET_RESEARCH.value,
        settings=_INTERNET_ON,
        internal_thin=False,
        query="Gmail.",
    )


def test_every_research_call_site_passes_the_query() -> None:
    """The voice knowledge path called without the query, so no intent check
    could run there. Every call now hands the words over."""
    root = Path(__file__).resolve().parents[2] / "app"
    missing: list[str] = []
    for path in root.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.Call)
                and getattr(node.func, "id", getattr(node.func, "attr", None)) == "should_run_internet_research"
                and not any(kw.arg == "query" for kw in node.keywords)
            ):
                missing.append(f"{path.relative_to(root)}:{node.lineno}")
    assert missing == []


# --- F2: retry and "the email" continue the draft -------------------------------------


def _email_draft_state() -> dict[str, Any]:
    return {
        "pending_task": {
            "intent": "send_email",
            "status": "collecting",
            "params": {
                "invoke_action": "gmail.messages.send",
                "args": {"to_name": "Stephanie"},
            },
        }
    }


@pytest.mark.parametrize(
    "utterance",
    ["Try again... the email now?", "Can you send the email now?", "Retry the email to Stephanie."],
)
def test_a_retry_on_a_draft_continues_the_task(utterance: str) -> None:
    assert recent_write_status_turn(utterance, _email_draft_state()) is None
    assert recent_write_status_turn(utterance, {}) is None


def test_a_status_question_with_nothing_written_is_not_a_dead_end() -> None:
    state = _email_draft_state()
    state["pending_task"]["params"]["missing"] = ["subject", "body"]
    turn = recent_write_status_turn("Did you send the email?", state)
    assert turn is not None and turn["provider_write"] is False
    assert turn["message"] == "Not yet. What should the subject and message be?"


def test_a_retry_after_an_uncertain_send_never_resends_blind() -> None:
    state = _email_draft_state()
    state["pending_task"]["status"] = "outcome_uncertain"
    turn = recent_write_status_turn("Try again, the email now?", state)
    assert turn is not None
    assert turn["stop_pipeline"] is True
    assert turn["provider_write"] is False
    assert "won't send it again" in turn["message"]


# --- F3: a failed read never replaces stored state --------------------------------------


def _stored_state() -> dict[str, Any]:
    return {
        "pending_task": {"intent": "send_email", "status": "collecting", "params": {"provider": "gmail"}},
        "conversation_memory": {"recipient": "Stephanie"},
    }


def _db() -> FakeSupabaseDB:
    db = FakeSupabaseDB()
    db.tables["conversations"] = [{"id": CONV, "org_id": ORG, "user_id": USER, "task_state": _stored_state()}]
    return db


@pytest.mark.asyncio
async def test_a_failed_read_does_not_erase_the_pending_task(mock_settings) -> None:
    db = _db()
    svc = ConversationStateService(mock_settings)

    def _fail(*_a: Any, **_k: Any) -> dict[str, Any]:
        raise ConnectionError("db unavailable")

    svc._read_task_state_sync = _fail  # type: ignore[method-assign]
    await svc.update_task_state(CONV, ORG, {"clarified_params": {"tone": "warm"}}, client=db)
    stored = db.tables["conversations"][0]["task_state"]
    assert stored == _stored_state(), "unknown state must not be replaced with defaults"


@pytest.mark.asyncio
async def test_one_failed_read_is_retried_and_the_save_merges(mock_settings) -> None:
    db = _db()
    svc = ConversationStateService(mock_settings)
    real = svc._read_task_state_sync
    calls = {"n": 0}

    def _flaky(*a: Any, **k: Any) -> dict[str, Any]:
        calls["n"] += 1
        if calls["n"] == 1:
            raise ConnectionError("blip")
        return real(*a, **k)

    svc._read_task_state_sync = _flaky  # type: ignore[method-assign]
    await svc.update_task_state(CONV, ORG, {"clarified_params": {"tone": "warm"}}, client=db)
    stored = db.tables["conversations"][0]["task_state"]
    assert stored["pending_task"]["params"]["provider"] == "gmail"
    assert stored["conversation_memory"] == {"recipient": "Stephanie"}
    assert stored["clarified_params"]["tone"] == "warm"


# --- F4: cancellation during embedding writes no memory --------------------------------


def _promote(db: FakeSupabaseDB, *, cancel_during_embedding: bool) -> None:
    from app.services.workspace_memory_service import promote_turn_memories

    turn = TurnCancellation()

    def _embed(*_a: Any, **_k: Any) -> list[float]:
        if cancel_during_embedding:
            turn.cancel("user_corrected")
        return [0.1, 0.2]

    with bound_turn_cancellation(turn), patch("app.rag.embedding.get_embedding", _embed):
        promote_turn_memories(
            db,
            org_id=ORG,
            user_id=USER,
            conversation_id=CONV,
            settings=SimpleNamespace(),
            memories=[{"category": "episodic", "content": "Stephanie prefers Gmail for updates"}],
        )


def _memory_writes(db: FakeSupabaseDB) -> list[Any]:
    return [w for w in db.writes if w[1] == "agent_memories"]


def test_a_turn_cancelled_during_embedding_writes_no_memory() -> None:
    db = _db()
    db.tables["agents"] = [{"id": "44444444-4444-4444-8444-444444444444", "org_id": ORG}]
    _promote(db, cancel_during_embedding=True)
    assert _memory_writes(db) == []


def test_a_live_turn_still_writes_its_memory() -> None:
    db = _db()
    db.tables["agents"] = [{"id": "44444444-4444-4444-8444-444444444444", "org_id": ORG}]
    _promote(db, cancel_during_embedding=False)
    assert _memory_writes(db), "control: an uncancelled turn writes the memory"


# --- F5: one answer per reply --------------------------------------------------------


def test_a_turn_inside_a_pending_task_does_not_stream_live_speech() -> None:
    """LIVE spoke the missing-details question, then handed the turn to the
    pending-task path, which asked it again: TTS got it twice."""
    from app.services.operator_task_intent import spoken_should_stream_live_deltas

    assert not spoken_should_stream_live_deltas(
        spoken_mode=True, message="Gmail.", task_state=_email_draft_state()
    )
    assert spoken_should_stream_live_deltas(spoken_mode=True, message="Gmail.", task_state={})
    assert spoken_should_stream_live_deltas(spoken_mode=True, message="hey, how's it going")


# --- Repair: "Sorry." and "No." keep the draft -------------------------------------------


def _draft_snapshot(status: str = "awaiting_params", missing: list[str] | None = None):
    from app.services.pending_reply_classifier import build_pending_snapshot

    state = _email_draft_state()
    state["pending_task"]["status"] = status
    state["pending_task"]["params"]["args"]["to"] = "Stephanie"
    if missing is not None:
        state["pending_task"]["params"]["missing"] = missing
    return build_pending_snapshot(state)


@pytest.mark.parametrize("utterance", ["Sorry.", "Sorry about that.", "Oh, my bad!", "No.", "Nope", "no, no"])
def test_sorry_and_a_bare_no_keep_the_draft_while_gathering_details(utterance: str) -> None:
    from app.services.pending_reply_classifier import classify_pending_reply_fast

    for status in ("awaiting_params", "collecting"):
        assert classify_pending_reply_fast(utterance, _draft_snapshot(status)) == "ambiguous"


def test_no_still_cancels_once_the_email_waits_for_approval() -> None:
    from app.services.pending_reply_classifier import classify_pending_reply_fast

    assert classify_pending_reply_fast("No.", _draft_snapshot("awaiting_confirm")) == "reject"
    assert classify_pending_reply_fast("Cancel it.", _draft_snapshot("awaiting_params")) == "reject"


def test_the_repair_reply_is_one_short_question_about_the_email() -> None:
    from app.services.pending_reply_classifier import format_ambiguous_clarify

    snap = _draft_snapshot(missing=["subject", "body"])
    assert format_ambiguous_clarify(snap, message="No.") == (
        "Okay. Should I drop the email to Stephanie, or change something?"
    )
    assert format_ambiguous_clarify(snap, message="Sorry.") == (
        "No problem. I've still got the email to Stephanie. What should the subject and message be?"
    )
    assert format_ambiguous_clarify(snap, message="hmm whatever") == (
        "I still need a few details for the email to Stephanie. What should the subject and message be?"
    )


def test_a_status_question_during_reconciliation_never_lets_the_write_run_again() -> None:
    state = _email_draft_state()
    state["pending_task"]["status"] = "awaiting_reconciliation"
    turn = recent_write_status_turn("Did it go through?", state)
    assert turn is not None and turn["stop_pipeline"] is True
    assert turn["provider_write"] is False


@pytest.mark.parametrize(
    "utterance",
    ["Send Stephanie the online order form.", "Email the team that the store is back online."],
)
def test_an_action_that_mentions_online_still_never_searches(utterance: str) -> None:
    assert auto_internet_research_blocked(utterance)
    assert not _thin_search(utterance)


def test_look_it_up_online_still_searches() -> None:
    assert _thin_search("Can you look up their pricing online?")


@pytest.mark.parametrize(
    "utterance",
    ["Did you make dinner?", "Did you book a flight for your trip?", "Did you send your mom a card?", "Did you cancel on them?"],
)
def test_everyday_did_you_questions_are_not_write_status_questions(utterance: str) -> None:
    assert recent_write_status_turn(utterance, _email_draft_state()) is None


@pytest.mark.parametrize("utterance", ["Did you send it?", "Did you send the email?", "Did you book the meeting?", "Did you do that?"])
def test_did_you_with_the_task_as_object_is_still_a_status_question(utterance: str) -> None:
    turn = recent_write_status_turn(utterance, _email_draft_state())
    assert turn is not None and turn["provider_write"] is False
