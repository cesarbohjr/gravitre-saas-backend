"""Shared feature extraction for workflow-run-based ML models."""
from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any

from app.config import Settings, get_settings
from app.workflows.execution_engine import _APPROVAL_NODE_TYPES
from app.workflows.repository import get_supabase_client

_CONNECTOR_NODE_TYPES = frozenset(
    {"tool", "invoke_tool", "connector", "integration", "slack_post_message", "email_send", "webhook_post"}
)
_ML_FEATURE_KEYS = (
    "step_count",
    "error_count",
    "retry_count",
    "longest_step_duration_ms",
    "avg_step_duration_ms",
    "node_count",
    "connector_node_count",
    "agent_node_count",
    "condition_node_count",
    "has_approval_gate",
    "max_graph_depth",
    "run_hour_of_day",
    "run_day_of_week",
    "run_is_weekend",
)


@dataclass
class WorkflowRunFeatures:
    """One workflow run's derived features for ML training and inference."""

    duration_ms: float | None
    status: str
    started_at: str
    step_count: int
    error_count: int
    retry_count: int
    longest_step_duration_ms: float
    avg_step_duration_ms: float
    node_count: int
    connector_node_count: int
    agent_node_count: int
    condition_node_count: int
    has_approval_gate: bool
    max_graph_depth: int
    run_hour_of_day: int
    run_day_of_week: int
    run_is_weekend: bool
    workflow_id: str | None = None
    run_id: str | None = None
    graph_features_from_snapshot: bool = True
    is_approximated: bool = False
    extra: dict[str, Any] = field(default_factory=dict)

    def to_ml_dict(self, *, include_targets: bool = False) -> dict[str, Any]:
        payload = {key: getattr(self, key) for key in _ML_FEATURE_KEYS}
        if include_targets:
            payload["duration_ms"] = self.duration_ms or 0.0
            payload["is_success"] = 1 if self.status == "completed" else 0
        return payload


