"""Connector action workflow checks: clarification, disambiguation, approval, capability gaps."""
from __future__ import annotations

import re
from dataclasses import replace
from typing import Any

from app.services.action_workflow_validation import WorkflowCheck
from app.services.chat_connector_models import ConnectorActionPlan, LIST_CREATE_INTENT
from app.services.confidence_honesty import CONFIDENCE_SOURCE_HEURISTIC, estimated_confidence
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


def scrub_gmail_write_plan(plan: ConnectorActionPlan) -> ConnectorActionPlan:
    """Sanitize Gmail subject/body and drop instruction-framing residue before gates."""
    if plan.invoke_action != "gmail.messages.send":
        return plan
    from app.services.parameter_ledger import (
        email_slot_looks_corrupted,
        sanitize_email_slot_value,
    )

    args = dict(plan.args or {})
    changed = False
    for key in ("subject", "body", "text", "message", "html_body"):
        if key not in args:
            continue
        raw = str(args.get(key) or "")
        kind = "subject" if key == "subject" else "body"
        cleaned = sanitize_email_slot_value(kind, raw)
        if not cleaned or email_slot_looks_corrupted(kind, cleaned):
            args.pop(key, None)
            changed = True
        elif cleaned != raw:
            args[key] = cleaned
            changed = True
    if not changed:
        return plan
    return replace(plan, args=args)


def validate_connector_plan(plan: ConnectorActionPlan, message: str) -> WorkflowCheck | None:
    """Return clarification when required parameters are missing — never invent values."""
    from app.services.action_selection_gate import resolve_call_time_action, schema_for_action
    from app.services.action_workflow_validation import validate_plan_against_schema

    plan = scrub_gmail_write_plan(plan)
    # Part 5 — same schema lookup as workflow invoke_tool (incl. outlook→m365 aliases).
    schema = schema_for_action(plan.invoke_action)
    if not schema:
        return None
    resolved = resolve_call_time_action(plan.invoke_action)
    if resolved != plan.invoke_action:
        plan = replace(plan, invoke_action=resolved)
    return validate_plan_against_schema(plan, schema)


def missing_params_stage_patch(
    plan: ConnectorActionPlan,
    message: str,
    *,
    task_state: dict[str, Any] | None = None,
    seal_source: str = "staged_plan",
) -> tuple[WorkflowCheck, dict[str, Any]] | None:
    """Shared write gate: incomplete plans stage awaiting_params — never awaiting_confirm.

    Classical chat, unified-turn live, and ReAct write staging must all use this so
    dual paths cannot ask for a blind **yes** on missing subject/body/recipient.
    Callers must apply ``scrub_gmail_write_plan`` to the live plan before approval.
    Pass ``seal_source="unified_turn_live"`` from LIVE so staging cannot demote
    already-confirmed proposal args back to ``staged_plan``.
    """
    plan = scrub_gmail_write_plan(plan)
    clarification = validate_connector_plan(plan, message or "")
    if not clarification:
        return None
    from app.services.parameter_ledger import get_ledger, stage_awaiting_params

    patch = stage_awaiting_params(
        plan,
        clarification.missing,
        ledger=get_ledger(task_state),
        seal_source=seal_source,
    )
    return clarification, patch


def format_write_approval_message(plan: ConnectorActionPlan) -> str:
    """Chat-native approval prompt — copy owned by Module D gravitree_voice."""
    from app.services.gravitree_voice import format_operator_message

    plan = scrub_gmail_write_plan(plan)
    vendor = (plan.integration or "").replace("_", " ").title() or "the connected app"
    label = (plan.label or plan.invoke_action or "this action").strip()
    details = _approval_details(plan)
    list_name = str((plan.args or {}).get("name") or details.get("Name") or "").strip()
    return format_operator_message(
        "write_approval",
        vendor=vendor,
        label=label,
        details=details,
        list_name=list_name,
        invoke_action=plan.invoke_action or "",
    )


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
    elif plan.invoke_action == "gmail.messages.send":
        # Always surface recipient/subject/body so "yes" is not a blind approve.
        to = str(args.get("to") or args.get("email") or "").strip()
        subject = str(args.get("subject") or "").strip()
        body = str(args.get("body") or args.get("text") or "").strip()
        if to:
            _display("to" if _arg_present(args, "to") else "email", "To", to)
        if subject:
            _display("subject", "Subject", subject)
        if body:
            details["Body"] = body[:200] + ("…" if len(body) > 200 else "")
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
        next_step=(
            "I can't create that kind of list in this integration yet. "
            "Tell me what you want to accomplish and I'll use one of the options above."
        ),
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
            from app.services.memory_role_title_heuristic import learn_role_aliases

            upsert_resolution(
                client,
                org_id=org_id,
                alias=hint,
                entity_type="employee",
                entity_id=result.entity_id,
                integration=plan.integration or "",
                source="memory_opaque"
                if result.reason == "memory_opaque_match"
                else result.reason or "memory_resolve",
                confidence=float(
                    estimated_confidence(0.85, source=CONFIDENCE_SOURCE_HEURISTIC)["confidence"]
                ),
            )
            # STA-320 Option B: persist role cues so next "the AE" binds without Memory.
            learn_role_aliases(
                client,
                org_id=org_id,
                integration=plan.integration or "",
                entity_id=result.entity_id,
                mention=hint,
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
            from app.services.memory_role_title_heuristic import learn_role_aliases

            upsert_resolution(
                client,
                org_id=org_id,
                alias=hint,
                entity_type="employee",
                entity_id=matches[0][1],
                integration="asana",
                source="disambiguation",
                confidence=float(
                    estimated_confidence(0.9, source=CONFIDENCE_SOURCE_HEURISTIC)["confidence"]
                ),
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
                    confidence=float(
                        estimated_confidence(0.9, source=CONFIDENCE_SOURCE_HEURISTIC)["confidence"]
                    ),
                )
            # STA-320 Option B: if hint was a role cue, learn role→entity aliases.
            learn_role_aliases(
                client,
                org_id=org_id,
                integration="asana",
                entity_id=matches[0][1],
                mention=hint,
                confidence=float(
                    estimated_confidence(0.9, source=CONFIDENCE_SOURCE_HEURISTIC)["confidence"]
                ),
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
