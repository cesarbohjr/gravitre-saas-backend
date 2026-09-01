"""A transport failure must not be reported to the user as bad parameters.

Live production run at 77c54964 recorded:

    tool.invoke.failed  hubspot.deals.list
    error      = "[Errno 11] Resource temporarily unavailable"
    error_code = "validation_error"

which rendered as "Invalid parameters for this Hubspot action (List deals via
hubspot API). Check required fields and try again." — advice that cannot help,
for a fault the caller did not cause and a retry would likely clear.

`_handle_hubspot_error` mapped everything that was not 429/401/403 to
ToolValidationError, so timeouts and 5xx-after-retry were mislabelled the same
way. These tests pin the classification per failure kind.
"""
from __future__ import annotations

import pytest

from app.connectors.hubspot import HubSpotAPIError
from app.services.tool_service import _handle_hubspot_error
from app.services.tool_types import (
    ToolAuthExpiredError,
    ToolError,
    ToolRateLimitedError,
    ToolValidationError,
)


def test_transport_failure_is_not_a_validation_error():
    """The exact production case: errno 11 with no HTTP status at all."""
    err = _handle_hubspot_error(HubSpotAPIError("[Errno 11] Resource temporarily unavailable"))
    assert not isinstance(err, ToolValidationError)
    assert err.code != "validation_error"
    assert err.code == "tool_error"


def test_timeout_is_reported_as_a_timeout():
    err = _handle_hubspot_error(HubSpotAPIError("HubSpot API timeout"))
    assert not isinstance(err, ToolValidationError)
    assert err.code == "connector_timeout"


@pytest.mark.parametrize("status", [500, 502, 503, 504])
def test_upstream_server_errors_are_not_the_callers_parameters(status):
    err = _handle_hubspot_error(HubSpotAPIError(f"HubSpot API {status}", status_code=status))
    assert not isinstance(err, ToolValidationError)
    assert err.code == "tool_error"


@pytest.mark.parametrize("status", [400, 404, 409, 422])
def test_genuine_client_errors_are_still_validation_errors(status):
    err = _handle_hubspot_error(HubSpotAPIError(f"HubSpot API {status}", status_code=status))
    assert isinstance(err, ToolValidationError)
    assert err.code == "validation_error"


def test_rate_limit_and_auth_classification_is_unchanged():
    assert isinstance(
        _handle_hubspot_error(HubSpotAPIError("429", status_code=429)), ToolRateLimitedError
    )
    for status in (401, 403):
        assert isinstance(
            _handle_hubspot_error(HubSpotAPIError(str(status), status_code=status)),
            ToolAuthExpiredError,
        )


def test_every_branch_returns_a_tool_error():
    for exc in (
        HubSpotAPIError("x", status_code=429),
        HubSpotAPIError("x", status_code=401),
        HubSpotAPIError("x", status_code=400),
        HubSpotAPIError("x", status_code=500),
        HubSpotAPIError("HubSpot API timeout"),
        HubSpotAPIError("[Errno 11] Resource temporarily unavailable"),
    ):
        assert isinstance(_handle_hubspot_error(exc), ToolError)


# --- _classify_error: the real chokepoint -------------------------------
#
# Fixing _handle_hubspot_error was one layer too low. The live re-run at
# dd218e89 still recorded error_code="validation_error" for
# "<ConnectionTerminated error_code:1, last_stream_id:107>" on
# hubspot.deals.search, because that exception never becomes a HubSpotAPIError —
# httpx.RemoteProtocolError is raised outside _request's wrapping (the OAuth
# refresh call is one such path) and lands in the generic _classify_error, whose
# fallthrough was also ToolValidationError. That function is connector-wide, so
# every vendor had this bug, not just HubSpot.


def _classify(exc: Exception):
    from app.services.tool_service import _classify_error

    return _classify_error(exc)


def test_the_production_connection_terminated_is_not_a_validation_error():
    import httpx

    err = _classify(
        httpx.RemoteProtocolError(
            "<ConnectionTerminated error_code:1, last_stream_id:107, additional_data:None>"
        )
    )
    assert err.code == "tool_error"
    assert not isinstance(err, ToolValidationError)


def test_the_production_errno_11_is_not_a_validation_error():
    err = _classify(OSError(11, "Resource temporarily unavailable"))
    assert err.code == "tool_error"
    assert not isinstance(err, ToolValidationError)


@pytest.mark.parametrize(
    "exc_name,message",
    [
        ("ConnectTimeout", "timed out"),
        ("ReadTimeout", "read timed out"),
        ("WriteTimeout", "write timed out"),
        ("PoolTimeout", "pool timeout"),
    ],
)
def test_transport_timeouts_get_the_timeout_code(exc_name, message):
    import httpx

    err = _classify(getattr(httpx, exc_name)(message))
    assert err.code == "connector_timeout"


@pytest.mark.parametrize(
    "exc",
    [
        ConnectionResetError("Connection reset by peer"),
        BrokenPipeError("Broken pipe"),
        ConnectionRefusedError("[Errno 111] Connection refused"),
    ],
)
def test_dropped_connections_are_not_validation_errors(exc):
    assert _classify(exc).code == "tool_error"


def test_a_transport_fault_re_raised_as_a_plain_exception_is_still_caught():
    """Vendor clients often re-raise transport text on a bare Exception."""
    assert _classify(Exception("server disconnected without sending a response")).code == "tool_error"


def test_genuine_validation_messages_are_still_validation_errors():
    """The fix must not swallow real input problems into a generic error."""
    for exc in (
        ValueError("name is required"),
        ValueError("hubspot.deals.search requires filter_groups array"),
    ):
        err = _classify(exc)
        assert isinstance(err, ToolValidationError)
        assert err.code == "validation_error"


def test_existing_specific_classifications_are_unchanged():
    from app.services.tool_types import (
        ToolAuthExpiredError as AuthErr,
        ToolConnectorNotConnectedError as NotConnErr,
        ToolMissingScopeError as ScopeErr,
    )

    assert isinstance(_classify(Exception("401 unauthorized")), AuthErr)
    assert isinstance(_classify(Exception("insufficient scope for crm.read")), ScopeErr)
    assert isinstance(_classify(Exception("No active connector found")), NotConnErr)


def test_a_tool_error_passes_through_untouched():
    original = ToolValidationError("deal_id is required")
    assert _classify(original) is original


def test_the_user_facing_template_exists_for_every_code_we_emit():
    """A code with no template would fall back to something less useful."""
    from app.services.voice_expression_range import EXPRESSION_BANKS

    for code in ("validation_error", "connector_timeout", "tool_error", "rate_limited"):
        assert f"tool_error.{code}" in EXPRESSION_BANKS
