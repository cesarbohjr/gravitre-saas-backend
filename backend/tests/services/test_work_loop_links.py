"""Proposal -> Play run -> goal loop (work_loop_links_enabled)."""
from __future__ import annotations

import asyncio
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException

from tests.services.test_phase5_operational import _DB, ORG, OTHER

WO = "00000000-0000-4000-8000-0000000000a1"
FOREIGN_WO = "00000000-0000-4000-8000-0000000000f1"
WF = "00000000-0000-4000-8000-0000000000b1"
OFF = SimpleNamespace(work_object_proposals_enabled=True)
LOOP = SimpleNamespace(work_object_proposals_enabled=True, work_loop_links_enabled=True)
LOOP_GOALS = SimpleNamespace(
    work_object_proposals_enabled=True, work_loop_links_enabled=True, goal_links_enabled=True
)


def _seed() -> _DB:
    db = _DB()
    db.tables["goals"] = [{"id": "g1", "org_id": ORG}, {"id": "g-foreign", "org_id": OTHER}]
    db.tables["org_business_entities"] = [
        {"id": "e1", "org_id": ORG},
        {"id": "e2", "org_id": ORG},
        {"id": "e-foreign", "org_id": OTHER},
    ]
    db.tables["work_objects"] = [
        {
            "id": WO,
            "org_id": ORG,
            "status": "planned",
            "title": "Rescue Acme",
            "object_type": "other",
            "business_entity_id": "e1",
            "metadata": {"proposal": {"play_key": "customer-rescue", "source": "account_health"}},
        },
        {"id": FOREIGN_WO, "org_id": OTHER, "status": "planned", "title": "Theirs", "object_type": "other"},
        {"id": "p-open", "org_id": ORG, "status": "proposed", "title": "P", "object_type": "other"},
    ]
    db.tables["play_installations"] = [
        {
            "id": "inst-1",
            "org_id": ORG,
            "play_key": "customer-rescue",
            "environment_name": "production",
            "operating_mode": "ACT WITH APPROVAL",
            "status": "ready",
            "goal_id": "g1",
        }
    ]
    return db


# --------------------------------------------------------------------------- run link validation


def test_run_request_accepts_work_object_and_entity_aliases():
    from app.routers.plays import RunPlayRequest

    body = RunPlayRequest.model_validate({"installationId": "i", "workObjectId": WO, "businessEntityId": "e1"})
    assert body.work_object_id == WO and body.business_entity_id == "e1"
    assert RunPlayRequest.model_validate({"installationId": "i"}).work_object_id is None


def test_run_links_are_off_by_default_and_org_scoped():
    from app.services.work_loop_links import WorkLoopLinkError, resolve_run_links

    db = _seed()
    assert resolve_run_links(db, OFF, org_id=ORG, work_object_id=None, business_entity_id=" ") == (None, None)
    with pytest.raises(WorkLoopLinkError, match="not enabled"):
        resolve_run_links(db, OFF, org_id=ORG, work_object_id=WO, business_entity_id=None)
    with pytest.raises(WorkLoopLinkError, match="work object not found"):
        resolve_run_links(db, LOOP, org_id=ORG, work_object_id=FOREIGN_WO, business_entity_id=None)
    with pytest.raises(WorkLoopLinkError, match="business entity not found"):
        resolve_run_links(db, LOOP, org_id=ORG, work_object_id=None, business_entity_id="e-foreign")
    with pytest.raises(WorkLoopLinkError, match="accept the proposal"):
        resolve_run_links(db, LOOP, org_id=ORG, work_object_id="p-open", business_entity_id=None)
    with pytest.raises(WorkLoopLinkError, match="does not match"):
        resolve_run_links(db, LOOP, org_id=ORG, work_object_id=WO, business_entity_id="e2")
    work_object, entity = resolve_run_links(db, LOOP, org_id=ORG, work_object_id=WO, business_entity_id=None)
    assert work_object["id"] == WO and entity == "e1"  # inherited from the work object
    assert resolve_run_links(db, LOOP, org_id=ORG, work_object_id=None, business_entity_id="e2") == (None, "e2")


def test_play_run_work_object_reaches_the_outcome_only_with_the_flag():
    from app.services.work_loop_links import play_run_work_object_id

    params = {"play": {"key": "customer-rescue", "work_object_id": WO}}
    assert play_run_work_object_id(OFF, params) is None
    assert play_run_work_object_id(LOOP, params) == WO
    assert play_run_work_object_id(LOOP, {"work_object_id": WO}) is None  # only the Play route sets it
    assert play_run_work_object_id(LOOP, None) is None


