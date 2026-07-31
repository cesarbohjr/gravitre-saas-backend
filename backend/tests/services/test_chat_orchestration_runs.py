"""Unit tests for chat orchestration run URL resolution and failure finalize bridge."""

from unittest.mock import MagicMock, patch

from app.services.chat_orchestration_runs import (
    finalize_orchestration_run,
    orchestration_run_fully_completed,
    resolve_orchestration_result_url,
)


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
    assert url == "/ai?c=conv-9"


def test_orchestration_run_fully_completed_rejects_partial_failure():
    assert not orchestration_run_fully_completed(
        [
            {"success": True, "label": "A"},
            {"success": False, "label": "B"},
        ]
    )


def test_orchestration_run_fully_completed_allows_skips_with_successes():
    assert orchestration_run_fully_completed(
        [
            {"success": True, "label": "A"},
            {"success": False, "skipped": True, "label": "B"},
        ]
    )


def test_orchestration_run_fully_completed_rejects_all_skipped():
    assert not orchestration_run_fully_completed(
        [{"success": False, "skipped": True, "label": "A"}]
    )


def test_finalize_orchestration_failure_orphan_emits_without_run():
    client = MagicMock()
    with (
        patch("app.services.chat_orchestration_runs.finalize_execution_outcome") as finalize,
        patch("app.services.chat_orchestration_runs.finalize_orchestration_run") as finalize_run,
    ):
        from app.services.chat_orchestration_runs import finalize_orchestration_failure

        finalize_orchestration_failure(
            client,
            org_id="org-1",
            user_id="user-1",
            conversation_id="conv-1",
            summary="Step failed",
            run_id=None,
            step_label="Post to Slack",
            integration="slack",
            invoke_action="slack.post_message",
        )
    finalize_run.assert_not_called()
    finalize.assert_called_once()
    assert finalize.call_args.kwargs["status"] == "failed"
    assert finalize.call_args.kwargs["persist_run"] is False
    assert finalize.call_args.kwargs["metadata"]["conversation_id"] == "conv-1"
    assert finalize.call_args.kwargs["metadata"]["invoke_action"] == "slack.post_message"


def test_finalize_orchestration_failure_with_run_delegates_to_run_finalize():
    client = MagicMock()
    with patch("app.services.chat_orchestration_runs.finalize_orchestration_run") as finalize_run:
        from app.services.chat_orchestration_runs import finalize_orchestration_failure

        finalize_orchestration_failure(
            client,
            org_id="org-1",
            user_id="user-1",
            conversation_id="conv-1",
            summary="Step failed",
            run_id="run-9",
        )
    finalize_run.assert_called_once()
    assert finalize_run.call_args.kwargs["run_id"] == "run-9"
    assert finalize_run.call_args.kwargs["success"] is False


def test_finalize_orchestration_run_failure_emits_audit_and_notification():
    client = MagicMock()
    with (
        patch("app.workflows.repository.update_run") as update_run,
        patch("app.workflows.repository.emit_execute_failed") as emit_failed,
        patch("app.services.notification_emitter.emit_notification") as emit_note,
    ):
        finalize_orchestration_run(
            client,
            org_id="org-1",
            run_id="run-9",
            success=False,
            summary="Step X failed",
            user_id="user-1",
        )
    update_run.assert_called_once()
    assert update_run.call_args.kwargs["status"] == "failed"
    emit_failed.assert_called_once()
    failed_args = emit_failed.call_args[0]
    assert failed_args[:4] == (client, "org-1", "user-1", "run-9")
    assert "Step X failed" in str(failed_args[4])
    emit_note.assert_called_once()
    assert emit_note.call_args.kwargs["event_type"] == "run_failed"
    assert emit_note.call_args.kwargs["entity_ref"]["entity_id"] == "run-9"


def test_finalize_orchestration_run_success_skips_failure_emit():
    client = MagicMock()
    with (
        patch("app.workflows.repository.update_run") as update_run,
        patch("app.workflows.repository.emit_execute_failed") as emit_failed,
        patch("app.workflows.repository.emit_execute_completed") as emit_completed,
        patch("app.services.notification_emitter.emit_notification") as emit_note,
    ):
        finalize_orchestration_run(
            client,
            org_id="org-1",
            run_id="run-9",
            success=True,
            summary="ok",
            user_id="user-1",
        )
    update_run.assert_called_once()
    assert update_run.call_args.kwargs["status"] == "completed"
    emit_failed.assert_not_called()
    emit_completed.assert_called_once()
    emit_note.assert_called_once()
    assert emit_note.call_args.kwargs["event_type"] == "run_completed"
