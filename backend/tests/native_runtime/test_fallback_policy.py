from app.services.native_runtime.fallback_policy import (
    RecoveryDecision, RecoveryEvidence, decide_recovery,
)


def evidence(**overrides):
    fields = dict(
        failure_kind="browser_crash",
        job_active=True,
        cancellation_requested=False,
        authorization_current=True,
        lease_fenced=True,
        checkpoint_durable=True,
        checkpoint_before_effect=True,
        pending_action=False,
        effect_outcome_uncertain=False,
    )
    fields.update(overrides)
    return RecoveryEvidence(**fields)


def test_safe_checkpoint_requires_all_fences():
    assert decide_recovery(evidence()) is RecoveryDecision.SAFE_CHECKPOINT


def test_no_automatic_replay_after_possible_effect():
    for change in ({"effect_outcome_uncertain": True},
                   {"pending_action": True},
                   {"checkpoint_before_effect": False},
                   {"checkpoint_durable": False}):
        assert decide_recovery(evidence(**change)) is RecoveryDecision.RECONCILE


def test_revocation_cancellation_and_unfenced_worker_stop():
    for change in ({"cancellation_requested": True},
                   {"authorization_current": False},
                   {"job_active": False},
                   {"lease_fenced": False},
                   {"failure_kind": "approval_denied"}):
        assert decide_recovery(evidence(**change)) is RecoveryDecision.STOP
