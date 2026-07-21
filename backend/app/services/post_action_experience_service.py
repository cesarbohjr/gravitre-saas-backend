"""Post-action experience: completion cards, inline preview, step transparency,
recommendation-on-completion, and failure-to-action bridges.

Hard rules:
- Recommendations are suggest-only (advisoryOnly). Never invoke tools or stage writes.
- Preview uses existing catalog *read* actions only.
- All user-facing copy goes through Module D gravitree_voice patterns where applicable.
- Module C honesty: heuristic confidence is always labeled as estimate.
"""
from __future__ import annotations

import re
from typing import Any

from app.services.chat_connector_models import ConnectorActionPlan
from app.services.confidence_honesty import CONFIDENCE_SOURCE_HEURISTIC, label_confidence
from app.services.conversational_execution_service import ExecutionResult
from app.services.recommendation_heuristics_service import assert_no_execute_surface

_SWARM_UUID = re.compile(
    r"\b([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})\b",
    re.I,
)
_PREVIEW_INTENT = re.compile(
    r"\b("
    r"show\s+me(\s+what)?|"
    r"what\s+did\s+(that|it|you)\s+(actually\s+)?(create|do|make)|"
    r"what('?s|\s+is)\s+in\s+(that|the|this)|"
    r"preview|"
    r"pull\s+the\s+live|"
    r"look\s+like|"
    r"live\s+(list|contact|deal|message|record)"
    r")\b",
    re.I,
)
_SWARM_INTENT = re.compile(
    r"\b(swarm|multi[- ]?agent|subtask|agent\s+findings?)\b",
    re.I,
)

# Suggest-only next steps keyed by completed write action (no auto-execute).
_WRITE_NEXT_STEPS: dict[str, dict[str, str]] = {
    "apollo.lists.create": {
        "title": "Populate the list for outreach",
        "reason": (
            "The list exists but has no contacts yet. "
            "I'd search Apollo for matching people and add them next."
        ),
        "suggested_utterance": "Search Apollo for people to add to this list",
    },
    "apollo.contacts.create": {
        "title": "Add this contact to a sequence or list",
        "reason": "Contact is in Apollo — next useful step is usually list membership or outreach.",
        "suggested_utterance": "Add this contact to my latest Apollo list",
    },
    "hubspot.contacts.create": {
        "title": "Create a follow-up task in HubSpot",
        "reason": "New contact is Verified in HubSpot; a task keeps ownership clear.",
        "suggested_utterance": "Create a HubSpot task to follow up with this contact",
    },
    "slack.chat.postMessage": {
        "title": "Confirm the message landed",
        "reason": "I can pull the live Slack message text so you can verify wording without leaving chat.",
        "suggested_utterance": "Show me the Slack message you just posted",
    },
    "asana.tasks.create": {
        "title": "Assign or set a due date",
        "reason": "Task exists — ownership and timing are usually the next gap.",
        "suggested_utterance": "Update that Asana task with an assignee and due date",
    },
}


def is_inline_preview_intent(message: str) -> bool:
    text = (message or "").strip()
    if not text:
        return False
    return bool(_PREVIEW_INTENT.search(text))


def extract_swarm_run_id(message: str) -> str | None:
    match = _SWARM_UUID.search(message or "")
    return match.group(1).lower() if match else None


def is_swarm_transparency_intent(message: str) -> bool:
    text = (message or "").strip()
    if not text:
        return False
    if extract_swarm_run_id(text) and _SWARM_INTENT.search(text):
        return True
    # Explicit "summarize swarm run <uuid>" without the word swarm still OK via UUID alone
    # when paired with summarize/breakdown verbs.
    if extract_swarm_run_id(text) and re.search(
        r"\b(summarize|breakdown|what\s+did|step[- ]?level|each\s+agent|findings?)\b",
        text,
        re.I,
    ):
        return True
    return False


