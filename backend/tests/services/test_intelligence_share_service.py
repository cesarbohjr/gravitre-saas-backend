"""Sharing a finding: only internal destinations, a Gravitre link, and an audit row."""
from __future__ import annotations

from typing import Any
from unittest.mock import patch

import pytest

from app.services import intelligence_share_service as share


class _Result:
    def __init__(self, data: list[dict[str, Any]]) -> None:
        self.data = data


class _Query:
    def __init__(self, rows: list[dict[str, Any]]) -> None:
        self.rows = rows

    def select(self, *_a: Any) -> "_Query":
        return self

    def eq(self, key: str, value: Any) -> "_Query":
        return _Query([r for r in self.rows if r.get(key) == value])

    def in_(self, key: str, values: list[Any]) -> "_Query":
        return _Query([r for r in self.rows if r.get(key) in values])

    def limit(self, *_a: Any) -> "_Query":
        return self

    def execute(self) -> _Result:
        return _Result(self.rows)


class _Db:
    tables = {
        "organization_members": [
            {"org_id": "org-1", "user_id": "u1", "role": "owner"},
            {"org_id": "org-1", "user_id": "u2", "role": "member"},
        ],
        "users": [
            {"auth_user_id": "u1", "email": "dana@x.co", "full_name": "Dana W."},
            {"auth_user_id": "u2", "email": "jordan@x.co", "full_name": "Jordan P."},
            {"auth_user_id": "u9", "email": "out@y.co", "full_name": "Outsider"},
        ],
    }

    def table(self, name: str) -> _Query:
        return _Query(self.tables.get(name, []))


class _Settings:
    disable_connectors = False
    notification_email_enabled = True
    public_app_url = "https://gravitre.app"


def _share(**kw: Any) -> dict[str, Any]:
    args = dict(
        user_id="u1",
        sender_name="Dana W.",
        app="slack",
        channel_id="C0123456",
        person_id=None,
        title="Acme may not renew",
        summary="Usage dropped 40% in 30 days.",
        note="Can someone check in before Friday?",
        path="/intelligence/predictive",
        now=0.0,
    )
    args.update(kw)
    return share.share_finding(_Db(), "org-1", _Settings(), **args)  # type: ignore[arg-type]


def test_slack_channel_share_posts_link_and_audits():
    share._recent.clear()
    with patch.object(share, "_slack_token", return_value="xoxb"), patch(
        "app.connectors.slack.send_slack_message", return_value={"ok": True, "ts": "1.2", "channel": "C0123456"}
    ) as send, patch("app.workflows.audit.write_audit_event") as audit:
        out = _share()
    text = send.call_args.args[2]
    assert "Can someone check in" in text and "https://gravitre.app/intelligence/predictive" in text
    assert out["url"] == "https://app.slack.com/archives/C0123456/p12"
    assert audit.call_args.kwargs["action"] == share.AUDIT_ACTION


def test_email_goes_only_to_people_in_the_org():
    share._recent.clear()
    with pytest.raises(share.ShareInputError):
        _share(app="email", channel_id=None, person_id="u9")
    with patch.object(share, "email_available", return_value=True), patch.object(share, "_send_email") as send, patch(
        "app.workflows.audit.write_audit_event"
    ):
        out = _share(app="email", channel_id=None, person_id="u2")
    assert send.call_args.kwargs["to_addr"] == "jordan@x.co"
    assert out["destination"] == "Jordan P."


def test_rejects_outside_links_and_bad_destinations():
    share._recent.clear()
    for bad in ("https://evil.example", "//evil.example/x", "javascript:alert(1)"):
        with pytest.raises(share.ShareInputError):
            _share(path=bad)
    with pytest.raises(share.ShareInputError):
        _share(channel_id="general")
    with pytest.raises(share.ShareInputError):
        _share(channel_id="C0123456", person_id="u2")


def test_slack_not_in_channel_says_how_to_fix():
    share._recent.clear()
    with patch.object(share, "_slack_token", return_value="xoxb"), patch(
        "app.connectors.slack.send_slack_message", side_effect=ValueError("not_in_channel")
    ), patch("app.connectors.slack.join_conversation", side_effect=ValueError("method_not_allowed_for_channel_type")):
        with pytest.raises(share.ShareDeliveryError, match="Invite the Gravitre app"):
            _share()


def test_options_hide_unconnected_apps_and_the_sender():
    with patch.object(share, "_slack_token", return_value=None), patch.object(share, "email_available", return_value=True):
        out = share.share_options(_Db(), "org-1", _Settings(), user_id="u1")  # type: ignore[arg-type]
    assert [a["id"] for a in out["apps"]] == ["email"]
    assert out["unavailable"] == ["Slack"]
    assert [p["name"] for p in out["apps"][0]["people"]] == ["Jordan P."]
