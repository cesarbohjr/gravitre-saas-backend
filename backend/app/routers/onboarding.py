"""Onboarding progress API."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Body, Depends, HTTPException, status
from pydantic import BaseModel, Field
from supabase import create_client

from app.auth.dependencies import get_current_user, get_org_context
from app.config import Settings, get_settings
from app.services.org_seed_service import seed_org_if_needed

router = APIRouter(prefix="/api/onboarding", tags=["onboarding"])

STEP_DEFINITIONS = [
    {
        "id": "welcome",
        "key": "welcome",
        "title": "Welcome",
        "description": "Set your organization name.",
        "is_required": True,
        "order": 0,
    },
    {
        "id": "role",
        "key": "role",
        "title": "Your Role",
        "description": "Choose your role and goals.",
        "is_required": True,
        "order": 1,
    },
    {
        "id": "ready",
        "key": "ready",
        "title": "Ready",
        "description": "Confirm workspace readiness.",
        "is_required": True,
        "order": 2,
    },
    {
        "id": "path",
        "key": "path",
        "title": "First Step",
        "description": "Pick how to start.",
        "is_required": True,
        "order": 3,
    },
    {
        "id": "connect",
        "key": "connect",
        "title": "Connect",
        "description": "Optionally connect a tool.",
        "is_required": False,
        "order": 4,
    },
    {
        "id": "operator",
        "key": "operator",
        "title": "Operator",
        "description": "Choose your first assistant.",
        "is_required": True,
        "order": 5,
    },
    {
        "id": "task",
        "key": "task",
        "title": "First Task",
        "description": "Run your first task.",
        "is_required": True,
        "order": 6,
    },
    {
        "id": "success",
        "key": "success",
        "title": "Success",
        "description": "Review your first result.",
        "is_required": True,
        "order": 7,
    },
    {
        "id": "next",
        "key": "next",
        "title": "Next Steps",
        "description": "See recommended next actions.",
        "is_required": True,
        "order": 8,
    },
]

STEP_KEYS = {step["key"] for step in STEP_DEFINITIONS}
REQUIRED_STEP_KEYS = {step["key"] for step in STEP_DEFINITIONS if step["is_required"]}


class CompleteStepRequest(BaseModel):
    step_key: str = Field(..., min_length=1)
    data: dict | None = None


class WelcomeCompleteRequest(BaseModel):
    role: str = Field(..., min_length=1)
    skipped_optional: bool = False


def _is_missing_table_error(error: Exception | None) -> bool:
    if error is None:
        return False
    return "does not exist" in str(error).lower()


def _build_progress(onboarding_state: dict | None) -> dict:
    state = onboarding_state or {}
    completed_keys = set(state.get("completed_steps") or [])
    skipped = bool(state.get("skipped") or False)
    completed_at = state.get("completed_at")

    steps = [
        {
            **step,
            "is_completed": step["key"] in completed_keys,
        }
        for step in STEP_DEFINITIONS
    ]

    if skipped:
        current_step = len(STEP_DEFINITIONS) - 1
    else:
        next_index = next((idx for idx, step in enumerate(steps) if not step["is_completed"]), None)
        current_step = next_index if next_index is not None else len(STEP_DEFINITIONS) - 1

    return {
        "current_step": current_step,
        "total_steps": len(STEP_DEFINITIONS),
        "steps": steps,
        "completed_at": completed_at,
        "skipped": skipped,
        "step_data": state.get("step_data") or {},
        "welcome_completed": bool(
            state.get("welcome_completed")
            or completed_at
            or skipped
        ),
    }


def _load_org_settings(client, org_id: str) -> dict:
    response = client.table("organizations").select("id, settings").eq("id", org_id).limit(1).execute()
    if not response.data:
        raise HTTPException(status_code=404, detail="Organization not found")
    settings_value = response.data[0].get("settings") or {}
    if not isinstance(settings_value, dict):
        settings_value = {}
    return settings_value


def _save_org_settings(client, org_id: str, settings_value: dict) -> None:
    try:
        client.table("organizations").update({"settings": settings_value}).eq("id", org_id).execute()
    except Exception as exc:  # noqa: BLE001
        if not _is_missing_table_error(exc):
            raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("")
async def get_progress(
    _user: Annotated[dict, Depends(get_current_user)],
    org_id: Annotated[str | None, Depends(get_org_context)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict:
    if org_id is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Organization context required")
    client = create_client(settings.supabase_url, settings.supabase_service_role_key)
    org_settings = _load_org_settings(client, org_id)
    onboarding_state = org_settings.get("onboarding")
    if onboarding_state is not None and not isinstance(onboarding_state, dict):
        onboarding_state = {}
    return _build_progress(onboarding_state)


@router.post("/welcome-complete")
async def complete_welcome(
    body: WelcomeCompleteRequest,
    user: Annotated[dict, Depends(get_current_user)],
    org_id: Annotated[str | None, Depends(get_org_context)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict:
    """Mark the streamlined /welcome flow complete and persist role selection."""
    if org_id is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Organization context required")

    client = create_client(settings.supabase_url, settings.supabase_service_role_key)
    org_settings = _load_org_settings(client, org_id)
    onboarding_state = org_settings.get("onboarding")
    if not isinstance(onboarding_state, dict):
        onboarding_state = {}

    completed_steps = set(onboarding_state.get("completed_steps") or [])
    completed_steps.update({"welcome", "role", "ready", "path"})
    if not body.skipped_optional:
        completed_steps.add("connect")
    onboarding_state["completed_steps"] = [
        step["key"] for step in STEP_DEFINITIONS if step["key"] in completed_steps
    ]

    step_data = onboarding_state.get("step_data")
    if not isinstance(step_data, dict):
        step_data = {}
    step_data["role"] = {"selected_role": body.role.strip()}
    onboarding_state["step_data"] = step_data
    onboarding_state["welcome_completed"] = True
    onboarding_state["skipped"] = False
    if REQUIRED_STEP_KEYS.issubset(set(onboarding_state["completed_steps"])):
        onboarding_state["completed_at"] = datetime.now(timezone.utc).isoformat()

    org_settings["onboarding"] = onboarding_state
    _save_org_settings(client, org_id, org_settings)

    user_id = user.get("id") or user.get("sub")
    if user_id:
        try:
            now = datetime.now(timezone.utc).isoformat()
            client.table("user_preferences").upsert(
                {
                    "user_id": user_id,
                    "org_id": org_id,
                    "user_role": body.role.strip(),
                    "onboarding_step": "complete",
                    "onboarding_completed_at": now,
                    "updated_at": now,
                }
            ).execute()
        except Exception:  # noqa: BLE001
            pass

    return _build_progress(onboarding_state)


@router.post("/complete-step")
async def complete_step(
    body: CompleteStepRequest,
    _user: Annotated[dict, Depends(get_current_user)],
    org_id: Annotated[str | None, Depends(get_org_context)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict:
    if org_id is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Organization context required")
    step_key = body.step_key.strip()
    if step_key not in STEP_KEYS:
        raise HTTPException(status_code=400, detail="Invalid onboarding step key")

    client = create_client(settings.supabase_url, settings.supabase_service_role_key)
    org_settings = _load_org_settings(client, org_id)
    onboarding_state = org_settings.get("onboarding")
    if not isinstance(onboarding_state, dict):
        onboarding_state = {}

    completed_steps = set(onboarding_state.get("completed_steps") or [])
    completed_steps.add(step_key)
    onboarding_state["completed_steps"] = [
        step["key"] for step in STEP_DEFINITIONS if step["key"] in completed_steps
    ]

    if body.data:
        step_data = onboarding_state.get("step_data")
        if not isinstance(step_data, dict):
            step_data = {}
        step_data[step_key] = body.data
        onboarding_state["step_data"] = step_data

    if REQUIRED_STEP_KEYS.issubset(set(onboarding_state["completed_steps"])):
        onboarding_state["completed_at"] = datetime.now(timezone.utc).isoformat()
    onboarding_state["skipped"] = False

    org_settings["onboarding"] = onboarding_state
    _save_org_settings(client, org_id, org_settings)
    return _build_progress(onboarding_state)


@router.post("/skip")
async def skip_onboarding(
    _user: Annotated[dict, Depends(get_current_user)],
    org_id: Annotated[str | None, Depends(get_org_context)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict:
    if org_id is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Organization context required")

    client = create_client(settings.supabase_url, settings.supabase_service_role_key)
    org_settings = _load_org_settings(client, org_id)
    onboarding_state = org_settings.get("onboarding")
    if not isinstance(onboarding_state, dict):
        onboarding_state = {}
    onboarding_state["skipped"] = True
    onboarding_state["welcome_completed"] = True
    onboarding_state["completed_at"] = datetime.now(timezone.utc).isoformat()
    org_settings["onboarding"] = onboarding_state
    _save_org_settings(client, org_id, org_settings)
    return {"ok": True}


@router.post("/bootstrap")
async def bootstrap_org(
    _user: Annotated[dict, Depends(get_current_user)],
    org_id: Annotated[str | None, Depends(get_org_context)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict:
    """Seed demo agents, workflows, and runs for a new organization (idempotent)."""
    if org_id is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Organization context required")
    client = create_client(settings.supabase_url, settings.supabase_service_role_key)
    try:
        return seed_org_if_needed(client, org_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)) from exc


@router.post("/reset")
async def reset_onboarding(
    _user: Annotated[dict, Depends(get_current_user)],
    org_id: Annotated[str | None, Depends(get_org_context)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict:
    if org_id is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Organization context required")

    client = create_client(settings.supabase_url, settings.supabase_service_role_key)
    org_settings = _load_org_settings(client, org_id)
    onboarding_state = {
        "completed_steps": [],
        "step_data": {},
        "completed_at": None,
        "skipped": False,
    }
    org_settings["onboarding"] = onboarding_state
    _save_org_settings(client, org_id, org_settings)
    return _build_progress(onboarding_state)
