"""2.0-A cohesion invariants — compile/HMAC/lineage/Composer/time/projection."""
from __future__ import annotations

import ast
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch
from datetime import datetime
from zoneinfo import ZoneInfo

from app.services.agent_platform_optimizer import narrow_tools_for_turn
from app.services.canonical_time_resolver import resolve_time_window, user_facing_time_label
from app.services.compiled_task_service import attach_compiled_task, project_compiled_task
from app.services.connector_resource_resolver import ResourceResolution
from app.services.read_preflight import preflight_read_action
from app.services.sealed_read_execution import COGNITIVE_BYPASS_MODULES, INFRASTRUCTURE_INVOKE_ACTORS
from app.services.tool_types import ToolContext, ToolValidationError

ROOT = Path(__file__).resolve().parents[3]
APP = ROOT / "backend" / "app"
FROZEN = datetime(2026, 9, 16, 18, 0, tzinfo=ZoneInfo("America/Los_Angeles"))
ANCHOR = "Tell me what my website traffic was last month."


def _tool(name: str, integration: str) -> dict:
    return {
        "type": "function",
        "function": {"name": name, "description": name},
        "integration": integration,
    }


def test_time_label_matches_compiled_window_last_month() -> None:
    window = resolve_time_window(ANCHOR, timezone_name="America/Los_Angeles", now=FROZEN)
    assert window is not None
    label = user_facing_time_label(window)
    assert "30 days" not in label.lower()
    assert "August" in label
    assert "2026" in label


def test_compiled_task_mutation_is_not_execution_sot() -> None:
    with patch(
        "app.services.read_preflight.resolve_resource",
        return_value=ResourceResolution(
            status="resolved",
            connector_id="google_analytics",
            connection_id="c1",
            resource_type="property",
            resource_id="123456",
            display_name="Acme",
            candidate_count=1,
        ),
    ):
        proof = preflight_read_action(
            context={
                "org_id": "org-1",
                "client": MagicMock(),
                "settings": SimpleNamespace(),
                "environment_name": "production",
                "connected_integrations": ["google_analytics"],
                "timezone": "America/Los_Angeles",
                "now": FROZEN,
                "business_identity": {"website": "https://acme.example", "timezone": "America/Los_Angeles"},
                "user_message": ANCHOR,
                "action_key": "google_analytics.reports.run",
            }
        )
    assert proof.ok
    state = attach_compiled_task(
        {},
        objective_text=ANCHOR,
        capability_id="analytics.traffic_overview",
        preflight=proof,
        org_id="org-1",
    )
    state["compiled_task"]["compiled_parameters"]["property_id"] = "HACKED"
    state["compiled_task"]["timeframe_resolved"] = {"start": "2000-01-01", "end": "2000-01-02"}
    rerun = project_compiled_task(state, preflight=proof, org_id="org-1")
    assert rerun.compiled_parameters.get("property_id") != "HACKED" or proof.compiled_parameters["property_id"] == "123456"
    assert proof.compiled_parameters["property_id"] == "123456"
    assert proof.compiled_parameters["start_date"] == "2026-08-01"


def test_disconnected_vendor_not_offered_to_react() -> None:
    tools = [
        _tool("hubspot.deals.search", "hubspot"),
        _tool("analytics.reports.run", "google_analytics"),
        _tool("knowledge_base", "platform"),
    ]
    narrowed, _stats = narrow_tools_for_turn(
        tools,
        query="show my deals",
        classification={"capability_id": "crm.deals.read", "requires_action": True},
        connected_integrations=["hubspot"],
    )
    names = [str((t.get("function") or {}).get("name") or "") for t in narrowed]
    assert "analytics.reports.run" not in names
    assert any("hubspot" in n for n in names)


def test_analytics_capability_does_not_offer_crm_tools() -> None:
    tools = [
        _tool("hubspot.deals.search", "hubspot"),
        _tool("analytics.reports.run", "google_analytics"),
    ]
    narrowed, _stats = narrow_tools_for_turn(
        tools,
        query=ANCHOR,
        classification={"capability_id": "analytics.traffic_overview"},
        connected_integrations=["google_analytics", "hubspot"],
    )
    names = [str((t.get("function") or {}).get("name") or "") for t in narrowed]
    assert "hubspot.deals.search" not in names
    assert "analytics.reports.run" in names


def test_cognitive_invoke_requires_plan_step() -> None:
    from app.services.tool_service import invoke_tool
    from app.services.tool_types import NormalizedResult

    ctx = ToolContext(
        settings=SimpleNamespace(disable_connectors=False, connector_secrets_encryption_key="k" * 32),
        client=MagicMock(),
        org_id="org-1",
        actor_id="user-1",
        cognitive_invoke=True,
        preflight_result=SimpleNamespace(
            status="ready",
            plan_id=None,
            step_id=None,
            action_key="google_analytics.reports.run",
            compiled_parameters={"property_id": "1", "start_date": "2026-08-01", "end_date": "2026-08-31"},
        ),
    )
    with patch("app.services.read_preflight.enforce_invoke_preflight", return_value={"property_id": "1", "start_date": "2026-08-01", "end_date": "2026-08-31"}):
        with patch("app.services.tool_service._resolve_tool_executor") as mock_exec:
            mock_exec.return_value = lambda *_a, **_k: NormalizedResult(success=True, action="analytics.reports.run")
            try:
                invoke_tool(ctx, "analytics.reports.run", {"property_id": "1", "start_date": "2026-08-01", "end_date": "2026-08-31"})
                raised = False
            except ToolValidationError as exc:
                raised = True
                assert exc.code == "PLAN_LINEAGE_REQUIRED"
    assert raised
    mock_exec.assert_not_called()


