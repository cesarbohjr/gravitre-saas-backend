"""BusinessOutcome projection — pipeline order, omit-empty, catalog undo, shared renderer."""
from __future__ import annotations

import ast
import inspect
from pathlib import Path

import pytest

from app.services.business_outcome.catalog_reversal import (
    get_compensating_action,
    supports_vendor_diff,
    undo_availability,
)
from app.services.business_outcome.models import BusinessOutcome
from app.services.business_outcome.pipeline import PipelineContext, run_business_outcome_pipeline
from app.services.business_outcome.projector import project_business_outcome
from app.services.compensation_service import authorize_compensation_write
from app.services.recommendation_heuristics_service import assert_no_execute_surface

REPO = Path(__file__).resolve().parents[3]
BO_PKG = REPO / "backend" / "app" / "services" / "business_outcome"
COMP_PATH = REPO / "backend" / "app" / "services" / "compensation_service.py"
CHAT_PANEL = (
    REPO
    / "apps"
    / "web"
    / "components"
    / "gravitre"
    / "assistant"
    / "chat-execution-panel.tsx"
)
RUNS_PAGE = REPO / "apps" / "web" / "app" / "runs" / "[id]" / "page.tsx"
VIEW_PATH = (
    REPO
    / "apps"
    / "web"
    / "components"
    / "gravitre"
    / "business-outcome"
    / "business-outcome-view.tsx"
)

BANNED_EXECUTE = (
    "execute_plan",
    "invoke_tool",
    "execute_write_action",
    "ToolRegistry",
)


def _sample_run(**overrides):
    base = {
        "id": "11111111-1111-1111-1111-111111111111",
        "status": "completed",
        "created_at": "2026-07-20T12:00:00Z",
        "parameters": {
            "invoke_action": "hubspot.contacts.create",
            "integration": "hubspot",
            "label": "Create contact",
            "conversation_id": "22222222-2222-2222-2222-222222222222",
        },
        "approval_status": "not_required",
    }
    base.update(overrides)
    return base


def test_pipeline_stage_order_is_strict():
    ctx = PipelineContext(
        org_id="org-1",
        run=_sample_run(),
        execution_result={
            "success": True,
            "title": "Create contact",
            "body": "Created contact Jane",
            "result_url": "/runs/11111111-1111-1111-1111-111111111111",
            "external_url": "https://app.hubspot.com/contacts/1",
            "integration": "hubspot",
            "entity_type": "contact",
            "entity_id": "c1",
        },
        invoke_action="hubspot.contacts.create",
        notification_emitted=True,
    )
    outcome = run_business_outcome_pipeline(ctx)
    assert outcome.pipeline_stages_completed == [
        "verify",
        "normalize",
        "business_outcome",
        "memory",
        "recommendation",
        "notification",
    ]
    assert outcome.projection == "business_outcome"
    assert "presented" in outcome.lifecycle_states_reached


def test_omits_fabricated_sections():
    outcome = project_business_outcome(
        org_id="org-1",
        run=_sample_run(),
        execution_result={
            "success": True,
            "title": "Create contact",
            "body": "Created contact Jane",
            "result_url": "/runs/r1",
        },
        invoke_action="hubspot.contacts.create",
    )
    d = outcome.to_dict()
    sections = d["sections"]
    assert "summary" in sections
    assert "impact" not in sections
    assert "relatedOutcomes" not in sections and "related_outcomes" not in sections
    assert "dependencies" not in sections
    assert "history" not in sections
    assert d["lifecycleState"] in {"created", "verified", "presented", "approved", "undone"}
    for banned in ("reviewed", "edited", "referenced", "archived"):
        assert banned not in d["lifecycleStatesReached"]


def test_undo_available_for_catalog_reversible_action():
    info = undo_availability("hubspot.contacts.create")
    assert info["available"] is True
    assert info["compensating_action"] == "hubspot.contacts.delete"
    assert get_compensating_action("hubspot.contacts.create") == "hubspot.contacts.delete"


