"""Unit tests for chat orchestration run URL resolution."""

from app.services.chat_orchestration_runs import resolve_orchestration_result_url


def test_prefers_run_detail_over_vendor_url():
    url = resolve_orchestration_result_url(
        run_id="run-1",
        step_results=[{"url": "https://app.hubspot.com/contacts/1"}],
        conversation_id="conv-1",
    )
    assert url == "/runs/run-1"


def test_falls_back_to_run_when_step_urls_are_ai():
    url = resolve_orchestration_result_url(
        run_id="run-2",
        step_results=[{"url": "/ai"}, {"url": "/connectors"}],
        conversation_id="conv-1",
    )
    assert url == "/runs/run-2"


def test_conversation_fallback_without_run():
    url = resolve_orchestration_result_url(
        run_id=None,
        step_results=[],
        conversation_id="conv-9",
    )
    assert url == "/ai?conversation=conv-9"
