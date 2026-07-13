"""Phase 1: auth_mode, BYO fail-closed, needs_connection stubs."""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from app.intelligence_packs.shared.auth_mode import (
    AuthMode,
    AuthModeError,
    ActivationGate,
    assert_byo_never_uses_platform_key,
    get_auth_mode,
    get_activation_gate,
    is_activation_allowed,
    resolve_credential_source,
)
from app.marketplace.connector_category_templates import (
    CONNECTOR_CATEGORY_TEMPLATES,
    install_connector_category_template,
    stage_connector_stubs,
)


def test_apollo_is_customer_owned():
    assert get_auth_mode("apollo") == AuthMode.CUSTOMER_OWNED


def test_fred_is_gravitree_managed():
    assert get_auth_mode("fred") == AuthMode.GRAVITREE_MANAGED


@pytest.mark.parametrize("vendor", ["zoominfo", "linkedin_sales_navigator"])
def test_byo_vendors_fail_closed_without_org_secret(vendor: str):
    result = resolve_credential_source(
        vendor,
        org_has_secret=False,
        platform_env_present=True,  # even if platform has a key, BYO must not use it
    )
    assert result["ok"] is False
    assert result["error_code"] == "BYO_CREDENTIAL_REQUIRED"
    assert result["source"] is None


@pytest.mark.parametrize("vendor", ["zoominfo", "linkedin_sales_navigator"])
def test_byo_never_accepts_platform_resolution(vendor: str):
    with pytest.raises(AuthModeError) as exc:
        assert_byo_never_uses_platform_key(vendor, resolved_from="platform_env")
    assert exc.value.code == "BYO_SHARED_KEY_FORBIDDEN"


def test_byo_ok_with_org_secret_only():
    result = resolve_credential_source(
        "zoominfo",
        org_has_secret=True,
        platform_env_present=True,
    )
    assert result["ok"] is True
    assert result["source"] == "org_secret"
    assert result["auth_mode"] == AuthMode.BYO_REQUIRED.value


def test_opencorporates_activation_blocked_until_license():
    assert get_activation_gate("opencorporates") == ActivationGate.COMMERCIAL_LICENSE_PENDING
    assert is_activation_allowed("opencorporates", settings=SimpleNamespace(opencorporates_license_confirmed=False)) is False
    assert is_activation_allowed("opencorporates", settings=SimpleNamespace(opencorporates_license_confirmed=True)) is True
    blocked = resolve_credential_source(
        "opencorporates",
        org_has_secret=False,
        platform_env_present=True,
        settings=SimpleNamespace(opencorporates_license_confirmed=False),
    )
    assert blocked["ok"] is False
    assert blocked["error_code"] == "SOURCE_ACTIVATION_BLOCKED"


def test_crunchbase_pdl_governance_stop_line():
    assert get_activation_gate("crunchbase") == ActivationGate.GOVERNANCE_STOP_LINE
    assert get_activation_gate("pdl") == ActivationGate.GOVERNANCE_STOP_LINE
    assert is_activation_allowed("crunchbase") is False
    assert is_activation_allowed("pdl") is False


def test_stage_connector_stubs_creates_needs_connection_only(monkeypatch):
    client = MagicMock()
    created_rows: list[dict] = []

    def fake_list(_client, _org, environment_name="production"):
        _ = environment_name
        return []

    def fake_create(_client, org_id, connector_type, config, created_by, environment_name="production", *, status="active"):
        row = {
            "id": f"id-{connector_type}",
            "org_id": org_id,
            "type": connector_type,
            "status": status,
            "config": config,
            "created_by": created_by,
            "environment": environment_name,
        }
        created_rows.append(row)
        return row

    monkeypatch.setattr(
        "app.marketplace.connector_category_templates.list_connectors",
        fake_list,
    )
    monkeypatch.setattr(
        "app.marketplace.connector_category_templates.create_connector",
        fake_create,
    )

    result = stage_connector_stubs(
        client,
        "org-1",
        ["fred", "zoominfo"],
        created_by="user-1",
        template_id="executive-intelligence-sources",
    )
    assert result["stagedCount"] == 2
    assert all(r["status"] == "needs_connection" for r in result["created"])
    assert all(r["status"] == "needs_connection" for r in created_rows)
    assert created_rows[0]["config"]["auth_mode"] == "gravitree_managed"
    assert created_rows[1]["config"]["auth_mode"] == "byo_required"


def test_template_install_never_creates_live_connection(monkeypatch):
    client = MagicMock()

    def fake_list(_client, _org, environment_name="production"):
        _ = environment_name
        return []

    def fake_create(_client, org_id, connector_type, config, created_by, environment_name="production", *, status="active"):
        # Simulate a bug that creates active — install must raise
        return {
            "id": "x",
            "type": connector_type,
            "status": "active",
            "config": config,
        }

    monkeypatch.setattr(
        "app.marketplace.connector_category_templates.list_connectors",
        fake_list,
    )
    monkeypatch.setattr(
        "app.marketplace.connector_category_templates.create_connector",
        fake_create,
    )
    with pytest.raises(RuntimeError, match="live connection"):
        install_connector_category_template(
            client,
            "org-1",
            "byo-premium-prospecting",
            created_by="user-1",
        )


def test_executive_template_lists_public_sources():
    spec = CONNECTOR_CATEGORY_TEMPLATES["executive-intelligence-sources"]
    assert "fred" in spec["connectors"]
    assert "sec_edgar" in spec["connectors"]
    assert "world_bank" in spec["connectors"]
    assert "oecd" in spec["connectors"]
