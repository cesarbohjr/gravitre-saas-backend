"""STA-290: Batch grouping and partial approval for in-graph approval gates."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


class ApprovalBatchError(Exception):
    def __init__(self, message: str, *, code: str = "APPROVAL_BATCH_ERROR") -> None:
        super().__init__(message)
        self.code = code


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def extract_batch_items(
    upstream_outputs: dict[str, Any],
    *,
    node_metadata: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """Build batch items from upstream node outputs."""
    metadata = node_metadata or {}
    batch_items_key = metadata.get("batch_items_key") or metadata.get("batchItemsKey")
    explicit_items = metadata.get("batch_items") or metadata.get("batchItems")
    if isinstance(explicit_items, list) and explicit_items:
        items: list[dict[str, Any]] = []
        for index, entry in enumerate(explicit_items):
            if not isinstance(entry, dict):
                continue
            item_key = str(entry.get("item_key") or entry.get("itemKey") or f"item-{index}")
            items.append(
                {
                    "item_key": item_key,
                    "label": str(entry.get("label") or item_key),
                    "source_node_id": entry.get("source_node_id") or entry.get("sourceNodeId"),
                    "route_to_node_id": entry.get("route_to_node_id") or entry.get("routeToNodeId"),
                    "payload": entry.get("payload") or entry,
                }
            )
        return items

    items = []
    for source_node_id, output in upstream_outputs.items():
        label = source_node_id
        payload: Any = output
        if isinstance(output, dict):
            label = str(output.get("title") or output.get("name") or source_node_id)
            if batch_items_key and batch_items_key in output:
                nested = output[batch_items_key]
                if isinstance(nested, list):
                    for index, entry in enumerate(nested):
                        entry_payload = entry if isinstance(entry, dict) else {"value": entry}
                        items.append(
                            {
                                "item_key": f"{source_node_id}:{index}",
                                "label": str(entry_payload.get("label") or f"{label} #{index + 1}"),
                                "source_node_id": source_node_id,
                                "route_to_node_id": entry_payload.get("route_to_node_id")
                                or entry_payload.get("routeToNodeId"),
                                "payload": entry_payload,
                            }
                        )
                    continue
        route_to = None
        if isinstance(metadata.get("item_routes"), dict):
            route_to = metadata["item_routes"].get(source_node_id)
        items.append(
            {
                "item_key": source_node_id,
                "label": label,
                "source_node_id": source_node_id,
                "route_to_node_id": route_to,
                "payload": payload if isinstance(payload, dict) else {"value": payload},
            }
        )
    return items


def should_create_batch(
    upstream_outputs: dict[str, Any],
    node_metadata: dict[str, Any] | None = None,
) -> bool:
    metadata = node_metadata or {}
    if metadata.get("batch_mode") or metadata.get("batchMode"):
        return True
    explicit_items = metadata.get("batch_items") or metadata.get("batchItems")
    if isinstance(explicit_items, list) and explicit_items:
        return True
    return len(upstream_outputs) > 1


def create_approval_batch(
    client: Any,
    *,
    org_id: str,
    run_id: str,
    node_id: str,
    approval_context: dict[str, Any],
    node_metadata: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    upstream = approval_context.get("upstream_outputs") or {}
    if not isinstance(upstream, dict) or not should_create_batch(upstream, node_metadata):
        return None

    items = extract_batch_items(upstream, node_metadata=node_metadata)
    if len(items) <= 1 and not (node_metadata or {}).get("batch_mode"):
        return None

    batch_row = {
        "org_id": org_id,
        "run_id": run_id,
        "node_id": node_id,
        "status": "pending",
        "metadata": {
            "approval_context": approval_context,
            "node_metadata": node_metadata or {},
        },
        "updated_at": _now_iso(),
    }
    inserted = client.table("approval_batches").insert(batch_row).execute()
    batch = dict((inserted.data or [batch_row])[0])
    batch_id = str(batch["id"])

    item_rows = []
    default_route = (node_metadata or {}).get("reject_route_node_id") or (node_metadata or {}).get(
        "rejectRouteNodeId"
    )
    for item in items:
        item_rows.append(
            {
                "batch_id": batch_id,
                "org_id": org_id,
                "item_key": item["item_key"],
                "label": item["label"],
                "source_node_id": item.get("source_node_id"),
                "payload": item.get("payload") or {},
                "route_to_node_id": item.get("route_to_node_id") or default_route,
                "status": "pending",
                "updated_at": _now_iso(),
            }
        )
    if item_rows:
        client.table("approval_batch_items").insert(item_rows).execute()

    batch["items"] = list_items_for_batch(client, batch_id)
    return batch


def list_items_for_batch(client: Any, batch_id: str) -> list[dict[str, Any]]:
    result = (
        client.table("approval_batch_items")
        .select("*")
        .eq("batch_id", batch_id)
        .order("created_at")
        .execute()
    )
    return [dict(row) for row in (result.data or [])]


def get_active_batch_for_run(client: Any, org_id: str, run_id: str) -> dict[str, Any] | None:
    result = (
        client.table("approval_batches")
        .select("*")
        .eq("org_id", org_id)
        .eq("run_id", run_id)
        .in_("status", ["pending", "partial"])
        .order("created_at", desc=True)
        .limit(1)
        .execute()
    )
    if not result.data:
        return None
    batch = dict(result.data[0])
    batch["items"] = list_items_for_batch(client, str(batch["id"]))
    return batch


def normalize_batch_for_api(batch: dict[str, Any]) -> dict[str, Any]:
    items = batch.get("items") or []
    return {
        "batchId": str(batch["id"]),
        "runId": str(batch["run_id"]),
        "nodeId": batch["node_id"],
        "status": batch["status"],
        "items": [
            {
                "itemKey": item["item_key"],
                "label": item["label"],
                "sourceNodeId": item.get("source_node_id"),
                "routeToNodeId": item.get("route_to_node_id"),
                "status": item["status"],
                "rejectComment": item.get("reject_comment"),
                "payload": item.get("payload") or {},
            }
            for item in items
        ],
    }


def apply_batch_decisions(
    client: Any,
    *,
    batch_id: str,
    org_id: str,
    actor_id: str,
    decisions: list[dict[str, Any]],
) -> dict[str, Any]:
    batch_result = (
        client.table("approval_batches")
        .select("*")
        .eq("id", batch_id)
        .eq("org_id", org_id)
        .limit(1)
        .execute()
    )
    if not batch_result.data:
        raise ApprovalBatchError("Approval batch not found", code="NOT_FOUND")
    batch = dict(batch_result.data[0])
    if batch["status"] not in {"pending", "partial"}:
        raise ApprovalBatchError("Approval batch is already resolved", code="ALREADY_RESOLVED")

    items = list_items_for_batch(client, batch_id)
    by_key = {str(item["item_key"]): item for item in items}
    now = _now_iso()

    for decision in decisions:
        item_key = str(decision.get("item_key") or decision.get("itemKey") or "")
        if not item_key or item_key not in by_key:
            raise ApprovalBatchError(f"Unknown batch item: {item_key or '?'}", code="INVALID_ITEM")
        normalized = str(decision.get("decision") or decision.get("status") or "").lower()
        if normalized not in {"approved", "rejected"}:
            raise ApprovalBatchError(f"Invalid decision for {item_key}", code="INVALID_DECISION")
        patch = {
            "status": normalized,
            "reject_comment": decision.get("comment") or decision.get("reject_comment"),
            "decided_at": now,
            "decided_by": actor_id,
            "updated_at": now,
        }
        route_to = decision.get("route_to_node_id") or decision.get("routeToNodeId")
        if route_to:
            patch["route_to_node_id"] = str(route_to)
        client.table("approval_batch_items").update(patch).eq("id", by_key[item_key]["id"]).execute()

    refreshed_items = list_items_for_batch(client, batch_id)
    statuses = {str(item["status"]) for item in refreshed_items}
    if "pending" in statuses:
        batch_status = "partial" if statuses - {"pending"} else "pending"
    else:
        batch_status = "resolved"
    client.table("approval_batches").update({"status": batch_status, "updated_at": now}).eq("id", batch_id).execute()

    batch["status"] = batch_status
    batch["items"] = refreshed_items
    return batch


def summarize_batch_items(items: list[dict[str, Any]]) -> dict[str, Any]:
    approved = [item for item in items if item.get("status") == "approved"]
    rejected = [item for item in items if item.get("status") == "rejected"]
    pending = [item for item in items if item.get("status") == "pending"]
    return {
        "approved": approved,
        "rejected": rejected,
        "pending": pending,
        "all_approved": bool(items) and not rejected and not pending,
        "all_rejected": bool(items) and not approved and not pending,
        "has_partial": bool(approved) and bool(rejected) and not pending,
    }
