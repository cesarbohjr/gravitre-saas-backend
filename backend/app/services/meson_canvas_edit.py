"""Meson conversational edit of an EXISTING saved canvas (Phase 2).

Proposes a reviewable structural diff; does not auto-save. Apply goes through
the same builder_sync path as manual saves (versions + compile).
"""
from __future__ import annotations

import copy
import json
import re
import uuid
from typing import Any

from pydantic import BaseModel, Field

from app.config import Settings
from app.core.logging import get_logger
from app.services.confidence_honesty import (
    CONFIDENCE_SOURCE_HEURISTIC,
    CONFIDENCE_SOURCE_MODEL,
    estimated_confidence,
    label_confidence,
)
from app.services.model_router import ModelRouter, TaskType, get_model_router
from app.workflows.builder_sync import resolve_builder_graph, sync_builder_graph
from app.workflows.definition_diff import diff_builder_graphs, summarize_diff_for_voice
from app.workflows.repository import get_workflow_def

logger = get_logger(__name__)

# In-process proposal cache (org-scoped keys). Survives for sequential edits in a session.
_PROPOSALS: dict[str, dict[str, Any]] = {}


class MesonEditProposal(BaseModel):
    proposal_id: str = Field(alias="proposalId")
    workflow_id: str = Field(alias="workflowId")
    instruction: str
    summary: str
    before: dict[str, Any]
    after: dict[str, Any]
    diff: dict[str, Any]
    confidence: float | None = None
    confidence_is_estimate: bool = Field(default=True, alias="confidenceIsEstimate")
    confidence_source: str = Field(default=CONFIDENCE_SOURCE_HEURISTIC, alias="confidenceSource")

    model_config = {"populate_by_name": True}


class MesonEditApplyResult(BaseModel):
    workflow_id: str = Field(alias="workflowId")
    proposal_id: str = Field(alias="proposalId")
    applied: bool = True
    node_count: int = Field(alias="nodeCount")
    edge_count: int = Field(alias="edgeCount")
    summary: str

    model_config = {"populate_by_name": True}


class MesonExplainResult(BaseModel):
    workflow_id: str = Field(alias="workflowId")
    explanation: str
    confidence: float | None = None
    confidence_is_estimate: bool = Field(default=True, alias="confidenceIsEstimate")
    confidence_source: str = Field(default=CONFIDENCE_SOURCE_MODEL, alias="confidenceSource")

    model_config = {"populate_by_name": True}


def _builder_snapshot(nodes: list[dict[str, Any]], edges: list[dict[str, Any]]) -> dict[str, Any]:
    slim_nodes: list[dict[str, Any]] = []
    for n in nodes:
        if not isinstance(n, dict):
            continue
        meta = n.get("metadata") if isinstance(n.get("metadata"), dict) else {}
        cfg = n.get("config") if isinstance(n.get("config"), dict) else {}
        slim_nodes.append(
            {
                "id": str(n.get("id") or ""),
                "name": str(n.get("name") or n.get("title") or "Node"),
                "type": str(n.get("type") or n.get("node_type") or meta.get("builder_node_type") or "task"),
                "description": n.get("description") or n.get("instruction"),
                "vendor": n.get("vendor") or cfg.get("vendor"),
                "selectedAction": n.get("selectedAction") or cfg.get("action") or cfg.get("selectedAction"),
                "position": n.get("position")
                or {"x": n.get("position_x") or 0, "y": n.get("position_y") or 0},
                "config": cfg,
                "metadata": meta,
                "connections": n.get("connections") or [],
            }
        )
    slim_edges: list[dict[str, Any]] = []
    for e in edges:
        if not isinstance(e, dict):
            continue
        fr = e.get("from_node_id") or e.get("from")
        to = e.get("to_node_id") or e.get("to")
        if not fr or not to:
            continue
        slim_edges.append(
            {
                "id": str(e.get("id") or f"{fr}-{to}"),
                "from_node_id": str(fr),
                "to_node_id": str(to),
            }
        )
    return {"nodes": slim_nodes, "edges": slim_edges}


