"""Decision queue enrichment: why each request paused and who decided it.

The Decision queue (GET /api/approvals) lists workflow runs waiting on a human
and connector writes staged from chat or the browser extension. This module adds
the facts the queue page shows next to each request, read from the real tables:

* ``policy``: the rule that made the request wait (a Human-in-the-loop policy,
  the workflow approval policy, or the safe default that applies when no policy
  covers a write).
* ``decisions``: the recorded approve / reject rows for workflow runs
  (``run_approvals``), so history shows the real reviewer, time and reason.
* ``steps``: what the agent asked to do, one row per planned step, each marked
  read or write (from the run's definition snapshot, or the staged write).
* ``context.risk_level``: the risk the request was scored at. A stored score
  wins; otherwise it is derived from the steps (reads are low, writes medium,
  money, customer email, deletes or a two-approver policy high).

Every lookup is one batched query and failures degrade to "no extra facts";
the queue itself never fails because enrichment could not load.
"""

from __future__ import annotations

import logging
from typing import Any

from app.workflows.constants import (
    SAFE_DEFAULT_APPROVER_ROLES,
    SAFE_DEFAULT_REQUIRED_APPROVALS,
)

logger = logging.getLogger(__name__)

# Actions that move money, email customers or delete data are high risk.
HIGH_RISK_MARKERS = (
    "delete",
    "remove",
    "archive",
    "refund",
    "payment",
    "charge",
    "invoice",
    "payout",
    "transfer",
    "send_email",
    "send_message",
    "email.send",
    "messages.send",
    "emails.send",
    "gmail.send",
    "sequence",
)

WORKFLOW_GATES = {"execute", "chat_orchestration_plan"}
EXTENSION_GATES = {"browser_extension_write", "browser_extension_workflow"}


def _rows(result: Any) -> list[dict[str, Any]]:
    data = getattr(result, "data", None)
    if not isinstance(data, list):
        return []
    return [row for row in data if isinstance(row, dict)]