# --------------------------------------------------------------------------- run_play end to end


def _run(db: _DB, settings: Any, body: dict[str, Any], *, approval_required: bool = True):
    import app.main  # noqa: F401 - loads app.routers.workflows (patched below) in import order
    from app.routers import plays
    from app.routers.plays import RunPlayRequest

    execute = AsyncMock(
        side_effect=[
            {"run_id": "run-1", "status": "pending_approval", "approval_required": approval_required},
        ]
    )
    with patch.object(plays, "get_supabase_client", return_value=db), patch.object(
        plays, "connected_vendors", return_value=set()
    ), patch.object(
        plays, "resolve_play_readiness", return_value=MagicMock(act_with_approval_ready=True)
    ), patch.object(plays, "_observed_signals", return_value=None), patch.object(
        plays, "list_play_workflow_bindings", return_value=[{"workflowId": WF}]
    ), patch.object(plays, "get_workflow_def", return_value={"id": WF}), patch.object(
        plays, "resolve_policy", return_value=(1, ["admin"])
    ), patch.object(plays, "write_audit_event") as audit, patch(
        "app.routers.workflows.execute_workflow", execute
    ):
        result = asyncio.run(
            plays.run_play(
                "customer-rescue",
                RunPlayRequest.model_validate({"installationId": "inst-1", **body}),
                ({"user_id": "u1"}, ORG, "member"),
                "production",
                settings,
            )
        )
    return result, execute, audit


def test_play_run_links_the_work_object_and_carries_the_entity():
    db = _seed()
    result, execute, audit = _run(db, LOOP_GOALS, {"workObjectId": WO})
    assert result["workObjectId"] == WO and result["workObjectLinked"] is True
    assert result["businessEntityId"] == "e1" and result["status"] == "awaiting_approval"

    play_params = execute.await_args.args[0].parameters["play"]
    assert play_params["work_object_id"] == WO and play_params["business_entity_id"] == "e1"
    play_run = db.tables["play_runs"][0]
    assert play_run["metadata"]["work_object_id"] == WO and play_run["metadata"]["business_entity_id"] == "e1"

    events = db.tables["work_object_events"]
    assert len(events) == 1 and events[0]["run_id"] == "run-1" and events[0]["event_type"] == "play_run_started"
    assert events[0]["org_id"] == ORG and events[0]["work_object_id"] == WO
    wo = next(w for w in db.tables["work_objects"] if w["id"] == WO)
    assert wo["status"] == "awaiting_approval"  # approval gate still owns the action
    assert wo["business_outcome_refs"] == ["run-1"]
    assert wo["goal_id"] == "g1"  # inherited from the Play setup
    assert audit.call_args.kwargs["metadata"]["work_object_id"] == WO


def test_play_run_inherits_a_goal_only_from_this_org_and_only_with_goal_links():
    db = _seed()
    db.tables["play_installations"][0]["goal_id"] = None
    _run(db, LOOP_GOALS, {"workObjectId": WO, "objectiveId": "g-foreign"})
    assert "goal_id" not in next(w for w in db.tables["work_objects"] if w["id"] == WO)

    db = _seed()
    _run(db, LOOP, {"workObjectId": WO})  # goal_links_enabled off: no goal column write
    wo = next(w for w in db.tables["work_objects"] if w["id"] == WO)
    assert "goal_id" not in wo and wo["status"] == "awaiting_approval"


def test_play_run_without_links_is_unchanged():
    db = _seed()
    result, execute, _audit = _run(db, OFF, {})
    assert "workObjectId" not in result
    assert "work_object_id" not in execute.await_args.args[0].parameters["play"]
    assert db.tables.get("work_object_events") is None
    assert db.tables["play_runs"][0]["metadata"] == {"execution_authority": "canonical_workflow_runtime"}


@pytest.mark.parametrize(
    ("settings", "body", "code"),
    [
        (OFF, {"workObjectId": WO}, 422),
        (LOOP, {"workObjectId": FOREIGN_WO}, 400),
        (LOOP, {"businessEntityId": "e-foreign"}, 400),
        (LOOP, {"workObjectId": "p-open"}, 400),
    ],
)
def test_play_run_rejects_bad_links_before_anything_starts(settings, body, code):
    db = _seed()
    with pytest.raises(HTTPException) as e:
        _run(db, settings, body)
    assert e.value.status_code == code
    assert "play_runs" not in db.tables and "work_object_events" not in db.tables


