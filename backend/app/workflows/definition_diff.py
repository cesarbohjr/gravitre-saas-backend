"""Structural diff between two workflow builder graphs (Meson conversational edit).

Reuses the BusinessOutcome "reviewable prior" idea for graph structure — not a
second outcome store. Diffs are computed in-memory from before/after node+edge lists.
"""
from __future__ import annotations

from typing import Any


def _node_key(node: dict[str, Any]) -> str:
    return str(node.get("id") or node.get("node_id") or "").strip()


def _node_label(node: dict[str, Any]) -> str:
    return str(node.get("name") or node.get("title") or node.get("type") or "node").strip()


def _edge_key(edge: dict[str, Any]) -> str:
    fr = str(edge.get("from_node_id") or edge.get("from") or "").strip()
    to = str(edge.get("to_node_id") or edge.get("to") or "").strip()
    return f"{fr}->{to}"


def _node_fingerprint(node: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": _node_key(node),
        "name": _node_label(node),
        "type": str(node.get("type") or node.get("node_type") or ""),
        "vendor": node.get("vendor"),
        "selectedAction": node.get("selectedAction") or node.get("selected_action"),
        "description": node.get("description"),
        "config": node.get("config") if isinstance(node.get("config"), dict) else {},
    }


def diff_builder_graphs(
    before: dict[str, Any] | None,
    after: dict[str, Any] | None,
) -> dict[str, Any]:
    """Return a reviewable structural diff of builder graphs.

    Shape mirrors BusinessOutcome sections.diff honesty:
    - available + changes when graphs differ
    - note when identical / empty
    """
    before = before if isinstance(before, dict) else {}
    after = after if isinstance(after, dict) else {}
    before_nodes = {
        _node_key(n): n
        for n in (before.get("nodes") or [])
        if isinstance(n, dict) and _node_key(n)
    }
    after_nodes = {
        _node_key(n): n
        for n in (after.get("nodes") or [])
        if isinstance(n, dict) and _node_key(n)
    }
    before_edges = {
        _edge_key(e): e
        for e in (before.get("edges") or [])
        if isinstance(e, dict) and _edge_key(e) != "->"
    }
    after_edges = {
        _edge_key(e): e
        for e in (after.get("edges") or [])
        if isinstance(e, dict) and _edge_key(e) != "->"
    }

    added_nodes = [
        _node_fingerprint(after_nodes[k]) for k in sorted(set(after_nodes) - set(before_nodes))
    ]
    removed_nodes = [
        _node_fingerprint(before_nodes[k]) for k in sorted(set(before_nodes) - set(after_nodes))
    ]
    changed_nodes: list[dict[str, Any]] = []
    for key in sorted(set(before_nodes) & set(after_nodes)):
        b_fp = _node_fingerprint(before_nodes[key])
        a_fp = _node_fingerprint(after_nodes[key])
        if b_fp != a_fp:
            changed_nodes.append({"id": key, "before": b_fp, "after": a_fp})

    added_edges = [after_edges[k] for k in sorted(set(after_edges) - set(before_edges))]
    removed_edges = [before_edges[k] for k in sorted(set(before_edges) - set(after_edges))]

    schedule_before = before.get("schedule")
    schedule_after = after.get("schedule")
    schedule_changed = schedule_before != schedule_after

    has_changes = bool(
        added_nodes
        or removed_nodes
        or changed_nodes
        or added_edges
        or removed_edges
        or schedule_changed
    )
    if not has_changes:
        return {
            "available": False,
            "prior": None,
            "note": "No structural changes proposed.",
            "summary": {"added": 0, "removed": 0, "changed": 0, "edges_added": 0, "edges_removed": 0},
            "added_nodes": [],
            "removed_nodes": [],
            "changed_nodes": [],
            "added_edges": [],
            "removed_edges": [],
            "schedule": None,
        }

    return {
        "available": True,
        "prior": {
            "node_count": len(before_nodes),
            "edge_count": len(before_edges),
            "nodes": [_node_fingerprint(n) for n in before_nodes.values()],
        },
        "note": None,
        "summary": {
            "added": len(added_nodes),
            "removed": len(removed_nodes),
            "changed": len(changed_nodes),
            "edges_added": len(added_edges),
            "edges_removed": len(removed_edges),
            "schedule_changed": schedule_changed,
        },
        "added_nodes": added_nodes,
        "removed_nodes": removed_nodes,
        "changed_nodes": changed_nodes,
        "added_edges": added_edges,
        "removed_edges": removed_edges,
        "schedule": (
            {"before": schedule_before, "after": schedule_after} if schedule_changed else None
        ),
    }


def summarize_diff_for_voice(diff: dict[str, Any]) -> str:
    """One-line human summary for Meson / Module D phrasing."""
    if not diff.get("available"):
        return str(diff.get("note") or "No changes.")
    s = diff.get("summary") or {}
    parts: list[str] = []
    if s.get("added"):
        parts.append(f"add {s['added']} step(s)")
    if s.get("removed"):
        parts.append(f"remove {s['removed']} step(s)")
    if s.get("changed"):
        parts.append(f"update {s['changed']} step(s)")
    if s.get("edges_added") or s.get("edges_removed"):
        parts.append("rewire connections")
    if s.get("schedule_changed"):
        parts.append("change schedule")
    return "; ".join(parts) if parts else "Update workflow structure."
