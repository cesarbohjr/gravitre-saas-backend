"""Joined per-run observability — read-only fan-in over existing stores.

Does NOT invent a new logging system. Joins:
- workflow_runs / workflow_steps (run spine)
- audit_events (tool.invoke.*, execute.*)
- cognitive_turn_traces (when conversation_id present)
- intelligence_outcome_events (Module A)
- business-outcome projection fields from run parameters
"""
from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


def _as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _safe_list(client: Any, table: str, **filters: Any) -> list[dict[str, Any]]:
    try:
        q = client.table(table).select("*")
        for key, val in filters.items():
            if val is None:
                continue
            q = q.eq(key, val)
        rows = q.limit(100).execute().data or []
        return [dict(r) for r in rows]
    except Exception as exc:  # noqa: BLE001
        logger.debug("run_observability_query_failed table=%s error=%s", table, exc)
        return []


def _audit_for_run(client: Any, org_id: str, run_id: str) -> list[dict[str, Any]]:
    """Prefer resource_id match; also scan recent org audits for metadata.run_id."""
    by_resource: list[dict[str, Any]] = []
    try:
        rows = (
            client.table("audit_events")
            .select("id, action, actor_id, resource_type, resource_id, metadata, created_at")
            .eq("org_id", org_id)
            .eq("resource_id", run_id)
            .order("created_at", desc=False)
            .limit(200)
            .execute()
            .data
            or []
        )
        by_resource = [dict(r) for r in rows]
    except Exception as exc:  # noqa: BLE001
        logger.debug("audit_events_by_resource_failed run_id=%s error=%s", run_id, exc)

    # Secondary: metadata->>'run_id' when resource_id was task_id.
    extras: list[dict[str, Any]] = []
    try:
        recent = (
            client.table("audit_events")
            .select("id, action, actor_id, resource_type, resource_id, metadata, created_at")
            .eq("org_id", org_id)
            .order("created_at", desc=True)
            .limit(300)
            .execute()
            .data
            or []
        )
        seen = {str(r.get("id")) for r in by_resource}
        for row in recent:
            meta = _as_dict(row.get("metadata"))
            if str(meta.get("run_id") or "") != run_id:
                continue
            rid = str(row.get("id") or "")
            if rid and rid not in seen:
                extras.append(dict(row))
                seen.add(rid)
    except Exception as exc:  # noqa: BLE001
        logger.debug("audit_events_metadata_scan_failed run_id=%s error=%s", run_id, exc)

    merged = by_resource + list(reversed(extras))
    return merged


def _cognitive_for_conversation(client: Any, org_id: str, conversation_id: str | None) -> list[dict[str, Any]]:
    if not conversation_id:
        return []
    try:
        rows = (
            client.table("cognitive_turn_traces")
            .select(
                "turn_id, surface, stages, memory_summary, knowledge_summary, "
                "confidence_summary, conversation_id, user_id, created_at"
            )
            .eq("org_id", org_id)
            .eq("conversation_id", conversation_id)
            .order("created_at", desc=False)
            .limit(50)
            .execute()
            .data
            or []
        )
        # Strip private chain-of-thought: stages keep meta but drop raw model thoughts if present.
        cleaned: list[dict[str, Any]] = []
        for row in rows:
            item = dict(row)
            stages = []
            for stage in list(item.get("stages") or []):
                if not isinstance(stage, dict):
                    continue
                meta = _as_dict(stage.get("meta"))
                # Never expose private CoT / raw prompt fields.
                for key in ("thought", "chain_of_thought", "raw_prompt", "system_prompt", "cot"):
                    meta.pop(key, None)
                stages.append(
                    {
                        "stage": stage.get("stage"),
                        "ok": stage.get("ok"),
                        "ms": stage.get("ms"),
                        "meta": meta,
                    }
                )
            item["stages"] = stages
            cleaned.append(item)
        return cleaned
    except Exception as exc:  # noqa: BLE001
        logger.debug("cognitive_turns_failed conversation_id=%s error=%s", conversation_id, exc)
        return []


def _outcome_events(client: Any, org_id: str, run_id: str) -> list[dict[str, Any]]:
    return _safe_list(client, "intelligence_outcome_events", org_id=org_id, workflow_run_id=run_id)


