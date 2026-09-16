from app.services.chat_interrupt_resume_service import (
    is_continue_utterance,
    load_interrupted_turn,
    merge_history_with_interrupt,
    reset_local_interrupts_for_tests,
    resume_instruction,
    sanitize_interrupt_extra,
    store_interrupted_turn,
)


def setup_function() -> None:
    reset_local_interrupts_for_tests()


def test_continue_utterances() -> None:
    assert is_continue_utterance("Continue")
    assert is_continue_utterance("keep going.")
    assert not is_continue_utterance("continue the apollo list with extra filters")


def test_store_and_merge_partial(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.services.chat_interrupt_resume_service.get_redis_client", lambda _s=None: None
    )
    store_interrupted_turn(
        "org-1",
        "conv-1",
        user_text="list apollo contacts",
        assistant_text="Here are the first two…",
    )
    loaded = load_interrupted_turn("org-1", "conv-1")
    assert loaded is not None
    merged = merge_history_with_interrupt([], loaded)
    assert merged[0]["content"] == "list apollo contacts"
    assert merged[1]["content"] == "Here are the first two…"
    again = merge_history_with_interrupt(merged, loaded)
    assert again == merged


def test_resume_instruction_uses_partial(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.services.chat_interrupt_resume_service.get_redis_client", lambda _s=None: None
    )
    store_interrupted_turn(
        "org-1",
        "conv-1",
        user_text="draft the email",
        assistant_text="Subject: Hello",
    )
    interrupt = load_interrupted_turn("org-1", "conv-1")
    text = resume_instruction(interrupt, "Continue")
    assert "do not restart" in text.lower()
    assert "draft the email" in text
    assert resume_instruction(interrupt, "add a P.S.") == "add a P.S."


def test_store_extra_hydrates_resume_instruction(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.services.chat_interrupt_resume_service.get_redis_client", lambda _s=None: None
    )
    store_interrupted_turn(
        "org-1",
        "conv-1",
        user_text="create a hubspot contact",
        assistant_text="Stopped.",
        extra={
            "tool_names": ["hubspot.contacts.search"],
            "pending_task": {"action": "hubspot.contacts.create", "label": "Create contact"},
            "parameter_ledger": {"slots": {"email": {"value": "a@x.com"}}},
        },
    )
    interrupt = load_interrupted_turn("org-1", "conv-1")
    assert interrupt is not None
    assert interrupt["extra"]["tool_names"] == ["hubspot.contacts.search"]
    text = resume_instruction(interrupt, "Continue")
    assert "hubspot.contacts.search" in text
    assert "a@x.com" in text


def test_sanitize_interrupt_extra_drops_noise() -> None:
    extra = sanitize_interrupt_extra(
        {
            "tool_names": ["gmail.messages.send", ""],
            "pending_task": {"label": "Send", "args": {"to": "x", "body": "hi"}},
            "ignored": object(),
        }
    )
    assert extra["tool_names"] == ["gmail.messages.send"]
    assert extra["pending_task"]["arg_keys"] == ["to", "body"]
