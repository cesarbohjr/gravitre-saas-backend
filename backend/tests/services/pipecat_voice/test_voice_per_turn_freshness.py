"""Voice reads the conversation and the system prompt per turn, like text does.

Before: Talk froze both at socket start — text typed in the panel while Talk was
open never reached the voice brain, and connected apps, org context and agent
memory stayed as they were when the socket opened.
"""
from __future__ import annotations

from types import SimpleNamespace

from app.services.pipecat_voice import cognitive_llm
from app.services.pipecat_voice.cognitive_llm import GravitreCognitiveLLMService
from app.services.pipecat_voice.llm_context_utils import merge_durable_and_socket_history

SEED = [
    {"role": "user", "content": "how are deals looking"},
    {"role": "assistant", "content": "Three deals are in negotiation."},
]


def _live(role: str, content: str) -> dict:
    return {"role": role, "content": content, "_live": True}


def test_no_live_rows_keeps_the_old_merge() -> None:
    socket = [{"role": "user", "content": "and the biggest one?"}]
    assert merge_durable_and_socket_history(SEED, socket) == SEED + socket


def test_text_typed_while_talk_is_open_reaches_the_voice_turn() -> None:
    durable = [*SEED, _live("user", "Draft an email to Dana"), _live("assistant", "Drafted. Want me to send it?")]
    socket = [{"role": "user", "content": "yes send it"}]
    merged = merge_durable_and_socket_history(durable, socket)
    assert [m["content"] for m in merged] == [
        "how are deals looking",
        "Three deals are in negotiation.",
        "Draft an email to Dana",
        "Drafted. Want me to send it?",
        "yes send it",
    ]
    assert all("_live" not in m for m in merged)


def test_persisted_socket_turns_are_not_repeated() -> None:
    durable = [*SEED, _live("user", "who owns Acme"), _live("assistant", "Maria owns Acme, and she's")]
    socket = [
        {"role": "user", "content": "who owns Acme"},
        {"role": "assistant", "content": "Maria owns Acme."},
        {"role": "user", "content": "email her"},
    ]
    merged = merge_durable_and_socket_history(durable, socket)
    assert [m["content"] for m in merged][-3:] == ["who owns Acme", "Maria owns Acme, and she's", "email her"]
    assert sum(1 for m in merged if m["content"] == "who owns Acme") == 1


def test_seed_rows_never_swallow_a_repeated_utterance() -> None:
    socket = [{"role": "user", "content": "how are deals looking"}]
    merged = merge_durable_and_socket_history(SEED, socket)
    assert sum(1 for m in merged if m["content"] == "how are deals looking") == 2


def _service(agent_id: str | None = None) -> GravitreCognitiveLLMService:
    return GravitreCognitiveLLMService(
        app_settings=SimpleNamespace(), org_id="o1", user_id="u1", agent={"id": agent_id} if agent_id else None
    )


def test_system_prompt_is_rebuilt_when_stale(monkeypatch) -> None:
    svc = _service()
    assert svc._base_prompt_stale("hi", agent_id=None)
    svc._base_prompt = "prompt"
    svc._base_prompt_built_at = cognitive_llm.time.monotonic()
    svc._base_prompt_query = "hi"
    assert not svc._base_prompt_stale("what's next", agent_id=None)
    svc._base_prompt_built_at -= cognitive_llm.BASE_PROMPT_MAX_AGE_S + 1
    assert svc._base_prompt_stale("what's next", agent_id=None)


def test_agent_prompt_is_rebuilt_for_each_new_question() -> None:
    svc = _service(agent_id="a1")
    svc._base_prompt = "prompt"
    svc._base_prompt_built_at = cognitive_llm.time.monotonic()
    svc._base_prompt_query = "hi"
    assert not svc._base_prompt_stale("hi", agent_id="a1")
    assert svc._base_prompt_stale("what did Acme say last week", agent_id="a1")
