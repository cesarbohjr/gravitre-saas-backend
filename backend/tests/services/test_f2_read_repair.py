"""F2 READ repair — classed budget, HMAC sibling, GA4→GSC auth fallback."""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from app.services.f2_read_repair import RepairBudget, repair_blocked_read
from app.services.read_preflight import PreflightResult
from app.services.tool_types import ToolContext


def _ctx() -> ToolContext:
    return ToolContext(
        settings=SimpleNamespace(),
        client=MagicMock(),
        org_id="org-1",
        actor_id="user-1",
        environment_name="production",
    )


def _ready(action: str, params: dict, digest: str = "abc") -> PreflightResult:
    ok = PreflightResult(
        status="ready",
        action_key=action,
        compiled_parameters=params,
        org_id="org-1",
        proof_digest=digest,
    )
    ok.status = "ready"
    return ok


def test_wrong_sibling_listing_falls_back_to_hmac_deals_list() -> None:
    blocked = PreflightResult(
        status="blocked",
        action_key="hubspot.deals.search",
        error_class="WRONG_SIBLING_ACTION",
        org_id="org-1",
    )
    ok = _ready("hubspot.deals.list", {"limit": 10})
    with patch("app.services.f2_read_repair.preflight_read_action", return_value=ok):
        repaired = repair_blocked_read(
            blocked=blocked,
            ctx=_ctx(),
            invoke_action="hubspot.deals.search",
            args={},
            user_message="List my deals.",
            connected_integrations=["hubspot"],
        )
    assert repaired is not None
    assert repaired.action == "hubspot.deals.list"
    assert repaired.reason == "sibling_list_fallback"
    assert repaired.preflight is ok
    assert repaired.repair_class == "sibling"
    assert repaired.budget_remaining["sibling"] == 0


def test_in_task_error_memory_strips_secrets() -> None:
    budget = RepairBudget.fresh()
    blocked = PreflightResult(
        status="blocked",
        action_key="hubspot.deals.search",
        error_class="WRONG_SIBLING_ACTION",
        org_id="org-1",
    )
    ok = _ready("hubspot.deals.list", {"limit": 10})
    with patch("app.services.f2_read_repair.preflight_read_action", return_value=ok):
        repair_blocked_read(
            blocked=blocked,
            ctx=_ctx(),
            invoke_action="hubspot.deals.search",
            args={"api_key": "secret", "limit": 10},
            user_message="List my deals.",
            connected_integrations=["hubspot"],
            budget=budget,
        )
    assert budget.error_memory
    row = budget.error_memory[0]
    assert row["action"] == "hubspot.deals.search"
    assert row["error_class"] == "WRONG_SIBLING_ACTION"
    assert "api_key" not in row["args"]
    assert row["args"].get("limit") == 10


def test_sibling_without_hmac_preflight_does_not_invoke() -> None:
    blocked = PreflightResult(
        status="blocked",
        action_key="hubspot.deals.search",
        error_class="WRONG_SIBLING_ACTION",
        org_id="org-1",
    )
    failed = PreflightResult(
        status="blocked",
        action_key="hubspot.deals.list",
        error_class="NOT_AUTHENTICATED",
        org_id="org-1",
    )
    with patch("app.services.f2_read_repair.preflight_read_action", return_value=failed):
        repaired = repair_blocked_read(
            blocked=blocked,
            ctx=_ctx(),
            invoke_action="hubspot.deals.search",
            args={},
            user_message="List my deals.",
            connected_integrations=["hubspot"],
        )
    assert repaired is None


def test_structured_search_does_not_convert_to_list() -> None:
    blocked = PreflightResult(
        status="blocked",
        action_key="hubspot.deals.search",
        error_class="WRONG_SIBLING_ACTION",
        org_id="org-1",
    )
    repaired = repair_blocked_read(
        blocked=blocked,
        ctx=_ctx(),
        invoke_action="hubspot.deals.search",
        args={},
        user_message="Find high-value deals over ten thousand.",
        connected_integrations=["hubspot"],
    )
    assert repaired is None


