"""Phase F1 — canonical READ action compilation + preflight."""
from __future__ import annotations

from datetime import datetime
from types import SimpleNamespace
from unittest.mock import MagicMock, patch
from zoneinfo import ZoneInfo

import pytest

from app.connectors.action_catalog.f1_read_slice import F1_CATALOG_ACTIONS, is_f1_read_action
from app.connectors.action_catalog.registry import get_action_spec
from app.services.canonical_time_resolver import resolve_time_window
from app.services.connector_resource_resolver import ResourceResolution
from app.services.read_preflight import (
    match_resource_to_domain,
    preflight_read_action,
)
from app.services.tool_types import ToolContext, ToolValidationError


FROZEN = datetime(2026, 9, 16, 18, 0, tzinfo=ZoneInfo("America/Los_Angeles"))


def _ctx(**overrides):
    base = {
        "org_id": "org-1",
        "client": MagicMock(),
        "settings": SimpleNamespace(),
        "environment_name": "production",
        "connected_integrations": [
            "google_analytics",
            "google_search_console",
            "hubspot",
            "quickbooks",
            "zendesk",
            "salesforce",
            "google_calendar",
            "slack",
        ],
        "timezone": "America/Los_Angeles",
        "now": FROZEN,
        "business_identity": {"website": "https://acme.example", "timezone": "America/Los_Angeles"},
    }
    base.update(overrides)
    return base


def _resolved(connector_id: str, resource_type: str, resource_id: str, **kwargs) -> ResourceResolution:
    return ResourceResolution(
        status="resolved",
        connector_id=connector_id,
        connection_id="conn-1",
        resource_type=resource_type,
        resource_id=resource_id,
        display_name=kwargs.get("display_name") or resource_id,
        confidence=0.98,
        resolution_reason=kwargs.get("reason") or "linked_config",
        candidate_count=1,
    )


def test_f1_action_spec_is_single_canonical_owner():
    from app.connectors.action_catalog.registry import all_catalog_action_specs

    catalog = {spec.id: spec for spec in all_catalog_action_specs()}
    for key in F1_CATALOG_ACTIONS:
        spec = get_action_spec(key)
        assert spec is not None
        assert spec is catalog[key]
        assert spec is get_action_spec(key)
        assert spec.kind == "read"
        assert spec.parameter_source_rules
        assert spec.governance_classification == "read"
        assert spec.execution_adapter
        assert spec.spec_revision
        assert spec.spec_revision == catalog[key].spec_revision


def test_last_month_is_previous_calendar_month_not_rolling_30():
    window = resolve_time_window(
        "Tell me what my website traffic was last month.",
        timezone_name="America/Los_Angeles",
        now=FROZEN,
    )
    assert window is not None
    assert window.start.isoformat() == "2026-08-01"
    assert window.end.isoformat() == "2026-08-31"
    assert window.interpretation == "previous_calendar_month"
    assert "30" not in window.interpretation


