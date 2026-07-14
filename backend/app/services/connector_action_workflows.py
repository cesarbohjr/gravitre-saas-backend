"""Connector action workflow checks: clarification, disambiguation, approval, capability gaps."""
from __future__ import annotations

import re
from dataclasses import replace
from typing import Any

from app.services.action_workflow_validation import WorkflowCheck
from app.services.chat_connector_models import ConnectorActionPlan, LIST_CREATE_INTENT
from app.services.connector_capability_analysis import (
    LIST_CAPABILITY_CHECKS,
    LIST_FALLBACK_CAPABILITIES,
    analyze_capability_gaps,
    build_capability_summary,
    capability_check_lines,
    resolve_missing_action,
)
from app.services.execution_envelope import format_operator_response
from app.services.connector_session_state import inference_confidence_for_source

# Backward-compatible alias for registry verification and tests.
analyze_list_capability_gaps = analyze_capability_gaps


def validate_connector_plan(plan: ConnectorActionPlan, message: str) -> WorkflowCheck | None:
    """Return clarification when required parameters are missing — never invent values."""
    from app.connectors.action_catalog.action_workflow_schema import get_workflow_schema
    from app.services.action_workflow_validation import validate_plan_against_schema

    schema = get_workflow_schema(plan.invoke_action)
    if not schema:
        return None
    return validate_plan_against_schema(plan, schema)


def format_write_approval_message(plan: ConnectorActionPlan) -> str:
    """Warm, chat-native approval prompt for governed write actions."""
    vendor = (plan.integration or "").replace("_", " ").title() or "the connected app"
    label = (plan.label or plan.invoke_action or "this action").strip()
    details = _approval_details(plan)

    # Prefer natural prose for the common Apollo/HubSpot list-create case.
    list_name = str((plan.args or {}).get("name") or details.get("Name") or "").strip()
    if list_name and "lists.create" in (plan.invoke_action or ""):
        intro = (
            f"I can create a contact list named **{list_name}** in {vendor}."
        )
        if "segment" in label.lower():
            intro = (
                f"Apollo doesn't expose CRM segments over API the same way, "
                f"but I can create an equivalent contact list named **{list_name}**."
            )
        lines = [intro]
        if details:
            for key, value in details.items():
                if key.lower() == "name":
                    continue
                lines.append(f"- {key}: {value}")
        lines.extend(
            [
                "",
                "Reply **yes** to create it, or tell me what to change "
                "(name, modality, or follow-up criteria to populate it).",
            ]
        )
        return "\n".join(lines)

    lines = [
        f"I'll run this in {vendor}: **{label}**.",
    ]
    if details:
        lines.append("")
        for key, value in details.items():
            lines.append(f"- {key}: {value}")
    lines.extend(
        [
            "",
            "Reply **yes** to proceed, or tell me what to change.",
        ]
    )
    return "\n".join(lines)


def _arg_present(args: dict[str, Any], key: str) -> bool:
    return bool(str(args.get(key) or "").strip())


def _approval_details(plan: ConnectorActionPlan) -> dict[str, str]:
    args = dict(plan.args or {})
    details: dict[str, str] = {}
    inferred = set(plan.inferred_fields or ())
    sources = dict(plan.inference_sources or {})

    def _display(arg_key: str, label: str, value: str) -> None:
        if arg_key in inferred:
            source = sources.get(arg_key, "context")
            confidence = inference_confidence_for_source(source)
            if confidence == "high":
                details[label] = f"{value} (inferred from {source})"
            else:
                details[label] = (
                    f"{value} (inferred from {source} — confidence: {confidence}; confirm or edit)"
                )
        else:
            details[label] = value

    if plan.invoke_action == "asana.tasks.create":
        name = str(args.get("name") or "").strip()
        if name:
            _display("name", "Task", name)
        assignee = str(args.get("assignee_hint") or args.get("assignee") or "").strip()
        if assignee:
            details["Assignee"] = assignee
        project = str(args.get("project") or args.get("project_id") or "").strip()
        if project:
            project_key = "project" if _arg_present(args, "project") else "project_id"
            _display(project_key, "Project", project)
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


