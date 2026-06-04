from __future__ import annotations

from unittest.mock import MagicMock, patch

from app.connectors.pagerduty import (
    PagerDutyAPIError,
    acknowledge_incident,
    add_incident_note,
    escalate_incident,
)


def test_acknowledge_incident_puts_status():
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.text = '{"incidents":[]}'
    mock_response.json.return_value = {"incidents": []}
    with patch("app.connectors.pagerduty.httpx.Client") as client_cls:
        client_cls.return_value.__enter__.return_value.request.return_value = mock_response
        acknowledge_incident("token", "P123", from_email="ops@example.com")
    req = client_cls.return_value.__enter__.return_value.request.call_args
    assert req.kwargs["json"]["incidents"][0]["status"] == "acknowledged"
    assert req.kwargs["headers"]["From"] == "ops@example.com"


def test_add_incident_note_posts_content():
    mock_response = MagicMock()
    mock_response.status_code = 201
    mock_response.text = '{"note":{"id":"N1"}}'
    mock_response.json.return_value = {"note": {"id": "N1"}}
    with patch("app.connectors.pagerduty.httpx.Client") as client_cls:
        client_cls.return_value.__enter__.return_value.request.return_value = mock_response
        add_incident_note("token", "P123", "Investigating", from_email="ops@example.com")
    assert "/incidents/P123/notes" in client_cls.return_value.__enter__.return_value.request.call_args.args[1]


def test_escalate_increments_level():
    get_resp = MagicMock()
    get_resp.status_code = 200
    get_resp.text = '{"incident":{"escalation_level":1}}'
    get_resp.json.return_value = {"incident": {"escalation_level": 1}}
    put_resp = MagicMock()
    put_resp.status_code = 200
    put_resp.text = '{"incidents":[]}'
    put_resp.json.return_value = {"incidents": []}
    with patch("app.connectors.pagerduty.httpx.Client") as client_cls:
        client_cls.return_value.__enter__.return_value.request.side_effect = [get_resp, put_resp]
        escalate_incident("token", "P123", from_email="ops@example.com")
    put_call = client_cls.return_value.__enter__.return_value.request.call_args_list[-1]
    assert put_call.kwargs["json"]["incidents"][0]["escalation_level"] == 2


def test_api_maps_401():
    mock_response = MagicMock()
    mock_response.status_code = 401
    mock_response.text = "Unauthorized"
    mock_response.json.side_effect = ValueError()
    with patch("app.connectors.pagerduty.httpx.Client") as client_cls:
        client_cls.return_value.__enter__.return_value.request.return_value = mock_response
        try:
            acknowledge_incident("bad", "P1", from_email="a@b.com")
        except PagerDutyAPIError as exc:
            assert exc.status_code == 401
        else:
            raise AssertionError("expected PagerDutyAPIError")