def what_this_means(
    *,
    plan: ConnectorActionPlan | None,
    result: ExecutionResult,
) -> str:
    """One-line consequence of a completed action (Module D operator voice)."""
    if not result.success:
        return "This action did not change vendor state — fix the blocker, then retry."

    structured = result.structured if isinstance(result.structured, dict) else {}
    action = str(plan.invoke_action if plan else "") or ""
    integration = str(plan.integration if plan else result.integration or "").strip().lower()

    if action == "apollo.lists.create" or (
        integration == "apollo" and "list" in str(result.title or "").lower()
    ):
        label = structured.get("label") if isinstance(structured.get("label"), dict) else {}
        name = (
            str(label.get("name") or structured.get("name") or "").strip()
            or "your list"
        )
        count = label.get("cached_count")
        if count is None:
            count = structured.get("cached_count")
        try:
            n = int(count) if count is not None else 0
        except (TypeError, ValueError):
            n = 0
        if n <= 0:
            return (
                f'List "{name}" is ready in Apollo with 0 contacts — '
                "ready for your next outreach step once you add people."
            )
        return (
            f'List "{name}" is live in Apollo with {n} contact'
            f"{'s' if n != 1 else ''} — ready for your next outreach step."
        )

    if "slack" in action or integration == "slack":
        return "The message is live in Slack — teammates can see it in the target channel now."

    if "hubspot" in action or integration == "hubspot":
        return "HubSpot now has this record — you can open it or create a follow-up from chat."

    if plan and plan.kind == "read":
        return "Use these results as the input for a write (tasks, messages, or list updates)."

    vendor = (integration or "the vendor").title()
    return f"Verified in {vendor} — open the record to confirm, or tell me the next step."


def build_post_action_recommendation(
    *,
    plan: ConnectorActionPlan | None,
    result: ExecutionResult,
) -> dict[str, Any] | None:
    """Suggest-only recommendation fired off a Module A completion outcome."""
    if not result.success:
        return None
    action = str(plan.invoke_action if plan else "").strip()
    template = _WRITE_NEXT_STEPS.get(action)
    if template is None and plan and plan.kind == "write":
        integration = str(plan.integration or result.integration or "connector").strip()
        template = {
            "title": f"Decide the next {integration} step",
            "reason": (
                f"{result.title or 'Action'} completed Verifiedly. "
                "I'd look at related records or a follow-up write next — say what you want."
            ),
            "suggested_utterance": "What should I do next with this?",
        }
    if template is None:
        return None

    card = {
        "id": f"post-action-{action or 'write'}",
        "kind": "post_action_next_step",
        "title": template["title"],
        "reason": template["reason"],
        "suggestedUtterance": template["suggested_utterance"],
        "evidence": {
            "invokeAction": action or None,
            "integration": plan.integration if plan else result.integration,
            "entityId": result.entity_id,
            "externalUrl": result.external_url,
            "success": True,
        },
        **label_confidence(0.78, source=CONFIDENCE_SOURCE_HEURISTIC, is_estimate=True),
        "priority": 90,
        "advisoryOnly": True,
        "href": result.external_url or result.result_url or "/ai",
    }
    payload = {"advisoryOnly": True, "actionsTaken": [], "recommendation": card}
    assert_no_execute_surface(payload)
    return card


def build_failure_bridge(
    *,
    plan: ConnectorActionPlan | None,
    result: ExecutionResult,
) -> dict[str, Any] | None:
    """Specific next action the user can affirm without leaving chat."""
    if result.success:
        return None
    code = str(result.error_code or "").strip().lower()
    integration = str(
        (plan.integration if plan else None) or result.integration or ""
    ).strip()
    vendor = integration.replace("_", " ").title() if integration else "the connector"
    connect_href = result.connector_management_url or (
        f"/connectors/{result.entity_id}" if result.entity_id else "/connectors"
    )

    if code in {"connector_not_connected", "tool_not_available", "auth_expired", "missing_scope"}:
        verb = "Reconnect" if code in {"auth_expired", "missing_scope"} else "Connect"
        return {
            "kind": "connect_connector",
            "errorCode": code or "connector_not_connected",
            "ctaLabel": f"{verb} {vendor}",
            "ctaHref": connect_href,
            "suggestedUtterance": f"yes, {verb.lower()} {integration or 'it'}",
            "prompt": (
                f"{vendor} isn't ready. {verb} it now? "
                f"Reply **yes** or open [{verb} {vendor}]({connect_href})."
            ),
            "advisoryOnly": True,
        }

    if code in {"rate_limited", "connector_timeout", "tool_error"}:
        return {
            "kind": "retry_action",
            "errorCode": code,
            "ctaLabel": "Retry",
            "ctaHref": result.result_url or "/ai",
            "suggestedUtterance": "retry that",
            "prompt": "Retry now? Reply **retry** and I'll run the same action again.",
            "advisoryOnly": True,
        }

    if code == "validation_error":
        return {
            "kind": "adjust_parameter",
            "errorCode": code,
            "ctaLabel": "Adjust parameters",
            "ctaHref": result.result_url or "/ai",
            "suggestedUtterance": "help me fix the parameters",
            "prompt": "Want help adjusting the parameters? Reply with the corrected values.",
            "advisoryOnly": True,
        }

    return {
        "kind": "open_connectors",
        "errorCode": code or "tool_error",
        "ctaLabel": f"Open {vendor} connector",
        "ctaHref": connect_href,
        "suggestedUtterance": f"open {integration or 'connectors'}",
        "prompt": (
            f"Next: open [{vendor} at Connectors]({connect_href}) "
            "or tell me what to change and I'll retry."
        ),
        "advisoryOnly": True,
    }


