"""Composer failure-mode classification and isolated-org probe gating."""
from __future__ import annotations

from app.connectors.hubspot import HubSpotAPIError
from app.services.composer_failure_triggers import resolve_composer_failure_probe
from app.services.conversation_write_guard import DEFAULT_ISOLATED_CONVERSATION_TEST_ORG_ID
from app.services.tool_service import _classify_error, _handle_hubspot_error, _vendor_api_error
from app.services.tool_types import ToolAuthExpiredError, ToolPermissionDeniedError


class _QueryCanceledError(Exception):
    sqlstate = "57014"


def test_postgres_query_canceled_is_statement_timeout():
    err = _classify_error(_QueryCanceledError("canceling statement due to statement timeout"))
    assert err.code == "statement_timeout"


def test_statement_timeout_is_not_connector_timeout():
    err = _classify_error(RuntimeError("SQLSTATE 57014 statement timeout"))
    assert err.code == "statement_timeout"


def test_http_timeout_stays_connector_timeout():
    import httpx

    err = _classify_error(httpx.ReadTimeout("read timed out"))
    assert err.code == "connector_timeout"


def test_hubspot_403_is_permission_denied_not_auth_expired():
    err = _handle_hubspot_error(HubSpotAPIError("HubSpot API 403: /x", status_code=403))
    assert isinstance(err, ToolPermissionDeniedError)
    assert err.code == "permission_denied"


def test_hubspot_401_stays_auth_expired():
    err = _handle_hubspot_error(HubSpotAPIError("401", status_code=401))
    assert isinstance(err, ToolAuthExpiredError)


def test_vendor_403_is_permission_denied():
    class _Ads(Exception):
        def __init__(self):
            super().__init__("Google Ads 403 PERMISSION_DENIED")
            self.status_code = 403

    err = _vendor_api_error(_Ads(), "google_ads")
    assert isinstance(err, ToolPermissionDeniedError)
    assert err.code == "permission_denied"


def test_probe_header_is_isolated_org_only():
    assert (
        resolve_composer_failure_probe(
            org_id=DEFAULT_ISOLATED_CONVERSATION_TEST_ORG_ID,
            header_value="statement_timeout",
        )
        == "statement_timeout"
    )
    assert (
        resolve_composer_failure_probe(
            org_id="cbbf993b-b22f-41ce-964b-1fc25e0dd9ea",
            header_value="statement_timeout",
        )
        is None
    )
    assert (
        resolve_composer_failure_probe(
            org_id=DEFAULT_ISOLATED_CONVERSATION_TEST_ORG_ID,
            header_value="not-a-probe",
        )
        is None
    )
