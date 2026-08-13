"""Admin CRUD for org_knowledge_nodes + edge create on org_entity_relationships."""
from __future__ import annotations

from typing import Any
from uuid import uuid4

from app.core.logging import get_logger

logger = get_logger(__name__)

VALID_NODE_TYPES = frozenset(
    {
        "company",
        "employee",
        "customer",
        "prospect",
        "vendor",
        "product",
        "competitor",
        "project",
        "campaign",
        "contract",
        "kpi",
        "system",
        "decision",
    }
)

# Product-facing primary types (subset of VALID_NODE_TYPES).
PRIMARY_NODE_TYPES = frozenset({"company", "employee", "customer", "vendor", "product"})


def list_knowledge_nodes(
    client: Any,
    org_id: str,
    *,
    node_type: str | None = None,
    limit: int = 100,
) -> list[dict[str, Any]]:
    if not client or not org_id:
        return []
    try:
        q = (
            client.table("org_knowledge_nodes")
            .select("id,org_id,node_type,name,attributes,created_at")
            .eq("org_id", org_id)
            .order("created_at", desc=True)
            .limit(max(1, min(int(limit), 500)))
        )
        if node_type and node_type.strip().lower() in VALID_NODE_TYPES:
            q = q.eq("node_type", node_type.strip().lower())
        rows = q.execute().data or []
    except Exception as exc:  # noqa: BLE001
        logger.debug("org_knowledge_nodes_list_failed error=%s", exc)
        return []
    return [r for r in rows if isinstance(r, dict) and str(r.get("org_id") or "") == org_id]


def get_knowledge_node(client: Any, org_id: str, node_id: str) -> dict[str, Any] | None:
    if not client or not org_id or not node_id:
        return None
    try:
        rows = (
            client.table("org_knowledge_nodes")
            .select("id,org_id,node_type,name,attributes,created_at")
            .eq("org_id", org_id)
            .eq("id", node_id)
            .limit(1)
            .execute()
            .data
            or []
        )
    except Exception as exc:  # noqa: BLE001
        logger.debug("org_knowledge_nodes_get_failed error=%s", exc)
        return None
    if not rows or not isinstance(rows[0], dict):
        return None
    row = rows[0]
    if str(row.get("org_id") or "") != org_id:
        return None
    return row


def create_knowledge_node(
    client: Any,
    org_id: str,
    *,
    node_type: str,
    name: str,
    attributes: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    if not client or not org_id:
        return None
    ntype = (node_type or "").strip().lower()
    if ntype not in VALID_NODE_TYPES:
        raise ValueError(f"Invalid node_type; expected one of {sorted(VALID_NODE_TYPES)}")
    label = (name or "").strip()
    if not label:
        raise ValueError("name is required")
    payload = {
        "id": str(uuid4()),
        "org_id": org_id,
        "node_type": ntype,
        "name": label[:500],
        "attributes": attributes if isinstance(attributes, dict) else {},
    }
    try:
        inserted = client.table("org_knowledge_nodes").insert(payload).execute().data or []
        if inserted and isinstance(inserted[0], dict):
            return inserted[0]
        return payload
    except Exception as exc:  # noqa: BLE001
        logger.debug("org_knowledge_nodes_create_failed error=%s", exc)
        return None


def update_knowledge_node(
    client: Any,
    org_id: str,
    node_id: str,
    *,
    node_type: str | None = None,
    name: str | None = None,
    attributes: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    existing = get_knowledge_node(client, org_id, node_id)
    if not existing:
        return None
    patch: dict[str, Any] = {}
    if node_type is not None:
        ntype = node_type.strip().lower()
        if ntype not in VALID_NODE_TYPES:
            raise ValueError(f"Invalid node_type; expected one of {sorted(VALID_NODE_TYPES)}")
        patch["node_type"] = ntype
    if name is not None:
        label = name.strip()
        if not label:
            raise ValueError("name cannot be empty")
        patch["name"] = label[:500]
    if attributes is not None:
        if not isinstance(attributes, dict):
            raise ValueError("attributes must be an object")
        patch["attributes"] = attributes
    if not patch:
        return existing
    try:
        updated = (
            client.table("org_knowledge_nodes")
            .update(patch)
            .eq("org_id", org_id)
            .eq("id", node_id)
            .execute()
            .data
            or []
        )
        if updated and isinstance(updated[0], dict):
            return updated[0]
        return {**existing, **patch}
    except Exception as exc:  # noqa: BLE001
        logger.debug("org_knowledge_nodes_update_failed error=%s", exc)
        return None


def delete_knowledge_node(client: Any, org_id: str, node_id: str) -> bool:
    if not client or not org_id or not node_id:
        return False
    try:
        client.table("org_knowledge_nodes").delete().eq("org_id", org_id).eq("id", node_id).execute()
        return True
    except Exception as exc:  # noqa: BLE001
        logger.debug("org_knowledge_nodes_delete_failed error=%s", exc)
        return False


def create_entity_relationship(
    client: Any,
    org_id: str,
    *,
    source_entity_type: str,
    source_entity_id: str,
    relationship_type: str,
    target_entity_type: str,
    target_entity_id: str,
    confidence: float = 0.8,
) -> dict[str, Any] | None:
    """Create (or upsert-by-unique-key) an edge on org_entity_relationships."""
    if not client or not org_id:
        return None
    src_type = (source_entity_type or "").strip()
    src_id = (source_entity_id or "").strip()
    rel_type = (relationship_type or "").strip()
    tgt_type = (target_entity_type or "").strip()
    tgt_id = (target_entity_id or "").strip()
    if not all((src_type, src_id, rel_type, tgt_type, tgt_id)):
        raise ValueError("source/target entity type+id and relationship_type are required")
    try:
        conf = max(0.0, min(1.0, float(confidence)))
    except (TypeError, ValueError):
        conf = 0.8
    payload = {
        "id": str(uuid4()),
        "org_id": org_id,
        "source_entity_type": src_type[:120],
        "source_entity_id": src_id[:500],
        "relationship_type": rel_type[:120],
        "target_entity_type": tgt_type[:120],
        "target_entity_id": tgt_id[:500],
        "confidence": conf,
        "evidence_count": 1,
    }
    try:
        # Prefer upsert on unique index when supported by client.
        inserted = (
            client.table("org_entity_relationships")
            .upsert(
                payload,
                on_conflict=(
                    "org_id,source_entity_type,source_entity_id,"
                    "relationship_type,target_entity_type,target_entity_id"
                ),
            )
            .execute()
            .data
            or []
        )
        if inserted and isinstance(inserted[0], dict):
            return inserted[0]
        return payload
    except Exception:
        # Fallback: plain insert (may fail on duplicate — surface as None).
        try:
            inserted = client.table("org_entity_relationships").insert(payload).execute().data or []
            if inserted and isinstance(inserted[0], dict):
                return inserted[0]
            return payload
        except Exception as exc:  # noqa: BLE001
            logger.debug("org_entity_relationship_create_failed error=%s", exc)
            return None
