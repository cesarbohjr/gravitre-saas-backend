"""Connector registry contract tests — structural guarantees for catalog ↔ router ↔ handlers."""
from __future__ import annotations

import pytest

from app.connectors.action_catalog.registry import get_action_spec
from app.connectors.action_catalog.tool_aliases import catalog_tool_is_implemented
from app.services.connector_execution_matrix import get_matrix_entry
from app.services.connector_registry_verification import (
    REGISTERED_WITHOUT_CATALOG_ALLOWLIST,
    assert_registry_contract,
    registry_violation_summary,
    verify_connector_registry,
)
from app.services.tool_service import list_registered_actions


def test_registry_contract_has_no_errors():
    assert_registry_contract()


def test_registry_violation_summary_shape():
    summary = registry_violation_summary()
    assert "totalViolations" in summary
    assert "errors" in summary
    assert "warnings" in summary
    assert "byCode" in summary
    assert summary["errors"] == 0


def test_apollo_lists_create_fully_wired():
    """Regression: apollo.lists.create must never fall through as a false capability gap."""
    action_key = "apollo.lists.create"
    spec = get_action_spec(action_key)
    assert spec is not None
    assert spec.kind == "write"
    registered = set(list_registered_actions())
    assert catalog_tool_is_implemented(action_key, registered)
    entry = get_matrix_entry("apollo", action_key)
    assert entry is not None
    assert entry.implementation_status != "not_implemented"
    assert entry.chat_executable is True


def test_allowlisted_orphans_do_not_produce_new_warnings():
    violations = verify_connector_registry()
    orphan_warnings = [
        v
        for v in violations
        if v.code == "registered_missing_catalog"
        and v.action_key not in REGISTERED_WITHOUT_CATALOG_ALLOWLIST
    ]
    assert orphan_warnings == []


def test_declared_capability_unimplemented_would_fail_for_missing_handler(monkeypatch: pytest.MonkeyPatch):
    from app.services import connector_registry_verification as mod

    original = mod.verify_connector_registry

    def _fake_verify() -> list[mod.RegistryViolation]:
        return [
            mod.RegistryViolation(
                code="declared_capability_unimplemented",
                severity="error",
                message="simulated gap",
                vendor="apollo",
            )
        ]

    monkeypatch.setattr(mod, "verify_connector_registry", _fake_verify)
    with pytest.raises(AssertionError, match="registry contract failed"):
        mod.assert_registry_contract()

    monkeypatch.setattr(mod, "verify_connector_registry", original)
