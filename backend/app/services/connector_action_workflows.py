"""Connector action workflow checks: clarification, disambiguation, approval, capability gaps."""
from __future__ import annotations

import re
from dataclasses import dataclass, field, replace
from typing import Any

from app.services.chat_connector_models import ConnectorActionPlan, LIST_CREATE_INTENT
from app.services.execution_envelope import format_operator_response

LIST_CAPABILITY_CHECKS: dict[str, tuple[str, ...]] = {
    "create_list": ("lists.create", "list.create", "contact_lists.create"),
    "add_to_list": ("lists.add", "lists.members.add", "sequences.add"),
    "saved_search": ("saved_searches.create", "segments.create", "lists.create"),
    "search_people": ("people.search", "contacts.search"),
    "search_companies": ("organizations.search", "companies.search"),
    "create_contact": ("contacts.create",),
}


@dataclass(frozen=True)
class WorkflowCheck:
    status: str
    message: str
    missing: tuple[str, ...] = ()
    known: dict[str, str] = field(default_factory=dict)
    candidates: tuple[str, ...] = ()
    dialogue_mode: str = "answer"
    updated_plan: ConnectorActionPlan | None = None


def validate_connector_plan(plan: ConnectorActionPlan, message: str) -> WorkflowCheck | None:
    """Return clarification when required parameters are missing — never invent values."""
    if plan.invoke_action == "asana.tasks.create":
        return _validate_asana_task_create(plan, message)
    return None


def _validate_asana_task_create(plan: ConnectorActionPlan, message: str) -> WorkflowCheck | None:
    args = dict(plan.args or {})
    assignee_hint = str(args.get("assignee_hint") or "").strip()
    name = str(args.get("name") or "").strip()
    project = str(args.get("project") or args.get("project_id") or "").strip()
    due_on = str(args.get("due_on") or "").strip()

    missing: list[str] = []
    known: dict[str, str] = {"Task type": "Asana task"}

    if assignee_hint:
        known["Assignee"] = assignee_hint
    if name and name.lower() != assignee_hint.lower():
        known["Task"] = name
    else:
        missing.append("task title")
    if not project:
        missing.append("project")
    if not due_on:
        missing.append("due date")

    if not missing:
        return None

    return WorkflowCheck(
        status="needs clarification",
        missing=tuple(missing),
        known=known,
        dialogue_mode="clarify",
        message=format_operator_response(
            intent="Create Asana task",
            status="needs clarification",
            matched_action=plan.invoke_action,
            planned=known,
            missing_parameters=missing,
            next_step="Reply with the missing details (task title, project, and due date).",
        ),
    )


def format_write_approval_message(plan: ConnectorActionPlan) -> str:
    """Universal approval prompt for governed write actions."""
    lines = [
        "**Planned action:**",
        plan.label or plan.invoke_action,
    ]
    details = _approval_details(plan)
    if details:
        lines.append("")
        for key, value in details.items():
            lines.append(f"- {key}: {value}")
    lines.extend(["", "Approve? Reply **yes** to proceed, or tell me what to change."])
    return "\n".join(lines)


def _approval_details(plan: ConnectorActionPlan) -> dict[str, str]:
    args = dict(plan.args or {})
    details: dict[str, str] = {}
    if plan.invoke_action == "asana.tasks.create":
        name = str(args.get("name") or "").strip()
        if name:
            details["Task"] = name
        assignee = str(args.get("assignee_hint") or args.get("assignee") or "").strip()
        if assignee:
            details["Assignee"] = assignee
        project = str(args.get("project") or args.get("project_id") or "").strip()
        if project:
            details["Project"] = project
        due_on = str(args.get("due_on") or "").strip()
        if due_on:
            details["Due"] = due_on
    elif args.get("properties") and isinstance(args["properties"], dict):
        for key, value in args["properties"].items():
            if value:
                details[key.replace("_", " ").title()] = str(value)
    elif args.get("name"):
        details["Name"] = str(args["name"])
    elif args.get("message"):
        details["Message"] = str(args["message"])[:120]
    return details


def analyze_list_capability_gaps(
    integration: str,
    available_actions: list[str],
) -> dict[str, bool]:
    """Map related capabilities for list/group intents against catalog actions."""
    joined = " ".join(available_actions).lower()
    result: dict[str, bool] = {}
    for capability, patterns in LIST_CAPABILITY_CHECKS.items():
        result[capability] = any(pattern in joined for pattern in patterns)
    if integration == "apollo":
        # Apollo has no native list create; sequences.add is the closest add-to-collection action.
        result["create_list"] = False
        result["add_to_list"] = "sequences.add" in joined
        result["saved_search"] = False
    return result