@pytest.mark.parametrize(
    "action,connector,rtype,rid,message,proposed",
    [
        (
            "google_analytics.reports.run",
            "google_analytics",
            "property",
            "123456",
            "Tell me what my website traffic was last month.",
            {"property_id": "wrong-model-id"},
        ),
        (
            "google_search_console.searchAnalytics.query",
            "google_search_console",
            "site",
            "https://acme.example/",
            "Tell me what my website traffic was last month.",
            {},
        ),
        (
            "hubspot.deals.search",
            "hubspot",
            "portal",
            "99887",
            "Show my high-value deals",
            {},
        ),
        (
            "quickbooks.invoices.list",
            "quickbooks",
            "company",
            "realm-1",
            "List recent invoices",
            {},
        ),
        (
            "zendesk.tickets.list",
            "zendesk",
            "subdomain",
            "acme",
            "What tickets are open?",
            {},
        ),
        (
            "hubspot.deals.list",
            "hubspot",
            "portal",
            "99887",
            "List my deals",
            {},
        ),
        (
            "hubspot.contacts.search",
            "hubspot",
            "portal",
            "99887",
            "Find contacts named Ada",
            {"query": "Ada"},
        ),
        (
            "hubspot.companies.search",
            "hubspot",
            "portal",
            "99887",
            "Search companies named Acme",
            {"query": "Acme"},
        ),
        (
            "salesforce.leads.search",
            "salesforce",
            "org",
            "https://acme.my.salesforce.com",
            "Search Salesforce leads",
            {},
        ),
        (
            "google_calendar.events.list",
            "google_calendar",
            "calendar",
            "primary",
            "List my calendar events last month",
            {},
        ),
        (
            "slack.conversations.list",
            "slack",
            "workspace",
            "T123",
            "List Slack channels",
            {},
        ),
    ],
)
def test_f1_preflight_compiles_without_user_parameter_questions(action, connector, rtype, rid, message, proposed):
    with patch(
        "app.services.read_preflight.resolve_resource",
        return_value=_resolved(connector, rtype, rid),
    ):
        result = preflight_read_action(
            context=_ctx(
                action_key=action,
                user_message=message,
                proposed_args=proposed,
            )
        )
    assert result.ok, result.as_dict()
    assert result.error_class is None
    sources = {p.parameter: p.source for p in result.parameter_provenance}
    if action == "google_analytics.reports.run":
        assert result.compiled_parameters["property_id"] == "123456"
        assert result.compiled_parameters["start_date"] == "2026-08-01"
        assert result.compiled_parameters["end_date"] == "2026-08-31"
        assert sources["property_id"] == "RESOURCE_RESOLVER"
        assert sources["start_date"] == "TIME_RESOLVER"
        assert result.shadow_diff and result.shadow_diff["property_id"]["proposed"] == "wrong-model-id"
    if action == "google_calendar.events.list":
        assert result.compiled_parameters["time_min"] == "2026-08-01T00:00:00"
        assert result.compiled_parameters["time_max"] == "2026-08-31T23:59:59"
        assert sources["time_min"] == "TIME_RESOLVER"
    if action == "salesforce.leads.search":
        assert "Lead" in str(result.compiled_parameters.get("soql") or "")


def test_website_traffic_optimized_and_react_paths_share_time_and_resource():
    with patch(
        "app.services.read_preflight.resolve_resource",
        return_value=_resolved("google_analytics", "property", "123456", display_name="Acme"),
    ):
        optimized = preflight_read_action(
            context=_ctx(
                action_key="google_analytics.reports.run",
                capability_id="analytics.traffic_overview",
                user_message="Tell me what my website traffic was last month.",
                proposed_args={},
            )
        )
        react = preflight_read_action(
            context=_ctx(
                action_key="google_analytics.reports.run",
                capability_id="analytics.traffic_overview",
                user_message="Tell me what my website traffic was last month.",
                proposed_args={"property_id": "999", "start_date": "30daysAgo"},
            )
        )
    assert optimized.ok and react.ok
    assert optimized.compiled_parameters["property_id"] == react.compiled_parameters["property_id"] == "123456"
    assert optimized.compiled_parameters["start_date"] == react.compiled_parameters["start_date"] == "2026-08-01"
    assert optimized.compiled_parameters["end_date"] == react.compiled_parameters["end_date"] == "2026-08-31"


def test_negative_ambiguous_resources_require_clarification():
    with patch(
        "app.services.read_preflight.resolve_resource",
        return_value=ResourceResolution(
            status="ambiguous",
            connector_id="google_analytics",
            resource_type="property",
            resolution_reason="multiple_properties",
            candidate_count=2,
            candidates=(
                {"property_id": "1", "display_name": "A", "org_id": "org-1"},
                {"property_id": "2", "display_name": "B", "org_id": "org-1"},
            ),
        ),
    ):
        result = preflight_read_action(
            context=_ctx(action_key="google_analytics.reports.run", business_identity={})
        )
    assert not result.ok
    assert result.error_class == "GENUINE_USER_CLARIFICATION_REQUIRED"