def _load_hitl_policies(client: Any, org_id: str, ids: set[str]) -> dict[str, dict[str, Any]]:
    if not ids:
        return {}
    try:
        rows = _rows(
            client.table("hitl_policies")
            .select("id, name, enabled, scope_type, action_kinds, approver_roles, required_approvals")
            .eq("org_id", org_id)
            .in_("id", sorted(ids))
            .execute()
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("decision_queue hitl lookup failed org=%s error=%s", org_id, exc)
        return {}
    return {str(row.get("id")): row for row in rows if row.get("id")}


def _load_approval_policies(client: Any, org_id: str) -> list[dict[str, Any]]:
    try:
        return _rows(
            client.table("approval_policies")
            .select("id, workflow_id, required_approvals, approver_roles, run_types")
            .eq("org_id", org_id)
            .execute()
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("decision_queue approval_policies lookup failed org=%s error=%s", org_id, exc)
        return []


def _load_run_decisions(client: Any, org_id: str, run_ids: set[str]) -> dict[str, list[dict[str, Any]]]:
    if not run_ids:
        return {}
    try:
        rows = _rows(
            client.table("run_approvals")
            .select("run_id, approver_id, status, comment, created_at")
            .eq("org_id", org_id)
            .in_("run_id", sorted(run_ids))
            .execute()
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("decision_queue run_approvals lookup failed org=%s error=%s", org_id, exc)
        return {}
    out: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        out.setdefault(str(row.get("run_id") or ""), []).append(row)
    for decisions in out.values():
        decisions.sort(key=lambda d: str(d.get("created_at") or ""))
    return out


def _workflow_policy(
    policies: list[dict[str, Any]],
    workflow_id: str | None,
    required_on_run: int,
) -> dict[str, Any]:
    """Mirror resolve_policy(): workflow-specific, then org default, then safe default."""

    def _covers(row: dict[str, Any]) -> bool:
        return "execute" in (row.get("run_types") or [])

    match: dict[str, Any] | None = None
    scope = "default"
    if workflow_id:
        match = next(
            (p for p in policies if str(p.get("workflow_id") or "") == workflow_id and _covers(p)),
            None,
        )
        if match:
            scope = "workflow"
    if match is None:
        match = next((p for p in policies if not p.get("workflow_id") and _covers(p)), None)
        if match:
            scope = "org"
    roles = list((match or {}).get("approver_roles") or SAFE_DEFAULT_APPROVER_ROLES)
    return {
        "source": "approval_policy",
        "scope": scope,
        "id": str(match.get("id")) if match and match.get("id") else None,
        "name": None,
        # The run stores the count it was opened with; that is what the gate enforces.
        "required_approvals": required_on_run or int((match or {}).get("required_approvals") or SAFE_DEFAULT_REQUIRED_APPROVALS),
        "approver_roles": [str(r) for r in roles if r],
    }


def _connector_policy(ctx: dict[str, Any], hitl: dict[str, dict[str, Any]], gate: str) -> dict[str, Any]:
    action_kind = str(ctx.get("hitl_action_kind") or "write")
    policy_id = str(ctx.get("hitl_policy_id") or "").strip()
    if policy_id:
        row = hitl.get(policy_id)
        if row:
            return {
                "source": "hitl",
                "id": policy_id,
                "name": str(row.get("name") or "") or None,
                "enabled": bool(row.get("enabled", True)),
                "scope": str(row.get("scope_type") or "org"),
                "action_kind": action_kind,
                "action_kinds": [str(k) for k in (row.get("action_kinds") or []) if k],
                "required_approvals": max(1, int(row.get("required_approvals") or 1)),
                "approver_roles": [str(r) for r in (row.get("approver_roles") or []) if r],
            }
        return {"source": "hitl", "id": policy_id, "name": None, "missing": True, "action_kind": action_kind}
    if gate in EXTENSION_GATES:
        return {
            "source": "extension_confirm",
            "id": None,
            "name": None,
            "action_kind": action_kind,
            "requires_approval": bool(ctx.get("requires_approval", True)),
        }
    return {
        "source": "hitl_default",
        "id": None,
        "name": None,
        "action_kind": action_kind,
        "required_approvals": SAFE_DEFAULT_REQUIRED_APPROVALS,
        "approver_roles": list(SAFE_DEFAULT_APPROVER_ROLES),
    }


def _is_write(action: str) -> bool:
    if not action:
        return False
    # The catalog knows declared writes; the verb heuristic covers actions it has no entry for
    # (e.g. slack.chat.postMessage). A reviewer should see either as a write.
    try:
        from app.services.outcome_verification import is_write_action

        if is_write_action(action):
            return True
    except Exception:  # noqa: BLE001 — classification must not break the queue
        pass
    try:
        from app.services.connector_outcome_effects import is_mutating_action

        return bool(is_mutating_action(action))
    except Exception:  # noqa: BLE001
        return False


def _app_of(action: str, fallback: str | None = None) -> str | None:
    """Integration slug from an invoke action like ``hubspot.contacts.create``."""
    if action and "." in action:
        return action.split(".", 1)[0].strip().lower() or fallback
    return fallback


def _step_rows(snapshot: dict[str, Any] | None) -> list[dict[str, Any]]:
    """Planned steps from a run's definition snapshot (chat plans and workflows)."""
    snap = snapshot if isinstance(snapshot, dict) else {}
    raw = snap.get("steps")
    if not isinstance(raw, list) or not raw:
        graph = snap.get("graph") if isinstance(snap.get("graph"), dict) else {}
        raw = graph.get("nodes") if isinstance(graph.get("nodes"), list) else snap.get("nodes")
    if not isinstance(raw, list):
        return []
    steps: list[dict[str, Any]] = []
    for idx, step in enumerate(raw, start=1):
        if not isinstance(step, dict):
            continue
        config = step.get("config") if isinstance(step.get("config"), dict) else {}
        kind = str(step.get("node_type") or step.get("type") or "").strip().lower()
        if kind in {"trigger", "start", "end", "note"}:
            continue
        action = str(
            step.get("invoke_action")
            or config.get("tool_action")
            or config.get("invoke_action")
            or config.get("action")
            or ""
        ).strip()
        integration = str(step.get("connector") or config.get("connector") or config.get("integration") or "").strip().lower()
        text = str(step.get("name") or step.get("label") or "").strip() or (action or f"Step {idx}")
        steps.append(
            {
                "text": text,
                "action": action or None,
                "app": _app_of(action, integration or None),
                "access": "write" if _is_write(action) else "read",
            }
        )
    return steps[:20]


def _connector_steps(item: dict[str, Any], ctx: dict[str, Any]) -> list[dict[str, Any]]:
    action = str(ctx.get("invoke_action") or ctx.get("tool_name") or ctx.get("action") or "").strip()
    integration = str(ctx.get("integration") or "").strip().lower() or None
    text = str(ctx.get("label") or item.get("title") or action or "Write to a connected app").strip()
    access = "write" if (_is_write(action) or str(ctx.get("hitl_action_kind") or "write") != "read") else "read"
    return [{"text": text, "action": action or None, "app": _app_of(action, integration), "access": access}]


def _derive_risk(steps: list[dict[str, Any]], required_approvals: int) -> str:
    actions = " ".join(str(s.get("action") or s.get("text") or "").lower() for s in steps)
    if required_approvals >= 2:
        return "high"
    if any(s.get("access") == "write" for s in steps) and any(m in actions for m in HIGH_RISK_MARKERS):
        return "high"
    if any(s.get("access") == "write" for s in steps):
        return "medium"
    return "low"


def _attach_steps_and_risk(item: dict[str, Any], steps: list[dict[str, Any]], required_approvals: int) -> None:
    item["steps"] = steps
    ctx = item.get("context")
    if not isinstance(ctx, dict):
        ctx = {}
        item["context"] = ctx
    stored = str(ctx.get("risk_level") or ctx.get("riskLevel") or "").strip().lower()
    if stored:
        return
    ctx["risk_level"] = _derive_risk(steps, required_approvals)
    ctx["risk_derived"] = True


def enrich_decision_queue(
    client: Any,
    org_id: str,
    approvals: list[dict[str, Any]],
    *,
    run_meta: dict[str, dict[str, Any]] | None = None,
    user_labels: dict[str, str] | None = None,
) -> list[dict[str, Any]]:
    """Attach ``policy`` and ``decisions`` to each queue item (in place, also returned).

    ``run_meta`` maps a workflow run id to ``{"workflow_id", "required_approvals",
    "definition_snapshot"}``.
    ``user_labels`` maps user ids to display names already resolved by the caller.
    """
    run_meta = run_meta or {}
    labels = dict(user_labels or {})
    workflow_items = [a for a in approvals if a.get("gate_type") in WORKFLOW_GATES]
    connector_items = [a for a in approvals if a.get("gate_type") not in WORKFLOW_GATES]

    hitl_ids = {
        str((a.get("context") or {}).get("hitl_policy_id") or "").strip()
        for a in connector_items
    } - {""}
    hitl = _load_hitl_policies(client, org_id, hitl_ids)
    policies = _load_approval_policies(client, org_id) if workflow_items else []
    decisions_by_run = _load_run_decisions(client, org_id, {str(a.get("id")) for a in workflow_items})

    missing_names = {
        str(d.get("approver_id"))
        for ds in decisions_by_run.values()
        for d in ds
        if d.get("approver_id") and str(d.get("approver_id")) not in labels
    }
    if missing_names:
        try:
            for user in _rows(
                client.table("users").select("id, email, full_name").in_("id", sorted(missing_names)).execute()
            ):
                uid = str(user.get("id") or "")
                name = str(user.get("full_name") or "").strip()
                email = str(user.get("email") or "").strip()
                if uid and (name or email):
                    labels[uid] = name or email.split("@")[0].replace(".", " ").replace("_", " ").title()
        except Exception as exc:  # noqa: BLE001
            logger.warning("decision_queue approver lookup failed org=%s error=%s", org_id, exc)

    for item in workflow_items:
        run_id = str(item.get("id"))
        meta = run_meta.get(run_id) or {}
        item["policy"] = _workflow_policy(
            policies,
            str(meta.get("workflow_id") or "") or None,
            int(meta.get("required_approvals") or 0),
        )
        _attach_steps_and_risk(
            item,
            _step_rows(meta.get("definition_snapshot")),
            int(item["policy"].get("required_approvals") or 0),
        )
        decisions = [
            {
                "approver_id": str(d.get("approver_id") or "") or None,
                "approver_name": labels.get(str(d.get("approver_id") or "")),
                "status": str(d.get("status") or ""),
                "comment": d.get("comment") or None,
                "decided_at": d.get("created_at"),
            }
            for d in decisions_by_run.get(run_id, [])
        ]
        item["decisions"] = decisions
        item["approvals_received"] = sum(1 for d in decisions if d["status"] == "approved")
        if item.get("status") in {"approved", "rejected"} and decisions:
            final = next(
                (d for d in reversed(decisions) if d["status"] == item.get("status")),
                decisions[-1],
            )
            # The run row has no decision time; the recorded decision does.
            item["reviewed_at"] = final["decided_at"]
            item["reviewed_by"] = final["approver_id"]
            item["reviewed_by_name"] = final["approver_name"]
            item["review_comment"] = final["comment"]

    for item in connector_items:
        ctx = item.get("context") if isinstance(item.get("context"), dict) else {}
        item["policy"] = _connector_policy(ctx, hitl, str(item.get("gate_type") or ""))
        item.setdefault("decisions", [])
        _attach_steps_and_risk(
            item,
            _connector_steps(item, ctx),
            int(item["policy"].get("required_approvals") or 0),
        )

    return approvals