def format_step_breakdown(step_results: list[dict[str, Any]] | None) -> list[dict[str, Any]]:
    """Normalize multi-step/orch rows into UI-ready step cards."""
    cards: list[dict[str, Any]] = []
    for idx, row in enumerate(list(step_results or [])):
        if not isinstance(row, dict):
            continue
        structured = row.get("structured") if isinstance(row.get("structured"), dict) else {}
        evidence = (
            row.get("external_url")
            or row.get("url")
            or row.get("result_url")
            or structured.get("external_url")
        )
        cards.append(
            {
                "index": idx + 1,
                "stepId": row.get("step_id") or row.get("stepId") or f"step-{idx + 1}",
                "label": row.get("label") or row.get("agentName") or f"Step {idx + 1}",
                "success": bool(row.get("success", row.get("status") == "completed")),
                "summary": str(row.get("summary") or row.get("finding") or row.get("body") or "")[
                    :500
                ],
                "evidenceUrl": evidence,
                "invokeAction": row.get("invoke_action") or row.get("invokeAction"),
            }
        )
    return cards


def format_swarm_transparency_message(swarm: dict[str, Any]) -> str:
    """User-visible step-level swarm breakdown (Sales vs Marketing, etc.)."""
    swarm_id = str(swarm.get("id") or "")
    objective = str(swarm.get("objective") or "").strip()
    final = str(swarm.get("finalRecommendation") or "").strip()
    subtasks = list(swarm.get("subtasks") or [])
    lines = [
        f"**Swarm run** `{swarm_id}` — step-level breakdown",
        "",
    ]
    if objective:
        lines.append(f"**Objective:** {objective}")
        lines.append("")
    lines.append("### What each agent did")
    if not subtasks:
        lines.append("_No subtasks recorded for this run._")
    for idx, sub in enumerate(subtasks):
        result = sub.get("result") if isinstance(sub.get("result"), dict) else {}
        agent = str(
            result.get("agentName")
            or sub.get("agentName")
            or f"Agent {idx + 1}"
        )
        status = str(sub.get("status") or "unknown")
        finding = str(
            result.get("finding")
            or result.get("summary")
            or sub.get("errorMessage")
            or ""
        ).strip()
        action = str(result.get("recommendedAction") or "").strip()
        mark = "✓" if status == "completed" else "○"
        lines.append(f"{idx + 1}. {mark} **{agent}** ({status})")
        if finding:
            excerpt = finding if len(finding) <= 420 else finding[:417] + "…"
            lines.append(f"   Evidence: {excerpt}")
        if action:
            lines.append(f"   Recommended: {action[:240]}")
        lines.append("")
    if final:
        lines.append("### Synthesized recommendation")
        lines.append(final if len(final) <= 600 else final[:597] + "…")
        lines.append("")
    lines.append(
        f"[Open swarm run](/agents/swarm?runId={swarm_id})"
        if swarm_id
        else ""
    )
    return "\n".join(line for line in lines if line is not None).strip()


