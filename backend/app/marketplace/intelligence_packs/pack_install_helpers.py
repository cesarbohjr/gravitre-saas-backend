"""Shared helpers for intelligence-pack demo installs (workflow + agent slug bind)."""
from __future__ import annotations

from typing import Any

from app.core.logging import get_logger
from app.marketplace.workflow_contract import resolve_step_agent_seeds, steps_to_rich_contract
from app.workflows.constants import SCHEMA_VERSION

logger = get_logger(__name__)


def with_marketplace_slug(config: dict[str, Any] | None, slug: str) -> dict[str, Any]:
    """Ensure agent config carries marketplaceSlug for builder seed bind."""
    next_cfg = dict(config or {})
    next_cfg["marketplaceSlug"] = slug
    next_cfg.setdefault("slug", slug)
    return next_cfg


def upsert_preconfigured_workflow(
    client: Any,
    *,
    org_id: str,
    workflow_id: str,
    workflow_name: str,
    workflow_description: str,
    steps: list[dict[str, Any]],
    agent_id: str,
    agent_slug: str,
    asset_id: str,
    pack_id: str,
    actor_id: str,
    environment_name: str = "production",
    log_prefix: str = "pack",
) -> list[dict[str, Any]]:
    """Resolve agent seeds, write rich definition + contract nodes/edges."""
    bound = resolve_step_agent_seeds(
        list(steps),
        agent_ids_by_seed={f"agent:{agent_slug}": agent_id},
    )
    definition = {"schema_version": SCHEMA_VERSION, "steps": bound}
    workflow_config = {"marketplaceAssetId": asset_id, "pack_id": pack_id}
    contract_nodes, contract_edges = steps_to_rich_contract(bound)
    client.table("workflow_defs").upsert(
        {
            "id": workflow_id,
            "org_id": org_id,
            "name": workflow_name,
            "description": workflow_description or "",
            "status": "active",
            "schema_version": SCHEMA_VERSION,
            "definition": definition,
            "config": workflow_config,
        },
        on_conflict="id",
    ).execute()
    client.table("workflows").upsert(
        {
            "id": workflow_id,
            "org_id": org_id,
            "name": workflow_name,
            "description": workflow_description or "",
            "status": "active",
            "environment": environment_name,
            "nodes": contract_nodes,
            "edges": contract_edges,
            "config": workflow_config,
        },
        on_conflict="id",
    ).execute()
    try:
        from app.services.vertical_workflow_helper import ensure_active_workflow_version

        ensure_active_workflow_version(
            client,
            org_id,
            workflow_id,
            definition,
            environment_name=environment_name,
            actor_id=actor_id,
        )
    except Exception as exc:  # noqa: BLE001
        logger.debug("%s_workflow_version_skipped err=%s", log_prefix, exc)
    return bound
