from __future__ import annotations

from pathlib import Path

SOURCE = Path("backend/app/services/conversational_execution_service.py")


def _source() -> str:
    return SOURCE.read_text(encoding="utf-8")


def test_success_result_has_separate_outcome_verification_bit() -> None:
    text = _source()
    assert "outcome_verified: bool = False" in text


def test_workflow_start_is_not_described_as_done() -> None:
    text = _source()
    assert 'I started **{execution.title}**. It is not complete until the run outcome is verified.' in text
    assert 'Done — I started **{execution.title}**.' not in text


def test_agent_result_is_not_automatically_requested_outcome_completion() -> None:
    text = _source()
    assert "returned a result. I have not marked the requested outcome complete without verification." in text


def test_success_only_finalizes_completed_when_verified() -> None:
    text = _source()
    assert 'status="completed" if (result.success and result.outcome_verified)' in text
    assert '"status": "executed" if result.outcome_verified else "verifying"' in text


def test_unverified_success_does_not_feed_learning_as_outcome() -> None:
    text = _source()
    assert "if result.outcome_verified or not result.success:" in text
    assert "await self._record_learning_outcome" in text