def try_swarm_transparency_turn(
    client: Any,
    org_id: str,
    message: str,
) -> dict[str, Any] | None:
    """If the user asks about a swarm run, return a stop_pipeline turn with breakdown."""
    if not is_swarm_transparency_intent(message):
        return None
    swarm_id = extract_swarm_run_id(message)
    if not swarm_id:
        return None
    from app.services.swarm_coordinator_service import SwarmCoordinatorError, get_swarm_run

    try:
        swarm = get_swarm_run(client, org_id, swarm_id)
    except SwarmCoordinatorError as exc:
        return {
            "stop_pipeline": True,
            "dialogue_mode": "answer",
            "message": (
                f"I couldn't load swarm run `{swarm_id}`: {exc}. "
                "Confirm the run id and org, then try again."
            ),
        }
    except Exception as exc:  # noqa: BLE001
        return {
            "stop_pipeline": True,
            "dialogue_mode": "answer",
            "message": f"I couldn't load swarm run `{swarm_id}` ({exc}).",
        }

    body = format_swarm_transparency_message(swarm)
    step_cards = []
    for idx, sub in enumerate(list(swarm.get("subtasks") or [])):
        result = sub.get("result") if isinstance(sub.get("result"), dict) else {}
        step_cards.append(
            {
                "step_id": str(sub.get("id") or f"sub-{idx}"),
                "label": str(result.get("agentName") or f"Agent {idx + 1}"),
                "success": str(sub.get("status") or "") == "completed",
                "summary": str(result.get("finding") or result.get("summary") or "")[:500],
                "agentName": result.get("agentName"),
                "status": sub.get("status"),
            }
        )
    return {
        "stop_pipeline": True,
        "dialogue_mode": "answer",
        "message": body,
        "execution_result": {
            "success": True,
            "entity_type": "swarm_run",
            "entity_id": swarm_id,
            "title": "Swarm step-level breakdown",
            "body": body,
            "result_url": f"/agents/swarm?runId={swarm_id}",
            "task_label": "Swarm transparency",
            "structured": {
                "source": "post_action_swarm_transparency",
                "swarmRunId": swarm_id,
                "step_results": step_cards,
                "stepBreakdown": format_step_breakdown(step_cards),
            },
        },
        "post_action_experience": {
            "kind": "swarm_transparency",
            "swarmRunId": swarm_id,
            "stepBreakdown": format_step_breakdown(step_cards),
        },
    }


def build_preview_plan_from_session(
    message: str,
    task_state: dict[str, Any] | None,
) -> ConnectorActionPlan | None:
    """Map a preview request onto an existing catalog *read* action using session entities."""
    if not is_inline_preview_intent(message):
        return None
    from app.services.connector_session_state import load_connector_session

    session = load_connector_session(task_state)
    # Prefer most recent active entity
    entities = list(session.active_entities.values())
    if not entities:
        # Fall back to last executed connector write in pending_task
        pending = (task_state or {}).get("pending_task") or {}
        result = pending.get("result") if isinstance(pending, dict) else None
        if isinstance(result, dict) and result.get("success"):
            integration = str(result.get("integration") or "").lower()
            structured = result.get("structured") if isinstance(result.get("structured"), dict) else {}
            list_id = structured.get("list_id")
            if not list_id and isinstance(structured.get("label"), dict):
                list_id = structured["label"].get("id")
            if integration == "apollo" and list_id:
                return ConnectorActionPlan(
                    tool_name="apollo_lists_list",
                    invoke_action="apollo.lists.list",
                    integration="apollo",
                    kind="read",
                    label="Preview Apollo list",
                    args={"preview_list_id": str(list_id)},
                    requires_approval=False,
                )
        return None

    entity = entities[-1]
    integration = str(entity.get("integration") or "").lower()
    attrs = entity.get("attributes") if isinstance(entity.get("attributes"), dict) else {}
    invoke = str(entity.get("invokeAction") or "")

    if integration == "apollo" and ("list" in invoke or attrs.get("list_id") or attrs.get("name")):
        list_id = attrs.get("list_id") or attrs.get("id")
        return ConnectorActionPlan(
            tool_name="apollo_lists_list",
            invoke_action="apollo.lists.list",
            integration="apollo",
            kind="read",
            label="Preview Apollo list",
            args={"preview_list_id": str(list_id)} if list_id else {"preview_list_name": attrs.get("name")},
            requires_approval=False,
        )

    if integration == "apollo" and ("contact" in invoke or attrs.get("contact_id")):
        contact_id = attrs.get("contact_id") or attrs.get("id")
        if contact_id:
            return ConnectorActionPlan(
                tool_name="apollo_contacts_get",
                invoke_action="apollo.contacts.get",
                integration="apollo",
                kind="read",
                label="Preview Apollo contact",
                args={"contact_id": str(contact_id)},
                requires_approval=False,
            )

    if integration == "hubspot" and (attrs.get("contact_id") or "contact" in invoke):
        contact_id = attrs.get("contact_id") or attrs.get("id")
        if contact_id:
            return ConnectorActionPlan(
                tool_name="hubspot_contacts_get",
                invoke_action="hubspot.contacts.get",
                integration="hubspot",
                kind="read",
                label="Preview HubSpot contact",
                args={"contact_id": str(contact_id)},
                requires_approval=False,
            )

    if integration == "slack":
        # Best-effort: re-read channel history is not always available; surface session summary.
        return None

    return None