def _tool_calls_from_audit(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    tools: list[dict[str, Any]] = []
    for ev in events:
        action = str(ev.get("action") or "")
        if not action.startswith("tool.invoke"):
            continue
        meta = _as_dict(ev.get("metadata"))
        tools.append(
            {
                "action": action,
                "tool": meta.get("action") or meta.get("tool") or meta.get("tool_name"),
                "connectorId": meta.get("connector_id"),
                "stepId": meta.get("step_id"),
                "agentId": meta.get("agent_id"),
                "status": "failed" if action.endswith("failed") else (
                    "completed" if action.endswith("completed") else "requested"
                ),
                "at": ev.get("created_at"),
            }
        )
    return tools


def _handoffs_from_audit(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Surface handoffs + collaboration trail as distinct, labeled events."""
    out: list[dict[str, Any]] = []
    for ev in events:
        action = str(ev.get("action") or "")
        lowered = action.lower()
        if "handoff" not in lowered and "collaboration" not in lowered:
            continue
        meta = _as_dict(ev.get("metadata"))
        from_dept = meta.get("from_department") or meta.get("fromDepartment")
        to_dept = meta.get("to_department") or meta.get("toDepartment")
        label = meta.get("label")
        if not label and (from_dept or to_dept):
            label = f"{from_dept or '?'} → {to_dept or '?'}"
        out.append(
            {
                "action": action,
                "fromAgentId": meta.get("from_agent_id") or meta.get("source_agent_id"),
                "toAgentId": meta.get("to_agent_id") or meta.get("target_agent_id"),
                "fromDepartment": from_dept,
                "toDepartment": to_dept,
                "label": label,
                "stance": meta.get("stance") or meta.get("receiver_stance"),
                "disagreementVisible": meta.get("disagreement_visible"),
                "at": ev.get("created_at"),
                "metadata": {
                    k: v
                    for k, v in meta.items()
                    if k not in {"thought", "chain_of_thought", "raw_prompt"}
                },
            }
        )
    return out


def build_run_observability(
    client: Any,
    *,
    org_id: str,
    run_payload: dict[str, Any],
    steps: list[dict[str, Any]],
) -> dict[str, Any]:
    """Compose the joined observability DTO for a single run."""
    run_id = str(run_payload.get("id") or "")
    params = _as_dict(run_payload.get("parameters"))
    snapshot = _as_dict(run_payload.get("definition_snapshot"))
    conversation_id = (
        str(params.get("conversation_id") or params.get("conversationId") or "").strip() or None
    )
    intent = (
        str(params.get("goal") or params.get("label") or snapshot.get("name") or "").strip() or None
    )
    model_used = (
        str(params.get("model") or params.get("model_name") or params.get("modelName") or "").strip()
        or None
    )

    audit_events = _audit_for_run(client, org_id, run_id) if run_id else []
    cognitive = _cognitive_for_conversation(client, org_id, conversation_id)
    outcomes = _outcome_events(client, org_id, run_id) if run_id else []

    latency_ms = run_payload.get("duration_ms")
    confidence = None
    cost_usd = None
    for row in outcomes:
        if confidence is None and row.get("confidence_score") is not None:
            confidence = row.get("confidence_score")
        meta = _as_dict(row.get("metadata"))
        if cost_usd is None and meta.get("cost_usd") is not None:
            cost_usd = meta.get("cost_usd")
        if not model_used:
            model_used = str(row.get("model_name") or "").strip() or model_used

    # Context sources from cognitive knowledge summaries + step types.
    context_sources: list[str] = []
    for turn in cognitive:
        ks = turn.get("knowledge_summary")
        if isinstance(ks, dict):
            for key in ("sources", "source_ids", "packs"):
                val = ks.get(key)
                if isinstance(val, list):
                    context_sources.extend(str(v) for v in val if v)
                elif isinstance(val, str) and val:
                    context_sources.append(val)
        elif isinstance(ks, str) and ks.strip():
            context_sources.append(ks.strip()[:200])
    for step in steps:
        st = str(step.get("step_type") or step.get("stepType") or "")
        if st in {"rag", "knowledge", "retrieve", "source"}:
            context_sources.append(st)

    # Deduplicate preserving order.
    seen_src: set[str] = set()
    unique_sources: list[str] = []
    for src in context_sources:
        if src not in seen_src:
            seen_src.add(src)
            unique_sources.append(src)

    approvals_required = int(run_payload.get("required_approvals") or 0) > 0
    final_status = str(run_payload.get("status") or "")

    # Replay path: ordered public actions without private CoT.
    replay: list[dict[str, Any]] = []
    for step in sorted(steps, key=lambda s: int(s.get("order_index") or s.get("step_index") or 0)):
        replay.append(
            {
                "kind": "step",
                "id": step.get("id"),
                "name": step.get("step_name") or step.get("name") or step.get("step_id"),
                "stepType": step.get("step_type") or step.get("stepType"),
                "status": step.get("status"),
                "startedAt": step.get("started_at") or step.get("startedAt"),
                "completedAt": step.get("completed_at") or step.get("completedAt"),
            }
        )
    for tool in _tool_calls_from_audit(audit_events):
        replay.append({"kind": "tool", **tool})
    for handoff in _handoffs_from_audit(audit_events):
        replay.append({"kind": "handoff", **handoff})

    return {
        "runId": run_id,
        "intent": intent,
        "modelUsed": model_used,
        "conversationId": conversation_id,
        "contextSources": unique_sources[:40],
        "ragQueries": [
            {
                "turnId": t.get("turn_id"),
                "knowledgeSummary": t.get("knowledge_summary"),
                "at": t.get("created_at"),
            }
            for t in cognitive
            if t.get("knowledge_summary")
        ],
        "toolsCalled": _tool_calls_from_audit(audit_events),
        "agentHandoffs": _handoffs_from_audit(audit_events),
        "actionsTaken": [
            {
                "action": ev.get("action"),
                "at": ev.get("created_at"),
                "actorId": ev.get("actor_id"),
            }
            for ev in audit_events
            if str(ev.get("action") or "").startswith(("execute.", "tool.invoke", "agent."))
        ],
        "approvalsRequired": approvals_required,
        "confidence": confidence,
        "latencyMs": latency_ms,
        "costUsd": cost_usd,
        "finalResult": {
            "status": final_status,
            "errorMessage": run_payload.get("error_message"),
            "completedAt": run_payload.get("completed_at"),
        },
        "cognitiveTurns": cognitive,
        "outcomeEvents": [
            {
                "event": row.get("outcome_event"),
                "modelName": row.get("model_name"),
                "confidenceScore": row.get("confidence_score"),
                "at": row.get("created_at"),
            }
            for row in outcomes
        ],
        "auditEventCount": len(audit_events),
        "replay": replay,
        "sources": {
            "run": "workflow_runs",
            "steps": "workflow_steps",
            "audit": "audit_events",
            "cognitive": "cognitive_turn_traces",
            "outcomes": "intelligence_outcome_events",
        },
    }
