"""Bind Plays to existing canonical workflows.

Bindings are metadata on workflow_defs.config. The workflow remains owned by
the canonical workflow runtime and builder; a Play never owns executable steps.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from app.plays.catalog import get_platform_play
from app.workflows.repository import get_workflow_def
from app.workflows.schema_sync import mirror_legacy_workflow_row_to_contract

PLAY_CONFIG_KEY = "play"




def play_binding_for_workflow(
    workflow: dict[str, Any],
    *,
    expected_play_key: str | None = None,
) -> dict[str, Any] | None:
    config = workflow.get("config") if isinstance(workflow.get("config"), dict) else {}
    play = config.get(PLAY_CONFIG_KEY) if isinstance(config.get(PLAY_CONFIG_KEY), dict) else None
    if play is None:
        return None
    key = str(play.get("key") or "").strip().lower()
    if not key:
        return None
    if expected_play_key and key != expected_play_key.strip().lower():
        return None
    return dict(play)


def list_play_workflow_bindings(
    client: Any,
    org_id: str,
    play_key: str,
) -> list[dict[str, Any]]:
    wanted = play_key.strip().lower()
    rows = (
        client.table("workflow_defs")
        .select("id, name, description, status, stage, version, config, updated_at")
        .eq("org_id", org_id)
        .order("updated_at", desc=True)
        .execute()
        .data
        or []
    )
    out: list[dict[str, Any]] = []
    for row in rows:
        config = row.get("config") if isinstance(row.get("config"), dict) else {}
        play = config.get(PLAY_CONFIG_KEY) if isinstance(config.get(PLAY_CONFIG_KEY), dict) else {}
        if str(play.get("key") or "").strip().lower() != wanted:
            continue
        out.append(
            {
                "workflowId": str(row.get("id") or ""),
                "name": row.get("name"),
                "description": row.get("description"),
                "status": row.get("status"),
                "stage": row.get("stage"),
                "version": row.get("version"),
                "play": play,
                "updatedAt": row.get("updated_at"),
            }
        )
    return out


def bind_play_to_workflow(
    client: Any,
    org_id: str,
    *,
    play_key: str,
    workflow_id: str,
    actor_id: str | None,
    environment_name: str,
) -> dict[str, Any]:
    play = get_platform_play(play_key)
    if play is None:
        raise ValueError("Play not found")

    existing = get_workflow_def(client, org_id, workflow_id)
    if existing is None:
        raise LookupError("Workflow not found")

    current_config = existing.get("config") if isinstance(existing.get("config"), dict) else {}
    bound = {
        "key": play.key,
        "version": play.version,
        "bound_at": datetime.now(timezone.utc).isoformat(),
        "bound_by": actor_id,
        "execution_authority": "canonical_workflow_runtime",
    }
    config = {**current_config, PLAY_CONFIG_KEY: bound}

    updated = (
        client.table("workflow_defs")
        .update({"config": config})
        .eq("org_id", org_id)
        .eq("id", workflow_id)
        .execute()
    )
    if not updated.data:
        raise LookupError("Workflow not found")

    row = dict(updated.data[0])
    mirror_legacy_workflow_row_to_contract(
        client,
        row,
        environment_name=environment_name,
    )
    return {
        "workflowId": workflow_id,
        "play": bound,
        "executionAuthority": "canonical_workflow_runtime",
    }


def unbind_play_from_workflow(
    client: Any,
    org_id: str,
    *,
    play_key: str,
    workflow_id: str,
    environment_name: str,
) -> dict[str, Any]:
    existing = get_workflow_def(client, org_id, workflow_id)
    if existing is None:
        raise LookupError("Workflow not found")

    current_config = existing.get("config") if isinstance(existing.get("config"), dict) else {}
    current_play = (
        current_config.get(PLAY_CONFIG_KEY)
        if isinstance(current_config.get(PLAY_CONFIG_KEY), dict)
        else {}
    )
    if str(current_play.get("key") or "").strip().lower() != play_key.strip().lower():
        raise ValueError("Workflow is not bound to this Play")

    config = {key: value for key, value in current_config.items() if key != PLAY_CONFIG_KEY}
    updated = (
        client.table("workflow_defs")
        .update({"config": config})
        .eq("org_id", org_id)
        .eq("id", workflow_id)
        .execute()
    )
    if not updated.data:
        raise LookupError("Workflow not found")
    row = dict(updated.data[0])
    mirror_legacy_workflow_row_to_contract(
        client,
        row,
        environment_name=environment_name,
    )
    return {
        "workflowId": workflow_id,
        "playKey": play_key,
        "bound": False,
    }