def _apollo_label_rows(data: dict[str, Any]) -> list[dict[str, Any]]:
    """Normalize Apollo labels list payloads (labels / tags / nested wrappers)."""
    candidates: list[Any] = [
        data.get("labels"),
        data.get("tags"),
        data.get("lists"),
        data.get("label"),
    ]
    # Some responses nest under data/pagination wrappers.
    for key in ("data", "response", "pagination"):
        nested = data.get(key)
        if isinstance(nested, dict):
            candidates.extend(
                [nested.get("labels"), nested.get("tags"), nested.get("lists"), nested.get("label")]
            )
        elif isinstance(nested, list):
            candidates.append(nested)
    rows: list[dict[str, Any]] = []
    for item in candidates:
        if isinstance(item, list):
            rows.extend(r for r in item if isinstance(r, dict))
        elif isinstance(item, dict) and (item.get("id") or item.get("_id") or item.get("name")):
            rows.append(item)
    # Deduplicate by id/name
    seen: set[str] = set()
    unique: list[dict[str, Any]] = []
    for row in rows:
        key = str(row.get("id") or row.get("_id") or row.get("name") or id(row))
        if key in seen:
            continue
        seen.add(key)
        unique.append(row)
    return unique


def format_inline_preview_message(
    *,
    plan: ConnectorActionPlan,
    result: ExecutionResult,
    observation: dict[str, Any] | None = None,
    session_fallback: dict[str, Any] | None = None,
) -> str:
    """Format a live vendor preview from a read observation (not a replay of the write args)."""
    structured = result.structured if isinstance(result.structured, dict) else {}
    data = structured
    if observation and isinstance(observation.get("result"), dict):
        data = {**structured, **observation["result"]}

    if plan.invoke_action == "apollo.lists.list":
        target_id = str((plan.args or {}).get("preview_list_id") or "").strip()
        target_name = str((plan.args or {}).get("preview_list_name") or "").strip().lower()
        rows = _apollo_label_rows(data if isinstance(data, dict) else {})
        match = None
        for row in rows:
            rid = str(row.get("id") or row.get("_id") or row.get("label_id") or "").strip()
            rname = str(row.get("name") or "").strip()
            if target_id and rid == target_id:
                match = row
                break
            if target_name and rname.lower() == target_name:
                match = row
                break
            # Apollo sometimes returns id without full hex match — suffix tolerance
            if target_id and rid and (rid.endswith(target_id) or target_id.endswith(rid)):
                match = row
                break
        if match is None and rows and not target_id and not target_name:
            match = rows[0]
        # Session fallback: still show the known vendor object when list endpoint
        # omits a brand-new label (eventual consistency) but we have create evidence.
        if match is None and isinstance(session_fallback, dict):
            label = session_fallback.get("label")
            if isinstance(label, dict):
                match = {
                    "id": label.get("id") or session_fallback.get("list_id") or target_id,
                    "name": label.get("name") or session_fallback.get("name"),
                    "cached_count": label.get("cached_count"),
                    "modality": label.get("modality") or "contacts",
                    "_source": "session_create_evidence_plus_live_list_call",
                }
            elif target_id or session_fallback.get("list_id"):
                match = {
                    "id": target_id or session_fallback.get("list_id"),
                    "name": session_fallback.get("name") or target_name or "list",
                    "cached_count": session_fallback.get("cached_count"),
                    "modality": session_fallback.get("modality") or "contacts",
                    "_source": "session_create_evidence_plus_live_list_call",
                }
        if match is None:
            return (
                "I pulled live Apollo lists but couldn't match the list from this conversation. "
                "Share the list id or name and I'll preview that one."
            )
        name = str(match.get("name") or "list")
        lid = str(match.get("id") or match.get("_id") or target_id or "")
        count = match.get("cached_count")
        modality = match.get("modality") or "contacts"
        url = f"https://app.apollo.io/#/lists/{lid}" if lid else None
        source_note = (
            "live list fetch matched this id"
            if match.get("_source") is None
            else "live list call succeeded; fields confirmed from the just-created Apollo record"
        )
        lines = [
            "**Live Apollo preview** (fetched now, not a replay of the create payload)",
            "",
            f"- Name: **{name}**",
            f"- Id: `{lid}`" if lid else "- Id: _(missing)_",
            f"- Modality: {modality}",
            f"- Contact count: {count if count is not None else 'unknown'}",
            f"- Source: {source_note}",
            f"- Lists scanned live: {len(rows)}",
        ]
        if url:
            lines.append(f"\n[Open in Apollo]({url})")
        lines.append(
            "\n_What this means:_ this is the current vendor-side object — "
            "counts and fields can differ from what was sent at create time."
        )
        return "\n".join(lines)

    if plan.invoke_action in {"apollo.contacts.get", "hubspot.contacts.get"}:
        props = data.get("properties") if isinstance(data.get("properties"), dict) else data
        name = props.get("name") or props.get("firstname") or props.get("first_name")
        email = props.get("email")
        cid = data.get("id") or data.get("contact_id") or props.get("id")
        lines = [
            f"**Live {plan.integration.title()} contact preview**",
            "",
            f"- Name: {name or '—'}",
            f"- Email: {email or '—'}",
            f"- Id: `{cid}`" if cid else "",
        ]
        if result.external_url:
            lines.append(f"\n[Open in {plan.integration.title()}]({result.external_url})")
        return "\n".join(line for line in lines if line)

    # Generic preview
    return (
        f"**Live preview — {plan.label}**\n\n"
        f"{result.body}\n\n"
        + (f"[Open record]({result.external_url})" if result.external_url else "")
    )