def test_negative_auth_expired():
    with patch(
        "app.services.read_preflight.resolve_resource",
        return_value=ResourceResolution(
            status="not_authorized",
            connector_id="google_analytics",
            resolution_reason="invalid_grant",
        ),
    ):
        result = preflight_read_action(context=_ctx(action_key="google_analytics.reports.run"))
    assert result.error_class == "AUTH_EXPIRED"


def test_negative_no_source_connected():
    result = preflight_read_action(
        context=_ctx(
            action_key="hubspot.deals.search",
            connected_integrations=["slack"],
        )
    )
    assert result.error_class == "ACTION_UNAVAILABLE"


def test_cross_tenant_candidate_rejected():
    matched = match_resource_to_domain(
        (
            {"site_url": "https://acme.example/", "org_id": "other-org"},
            {"site_url": "https://other.example/", "org_id": "org-1"},
        ),
        host="acme.example",
        org_id="org-1",
    )
    assert matched is None


def test_domain_binding_selects_single_tenant_match():
    matched = match_resource_to_domain(
        (
            {"site_url": "https://acme.example/", "display_name": "Acme", "org_id": "org-1"},
            {"site_url": "https://other.example/", "org_id": "org-1"},
        ),
        host="acme.example",
        org_id="org-1",
    )
    assert matched is not None
    assert matched["site_url"] == "https://acme.example/"


def test_invoke_tool_defense_does_not_call_provider_when_preflight_fails():
    from dataclasses import replace

    from app.services.tool_service import invoke_tool
    from app.services.tool_types import NormalizedResult

    tool_ctx = ToolContext(
        settings=SimpleNamespace(disable_connectors=False, connector_secrets_encryption_key="k" * 32),
        client=MagicMock(),
        org_id="org-1",
        actor_id="user-1",
        environment_name="production",
    )
    with patch("app.services.tool_service._resolve_tool_executor") as mock_exec:
        mock_exec.return_value = lambda *_a, **_k: NormalizedResult(success=True, action="analytics.reports.run")
        with pytest.raises(ToolValidationError) as exc:
            invoke_tool(tool_ctx, "analytics.reports.run", {"property_id": "x", "_preflight_ok": "true"})
        assert exc.value.code == "PREFLIGHT_REQUIRED"
        mock_exec.assert_not_called()

    with patch(
        "app.services.read_preflight.resolve_resource",
        return_value=_resolved("google_analytics", "property", "123"),
    ):
        proof = preflight_read_action(
            context=_ctx(action_key="google_analytics.reports.run", proposed_args={}, user_message="last month")
        )
    assert proof.ok
    bound = replace(tool_ctx, preflight_result=proof)
    with patch("app.services.tool_service.enforce_rate_limit"):
        with patch("app.services.tool_service.write_audit_event") as audit:
            with patch(
                "app.services.agent_tool_permissions.list_agent_tool_permissions",
                return_value=[{"connector_type": "google_analytics", "scopes": ["google_analytics:read"], "expires_at": None}],
            ):
                with patch("app.services.tool_service._resolve_tool_executor") as mock_exec:
                    called = {}

                    def _exec(_ctx, params):
                        called["params"] = params
                        return NormalizedResult(success=True, action="analytics.reports.run", data={"ok": True})

                    mock_exec.return_value = _exec
                    result = invoke_tool(bound, "analytics.reports.run", dict(proof.compiled_parameters))
    assert result.success is True
    assert called["params"]["property_id"] == "123"
    metadatas = [call.kwargs.get("metadata") or {} for call in audit.call_args_list]
    assert any(meta.get("preflight_status") == "ready" for meta in metadatas)
    assert any(meta.get("spec_revision") for meta in metadatas)


def test_write_actions_are_not_f1_preflighted():
    assert not is_f1_read_action("hubspot.deals.create")
    result = preflight_read_action(context=_ctx(action_key="hubspot.deals.create"))
    assert not result.ok
    assert result.error_class in {"ACTION_UNAVAILABLE", "PERMISSION_BLOCKED"}