def _parse_timestamp(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None


def _step_duration_ms(step: dict[str, Any]) -> int | None:
    started = _parse_timestamp(step.get("started_at"))
    completed = _parse_timestamp(step.get("completed_at"))
    if started and completed:
        return max(int((completed - started).total_seconds() * 1000), 0)
    output = step.get("output_snapshot")
    if isinstance(output, dict) and output.get("duration_ms") is not None:
        try:
            return max(int(output["duration_ms"]), 0)
        except (TypeError, ValueError):
            return None
    return None


def _aggregate_steps(steps: list[dict[str, Any]]) -> tuple[int, int, int, float, float]:
    if not steps:
        return 0, 0, 0, 0.0, 0.0
    durations: list[int] = []
    error_count = 0
    retry_count = 0
    for step in steps:
        status = str(step.get("status") or "")
        if status == "failed":
            error_count += 1
        if bool(step.get("is_retryable")):
            retry_count += 1
        duration = _step_duration_ms(step)
        if duration is not None:
            durations.append(duration)
    longest = float(max(durations)) if durations else 0.0
    avg = float(sum(durations) / len(durations)) if durations else 0.0
    return len(steps), error_count, retry_count, longest, avg


def _graph_nodes_edges(definition_snapshot: dict | None) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    if not isinstance(definition_snapshot, dict):
        return [], []
    graph = definition_snapshot.get("graph")
    if isinstance(graph, dict):
        nodes = [dict(n) for n in (graph.get("nodes") or []) if isinstance(n, dict)]
        edges = [dict(e) for e in (graph.get("edges") or []) if isinstance(e, dict)]
        if nodes:
            return nodes, edges
    steps = definition_snapshot.get("steps")
    if isinstance(steps, list) and steps:
        pseudo_nodes = [
            {
                "id": str(step.get("id") or step.get("step_id") or idx),
                "node_type": str(step.get("type") or step.get("step_type") or "noop"),
            }
            for idx, step in enumerate(steps)
            if isinstance(step, dict)
        ]
        pseudo_edges = [
            {"from_node_id": pseudo_nodes[i]["id"], "to_node_id": pseudo_nodes[i + 1]["id"]}
            for i in range(len(pseudo_nodes) - 1)
        ]
        return pseudo_nodes, pseudo_edges
    return [], []


def _node_type(node: dict[str, Any]) -> str:
    return str(node.get("node_type") or node.get("type") or "").strip().lower()


def _max_graph_depth(nodes: list[dict[str, Any]], edges: list[dict[str, Any]]) -> int:
    if not nodes:
        return 0
    node_ids = [str(n.get("id") or "") for n in nodes if n.get("id")]
    if not node_ids:
        return len(nodes)
    indegree: dict[str, int] = {nid: 0 for nid in node_ids}
    adjacency: dict[str, list[str]] = defaultdict(list)
    for edge in edges:
        src = str(edge.get("from_node_id") or edge.get("source") or "")
        dst = str(edge.get("to_node_id") or edge.get("target") or "")
        if src not in indegree or dst not in indegree:
            continue
        adjacency[src].append(dst)
        indegree[dst] += 1
    roots = deque([nid for nid in node_ids if indegree[nid] == 0])
    if not roots:
        roots = deque(node_ids[:1])
    depth_by_node: dict[str, int] = {nid: 1 for nid in node_ids}
    while roots:
        current = roots.popleft()
        for nxt in adjacency.get(current, []):
            depth_by_node[nxt] = max(depth_by_node.get(nxt, 1), depth_by_node[current] + 1)
            indegree[nxt] -= 1
            if indegree[nxt] == 0:
                roots.append(nxt)
    return max(depth_by_node.values()) if depth_by_node else len(nodes)


def _graph_shape_features(definition_snapshot: dict | None) -> dict[str, Any]:
    nodes, edges = _graph_nodes_edges(definition_snapshot)
    if not nodes:
        return {
            "node_count": 0,
            "connector_node_count": 0,
            "agent_node_count": 0,
            "condition_node_count": 0,
            "has_approval_gate": False,
            "max_graph_depth": 0,
            "graph_features_from_snapshot": False,
            "is_approximated": True,
        }
    connector_count = 0
    agent_count = 0
    condition_count = 0
    has_approval = False
    for node in nodes:
        node_type = _node_type(node)
        if node_type == "agent":
            agent_count += 1
        elif node_type == "condition":
            condition_count += 1
        elif node_type in _CONNECTOR_NODE_TYPES:
            connector_count += 1
        if node_type in _APPROVAL_NODE_TYPES or bool(node.get("has_approval_gate") or node.get("hasApprovalGate")):
            has_approval = True
    return {
        "node_count": len(nodes),
        "connector_node_count": connector_count,
        "agent_node_count": agent_count,
        "condition_node_count": condition_count,
        "has_approval_gate": has_approval,
        "max_graph_depth": _max_graph_depth(nodes, edges),
        "graph_features_from_snapshot": isinstance(definition_snapshot, dict),
        "is_approximated": False,
    }


def extract_features_for_run(
    run_row: dict[str, Any],
    steps: list[dict[str, Any]],
    definition_snapshot: dict | None,
) -> WorkflowRunFeatures:
    """Build one WorkflowRunFeatures record from a run, its steps, and definition snapshot."""
    started_at = str(run_row.get("started_at") or run_row.get("created_at") or "")
    started_dt = _parse_timestamp(started_at) or datetime.now(timezone.utc)
    duration_ms = run_row.get("duration_ms")
    if duration_ms is None:
        duration_ms = _step_duration_ms(
            {"started_at": run_row.get("created_at"), "completed_at": run_row.get("completed_at")}
        )
    try:
        duration_value = float(duration_ms) if duration_ms is not None else None
    except (TypeError, ValueError):
        duration_value = None

    step_count, error_count, retry_count, longest, avg = _aggregate_steps(steps)
    graph_feats = _graph_shape_features(definition_snapshot)
    if step_count and graph_feats["node_count"] == 0:
        graph_feats["node_count"] = step_count
        graph_feats["is_approximated"] = True

    return WorkflowRunFeatures(
        duration_ms=duration_value,
        status=str(run_row.get("status") or ""),
        started_at=started_at,
        step_count=step_count,
        error_count=error_count,
        retry_count=retry_count,
        longest_step_duration_ms=longest,
        avg_step_duration_ms=avg,
        node_count=int(graph_feats["node_count"]),
        connector_node_count=int(graph_feats["connector_node_count"]),
        agent_node_count=int(graph_feats["agent_node_count"]),
        condition_node_count=int(graph_feats["condition_node_count"]),
        has_approval_gate=bool(graph_feats["has_approval_gate"]),
        max_graph_depth=int(graph_feats["max_graph_depth"]),
        run_hour_of_day=started_dt.hour,
        run_day_of_week=started_dt.weekday(),
        run_is_weekend=started_dt.weekday() >= 5,
        workflow_id=str(run_row.get("workflow_id") or "") or None,
        run_id=str(run_row.get("id") or "") or None,
        graph_features_from_snapshot=bool(graph_feats["graph_features_from_snapshot"]),
        is_approximated=bool(graph_feats["is_approximated"]),
    )


def _fetch_recent_runs(client: Any, org_id: str, since_days: int) -> list[dict[str, Any]]:
    since = datetime.now(timezone.utc) - timedelta(days=since_days)
    result = (
        client.table("workflow_runs")
        .select("id, org_id, workflow_id, status, created_at, completed_at, duration_ms, definition_snapshot")
        .eq("org_id", org_id)
        .gte("created_at", since.isoformat())
        .order("created_at", desc=True)
        .limit(500)
        .execute()
    )
    return list(result.data or [])


def _fetch_steps_for_runs(client: Any, org_id: str, run_ids: list[str]) -> dict[str, list[dict[str, Any]]]:
    if not run_ids:
        return {}
    result = (
        client.table("workflow_steps")
        .select("run_id, status, started_at, completed_at, is_retryable, output_snapshot, step_index")
        .eq("org_id", org_id)
        .in_("run_id", run_ids)
        .order("step_index")
        .execute()
    )
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in result.data or []:
        grouped[str(row.get("run_id") or "")].append(row)
    return grouped


def collect_workflow_run_features(
    settings: Settings | None,
    org_id: str,
    since_days: int = 30,
    *,
    client: Any | None = None,
) -> list[dict[str, Any]]:
    """
    Org-scoped collector returning feature dicts for forecaster, success predictor,
    and anomaly detector training.

    Graph-shape features are derived from each run's ``definition_snapshot`` jsonb
    column (stored per run at execution time). When the snapshot lacks a graph,
    step-list fallbacks mark ``is_approximated`` on the output.
    """
    active_settings = settings or get_settings()
    db = client or get_supabase_client(active_settings)
    runs = _fetch_recent_runs(db, org_id, since_days)
    steps_by_run = _fetch_steps_for_runs(db, org_id, [str(r["id"]) for r in runs if r.get("id")])
    features: list[dict[str, Any]] = []
    for run in runs:
        run_id = str(run.get("id") or "")
        snapshot = run.get("definition_snapshot")
        if not isinstance(snapshot, dict):
            snapshot = None
        feat = extract_features_for_run(run, steps_by_run.get(run_id, []), snapshot)
        row = feat.to_ml_dict(include_targets=True)
        row["workflow_id"] = feat.workflow_id
        row["run_id"] = feat.run_id
        row["graph_features_from_snapshot"] = feat.graph_features_from_snapshot
        row["is_approximated"] = feat.is_approximated
        features.append(row)
    return features


def features_to_anomaly_input(feature_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "duration_ms": row.get("duration_ms") or 0,
            "error_count": row.get("error_count") or 0,
            "retry_count": row.get("retry_count") or 0,
            "step_count": row.get("step_count") or 0,
        }
        for row in feature_rows
    ]


def features_to_forecaster_train(
    feature_rows: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[float]]:
    x_rows: list[dict[str, Any]] = []
    y_values: list[float] = []
    for row in feature_rows:
        duration = row.get("duration_ms")
        if duration is None:
            continue
        try:
            y_values.append(float(duration))
        except (TypeError, ValueError):
            continue
        x_rows.append({key: row.get(key, 0) for key in _ML_FEATURE_KEYS})
    return x_rows, y_values


def features_to_success_train(
    feature_rows: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[bool]]:
    x_rows = [{key: row.get(key, 0) for key in _ML_FEATURE_KEYS} for row in feature_rows]
    y_values = [str(row.get("status") or "") == "completed" for row in feature_rows]
    return x_rows, y_values


def feature_row_as_dict(row: WorkflowRunFeatures | dict[str, Any]) -> dict[str, Any]:
    if isinstance(row, WorkflowRunFeatures):
        return asdict(row)
    return dict(row)