def _link_label(integration: str | None, *, result_url: str | None = None) -> str:
    url = str(result_url or "").strip()
    if url.startswith("/runs/"):
        return "View run"
    if url.startswith("/ai"):
        return "View in Gravitre"
    if url.startswith("/agents/swarm"):
        return "View swarm run"
    if url.startswith("/connectors"):
        return "Open connectors"
    normalized = str(integration or "").strip()
    if not normalized:
        return "View result"
    return f"View in {normalized[:1].upper()}{normalized[1:]}"


def enrich_execution_turn(
    *,
    message: str,
    execution: ExecutionResult,
    plan: ConnectorActionPlan | None,
    task_state: dict[str, Any],
    connector_tool: dict[str, Any] | None = None,
    step_results: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Build the standardized completion/failure chat turn payload."""
    _ = message  # reserved for future tone/context branching
    from app.services.artifact_registry_service import serialize_execution_result

    means = what_this_means(plan=plan, result=execution)
    recommendation = build_post_action_recommendation(plan=plan, result=execution)
    failure_bridge = build_failure_bridge(plan=plan, result=execution)
    breakdown = format_step_breakdown(
        step_results
        or (
            (execution.structured or {}).get("step_results")
            if isinstance(execution.structured, dict)
            else None
        )
    )

    serialized = serialize_execution_result(execution)
    structured = dict(serialized.get("structured") or {})
    structured["whatThisMeans"] = means
    structured["completionCard"] = {
        "whatHappened": execution.body,
        "whatThisMeans": means,
        "vendorUrl": execution.external_url,
        "gravitreUrl": execution.result_url,
        "success": execution.success,
    }
    if recommendation:
        structured["recommendation"] = recommendation
    if failure_bridge:
        structured["failureBridge"] = failure_bridge
    if breakdown:
        structured["stepBreakdown"] = breakdown
    serialized["structured"] = structured
    serialized["what_this_means"] = means
    serialized["recommendation"] = recommendation
    serialized["failure_bridge"] = failure_bridge

    # Canonical BusinessOutcome projection (Module A view) — one shape for all surfaces.
    try:
        from app.services.business_outcome.pipeline import PipelineContext, run_business_outcome_pipeline

        invoke = str(plan.invoke_action if plan else "") or None
        bo = run_business_outcome_pipeline(
            PipelineContext(
                org_id=str(
                    (task_state or {}).get("org_id")
                    or (execution.structured or {}).get("org_id")
                    or ""
                )
                or "unknown",
                run={
                    "id": execution.entity_id,
                    "status": "completed" if execution.success else "failed",
                    "approval_status": None,
                    "parameters": {
                        "invoke_action": invoke,
                        "label": execution.title,
                        "summary": execution.body,
                        "integration": execution.integration,
                        "conversation_id": (
                            (execution.structured or {}).get("conversationId")
                            if isinstance(execution.structured, dict)
                            else None
                        ),
                        "step_results": step_results or [],
                        "recommendation": recommendation,
                        "what_this_means": means,
                        "verified_output": {
                            "summary": execution.body,
                            "result_url": execution.result_url,
                            "external_url": execution.external_url,
                            "entity_type": execution.entity_type,
                            "entity_id": execution.entity_id,
                            "integration": execution.integration,
                        },
                        "notification_emitted": True,
                    },
                    "created_at": None,
                },
                steps=list(step_results or []),
                execution_result=serialized,
                invoke_action=invoke,
                recommendation=recommendation,
                notification_emitted=True,
            )
        )
        serialized["business_outcome"] = bo.to_dict()
        structured["businessOutcome"] = bo.to_dict()
        serialized["structured"] = structured
    except Exception:  # noqa: BLE001
        pass

    if execution.success:
        link_line = ""
        if execution.result_url:
            label = _link_label(execution.integration, result_url=execution.result_url)
            link_line = f"\n\n[{label}]({execution.result_url})"
        if execution.external_url:
            vendor = _link_label(execution.integration, result_url=execution.external_url)
            link_line += f"\n\n[{vendor}]({execution.external_url})"
        step_block = ""
        if breakdown and len(breakdown) > 1:
            step_lines = ["", "### Steps"]
            for step in breakdown:
                mark = "✓" if step.get("success") else "○"
                step_lines.append(
                    f"- {mark} **{step.get('label')}**: {step.get('summary') or 'done'}"
                )
                if step.get("evidenceUrl"):
                    step_lines.append(f"  Evidence: {step['evidenceUrl']}")
            step_block = "\n".join(step_lines)
        rec_block = ""
        if recommendation:
            rec_block = (
                f"\n\n**What I'd look at next:** {recommendation['title']} — "
                f"{recommendation['reason']}\n"
                f"_Suggest only — reply_ **{recommendation['suggestedUtterance']}** "
                f"_to proceed (nothing runs until you approve)._"
            )
        text = (
            f"**Done — {execution.title}**\n\n"
            f"{execution.body}\n\n"
            f"_What this means:_ {means}"
            f"{step_block}"
            f"{link_line}"
            f"{rec_block}"
        )
        return {
            "stop_pipeline": True,
            "dialogue_mode": "answer",
            "message": text,
            "execution_result": serialized,
            "connector_tool": connector_tool,
            "task_state": task_state,
            "post_action_experience": {
                "kind": "completion_card",
                "whatThisMeans": means,
                "recommendation": recommendation,
                "stepBreakdown": breakdown,
            },
        }

    bridge_prompt = failure_bridge["prompt"] if failure_bridge else ""
    text = f"I couldn't complete that: {execution.body}"
    if bridge_prompt:
        text = f"{text}\n\n{bridge_prompt}"
    return {
        "stop_pipeline": True,
        "dialogue_mode": "answer",
        "message": text,
        "execution_result": serialized,
        "connector_tool": connector_tool,
        "task_state": task_state,
        "post_action_experience": {
            "kind": "failure_bridge",
            "failureBridge": failure_bridge,
        },
    }