def _heuristic_edit(instruction: str, graph: dict[str, Any]) -> tuple[dict[str, Any], float]:
    """Deterministic NL→graph edits when the model is unavailable."""
    text = (instruction or "").strip().lower()
    after = copy.deepcopy(graph)
    nodes: list[dict[str, Any]] = list(after.get("nodes") or [])
    edges: list[dict[str, Any]] = list(after.get("edges") or [])

    # Remove step by name fragment
    remove_match = re.search(
        r"(?:remove|delete|drop)\s+(?:the\s+)?(.+?)(?:\s+step|\s+node)?$",
        text,
    )
    if remove_match or "remove" in text or "delete" in text:
        fragment = (remove_match.group(1) if remove_match else text).strip()
        for token in ("remove", "delete", "drop", "the", "step", "node", "notification"):
            fragment = fragment.replace(token, " ")
        fragment = " ".join(fragment.split())
        if fragment:
            keep: list[dict[str, Any]] = []
            removed_ids: set[str] = set()
            for n in nodes:
                name = str(n.get("name") or "").lower()
                ntype = str(n.get("type") or "").lower()
                vendor = str(n.get("vendor") or "").lower()
                if fragment in name or fragment in ntype or fragment in vendor:
                    removed_ids.add(str(n.get("id")))
                else:
                    keep.append(n)
            if removed_ids:
                nodes = keep
                edges = [
                    e
                    for e in edges
                    if str(e.get("from_node_id")) not in removed_ids
                    and str(e.get("to_node_id")) not in removed_ids
                ]
                after["nodes"] = nodes
                after["edges"] = edges
                return after, 0.72

    # Add HubSpot check before send / add Slack / add approval
    add_hubspot = "hubspot" in text and ("add" in text or "check" in text or "before" in text)
    add_slack = "slack" in text and ("add" in text or "notify" in text)
    add_approval = "approval" in text and ("add" in text or "require" in text)

    def _append_node(node_type: str, name: str, vendor: str | None = None, action: str | None = None) -> None:
        new_id = str(uuid.uuid4())
        y = 120 + len(nodes) * 100
        node: dict[str, Any] = {
            "id": new_id,
            "name": name,
            "type": node_type,
            "description": f"Added by Meson: {instruction[:120]}",
            "position": {"x": 320, "y": y},
            "config": {},
            "metadata": {},
            "connections": [],
        }
        if vendor:
            node["vendor"] = vendor
            node["config"] = {"vendor": vendor, "action": action or ""}
            if action:
                node["selectedAction"] = action.split(".")[-1] if "." in action else action
        nodes.append(node)
        if nodes[:-1]:
            prev = str(nodes[-2].get("id"))
            edges.append(
                {"id": f"{prev}-{new_id}", "from_node_id": prev, "to_node_id": new_id}
            )

    if add_hubspot:
        _append_node("connector", "Check HubSpot", vendor="hubspot", action="hubspot.contacts.search")
        after["nodes"] = nodes
        after["edges"] = edges
        return after, 0.68
    if add_slack:
        _append_node("connector", "Slack Notification", vendor="slack", action="slack.chat.postMessage")
        after["nodes"] = nodes
        after["edges"] = edges
        return after, 0.7
    if add_approval:
        _append_node("approval", "Quality Gate")
        after["nodes"] = nodes
        after["edges"] = edges
        return after, 0.74

    # Schedule: every morning / every hour
    if "every morning" in text or "each morning" in text or "daily at" in text:
        after["schedule"] = {"cron": "0 9 * * *", "label": "Every morning (09:00 UTC)"}
        return after, 0.65
    if "every hour" in text or "hourly" in text:
        after["schedule"] = {"cron": "0 * * * *", "label": "Every hour"}
        return after, 0.65

    return after, 0.4


