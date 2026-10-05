"""P0 regression coverage for durable text <-> Pipecat voice continuity."""
from __future__ import annotations

from app.services.pipecat_voice.cognitive_llm import GravitreCognitiveLLMService


def _service() -> GravitreCognitiveLLMService:
    return GravitreCognitiveLLMService(
        app_settings=object(),
        org_id="00000000-0000-4000-8000-000000000001",
        user_id="00000000-0000-4000-8000-000000000002",
        conversation_id="00000000-0000-4000-8000-000000000003",
    )


def test_durable_history_precedes_new_socket_history() -> None:
    durable = [
        {"role": "user", "content": "Budget is $10k and no paid social."},
        {"role": "assistant", "content": "Understood."},
    ]
    socket = [
        {"role": "user", "content": "Actually forget the paid-social constraint."},
        {"role": "assistant", "content": "Understood; the $10k budget remains."},
    ]

    merged = _service()._merge_durable_and_socket_history(durable, socket)

    assert merged == durable + socket
    assert merged[0]["content"].startswith("Budget is $10k")
    assert merged[-1]["content"].endswith("$10k budget remains.")


def test_socket_history_is_appended_without_collapsing_repeated_turns() -> None:
    durable = [
        {"role": "user", "content": "Use the second option."},
        {"role": "assistant", "content": "We'll use option two."},
    ]
    # Pipecat's context is created empty in pipeline.py; it contains only live
    # socket turns. A repeated utterance is legitimate conversation, not overlap.
    socket = [
        {"role": "user", "content": "Use the second option."},
        {"role": "assistant", "content": "We'll use option two."},
        {"role": "user", "content": "Continue from there."},
    ]

    merged = _service()._merge_durable_and_socket_history(durable, socket)

    assert merged == durable + socket
    assert sum(m["content"] == "Use the second option." for m in merged) == 2


def test_cross_modal_history_is_capped_without_losing_recent_context() -> None:
    durable = [
        {"role": "user" if i % 2 == 0 else "assistant", "content": f"turn-{i}"}
        for i in range(60)
    ]
    socket = [{"role": "user", "content": "What did we just decide?"}]

    merged = _service()._merge_durable_and_socket_history(durable, socket)

    assert len(merged) == 48
    assert merged[-1]["content"] == "What did we just decide?"
    assert merged[-2]["content"] == "turn-59"
