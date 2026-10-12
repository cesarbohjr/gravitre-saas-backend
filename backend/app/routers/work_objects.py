"""WorkObject API.

Durable business lifecycle objects that aggregate multiple BusinessOutcomes.
"""
from __future__ import annotations

from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict, Field

from app.auth.dependencies import (
    get_current_user,
    get_environment_context,
    get_org_context,
)
from app.config import Settings, get_settings
from app.core.logging import get_logger
from app.services.work_object_service import (
    get_work_object,
    list_work_object_events,
    list_work_objects,
    summarize_work_object_coverage,
)
from app.workflows.repository import get_supabase_client

logger = get_logger(__name__)

router = APIRouter(prefix="/api/work-objects", tags=["work-objects"])


@router.get("")
def list_work_objects_route(
    _user: Annotated[dict, Depends(get_current_user)],
    org_id: Annotated[str | None, Depends(get_org_context)],
    settings: Annotated[Settings, Depends(get_settings)],
    object_type: str | None = Query(default=None, alias="objectType"),
    department: str | None = Query(default=None),
    status_filter: str | None = Query(default=None, alias="status"),
    priority: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
) -> dict[str, Any]:
    if not org_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Organization context required")
    client = get_supabase_client(settings)
    items = list_work_objects(
        client,
        org_id=org_id,
        object_type=object_type,
        department=department,
        status=status_filter,
        priority=priority,
        limit=limit,
    )
    return {"workObjects": items, "count": len(items)}


@router.get("/coverage")
def work_object_coverage_route(
    _user: Annotated[dict, Depends(get_current_user)],
    org_id: Annotated[str | None, Depends(get_org_context)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict[str, Any]:
    if not org_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Organization context required")
    client = get_supabase_client(settings)
    coverage = summarize_work_object_coverage(client, org_id=org_id)
    return {"coverage": coverage}


@router.get("/{work_object_id}")
def get_work_object_route(
    work_object_id: UUID,
    _user: Annotated[dict, Depends(get_current_user)],
    org_id: Annotated[str | None, Depends(get_org_context)],
    settings: Annotated[Settings, Depends(get_settings)],
    events_limit: int = Query(default=150, ge=1, le=500, alias="eventsLimit"),
) -> dict[str, Any]:
    if not org_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Organization context required")
    client = get_supabase_client(settings)
    item = get_work_object(client, org_id=org_id, work_object_id=str(work_object_id))
    if item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="WorkObject not found")
    events = list_work_object_events(
        client,
        org_id=org_id,
        work_object_id=str(work_object_id),
        limit=events_limit,
    )
    return {"workObject": item, "events": events}


class ProposalDecisionRequest(BaseModel):
    reason: str | None = None


def _decide(
    work_object_id: UUID,
    body: ProposalDecisionRequest,
    user: dict,
    org_id: str | None,
    settings: Settings,
    *,
    accept: bool,
    environment_name: str = "production",
) -> dict[str, Any]:
    from app.services.work_object_proposals import (
        ProposalError,
        decide_proposal,
        proposals_enabled,
    )
    from app.workflows.audit import write_audit_event

    if not proposals_enabled(settings):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    if not org_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Organization context required")
    client = get_supabase_client(settings)
    try:
        result = decide_proposal(
            client,
            org_id=org_id,
            work_object_id=str(work_object_id),
            actor_id=str(user.get("user_id") or ""),
            accept=accept,
            reason=body.reason,
        )
    except ProposalError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    if result is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="WorkObject not found")
    write_audit_event(
        client,
        org_id=org_id,
        actor_id=str(user.get("user_id") or ""),
        action="work_object.proposal_accepted" if accept else "work_object.proposal_dismissed",
        resource_type="work_object",
        resource_id=str(work_object_id),
        metadata={"reason": body.reason},
    )
    response: dict[str, Any] = {"workObject": {"id": result["id"], "status": result["status"]}}
    if accept:
        from app.services.work_loop_links import (
            play_run_request_for_proposal,
            work_loop_links_enabled,
        )

        if work_loop_links_enabled(settings):
            # Accepting never starts work: hand back the governed Play run request.
            try:
                run_request = play_run_request_for_proposal(
                    client,
                    org_id=org_id,
                    environment_name=environment_name,
                    work_object=result,
                )
            except Exception as exc:  # noqa: BLE001 - the decision is already saved
                logger.warning("proposal_play_run_request_failed work_object_id=%s error=%s", work_object_id, exc)
                run_request = None
            if run_request is not None:
                response["playRunRequest"] = run_request
    return response


@router.post("/{work_object_id}/accept")
def accept_proposal_route(
    work_object_id: UUID,
    body: ProposalDecisionRequest,
    user: Annotated[dict, Depends(get_current_user)],
    org_id: Annotated[str | None, Depends(get_org_context)],
    settings: Annotated[Settings, Depends(get_settings)],
    environment_name: Annotated[str, Depends(get_environment_context)],
) -> dict[str, Any]:
    """Turn an AI proposal into planned work. Nothing runs until someone starts it.

    With work_loop_links_enabled, a proposal that names a Play also returns
    ``playRunRequest``: the ``POST /api/plays/{key}/runs`` call that starts it
    through the Play's approval-gated run path.
    """
    return _decide(work_object_id, body, user, org_id, settings, accept=True, environment_name=environment_name)


