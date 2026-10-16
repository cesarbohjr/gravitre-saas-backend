from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from app.connectors.segment_api import (
    SegmentAPIError,
    identify,
    group,
    resolve_segment_write_key,
    track,
)


def test_resolve_segment_write_key_from_secret():
    settings = SimpleNamespace(connector_secrets_encryption_key="a" * 32, encryption_key="")
    client = MagicMock()
    client.table.return_value.select.return_value.eq.return_value.eq.return_value.limit.return_value.execute.return_value = MagicMock(
        data=[{"id": "conn-1", "org_id": "org-1", "type": "segment", "config": {}, "api_key_encrypted": None}]
    )
    with patch("app.connectors.segment_api.get_decrypted_secret", return_value="wk_test"):
        key = resolve_segment_write_key(client, "org-1", "conn-1", settings)
    assert key == "wk_test"


@pytest.mark.parametrize("user_id", ["", "   ", None])
def test_identify_requires_user_id_without_provider_request(user_id):
    with patch("app.connectors.segment_api._request") as request:
        with pytest.raises(SegmentAPIError, match="user_id required"):
            identify("synthetic-test-key", user_id=user_id)
    request.assert_not_called()


@pytest.mark.parametrize("user_id,group_id", [("", "group"), ("user", ""), ("user", "  ")])
def test_group_requires_identities_without_provider_request(user_id, group_id):
    with patch("app.connectors.segment_api._request") as request:
        with pytest.raises(SegmentAPIError, match="required"):
            group("synthetic-test-key", user_id=user_id, group_id=group_id)
    request.assert_not_called()


def test_track_posts_event():
    with patch("app.connectors.segment_api._request", return_value={"success": True}) as req:
        track("wk", user_id="u1", event="Webinar Attended", properties={"plan": "pro"})
    body = req.call_args.kwargs["json_body"]
    assert body["event"] == "Webinar Attended"
    assert body["userId"] == "u1"


def test_identify_preserves_valid_identifier_and_payload():
    with patch("app.connectors.segment_api._request", return_value={"success": True}) as request:
        identify("synthetic-test-key", user_id="User-1", traits={"plan": "test"})
    request.assert_called_once_with("POST", "/identify", "synthetic-test-key", json_body={"userId": "User-1", "traits": {"plan": "test"}})


def test_group_preserves_valid_identifiers_and_payload():
    with patch("app.connectors.segment_api._request", return_value={"success": True}) as request:
        group("synthetic-test-key", user_id="User-1", group_id="Group-1")
    request.assert_called_once_with("POST", "/group", "synthetic-test-key", json_body={"userId": "User-1", "groupId": "Group-1"})