# --------------------------------------------------------------------------- proposals


def _propose(db: _DB, settings: Any, **extra: Any) -> dict[str, Any]:
    from app.services.work_object_proposals import propose_work_object

    return propose_work_object(
        db,
        settings,
        org_id=ORG,
        title="Review Acme",
        dedupe_key=f"k-{len(db.tables.get('work_objects', []))}",
        source="account_health",
        evidence=[{"summary": "usage falling"}],
        **extra,
    )


def test_proposals_inherit_the_play_setup_goal_when_enabled():
    db = _seed()
    _propose(db, LOOP_GOALS, play_key="customer-rescue")
    assert db.tables["work_objects"][-1]["goal_id"] == "g1"
    _propose(db, LOOP, play_key="customer-rescue")  # goal links off
    assert "goal_id" not in db.tables["work_objects"][-1]
    _propose(db, LOOP_GOALS, play_key="client-risk-radar")  # no setup for this Play
    assert "goal_id" not in db.tables["work_objects"][-1]
    _propose(db, LOOP_GOALS, play_key="customer-rescue", goal_id="g-explicit")
    assert db.tables["work_objects"][-1]["goal_id"] == "g-explicit"


def test_inherited_goal_skips_archived_setups_and_other_orgs():
    from app.services.work_loop_links import installation_goal_id

    db = _seed()
    db.tables["play_installations"] = [
        {"id": "a", "org_id": ORG, "play_key": "customer-rescue", "status": "archived", "goal_id": "g-old"},
        {"id": "b", "org_id": OTHER, "play_key": "customer-rescue", "status": "ready", "goal_id": "g-foreign"},
    ]
    assert installation_goal_id(db, ORG, "customer-rescue") is None


def _accept(db: _DB, settings: Any, work_object_id: str):
    from app.routers import work_objects
    from app.routers.work_objects import ProposalDecisionRequest

    with patch.object(work_objects, "get_supabase_client", return_value=db), patch(
        "app.workflows.audit.write_audit_event"
    ):
        return work_objects.accept_proposal_route(
            work_object_id, ProposalDecisionRequest(), {"user_id": "u1"}, ORG, settings, "production"
        )


def test_accepting_a_play_proposal_returns_the_run_request_and_starts_nothing():
    db = _seed()
    db.tables["work_objects"][0]["status"] = "proposed"
    out = _accept(db, LOOP, WO)
    assert out["workObject"] == {"id": WO, "status": "planned"}
    req = out["playRunRequest"]
    assert req["method"] == "POST" and req["path"] == "/api/plays/customer-rescue/runs"
    assert req["body"] == {"workObjectId": WO, "businessEntityId": "e1", "installationId": "inst-1"}
    assert req["operatingMode"] == "ACT WITH APPROVAL" and "blockedReason" not in req
    assert "play_runs" not in db.tables and "work_object_events" not in db.tables


def test_accept_without_flag_setup_or_play_has_no_run_request():
    db = _seed()
    db.tables["work_objects"][0]["status"] = "proposed"
    assert "playRunRequest" not in _accept(db, OFF, WO)

    db = _seed()
    db.tables["work_objects"][0]["status"] = "proposed"
    db.tables["play_installations"] = []
    req = _accept(db, LOOP, WO)["playRunRequest"]
    assert req["blockedReason"] and "installationId" not in req["body"]

    db = _seed()
    db.tables["work_objects"][0].update(status="proposed", metadata={"proposal": {}})
    assert "playRunRequest" not in _accept(db, LOOP, WO)


# --------------------------------------------------------------------------- create / patch


def _create(db: _DB, settings: Any, body: dict[str, Any], org: str | None = ORG):
    from app.routers import work_objects
    from app.routers.work_objects import CreateWorkObjectRequest

    with patch.object(work_objects, "get_supabase_client", return_value=db), patch(
        "app.workflows.audit.write_audit_event"
    ):
        return work_objects.create_work_object_route(
            CreateWorkObjectRequest.model_validate(body), {"user_id": "u1"}, org, settings
        )