def test_undo_honest_for_irreversible_action():
    for action in ("gmail.messages.send", "apollo.lists.create"):
        info = undo_availability(action)
        assert info["available"] is False, action
        assert info["compensating_action"] is None
        assert "cannot be reversed" in (info["honest_unavailable_reason"] or "").lower()
        outcome = project_business_outcome(
            org_id="org-1",
            run=_sample_run(parameters={"invoke_action": action, "label": action}),
            execution_result={"success": True, "title": action, "body": "done", "result_url": "/runs/r"},
            invoke_action=action,
        )
        undo = outcome.to_dict()["sections"]["undo"]
        assert undo["available"] is False
        assert undo["honestUnavailableReason"]


def test_diff_never_fabricates_prior():
    assert supports_vendor_diff("hubspot.contacts.update") is True
    outcome = project_business_outcome(
        org_id="org-1",
        run=_sample_run(parameters={"invoke_action": "hubspot.contacts.update"}),
        execution_result={"success": True, "title": "Update", "body": "ok", "result_url": "/r"},
        invoke_action="hubspot.contacts.update",
        compensation_snapshot=None,
    )
    diff = outcome.to_dict()["sections"]["diff"]
    assert diff["available"] is False
    assert diff["prior"] is None
    assert "no prior snapshot" in (diff["note"] or "").lower()

    with_snap = project_business_outcome(
        org_id="org-1",
        run=_sample_run(parameters={"invoke_action": "hubspot.contacts.update"}),
        execution_result={"success": True, "title": "Update", "body": "ok", "result_url": "/r"},
        invoke_action="hubspot.contacts.update",
        compensation_snapshot={"properties": {"email": "a@b.com"}},
    )
    diff2 = with_snap.to_dict()["sections"]["diff"]
    assert diff2["available"] is True
    assert diff2["prior"] == {"properties": {"email": "a@b.com"}}


def test_recommendation_stage_is_suggest_only():
    ctx = PipelineContext(
        org_id="org-1",
        run=_sample_run(),
        execution_result={
            "success": True,
            "title": "Done",
            "body": "ok",
            "result_url": "/r",
            "recommendation": {
                "title": "Next",
                "reason": "Because",
                "suggestedUtterance": "add contacts",
                "confidence": 0.4,
                "confidenceIsEstimate": True,
            },
        },
        invoke_action="hubspot.contacts.create",
    )
    outcome = run_business_outcome_pipeline(ctx)
    recs = outcome.to_dict()["sections"]["recommendations"]
    assert recs[0]["advisoryOnly"] is True
    assert_no_execute_surface({"recommendations": recs, "advisoryOnly": True, "actionsTaken": []})


def test_pipeline_builders_ban_execute_calls():
    for path in BO_PKG.glob("*.py"):
        src = path.read_text(encoding="utf-8")
        tree = ast.parse(src)
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                name = ""
                if isinstance(node.func, ast.Name):
                    name = node.func.id
                elif isinstance(node.func, ast.Attribute):
                    name = node.func.attr
                assert name not in BANNED_EXECUTE, f"{path.name} calls {name}"


def test_compensation_authorize_uses_catalog_write_authority():
    authorize_compensation_write("hubspot.contacts.create", "hubspot.contacts.delete")
    with pytest.raises(PermissionError):
        authorize_compensation_write("hubspot.contacts.create", "hubspot.contacts.update")
    with pytest.raises(PermissionError):
        authorize_compensation_write("gmail.messages.send", "gmail.messages.send")

    src = COMP_PATH.read_text(encoding="utf-8")
    assert "authorize_compensation_write" in src
    assert "catalog_write_authority" in src
    assert "invoke_action_requires_write_approval" in src
    # execute_compensations must authorize before the invoke_tool call (not the import).
    tree = ast.parse(src)
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == "execute_compensations":
            body_src = ast.get_source_segment(src, node) or ""
            auth_pos = body_src.find("authorize_compensation_write(")
            invoke_pos = body_src.find("invoke_tool(ctx")
            assert auth_pos >= 0 and invoke_pos > auth_pos, (
                f"authorize must precede invoke_tool(ctx): auth={auth_pos} invoke={invoke_pos}"
            )
            break
    else:
        pytest.fail("execute_compensations not found")


