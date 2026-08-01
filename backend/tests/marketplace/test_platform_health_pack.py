"""Platform Health self-signal pack unit tests."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

from app.marketplace.intelligence_packs.catalog import get_intelligence_pack_spec, list_intelligence_pack_specs
from app.services.catalog_write_authority import invoke_action_requires_write_approval
from app.services.tool_service import list_registered_actions


def test_platform_health_pack_in_catalog():
    spec = get_intelligence_pack_spec("platform-health-intelligence-pack")
    assert spec is not None
    assert spec.demo_agent_name == "Platform Reliability Analyst"
    assert spec.connector_template_id is None
    assert spec.demo_systems == ["platform"]
    actions = {
        s.get("config", {}).get("action")
        for s in spec.workflow_steps
        if s.get("type") == "invoke_tool"
    }
    assert actions == {"platform.health.snapshot"}
    assert any(s.get("type") == "agent" for s in spec.workflow_steps)
    assert "platform-health-intelligence-pack" in {s.pack_id for s in list_intelligence_pack_specs()}


def test_platform_health_action_registered_and_read_only():
    assert "platform.health.snapshot" in set(list_registered_actions())
    assert invoke_action_requires_write_approval("platform.health.snapshot") is False


def test_platform_health_snapshot_emits_notification():
    from types import SimpleNamespace

    from app.services.platform_health_tools import exec_platform_health_snapshot
    from app.services.tool_types import ToolContext

    ctx = ToolContext(
        settings=SimpleNamespace(),
        client=MagicMock(),
        org_id="org-1",
        actor_id="actor-1",
    )
    health = {
        "score": 72,
        "grade": "at_risk",
        "dimensions": {
            "approvalLatency": {
                "score": 50,
                "p95LatencyMinutes": 60 * 24 * 2.4,
                "pendingApprovals": 12,
            },
            "workflowSuccessRate": {"score": 80},
            "connectorsLive": {"score": 90},
            "agentUtilization": {"score": 70},
        },
    }
    with (
        patch(
            "app.services.integration_health_score_service.get_integration_health_score",
            return_value=health,
        ),
        patch("app.services.platform_health_tools._stalled_run_count", return_value=3),
        patch("app.services.platform_health_tools._pending_approvals", return_value=12),
        patch("app.services.platform_health_tools._count_audit_actions", return_value=0),
        patch("app.services.intelligence_pack_tools.emit_pack_source_notification") as emit,
    ):
        result = exec_platform_health_snapshot(ctx, {})

    assert result.success is True
    assert result.data.get("result_url")
    assert result.data["kpis"]["approvalP95Days"] == 2.4
    assert any(r["id"] == "rec.approval_sla" for r in result.data["recommendations"])
    emit.assert_called_once()
    assert emit.call_args.kwargs["action"] == "platform.health.snapshot"
    assert "2.4" in (emit.call_args.kwargs.get("body") or "")
