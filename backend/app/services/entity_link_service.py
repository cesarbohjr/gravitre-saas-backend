"""Canonical in-app URLs for Gravitre entities and external connector results."""
from __future__ import annotations


def build_connector_management_url(connector_id: str) -> str:
    """Integration settings page — not the artifact created by a write action."""
    connector_id = str(connector_id or "").strip()
    if not connector_id:
        return "/connectors"
    return build_entity_url("connector", connector_id)


def resolve_execution_result_url(
    *,
    entity_type: str,
    entity_id: str,
    external_url: str | None = None,
) -> str | None:
    """Resolvable deep link to the created/modified artifact, or None when unknown."""
    if external_url and external_url.startswith(("http://", "https://")):
        return external_url
    normalized = (entity_type or "").strip().lower()
    entity_id = str(entity_id or "").strip()
    if not entity_id or normalized in {"connector", "conversation", "unknown", "orchestration"}:
        return None
    built = build_entity_url(normalized, entity_id)
    if built in {"/", ""}:
        return None
    if normalized == "connector":
        return None
    return built


def build_entity_url(entity_type: str, entity_id: str, *, external_url: str | None = None) -> str:
    normalized = (entity_type or "").strip().lower()
    entity_id = str(entity_id or "").strip()
    if external_url and external_url.startswith(("http://", "https://")):
        return external_url
    if normalized in {"agent", "operator"} and entity_id:
        return f"/agents/{entity_id}"
    if normalized in {"workflow", "workflow_def"} and entity_id:
        return f"/workflows/{entity_id}/builder"
    if normalized in {"run", "workflow_run"} and entity_id:
        return f"/runs/{entity_id}"
    if normalized == "approval" and entity_id:
        return f"/approvals?id={entity_id}"
    if normalized == "connector" and entity_id:
        return f"/connectors/{entity_id}"
    if normalized == "swarm_run" and entity_id:
        return f"/agents/swarm?runId={entity_id}"
    if entity_id:
        return f"/{normalized}s/{entity_id}" if normalized else "/"
    return "/"
