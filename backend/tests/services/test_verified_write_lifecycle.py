from __future__ import annotations

from app.services.write_success_verification import _verification_terminal_status


def test_only_positive_source_proof_completes_write() -> None:
    assert (
        _verification_terminal_status(
            verified=True,
            effect="created",
            detail="follow_up_entity_get_confirmed",
        )
        == "completed"
    )


def test_explicit_source_mismatch_fails_write() -> None:
    assert (
        _verification_terminal_status(
            verified=False,
            effect="unknown",
            detail="field_value_mismatch",
        )
        == "failed"
    )
    assert (
        _verification_terminal_status(
            verified=False,
            effect="unknown",
            detail="entity_id_mismatch:999",
        )
        == "failed"
    )


def test_unprovable_source_state_is_inconclusive_not_success() -> None:
    assert (
        _verification_terminal_status(
            verified=False,
            effect="accepted_async",
            detail="follow_up_read_failed",
        )
        == "verification_inconclusive"
    )
