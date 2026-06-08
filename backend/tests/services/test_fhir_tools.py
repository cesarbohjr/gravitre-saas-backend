"""STA-113: FHIR tools."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from app.services.fhir_tools import _exec_fhir_prior_auth_checklist, _exec_fhir_patients_search
from app.services.tool_types import ToolContext, ToolValidationError


def _ctx() -> ToolContext:
    return ToolContext(
        settings=MagicMock(disable_connectors=False),
        client=MagicMock(),
        org_id="org-1",
        actor_id="user-1",
        connector_id="conn-fhir",
    )


@patch("app.services.fhir_tools.enforce_rate_limit")
@patch("app.services.fhir_tools.resolve_fhir_session")
@patch("app.services.fhir_tools.search_patients")
def test_fhir_patients_search_returns_bundle(mock_search, mock_session, _rate):
    mock_session.return_value = ("conn-fhir", "https://hapi.fhir.org/baseR4", None)
    mock_search.return_value = {"resourceType": "Bundle", "entry": []}
    result = _exec_fhir_patients_search(_ctx(), {"name": "Smith"})
    assert result.success is True
    assert result.data["bundle"]["resourceType"] == "Bundle"


@patch("app.services.fhir_tools.enforce_rate_limit")
@patch("app.services.fhir_tools.resolve_fhir_session")
def test_fhir_prior_auth_checklist_builds_items(mock_session, _rate):
    mock_session.return_value = ("conn-fhir", "https://hapi.fhir.org/baseR4", None)
    result = _exec_fhir_prior_auth_checklist(
        _ctx(),
        {"referral_reason": "MRI", "payer": "Medicare", "patient_id": "p-1"},
    )
    assert result.success is True
    assert len(result.data["checklist"]) >= 5
    assert result.data["referralReason"] == "MRI"


@patch("app.services.fhir_tools.resolve_fhir_session")
def test_fhir_patients_get_requires_id(mock_session):
    mock_session.return_value = ("conn-fhir", "https://hapi.fhir.org/baseR4", None)
    with pytest.raises(ToolValidationError):
        from app.services.fhir_tools import _exec_fhir_patients_get

        _exec_fhir_patients_get(_ctx(), {})