def test_routing_parity_crm_finance_support():
    cases = [
        ("hubspot.deals.search", "hubspot", "portal", "p1", "Show my high-value deals"),
        ("hubspot.deals.list", "hubspot", "portal", "p1", "List my deals"),
        ("quickbooks.invoices.list", "quickbooks", "company", "r1", "List recent invoices"),
        ("zendesk.tickets.list", "zendesk", "subdomain", "acme", "What tickets are open?"),
        ("salesforce.leads.search", "salesforce", "org", "https://acme.my.salesforce.com", "Search Salesforce leads"),
        ("slack.conversations.list", "slack", "workspace", "T123", "List Slack channels"),
    ]
    for action, connector, rtype, rid, message in cases:
        with patch(
            "app.services.read_preflight.resolve_resource",
            return_value=_resolved(connector, rtype, rid),
        ):
            direct = preflight_read_action(context=_ctx(action_key=action, user_message=message))
            react = preflight_read_action(
                context=_ctx(action_key=action, user_message=message, proposed_args={"limit": 10})
            )
        assert direct.ok and react.ok, (action, direct.as_dict())
        assert direct.connector_id == react.connector_id == connector
        assert direct.resource and react.resource
        assert direct.resource["id"] == react.resource["id"]


def test_preflight_latency_p50_p95():
    import statistics
    import time

    samples: list[float] = []
    with patch(
        "app.services.read_preflight.resolve_resource",
        return_value=_resolved("hubspot", "portal", "p1"),
    ):
        for _ in range(40):
            t0 = time.perf_counter()
            result = preflight_read_action(
                context=_ctx(action_key="hubspot.deals.search", user_message="show high-value deals")
            )
            assert result.ok
            samples.append((time.perf_counter() - t0) * 1000)
    samples.sort()
    p50 = statistics.median(samples)
    p95 = samples[int(len(samples) * 0.95) - 1]
    assert p50 < 50
    assert p95 < 150
    print(f"F1_PREFLIGHT_LATENCY_MS p50={p50:.2f} p95={p95:.2f}")


def test_last_month_phrase_variants():
    for phrase in (
        "last month",
        "previous month",
        "last calendar month",
        "in August",
        "August 2026",
    ):
        window = resolve_time_window(phrase, timezone_name="America/Los_Angeles", now=FROZEN)
        assert window is not None, phrase
        assert window.start.isoformat() == "2026-08-01", phrase
        assert window.end.isoformat() == "2026-08-31", phrase


def test_wrong_sibling_hubspot_search_without_criteria():
    with patch(
        "app.services.read_preflight.resolve_resource",
        return_value=_resolved("hubspot", "portal", "p1"),
    ):
        result = preflight_read_action(
            context=_ctx(
                action_key="hubspot.deals.search",
                user_message="list my deals",
                proposed_args={},
            )
        )
    assert not result.ok
    assert result.error_class == "WRONG_SIBLING_ACTION"


def test_hubspot_search_preserved_with_structured_criteria():
    with patch(
        "app.services.read_preflight.resolve_resource",
        return_value=_resolved("hubspot", "portal", "p1"),
    ):
        result = preflight_read_action(
            context=_ctx(
                action_key="hubspot.deals.search",
                user_message="find deals",
                proposed_args={"filter_groups": [{"filters": [{"propertyName": "amount", "operator": "GT", "value": "10000"}]}]},
            )
        )
    assert result.ok
    assert result.compiled_parameters["filter_groups"]


def test_cross_tenant_supplied_resource_is_hard_failure():
    with patch(
        "app.services.read_preflight.resolve_resource",
        return_value=ResourceResolution(
            status="resolved",
            connector_id="google_analytics",
            resource_type="property",
            resource_id="123",
            resolution_reason="linked_config",
            candidates=({"property_id": "999", "org_id": "other-org"},),
        ),
    ):
        result = preflight_read_action(
            context=_ctx(
                action_key="google_analytics.reports.run",
                proposed_args={"property_id": "999"},
            )
        )
    assert result.error_class == "TENANT_SCOPE_VIOLATION"
    assert "999" not in result.user_message()