@router.post("/{work_object_id}/dismiss")
def dismiss_proposal_route(
    work_object_id: UUID,
    body: ProposalDecisionRequest,
    user: Annotated[dict, Depends(get_current_user)],
    org_id: Annotated[str | None, Depends(get_org_context)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict[str, Any]:
    return _decide(work_object_id, body, user, org_id, settings, accept=False)


# --------------------------------------------------------------------------- create / re-link


class CreateWorkObjectRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    title: str = Field(..., min_length=1, max_length=220)
    objective: str | None = Field(default=None, max_length=2000)
    object_type: str = Field(default="objective", alias="objectType")
    department: str | None = None
    priority: str = "medium"
    goal_id: str | None = Field(default=None, alias="goalId", max_length=64)
    business_entity_id: str | None = Field(default=None, alias="businessEntityId", max_length=64)


class PatchWorkObjectLinksRequest(BaseModel):
    """Only the fields sent are changed; ``null`` unlinks."""

    model_config = ConfigDict(populate_by_name=True)

    goal_id: str | None = Field(default=None, alias="goalId", max_length=64)
    business_entity_id: str | None = Field(default=None, alias="businessEntityId", max_length=64)


def _links_client(settings: Settings, org_id: str | None, *, wants_links: bool) -> tuple[Any, str]:
    from app.services.work_loop_links import (
        goal_links_writable,
        work_loop_links_enabled,
    )

    if not work_loop_links_enabled(settings):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    if not org_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Organization context required")
    if wants_links and not goal_links_writable(settings):
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Goal links are not enabled")
    return get_supabase_client(settings), org_id


def _checked_links(client: Any, org_id: str, goal_id: str | None, entity_id: str | None) -> tuple[str | None, str | None]:
    from app.services.work_loop_links import (
        WorkLoopLinkError,
        require_org_business_entity,
        require_org_goal,
    )

    try:
        return require_org_goal(client, org_id, goal_id), require_org_business_entity(client, org_id, entity_id)
    except WorkLoopLinkError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.post("", status_code=status.HTTP_201_CREATED)
def create_work_object_route(
    body: CreateWorkObjectRequest,
    user: Annotated[dict, Depends(get_current_user)],
    org_id: Annotated[str | None, Depends(get_org_context)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict[str, Any]:
    """Create planned work by hand, optionally linked to a goal and an entity."""
    from datetime import UTC, datetime

    from app.services.work_object_service import (
        _serialize_work_object,
        infer_work_object_department,
        infer_work_object_type,
    )
    from app.workflows.audit import write_audit_event

    wants_links = bool((body.goal_id or "").strip() or (body.business_entity_id or "").strip())
    client, org_id = _links_client(settings, org_id, wants_links=wants_links)
    goal_id, entity_id = _checked_links(client, org_id, body.goal_id, body.business_entity_id)
    priority = body.priority if body.priority in {"low", "medium", "high", "critical"} else "medium"
    object_type = infer_work_object_type(explicit_type=body.object_type)
    now = datetime.now(UTC).isoformat()
    row: dict[str, Any] = {
        "org_id": org_id,
        "object_type": object_type,
        "department": infer_work_object_department(object_type, body.department),
        "title": body.title.strip()[:220],
        "objective": (body.objective or "").strip()[:2000] or None,
        "owner_user_id": str(user.get("user_id") or "") or None,
        "status": "planned",
        "priority": priority,
        "metadata": {"created_by": str(user.get("user_id") or "") or None, "source": "manual"},
        "created_at": now,
        "updated_at": now,
        "last_activity_at": now,
    }
    if goal_id:
        row["goal_id"] = goal_id
    if entity_id:
        row["business_entity_id"] = entity_id
    inserted = (client.table("work_objects").insert(row).execute().data or [row])[0]
    write_audit_event(
        client,
        org_id=org_id,
        actor_id=str(user.get("user_id") or ""),
        action="work_object.created",
        resource_type="work_object",
        resource_id=str(inserted.get("id") or ""),
        metadata={"goal_id": goal_id, "business_entity_id": entity_id},
    )
    return {"workObject": _serialize_work_object(inserted)}


@router.patch("/{work_object_id}")
def patch_work_object_links_route(
    work_object_id: UUID,
    body: PatchWorkObjectLinksRequest,
    user: Annotated[dict, Depends(get_current_user)],
    org_id: Annotated[str | None, Depends(get_org_context)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict[str, Any]:
    """Link (or unlink with ``null``) a work object to a goal and/or entity."""
    from datetime import UTC, datetime

    from app.workflows.audit import write_audit_event

    sent = body.model_fields_set
    if not sent & {"goal_id", "business_entity_id"}:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Send goalId and/or businessEntityId")
    client, org_id = _links_client(settings, org_id, wants_links=True)
    if get_work_object(client, org_id=org_id, work_object_id=str(work_object_id)) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="WorkObject not found")
    goal_id, entity_id = _checked_links(client, org_id, body.goal_id, body.business_entity_id)
    now = datetime.now(UTC).isoformat()
    patch: dict[str, Any] = {"updated_at": now, "last_activity_at": now}
    if "goal_id" in sent:
        patch["goal_id"] = goal_id
    if "business_entity_id" in sent:
        patch["business_entity_id"] = entity_id
    (
        client.table("work_objects")
        .update(patch)
        .eq("org_id", org_id)
        .eq("id", str(work_object_id))
        .execute()
    )
    write_audit_event(
        client,
        org_id=org_id,
        actor_id=str(user.get("user_id") or ""),
        action="work_object.links_updated",
        resource_type="work_object",
        resource_id=str(work_object_id),
        metadata={k: v for k, v in patch.items() if k in {"goal_id", "business_entity_id"}},
    )
    return {"workObject": get_work_object(client, org_id=org_id, work_object_id=str(work_object_id))}