def test_sibling_budget_is_one_shot() -> None:
    blocked = PreflightResult(
        status="blocked",
        action_key="hubspot.deals.search",
        error_class="WRONG_SIBLING_ACTION",
        org_id="org-1",
    )
    budget = RepairBudget.fresh()
    ok = _ready("hubspot.deals.list", {"limit": 10})
    with patch("app.services.f2_read_repair.preflight_read_action", return_value=ok):
        first = repair_blocked_read(
            blocked=blocked,
            ctx=_ctx(),
            invoke_action="hubspot.deals.search",
            args={},
            user_message="List my deals.",
            connected_integrations=["hubspot"],
            budget=budget,
        )
        second = repair_blocked_read(
            blocked=blocked,
            ctx=_ctx(),
            invoke_action="hubspot.deals.search",
            args={},
            user_message="List my deals.",
            connected_integrations=["hubspot"],
            budget=budget,
        )
    assert first is not None
    assert second is None
    assert any(row.get("reason") in {"budget_exhausted", "same_malformed_args"} for row in budget.traces)


def test_ga4_auth_expired_falls_back_to_gsc_when_preflight_ok() -> None:
    blocked = PreflightResult(
        status="blocked",
        action_key="google_analytics.reports.run",
        error_class="AUTH_EXPIRED",
        org_id="org-1",
    )
    ok = _ready(
        "google_search_console.searchAnalytics.query",
        {"site_url": "https://acme.example/", "start_date": "2026-08-01", "end_date": "2026-08-31"},
    )
    with patch("app.services.f2_read_repair.preflight_read_action", return_value=ok):
        repaired = repair_blocked_read(
            blocked=blocked,
            ctx=_ctx(),
            invoke_action="analytics.reports.run",
            args={},
            user_message="Tell me what my website traffic was last month.",
            connected_integrations=["google_analytics", "google_search_console"],
        )
    assert repaired is not None
    assert repaired.reason == "ga4_auth_fallback_gsc"
    assert repaired.action == "searchconsole.searchAnalytics.query"
    assert repaired.preflight is ok
    assert repaired.repair_class == "source_switch"


def test_ga4_auth_does_not_fallback_without_gsc() -> None:
    blocked = PreflightResult(
        status="blocked",
        action_key="google_analytics.reports.run",
        error_class="AUTH_EXPIRED",
        org_id="org-1",
    )
    repaired = repair_blocked_read(
        blocked=blocked,
        ctx=_ctx(),
        invoke_action="analytics.reports.run",
        args={},
        user_message="Tell me what my website traffic was last month.",
        connected_integrations=["google_analytics"],
    )
    assert repaired is None


def test_emit_f2_repair_audit_writes_without_secrets() -> None:
    from uuid import uuid4

    from app.services.f2_read_repair import AUDIT_F2_REPAIR, ReadRepair, emit_f2_repair_audit

    ctx = ToolContext(
        settings=SimpleNamespace(),
        client=MagicMock(),
        org_id=str(uuid4()),
        actor_id=str(uuid4()),
        environment_name="production",
        conversation_id=str(uuid4()),
    )
    budget = RepairBudget.fresh()
    budget.error_memory.append({"action": "hubspot.deals.search", "args": {"limit": 10}})
    repaired = ReadRepair(
        kind="reinvoke",
        action="hubspot.deals.list",
        args={"limit": 10},
        preflight=None,
        reason="sibling_list_fallback",
        repair_class="sibling",
    )
    with patch("app.workflows.audit.write_audit_event") as write:
        emit_f2_repair_audit(
            ctx, from_action="hubspot.deals.search", repaired=repaired, budget=budget
        )
    write.assert_called_once()
    args = write.call_args.args
    meta = args[-1]
    assert args[3] == AUDIT_F2_REPAIR
    assert meta["from_action"] == "hubspot.deals.search"
    assert meta["to_action"] == "hubspot.deals.list"
    assert meta["provider_write"] is False
    assert "api_key" not in meta