def format_capability_fallback_message(
    *,
    integration: str,
    intent: str,
    missing_action: str,
    available_actions: list[str],
    planned: dict[str, str] | None = None,
) -> str:
    gaps = analyze_list_capability_gaps(integration, available_actions)
    vendor = integration.replace("_", " ").title()
    summary = (
        f"I can search {vendor} people/companies"
        if gaps.get("search_people") or gaps.get("search_companies")
        else f"The {vendor} connector is connected"
    )
    if not gaps.get("create_list"):
        summary += f", but I cannot create {vendor} lists yet."

    capability_lines = [
        f"- Can create list? {'yes' if gaps.get('create_list') else 'no'}",
        f"- Can add contacts to existing list/sequence? {'yes' if gaps.get('add_to_list') else 'no'}",
        f"- Can create saved search? {'yes' if gaps.get('saved_search') else 'no'}",
    ]
    return format_operator_response(
        intent=intent,
        status="blocked — action not in catalog",
        missing_action=missing_action,
        planned=planned or None,
        result="\n".join([summary, "", "**Capability check:**", *capability_lines]),
        available_actions=available_actions,
        next_step=f"Missing action: `{missing_action}`. Use available search/contact actions above.",
    )


async def resolve_assignee_disambiguation(
    *,
    client: Any,
    org_id: str,
    plan: ConnectorActionPlan,
    settings: Any,
    environment_name: str = "production",
) -> WorkflowCheck | None:
    """Resolve assignee hints or ask the user to pick among multiple matches."""
    hint = str((plan.args or {}).get("assignee_hint") or "").strip()
    if not hint or (plan.args or {}).get("assignee"):
        return None

    if plan.integration == "asana":
        return await _resolve_asana_assignee(
            client=client,
            org_id=org_id,
            plan=plan,
            hint=hint,
            settings=settings,
            environment_name=environment_name,
        )
    return None


async def _resolve_asana_assignee(
    *,
    client: Any,
    org_id: str,
    plan: ConnectorActionPlan,
    hint: str,
    settings: Any,
    environment_name: str,
) -> WorkflowCheck | None:
    from app.connectors.asana_api import AsanaAPIError, ensure_asana_session, list_users

    try:
        _cid, token = ensure_asana_session(
            client,
            org_id,
            None,
            settings,
            environment_name=environment_name,
        )
        payload = list_users(token)
    except AsanaAPIError:
        return None

    users = payload.get("users") if isinstance(payload, dict) else payload
    if not isinstance(users, list):
        return None

    matches: list[tuple[str, str]] = []
    hint_lower = hint.lower()
    for user in users:
        if not isinstance(user, dict):
            continue
        name = str(user.get("name") or "").strip()
        gid = str(user.get("gid") or user.get("id") or "").strip()
        if not name or not gid:
            continue
        if hint_lower in name.lower() or name.lower().startswith(hint_lower):
            matches.append((name, gid))

    if len(matches) == 1:
        updated_args = dict(plan.args or {})
        updated_args["assignee"] = matches[0][1]
        return WorkflowCheck(
            status="resolved",
            message="",
            updated_plan=replace(plan, args=updated_args),
        )

    if len(matches) > 1:
        candidates = tuple(name for name, _gid in matches[:8])
        return WorkflowCheck(
            status="needs disambiguation",
            candidates=candidates,
            known={"Assignee hint": hint},
            dialogue_mode="clarify",
            message=format_operator_response(
                intent="Create Asana task",
                status="needs disambiguation",
                matched_action=plan.invoke_action,
                known={"Assignee hint": hint},
                disambiguation_options=list(candidates),
                next_step="Which one should I assign?",
            ),
        )
    return None


def extract_asana_assignee_only(text: str) -> dict[str, Any] | None:
    """Parse 'Create an Asana task for Sarah' without inventing a task title."""
    match = re.search(
        r"\bcreate\s+(?:an?\s+)?(?:asana\s+)?tasks?\s+for\s+(\w+)\s*(?:[?.!]|$)",
        text.strip(),
        re.I,
    )
    if not match:
        return None
    return {"assignee_hint": match.group(1).strip()}
