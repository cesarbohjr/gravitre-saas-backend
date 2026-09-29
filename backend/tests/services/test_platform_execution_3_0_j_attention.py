"""3.0-J ranked safe-READ notices — no auto high-risk WRITE."""
from __future__ import annotations

from app.services.proactive_business_operator import (
    ATTENTION_AXES,
    format_ranked_read_notices,
    rank_safe_read_notices,
)


def test_rank_prefers_auth_over_metric_and_caps_quiet_notices() -> None:
    recs = rank_safe_read_notices(
        [
            {
                "id": "metric",
                "kind": "metric_moved",
                "connector": "hubspot",
                "evidence": ["deals_down"],
                "recommendation": "Review pipeline movement against live HubSpot READ.",
            },
            {
                "id": "gsc-expired",
                "kind": "token_expired",
                "connector": "google_search_console",
                "evidence": ["token_expired"],
            },
            {
                "id": "ga-pending",
                "kind": "pending_auth",
                "connector": "google_analytics",
                "evidence": ["pending_auth"],
            },
            {
                "id": "noise",
                "kind": "other",
                "connector": "zendesk",
                "evidence": ["note"],
                "notify_low": True,
            },
        ],
        limit=3,
    )
    assert len(recs) == 3
    assert recs[0].rank_score >= recs[1].rank_score >= recs[2].rank_score
    assert recs[0].signal_id in {"gsc-expired", "ga-pending"}
    assert all(rec.write_allowed is False for rec in recs)
    assert all(rec.investigation == "safe_read" for rec in recs)
    assert all(set(rec.axes or {}) == set(ATTENTION_AXES) for rec in recs)


def test_high_risk_write_signals_are_dropped() -> None:
    recs = rank_safe_read_notices(
        [
            {
                "id": "send",
                "kind": "send_email",
                "connector": "gmail",
                "evidence": ["draft ready"],
                "write_requested": True,
            },
            {
                "id": "auth",
                "kind": "pending_auth",
                "connector": "google_analytics",
                "evidence": ["pending_auth"],
            },
        ]
    )
    assert [rec.signal_id for rec in recs] == ["auth"]
    assert recs[0].write_allowed is False


def test_attention_intent_does_not_auto_write(monkeypatch) -> None:
    from app.services.proactive_business_operator import is_attention_intent, try_ranked_attention_turn

    monkeypatch.setattr(
        "app.services.website_source_status.website_source_readiness",
        lambda *args, **kwargs: {
            "google_analytics": {
                "present": True,
                "executable": False,
                "blocking_reason": "pending_auth",
            }
        },
    )
    assert is_attention_intent("what needs my attention") is True
    turn = try_ranked_attention_turn(
        message="what needs my attention",
        org_id="org",
        client=None,
        settings=None,
        task_state={},
    )
    assert turn is not None
    assert turn["write_allowed"] is False
    assert turn["provider_write"] is False
    assert "will not write" in turn["message"].lower()


def test_invented_enable_copy_is_stripped() -> None:
    recs = rank_safe_read_notices(
        [
            {
                "id": "sku",
                "kind": "threshold",
                "connector": "hubspot",
                "evidence": ["threshold"],
                "recommendation": "Enable Pipeline Plus for $49.",
            }
        ]
    )
    assert recs
    assert "Enable" not in recs[0].recommendation
    assert "$49" not in recs[0].recommendation
    text = format_ranked_read_notices(recs)
    assert "I will not write anything" in text
    assert "Enable" not in text