def test_shared_frontend_renderer_single_component():
    """Chat + timeline must import the same BusinessOutcomeView module (code-level)."""
    assert VIEW_PATH.is_file()
    chat = CHAT_PANEL.read_text(encoding="utf-8")
    runs = RUNS_PAGE.read_text(encoding="utf-8")
    marker = '@/components/gravitre/business-outcome/business-outcome-view'
    assert marker in chat
    assert marker in runs
    assert "BusinessOutcomeView" in chat
    assert "BusinessOutcomeView" in runs
    # No duplicate local renderer implementations in those surfaces.
    assert "function BusinessOutcomeView" not in chat
    assert "function BusinessOutcomeView" not in runs


def test_business_outcome_dto_is_dataclass_projection():
    assert inspect.isclass(BusinessOutcome)
    outcome = project_business_outcome(
        org_id="org-1",
        run={"id": "r1", "status": "failed", "error_message": "boom"},
        execution_result={"success": False, "title": "Failed", "body": "boom"},
    )
    assert outcome.kind == "failed_action"
    assert outcome.to_dict()["sections"]["verification"]["verified"] is False


def test_flagged_for_review_phase4_finding_on_business_outcome():
    """Phase 6 — flagged status carries Phase 4 finding + next actions (not verified)."""
    deg = {
        "flagged": True,
        "batch_class": "enrichment",
        "record_count": 6,
        "reason": "identical_value_dominance",
        "field": "industry",
        "identical_ratio": 1.0,
        "placeholder_ratio": 1.0,
        "threshold_identical": 0.8,
        "threshold_placeholder": 0.5,
        "modal_value": "cannot tell",
    }
    outcome = project_business_outcome(
        org_id="org-1",
        run=_sample_run(
            status="flagged_for_review",
            parameters={
                "invoke_action": "clay.enrich",
                "integration": "clay",
                "label": "Enrich batch",
                "outcome_effect": "flagged_for_review",
                "batch_degeneracy": deg,
            },
        ),
        execution_result={
            "success": False,
            "title": "Enrich batch",
            "body": "Enrichment returned.",
            "result_url": "/runs/11111111-1111-1111-1111-111111111111",
            "structured": {"batch_degeneracy": deg, "outcome_effect": "flagged_for_review"},
        },
        invoke_action="clay.enrich",
    )
    d = outcome.to_dict()
    assert d["status"] == "flagged_for_review"
    assert d["kind"] != "created_record"
    ver = d["sections"]["verification"]
    assert ver["verified"] is False
    assert ver["reviewState"] == "flagged_for_review"
    assert ver["checkFailed"] == "batch_degeneracy"
    assert "6 of 6" in ver["finding"]
    assert "cannot tell" in ver["finding"]
    assert ver["nextActions"]
    assert "verified" not in d["lifecycleStatesReached"]
    # Finding becomes the customer-facing summary.
    assert "6 of 6" in d["sections"]["summary"]
    assert d["sections"]["recommendations"]


def test_follow_up_proof_phase3_distinct_from_batch_degeneracy():
    """Phase 3 missing follow-up is distinguishable from Phase 4 degeneracy."""
    outcome = project_business_outcome(
        org_id="org-1",
        run=_sample_run(
            status="partial_success",
            parameters={
                "invoke_action": "apollo.lists.add",
                "outcome_effect": "accepted_async",
                "population_verify": {
                    "verified": False,
                    "detail": "follow_up_empty_membership",
                    "effect": "unknown",
                },
            },
        ),
        execution_result={
            "success": True,
            "title": "Add to list",
            "body": "Accepted",
            "result_url": "/runs/r",
            "structured": {
                "population_verify": {
                    "verified": False,
                    "detail": "follow_up_empty_membership",
                }
            },
        },
        invoke_action="apollo.lists.add",
    )
    ver = outcome.to_dict()["sections"]["verification"]
    assert ver["verified"] is False
    assert ver["checkFailed"] == "follow_up_proof"
    assert ver.get("reviewState") in (None, "")
    assert "Phase 3" in (ver.get("finding") or ver.get("detail") or "")
    assert VIEW_PATH.read_text(encoding="utf-8").count("Flagged for review") >= 1