def _patch(db: _DB, settings: Any, work_object_id: str, body: dict[str, Any]):
    from app.routers import work_objects
    from app.routers.work_objects import PatchWorkObjectLinksRequest

    with patch.object(work_objects, "get_supabase_client", return_value=db), patch(
        "app.workflows.audit.write_audit_event"
    ):
        return work_objects.patch_work_object_links_route(
            work_object_id, PatchWorkObjectLinksRequest.model_validate(body), {"user_id": "u1"}, ORG, settings
        )


def test_create_writes_the_goal_link_that_goal_progress_counts():
    from app.services.goal_records import goal_link_progress

    db = _seed()
    created = _create(db, LOOP_GOALS, {"title": "Win back Acme", "goalId": "g1", "businessEntityId": "e1"})["workObject"]
    assert created["goalId"] == "g1" and created["businessEntityId"] == "e1" and created["status"] == "planned"
    assert created["orgId"] == ORG
    assert goal_link_progress(db, ORG, "g1")["linkedWork"]["total"] == 1
    plain = _create(db, LOOP, {"title": "No links"})["workObject"]
    assert plain["goalId"] is None


@pytest.mark.parametrize(
    ("settings", "body", "org", "code"),
    [
        (OFF, {"title": "x"}, ORG, 404),
        (LOOP, {"title": "x"}, None, 403),
        (LOOP, {"title": "x", "goalId": "g1"}, ORG, 422),
        (LOOP_GOALS, {"title": "x", "goalId": "g-foreign"}, ORG, 400),
        (LOOP_GOALS, {"title": "x", "businessEntityId": "e-foreign"}, ORG, 400),
    ],
)
def test_create_is_flagged_and_rejects_foreign_links(settings, body, org, code):
    db = _seed()
    before = len(db.tables["work_objects"])
    with pytest.raises(HTTPException) as e:
        _create(db, settings, body, org)
    assert e.value.status_code == code
    assert len(db.tables["work_objects"]) == before


def test_patch_links_and_unlinks_a_goal_in_this_org_only():
    db = _seed()
    out = _patch(db, LOOP_GOALS, WO, {"goalId": "g1"})["workObject"]
    assert out["goalId"] == "g1" and out["businessEntityId"] == "e1"  # untouched field kept
    out = _patch(db, LOOP_GOALS, WO, {"goalId": None})["workObject"]
    assert out["goalId"] is None
    for wo, body, code in (
        (FOREIGN_WO, {"goalId": "g1"}, 404),
        (WO, {"goalId": "g-foreign"}, 400),
        (WO, {"businessEntityId": "e-foreign"}, 400),
        (WO, {}, 400),
    ):
        with pytest.raises(HTTPException) as e:
            _patch(db, LOOP_GOALS, wo, body)
        assert e.value.status_code == code
    with pytest.raises(HTTPException) as e:
        _patch(db, OFF, WO, {"goalId": "g1"})
    assert e.value.status_code == 404
    with pytest.raises(HTTPException) as e:
        _patch(db, LOOP, WO, {"goalId": "g1"})
    assert e.value.status_code == 422
    foreign = next(w for w in db.tables["work_objects"] if w["id"] == FOREIGN_WO)
    assert "goal_id" not in foreign


# --------------------------------------------------------------------------- outcome attribution


def test_play_run_outcome_is_attributed_to_the_linked_work_object():
    from app.services.work_loop_links import play_run_work_object_id
    from app.services.work_object_service import record_execution_work_object

    db = _seed()
    before = len(db.tables["work_objects"])
    meta = {"path": "execute_workflow_steps", "work_object_id": play_run_work_object_id(LOOP, {"play": {"work_object_id": WO}})}
    ref = record_execution_work_object(
        db, org_id=ORG, run_id="run-1", terminal_status="flagged_for_review", metadata=meta, verified_output=None
    )
    assert ref["work_object_id"] == WO and len(db.tables["work_objects"]) == before
    assert db.tables["work_object_events"][-1]["work_object_id"] == WO
    # A foreign id never attaches the outcome to another org's work.
    ref = record_execution_work_object(
        db, org_id=ORG, run_id="run-2", terminal_status="failed", metadata={"work_object_id": FOREIGN_WO}, verified_output=None
    )
    assert ref["work_object_id"] != FOREIGN_WO


def test_both_finalize_paths_read_the_play_work_object():
    from pathlib import Path

    root = Path(__file__).resolve().parents[2] / "app" / "workflows"
    for name in ("execute.py", "execution_engine_runtime.py"):
        assert "play_run_work_object_id(" in (root / name).read_text()