def test_repair_classifications_for_model_overrides():
    with patch(
        "app.services.read_preflight.resolve_resource",
        return_value=_resolved("google_analytics", "property", "123456"),
    ):
        result = preflight_read_action(
            context=_ctx(
                action_key="google_analytics.reports.run",
                user_message="last month",
                proposed_args={"property_id": "999", "start_date": "30daysAgo"},
            )
        )
    assert result.ok
    by_param = {p.parameter: p.classification for p in result.parameter_provenance}
    assert by_param["property_id"] == "OVERRIDDEN_BY_RESOURCE_RESOLVER"
    assert by_param["start_date"] == "OVERRIDDEN_BY_TIME_RESOLVER"


def test_optimized_and_react_share_same_action_spec_object():
    spec_a = get_action_spec("google_analytics.reports.run")
    spec_b = get_action_spec("analytics.reports.run")
    assert spec_a is spec_b
    assert spec_a.parameter_source_rules == spec_b.parameter_source_rules


def _bound_ctx(proof, org_id="org-1"):
    from dataclasses import replace

    return replace(
        ToolContext(
            settings=SimpleNamespace(disable_connectors=False, connector_secrets_encryption_key="k" * 32),
            client=MagicMock(),
            org_id=org_id,
            actor_id="user-1",
            environment_name="production",
        ),
        preflight_result=proof,
    )


def _ga_proof():
    with patch(
        "app.services.read_preflight.resolve_resource",
        return_value=_resolved("google_analytics", "property", "123"),
    ):
        return preflight_read_action(
            context=_ctx(action_key="google_analytics.reports.run", user_message="last month", proposed_args={})
        )


def test_mutation_parameter_resource_action_tenant_and_exact_match():
    from app.services.tool_service import invoke_tool
    from app.services.tool_types import NormalizedResult

    proof = _ga_proof()
    assert proof.ok
    compiled = dict(proof.compiled_parameters)

    def _run(ctx, params):
        with patch("app.services.tool_service.enforce_rate_limit"):
            with patch("app.services.tool_service.write_audit_event"):
                with patch(
                    "app.services.agent_tool_permissions.list_agent_tool_permissions",
                    return_value=[{"connector_type": "google_analytics", "scopes": ["google_analytics:read"], "expires_at": None}],
                ):
                    with patch("app.services.tool_service._resolve_tool_executor") as mock_exec:
                        mock_exec.return_value = lambda *_a, **_k: NormalizedResult(success=True, action="analytics.reports.run")
                        return invoke_tool(ctx, "analytics.reports.run", params), mock_exec

    ctx = _bound_ctx(proof)
    mutated = dict(compiled, property_id="999")
    with pytest.raises(ToolValidationError) as exc:
        _run(ctx, mutated)
    assert exc.value.code == "PREFLIGHT_STALE"

    with pytest.raises(ToolValidationError) as exc:
        invoke_tool(ctx, "zendesk.tickets.list", compiled)
    assert exc.value.code in {"PREFLIGHT_STALE", "PREFLIGHT_REQUIRED"}

    other_org = _bound_ctx(proof, org_id="org-2")
    with pytest.raises(ToolValidationError) as exc:
        _run(other_org, compiled)
    assert exc.value.code == "PERMISSION_BLOCKED"

    result, mock_exec = _run(ctx, compiled)
    assert result.success is True
    mock_exec.assert_called()


def test_direct_invoke_bypass_each_f1_action():
    from app.connectors.action_catalog.f1_read_slice import registry_action_key
    from app.services.tool_service import invoke_tool

    ctx = ToolContext(
        settings=SimpleNamespace(disable_connectors=False, connector_secrets_encryption_key="k" * 32),
        client=MagicMock(),
        org_id="org-1",
        actor_id="user-1",
        environment_name="production",
    )
    for key in F1_CATALOG_ACTIONS:
        with patch("app.services.tool_service._resolve_tool_executor") as mock_exec:
            mock_exec.return_value = lambda *_a, **_k: None
            with pytest.raises(ToolValidationError) as exc:
                invoke_tool(ctx, registry_action_key(key), {"_preflight_ok": "forged"})
            assert exc.value.code == "PREFLIGHT_REQUIRED"
            mock_exec.assert_not_called()