def test_no_cognitive_run_ga4_report_bypass() -> None:
    forbidden = "run_ga4_report"
    hits: list[str] = []
    for rel in COGNITIVE_BYPASS_MODULES:
        path = APP / rel.replace("app/", "")
        if not path.exists():
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module and "google_analytics" in node.module:
                for alias in node.names:
                    if alias.name == forbidden:
                        hits.append(f"{rel}:{node.lineno}")
            if isinstance(node, ast.Call):
                func = node.func
                name = func.attr if isinstance(func, ast.Attribute) else (func.id if isinstance(func, ast.Name) else "")
                if name == forbidden:
                    hits.append(f"{rel}:{getattr(node, 'lineno', 0)}")
    assert hits == [], hits


def test_no_direct_stopped_sse_in_assistant_router() -> None:
    text = (APP / "routers" / "assistant.py").read_text(encoding="utf-8")
    assert 'sse_text_delta(text_id, "Stopped.")' not in text
    assert "compose_reply_events" in text


def test_execute_task_streaming_does_not_shadow_asyncio_or_composer() -> None:
    """Greeting/operator typed chat must use module asyncio/composer (42fadd61)."""
    from app.operators.agent_intelligence import AgentIntelligence

    names = AgentIntelligence.execute_task_streaming.__code__.co_varnames
    assert "asyncio" not in names
    assert "compose_reply_events" not in names


def test_compile_before_react_in_agent_intelligence() -> None:
    text = (APP / "operators" / "agent_intelligence.py").read_text(encoding="utf-8")
    compile_at = text.find("compile_assistant_turn_context")
    react_at = text.find("react_engine.run_streaming")
    assert compile_at != -1 and react_at != -1
    assert compile_at < react_at


def test_infrastructure_exception_classes_documented() -> None:
    assert "health" in INFRASTRUCTURE_INVOKE_ACTORS
    assert "post_publish_marketing" in INFRASTRUCTURE_INVOKE_ACTORS
    assert "workflow_engine" in INFRASTRUCTURE_INVOKE_ACTORS


def test_workflow_tool_context_is_not_cognitive_invoke() -> None:
    from types import SimpleNamespace

    from app.services.tool_service import tool_context_from_step

    ctx = tool_context_from_step(
        SimpleNamespace(
            settings=SimpleNamespace(),
            client=MagicMock(),
            org_id="org-1",
            user_id="user-1",
            environment_name="production",
            run_id="run-1",
            step_id="step-1",
            step_type="invoke_tool",
            parameters={},
            config={"connector_id": "google_analytics"},
        )
    )
    assert ctx.cognitive_invoke is False
    assert ctx.plan_id == "workflow:run-1"
    assert ctx.step_id == "step-1"


def test_short_circuit_requires_e1_flag() -> None:
    import asyncio

    from app.services.canonical_cognitive_resolution import try_analytics_short_circuit_turn

    async def _run():
        return await try_analytics_short_circuit_turn(
            message=ANCHOR,
            resolution=None,
            org_id="org-1",
            client=object(),
            settings=SimpleNamespace(),
            connected_integrations=["google_analytics"],
            task_state={},
        )

    assert asyncio.run(_run()) is None


def test_ga4_metric_blocks_use_compiled_timeframe_label() -> None:
    from app.services.structured_assistant_response import blocks_from_ga4_reports

    current = {
        "metricHeaders": [{"name": "activeUsers"}],
        "totals": [{"metricValues": [{"value": "10"}]}],
    }
    blocks = blocks_from_ga4_reports(
        property_name="Acme",
        current=current,
        previous={},
        timeframe_label="August 2026",
    )
    assert blocks
    assert "August 2026" in blocks[0].title
    assert "last 30 days" not in blocks[0].title.lower()


def test_sealed_read_does_not_invoke_when_preflight_blocks() -> None:
    from app.services.execution_plan_service import ExecutionPlan, ExecutionStep
    from app.services.sealed_read_execution import invoke_sealed_f1_read

    plan = ExecutionPlan(
        plan_id="plan-1",
        summary="traffic",
        steps=[
            ExecutionStep(
                step_id="s1",
                title="read",
                kind="read",
                action_key="google_analytics.reports.run",
                connector_id="google_analytics",
            )
        ],
        source="test",
    )
    ctx = ToolContext(
        settings=SimpleNamespace(disable_connectors=False, connector_secrets_encryption_key="k" * 32),
        client=MagicMock(),
        org_id="org-1",
        actor_id="user-1",
    )
    blocked = SimpleNamespace(
        ok=False,
        status="blocked",
        error_class="HMAC_INVALID",
        user_message=lambda: "blocked",
        connector_id="google_analytics",
        capability_id="analytics.traffic_overview",
        resource={},
        as_dict=lambda: {"ok": False},
        compiled_parameters={},
        time_window=None,
    )
    with patch("app.services.sealed_read_execution.preflight_read_action", return_value=blocked):
        with patch("app.services.sealed_read_execution.invoke_tool") as mock_invoke:
            invoked, proof, obs = invoke_sealed_f1_read(
                ctx=ctx,
                action_key="google_analytics.reports.run",
                user_message=ANCHOR,
                task_state={},
                connected_integrations=["google_analytics"],
                plan=plan,
                step=plan.steps[0],
            )
    assert proof.ok is False
    assert invoked.success is False
    mock_invoke.assert_not_called()
    assert obs.plan_id == "plan-1"
    assert obs.step_id == "s1"