def format_capability_fallback_message(
    *,
    integration: str,
    intent: str,
    missing_action: str | None = None,
    available_actions: list[str] | None = None,
    planned: dict[str, str] | None = None,
    capability: str = "create_list",
    plan_limited_discovery: bool | None = None,
) -> str:
    gaps = analyze_capability_gaps(integration, available_actions)
    vendor_label = integration.replace("_", " ").title()
    resolved_missing = missing_action or resolve_missing_action(integration, capability)
    summary = build_capability_summary(
        integration=integration,
        vendor_label=vendor_label,
        gaps=gaps,
        focus_capability=capability,
    )
    caps = LIST_FALLBACK_CAPABILITIES
    if str(integration or "").strip().lower() == "apollo":
        caps = (
            "search_people",
            "search_companies",
            "create_list",
            "add_to_list",
            "saved_search",
        )
    check_lines = capability_check_lines(
        gaps,
        vendor=integration,
        capabilities=caps,
        plan_limited_discovery=plan_limited_discovery,
    )
    return format_operator_response(
        intent=intent,
        status="blocked — action not in catalog",
        missing_action=resolved_missing,
        planned=planned or None,
        result="\n".join([summary, "", "**Capability check:**", *check_lines]) if check_lines else summary,
        available_actions=available_actions or [],
        next_step=f"Missing action: `{resolved_missing}`. Use available actions above.",
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

    # STA-316: WorkflowFieldSpec-backed Memory path (opt-in opaque tokens only).
    memory_check = await _try_memory_assignee_resolve(
        client=client,
        org_id=org_id,
        plan=plan,
        hint=hint,
        settings=settings,
    )
    if memory_check is not None:
        return memory_check

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


async def _try_memory_assignee_resolve(
    *,
    client: Any,
    org_id: str,
    plan: ConnectorActionPlan,
    hint: str,
    settings: Any,
) -> WorkflowCheck | None:
    """Opt-in Memory resolver for sensitive assignee fields. Returns None to fall through."""
    from app.connectors.action_catalog.action_workflow_schema import get_workflow_schema
    from app.services.memory_field_resolver import (
        pick_sensitive_field_for_arg,
        resolve_sensitive_field_mention,
    )

    schema = get_workflow_schema(plan.invoke_action)
    if not schema:
        return None
    fields = list(schema.required_fields) + list(schema.optional_fields)
    field = pick_sensitive_field_for_arg(fields, "assignee_hint") or pick_sensitive_field_for_arg(
        fields, "assignee"
    )
    if field is None:
        return None

    result = await resolve_sensitive_field_mention(
        client=client,
        settings=settings,
        org_id=org_id,
        integration=plan.integration or "",
        field=field,
        mention=hint,
        entity_type="employee",
        primary_arg_key="assignee",
    )
    if result.status == "skipped" or result.status == "miss":
        return None
    if result.status == "bound" and result.entity_id:
        updated_args = dict(plan.args or {})
        updated_args["assignee"] = result.entity_id
        try:
            from app.services.entity_resolution_store import upsert_resolution

            upsert_resolution(
                client,
                org_id=org_id,
                alias=hint,
                entity_type="employee",
                entity_id=result.entity_id,
                integration=plan.integration or "",
                source="memory_opaque",
                confidence=0.85,
            )
        except Exception:  # noqa: BLE001
            pass
        return WorkflowCheck(
            status="resolved",
            message="",
            updated_plan=replace(plan, args=updated_args),
        )
    if result.status == "ambiguous" and result.candidates:
        labels = tuple(label for _eid, label in result.candidates[:8])
        return WorkflowCheck(
            status="needs disambiguation",
            candidates=labels,
            known={"Assignee hint": hint},
            dialogue_mode="clarify",
            message=format_operator_response(
                intent=schema.intent_label or "Assign task",
                status="needs disambiguation",
                matched_action=plan.invoke_action,
                known={"Assignee hint": hint},
                disambiguation_options=list(labels),
                next_step="Which one should I assign?",
            ),
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
    from app.services.asana_tools import fetch_asana_users_for_disambiguation

    users = fetch_asana_users_for_disambiguation(
        client,
        org_id,
        settings,
        environment_name=environment_name,
    )
    if users is None:
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
        try:
            from app.services.entity_resolution_store import upsert_resolution

            upsert_resolution(
                client,
                org_id=org_id,
                alias=hint,
                entity_type="employee",
                entity_id=matches[0][1],
                integration="asana",
                source="disambiguation",
                confidence=0.9,
            )
            if matches[0][0]:
                upsert_resolution(
                    client,
                    org_id=org_id,
                    alias=matches[0][0],
                    entity_type="employee",
                    entity_id=matches[0][1],
                    integration="asana",
                    source="disambiguation",
                    confidence=0.9,
                )
        except Exception:  # noqa: BLE001
            pass
        # Best-effort: index opaque tokens when Memory opt-in is enabled.
        try:
            from app.services.memory_entity_embeddings_service import index_entity_and_alias
            from app.services.memory_entity_embeddings_settings import (
                load_memory_entity_embeddings_settings,
                memory_embeddings_enabled_for,
            )

            policy = load_memory_entity_embeddings_settings(client, org_id)
            if memory_embeddings_enabled_for(policy, integration="asana"):
                await index_entity_and_alias(
                    client,
                    settings,
                    org_id=org_id,
                    integration="asana",
                    entity_type="employee",
                    entity_id=matches[0][1],
                    alias=hint,
                )
                if matches[0][0]:
                    await index_entity_and_alias(
                        client,
                        settings,
                        org_id=org_id,
                        integration="asana",
                        entity_type="employee",
                        entity_id=matches[0][1],
                        alias=matches[0][0],
                    )
        except Exception:  # noqa: BLE001
            pass
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
