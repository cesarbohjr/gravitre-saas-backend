from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from app.connectors.segment_api import (
    SegmentAPIError,
    identify,
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


def test_identify_requires_user_id():
    with pytest.raises(SegmentAPIError):
        identify("wk", user_id="")


def test_track_posts_event():
    with patch("app.connectors.segment_api._request", return_value={"success": True}) as req:
        track("wk", user_id="u1", event="Webinar Attended", properties={"plan": "pro"})
    body = req.call_args.kwargs["json_body"]
    assert body["event"] == "Webinar Attended"
    assert body["userId"] == "u1"