async def _llm_edit(
    *,
    instruction: str,
    graph: dict[str, Any],
    org_id: str,
    model_router: ModelRouter,
) -> tuple[dict[str, Any] | None, float]:
    compact = {
        "nodes": [
            {
                "id": n.get("id"),
                "name": n.get("name"),
                "type": n.get("type"),
                "vendor": n.get("vendor"),
                "selectedAction": n.get("selectedAction"),
                "description": n.get("description"),
            }
            for n in (graph.get("nodes") or [])
        ],
        "edges": [
            {"from": e.get("from_node_id"), "to": e.get("to_node_id")}
            for e in (graph.get("edges") or [])
        ],
        "schedule": graph.get("schedule"),
    }
    prompt = (
        "You edit an existing workflow canvas. Apply the user's instruction to the graph.\n"
        "Return ONLY JSON with keys: nodes (array), edges (array of {from_node_id,to_node_id}), "
        "schedule (optional object or null), summary (short string), confidence (0-1).\n"
        "Preserve node ids when updating existing nodes. Mint new UUIDs only for new nodes.\n"
        "Do not invent connector vendors that are not implied by the instruction.\n"
        f"Instruction: {instruction}\n"
        f"Current graph: {json.dumps(compact)[:6000]}\n"
    )
    try:
        response = await model_router.complete(
            task_type=TaskType.WORKFLOW_PLANNING,
            prompt=prompt,
            system_prompt=(
                "You are Meson, Gravitree's workflow editor. Propose the smallest correct "
                "graph change. Never execute writes — structure only."
            ),
            org_id=org_id,
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("meson_canvas_edit_llm_failed org_id=%s error=%s", org_id, exc)
        return None, 0.0

    text = str(getattr(response, "text", None) or getattr(response, "content", None) or "")
    if not text and getattr(response, "parsed", None) is not None:
        text = json.dumps(response.parsed)
    match = re.search(r"\{[\s\S]*\}", text)
    if not match:
        return None, 0.0
    try:
        payload = json.loads(match.group(0))
    except json.JSONDecodeError:
        return None, 0.0
    if not isinstance(payload, dict) or not isinstance(payload.get("nodes"), list):
        return None, 0.0

    after = copy.deepcopy(graph)
    # Merge LLM nodes onto full graph nodes (keep config/position when id matches)
    by_id = {str(n.get("id")): copy.deepcopy(n) for n in (graph.get("nodes") or [])}
    new_nodes: list[dict[str, Any]] = []
    for raw in payload["nodes"]:
        if not isinstance(raw, dict):
            continue
        nid = str(raw.get("id") or uuid.uuid4())
        base = by_id.get(nid) or {
            "id": nid,
            "position": {"x": 280, "y": 120 + len(new_nodes) * 100},
            "config": {},
            "metadata": {},
            "connections": [],
        }
        base["id"] = nid
        if raw.get("name"):
            base["name"] = str(raw["name"])
        if raw.get("type"):
            base["type"] = str(raw["type"])
        if raw.get("vendor") is not None:
            base["vendor"] = raw.get("vendor")
        if raw.get("selectedAction") is not None:
            base["selectedAction"] = raw.get("selectedAction")
        if raw.get("description") is not None:
            base["description"] = raw.get("description")
        new_nodes.append(base)
    after["nodes"] = new_nodes
    llm_edges = payload.get("edges") or []
    if isinstance(llm_edges, list) and llm_edges:
        after["edges"] = [
            {
                "id": str(e.get("id") or f"{e.get('from_node_id') or e.get('from')}-{e.get('to_node_id') or e.get('to')}"),
                "from_node_id": str(e.get("from_node_id") or e.get("from") or ""),
                "to_node_id": str(e.get("to_node_id") or e.get("to") or ""),
            }
            for e in llm_edges
            if isinstance(e, dict)
        ]
    if "schedule" in payload:
        after["schedule"] = payload.get("schedule")
    try:
        raw_conf = payload.get("confidence")
        conf = float(
            estimated_confidence(
                float(raw_conf) if raw_conf is not None else 0.7,
                source=CONFIDENCE_SOURCE_HEURISTIC,
            )["confidence"]
        )
    except (TypeError, ValueError):
        conf = float(estimated_confidence(0.7, source=CONFIDENCE_SOURCE_HEURISTIC)["confidence"])
    return after, max(0.0, min(1.0, conf))


async def propose_workflow_edit(
    *,
    client: Any,
    settings: Settings,
    org_id: str,
    workflow_id: str,
    environment_name: str,
    instruction: str,
    workflow_state: dict[str, Any] | None = None,
    model_router: ModelRouter | None = None,
) -> MesonEditProposal:
    """Propose an edit against the current saved (or provided) canvas. Does not save."""
    instruction = (instruction or "").strip()
    if len(instruction) < 3:
        raise ValueError("instruction is required")

    wf = get_workflow_def(client, org_id, workflow_id)
    if not wf:
        raise ValueError("Workflow not found")

    if workflow_state and isinstance(workflow_state.get("nodes"), list):
        before = _builder_snapshot(
            list(workflow_state.get("nodes") or []),
            list(workflow_state.get("edges") or []),
        )
        if workflow_state.get("schedule") is not None:
            before["schedule"] = workflow_state.get("schedule")
    else:
        nodes, edges = resolve_builder_graph(
            client,
            org_id=org_id,
            workflow_id=workflow_id,
            environment_name=environment_name,
            wf=wf,
        )
        before = _builder_snapshot(nodes, edges)

    router = model_router or get_model_router()
    after, conf = await _llm_edit(
        instruction=instruction, graph=before, org_id=org_id, model_router=router
    )
    source = CONFIDENCE_SOURCE_MODEL
    if after is None:
        after, conf = _heuristic_edit(instruction, before)
        source = CONFIDENCE_SOURCE_HEURISTIC

    diff = diff_builder_graphs(before, after)
    summary = summarize_diff_for_voice(diff)
    if not diff.get("available"):
        # Still return proposal so UI can show honesty note
        summary = (
            f"I couldn't derive a structural change from “{instruction[:80]}”. "
            "Try naming the step to add/remove, or the schedule change."
        )

    conf_fields = label_confidence(conf, source=source, is_estimate=True)
    proposal_id = str(uuid.uuid4())
    payload = {
        "proposal_id": proposal_id,
        "org_id": org_id,
        "workflow_id": workflow_id,
        "instruction": instruction,
        "before": before,
        "after": after,
        "diff": diff,
        "summary": summary,
        **conf_fields,
    }
    _PROPOSALS[f"{org_id}:{proposal_id}"] = payload

    return MesonEditProposal(
        proposalId=proposal_id,
        workflowId=workflow_id,
        instruction=instruction,
        summary=summary,
        before=before,
        after=after,
        diff=diff,
        confidence=conf_fields.get("confidence"),
        confidenceIsEstimate=bool(conf_fields.get("confidence_is_estimate")),
        confidenceSource=str(conf_fields.get("confidence_source") or source),
    )


def apply_workflow_edit(
    *,
    client: Any,
    org_id: str,
    workflow_id: str,
    environment_name: str,
    proposal_id: str,
    created_by: str | None,
) -> MesonEditApplyResult:
    """Commit a previously proposed edit via builder_sync (creates a new version)."""
    key = f"{org_id}:{proposal_id}"
    payload = _PROPOSALS.get(key)
    if not payload or str(payload.get("workflow_id")) != workflow_id:
        raise ValueError("Edit proposal not found or expired — propose again")

    after = payload.get("after") if isinstance(payload.get("after"), dict) else {}
    nodes = list(after.get("nodes") or [])
    edges = list(after.get("edges") or [])
    stored_nodes, stored_edges, _definition = sync_builder_graph(
        client,
        org_id=org_id,
        workflow_id=workflow_id,
        environment_name=environment_name,
        nodes=nodes,
        edges=edges,
        created_by=created_by,
    )
    # Keep proposal for undo history listing; mark applied
    payload["applied"] = True
    _PROPOSALS[key] = payload

    return MesonEditApplyResult(
        workflowId=workflow_id,
        proposalId=proposal_id,
        applied=True,
        nodeCount=len(stored_nodes),
        edgeCount=len(stored_edges),
        summary=str(payload.get("summary") or "Applied canvas edit."),
    )


async def explain_workflow(
    *,
    client: Any,
    org_id: str,
    workflow_id: str,
    environment_name: str,
    model_router: ModelRouter | None = None,
) -> MesonExplainResult:
    """Plain-language explanation of the real node graph (Module D voice, Phase 5.1)."""
    from app.services.gravitree_voice import format_operator_message

    wf = get_workflow_def(client, org_id, workflow_id)
    if not wf:
        raise ValueError("Workflow not found")
    nodes, edges = resolve_builder_graph(
        client,
        org_id=org_id,
        workflow_id=workflow_id,
        environment_name=environment_name,
        wf=wf,
    )
    snapshot = _builder_snapshot(nodes, edges)
    names = [str(n.get("name") or n.get("type")) for n in snapshot["nodes"]]
    if not names:
        conf = label_confidence(0.9, source=CONFIDENCE_SOURCE_HEURISTIC, is_estimate=True)
        return MesonExplainResult(
            workflowId=workflow_id,
            explanation="This canvas has no steps yet — add a trigger or connector to get started.",
            confidence=conf.get("confidence"),
            confidenceIsEstimate=True,
            confidenceSource=str(conf.get("confidence_source")),
        )

    router = model_router or get_model_router()
    prompt = (
        f"Workflow name: {wf.get('name')}\n"
        f"Steps ({len(names)}): {json.dumps(snapshot['nodes'])[:4000]}\n"
        f"Edges: {json.dumps(snapshot['edges'])[:1500]}\n"
        "Explain in 2-4 short sentences what this workflow does for a non-technical operator. "
        "Mention write steps that need approval when obvious from action names."
    )
    explanation: str | None = None
    source = CONFIDENCE_SOURCE_MODEL
    conf_val = 0.72
    try:
        response = await router.complete(
            task_type=TaskType.SUMMARIZATION,
            prompt=prompt,
            system_prompt=(
                "You are Gravitree's operator voice: clear, direct, no hype. "
                "Explain the workflow graph honestly."
            ),
            org_id=org_id,
        )
        explanation = str(
            getattr(response, "text", None) or getattr(response, "content", None) or ""
        ).strip()
    except Exception as exc:  # noqa: BLE001
        logger.warning("meson_explain_llm_failed org_id=%s error=%s", org_id, exc)
        explanation = None

    if not explanation:
        source = CONFIDENCE_SOURCE_HEURISTIC
        conf_val = 0.55
        chain = " → ".join(names[:8])
        if len(names) > 8:
            chain += f" (+{len(names) - 8} more)"
        try:
            explanation = format_operator_message(
                "workflow_explain_fallback",
                confidence_register="estimate",
                allow_humor=False,
                chain=chain,
                name=str(wf.get("name") or "This workflow"),
            )
        except Exception:  # noqa: BLE001
            explanation = (
                f"{wf.get('name') or 'This workflow'} runs these steps in order: {chain}."
            )

    conf = label_confidence(conf_val, source=source, is_estimate=True)
    return MesonExplainResult(
        workflowId=workflow_id,
        explanation=explanation,
        confidence=conf.get("confidence"),
        confidenceIsEstimate=bool(conf.get("confidence_is_estimate")),
        confidenceSource=str(conf.get("confidence_source") or source),
    )


def list_edit_proposals(org_id: str, workflow_id: str, *, limit: int = 20) -> list[dict[str, Any]]:
    """Recent in-session edit proposals for undo/rollback UX (Phase 5.5 foundation)."""
    rows: list[dict[str, Any]] = []
    prefix = f"{org_id}:"
    for key, payload in _PROPOSALS.items():
        if not key.startswith(prefix):
            continue
        if str(payload.get("workflow_id")) != workflow_id:
            continue
        rows.append(
            {
                "proposalId": payload.get("proposal_id"),
                "instruction": payload.get("instruction"),
                "summary": payload.get("summary"),
                "applied": bool(payload.get("applied")),
                "diff": payload.get("diff"),
            }
        )
    return rows[-limit:]
