"""Capability registry is derived from canonical sources, not a parallel catalog."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

from app.capabilities import registry
from app.connectors.action_catalog.registry import all_catalog_action_specs, get_vendor_catalog
from app.services.catalog_write_authority import catalog_action_requires_write_approval
from app.workflows.constants import ALLOWED_STEP_TYPES


def test_every_catalog_action_is_in_registry():
    # Other tests register fixture vendors after the index is cached; rebuild it.
    registry.clear_registry_cache()
    tools = {c.tool for c in registry.list_actions()}
    for vendor, spec in get_vendor_catalog().items():
        for action in spec.all_actions():
            key = action.id if action.id.startswith(f"{vendor}.") else f"{vendor}.{action.id}"
            assert key in tools


def test_access_and_approval_follow_write_authority():
    for spec in all_catalog_action_specs()[:200]:
        vendor = spec.id.split(".", 1)[0]
        cap = registry.get_action(spec.id) or registry.get_action(f"{vendor}.{spec.id}")
        if cap is None:
            continue
        expected = catalog_action_requires_write_approval(
            kind=spec.kind,
            destructive=spec.destructive,
            requires_approval=spec.requires_approval,
            scopes=spec.scopes,
        )
        assert cap.requires_approval is expected
        assert cap.access == ("write" if expected else "read")


def test_reads_carry_no_verification_mode_and_writes_do():
    for cap in registry.list_actions():
        if cap.access == "read":
            assert cap.verification_mode is None
        else:
            assert cap.verification_mode in {
                "follow_up_membership",
                "follow_up_entity_get",
                "follow_up_field_assert",
                "accepted_async",
            }


def test_connectors_match_catalog_vendors():
    assert {c.vendor for c in registry.list_catalog_connectors()} == set(get_vendor_catalog())


def test_workflow_primitives_come_from_step_constants():
    steps = {p["step_type"] for p in registry.workflow_primitives()}
    assert steps == set(ALLOWED_STEP_TYPES)


def test_event_taxonomy_separates_execution_from_business_impact():
    tax = registry.event_taxonomy()
    assert "connector_action_executed" in tax["execution_evidence_events"]
    assert "connector_action_executed" not in tax["business_impact_events"]
    assert set(tax["signal_events"]) == {"recommendation_created", "prediction_generated"}


def test_evidence_states_are_distinct():
    sources = registry.evidence_sources()
    assert tuple(sources) == registry.EVIDENCE_STATES
    assert "SUCCESS" not in sources


def test_business_metrics_without_org_returns_platform_defaults_only():
    out = registry.business_metrics()
    assert out["orgId"] is None
    assert out["overrides"] == []
    assert {"mql", "cac", "arr"} <= {d["metric_key"] for d in out["defaults"]}


def test_readiness_unknown_org_is_external_connection_required():
    assert registry.connector_readiness("hubspot", None) == "EXTERNAL_CONNECTION_REQUIRED"
    assert registry.connector_readiness("hubspot", {"hubspot"}) == "AVAILABLE"
    assert registry.connector_readiness("not_a_vendor", {"not_a_vendor"}) == "MISSING"
    assert registry.action_readiness("hubspot.nope.nope", {"hubspot"}) == "MISSING"


def test_resolve_dependencies_reports_approval_and_verification():
    out = registry.resolve_dependencies(
        connectors=["stripe"],
        actions=["stripe.subscriptions.update", "stripe.invoices.list"],
        connected={"stripe"},
    )
    assert out["connectors"]["stripe"] == "AVAILABLE"
    write = out["actions"]["stripe.subscriptions.update"]
    assert write["access"] == "write" and write["requires_approval"] is True
    read = out["actions"]["stripe.invoices.list"]
    assert read["access"] == "read" and read["verification_mode"] is None


def test_connected_vendors_filters_unusable_status():
    rows = [
        {"vendor": "hubspot", "status": "connected"},
        {"type": "Stripe", "status": "active"},
        {"vendor": "zendesk", "status": "error"},
        {"vendor": "", "type": "", "status": "connected"},
    ]
    with patch("app.connectors.repository.list_connectors", return_value=rows) as lc:
        assert registry.connected_vendors(object(), "org-1") == {"hubspot", "stripe"}
        assert lc.call_args.args[1] == "org-1"


def test_list_agents_is_org_scoped():
    rows = [{"id": "a1", "name": "Rescue", "status": "active", "requires_approval": True}]
    with patch("app.operators.repository.list_operators", return_value=rows) as lo:
        agents = registry.list_agents(object(), "org-9")
    assert lo.call_args.args[1] == "org-9"
    assert agents[0]["requires_approval"] is True and agents[0]["capabilities"] == []
    assert agents[0]["executionMode"] == "plan_only"


def test_tenant_snapshot_strips_connector_config_and_is_org_scoped():
    rows = [
        {
            "id": "c1",
            "org_id": "org-9",
            "vendor": "hubspot",
            "name": "HS",
            "status": "connected",
            "environment": "production",
            "config": {"access_token": "secret-token", "refresh_token": "rt"},
        }
    ]
    empty_hitl = MagicMock()
    empty_hitl.table.return_value.select.return_value.eq.return_value.eq.return_value.execute.return_value = MagicMock(
        data=[]
    )
    with patch("app.connectors.repository.list_connectors", return_value=rows):
        with patch("app.operators.repository.list_operators", return_value=[]):
            with patch(
                "app.services.cognitive_metrics.list_metrics_with_defaults",
                return_value={"defaults": [], "overrides": [], "orgId": "org-9"},
            ):
                snap = registry.tenant_capability_snapshot(empty_hitl, "org-9")
    blob = str(snap)
    assert "secret-token" not in blob
    assert "refresh_token" not in blob
    assert snap["orgId"] == "org-9"
    assert snap["mutation"] is False
    assert snap["orgConnectors"][0]["vendor"] == "hubspot"
    assert "config" not in snap["orgConnectors"][0]
    writes = [a for a in snap["actions"] if a["access"] == "write"]
    reads = [a for a in snap["actions"] if a["access"] == "read"]
    assert writes and all(a["runtimeRequiresUserApproval"] is True for a in writes)
    assert reads and all(a["runtimeRequiresUserApproval"] is False for a in reads)
    assert snap["governance"]["noHitlPolicyMeans"] == "ACT WITH APPROVAL"
    assert snap["governance"]["writeRequiresApprovalByDefault"] is True
