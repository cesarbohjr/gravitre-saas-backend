"""Context-aware parameter inference before connector plan validation."""
from __future__ import annotations

import re
from dataclasses import dataclass, field, replace
from typing import Any

from app.services.connector_session_state import (
    ConnectorSessionState,
    bind_plan_from_session,
    compress_session_for_context,
    connector_session_patch,
    inference_confidence_for_source,
    load_connector_session,
    record_entity_from_execution,
    record_step_output,
    build_session_summary,
)

PROJECT_IN_MESSAGE = re.compile(
    r"\bin\s+(?:the\s+)?([\"']?[\w-]{1,80}[\"']?)\s+project\b",
    re.I,
)
PROJECT_NAMED = re.compile(r"\bproject\s+[:\s]+[\"']?([\w\s-]{1,80})[\"']?", re.I)
TASK_PHRASE = re.compile(
    r"\b(?:to\s+)?((?:review|update|check|finish|complete|prepare)\s+[\w\s'-]{3,80})\b",
    re.I,
)


@dataclass
class ParameterInferenceContext:
    message: str
    conversation_history: list[str] = field(default_factory=list)
    task_state: dict[str, Any] = field(default_factory=dict)
    connector_session: ConnectorSessionState | None = None
    client: Any = None
    org_id: str = ""
    settings: Any = None
    environment_name: str = "production"


def infer_missing_parameters(
    plan: ConnectorActionPlan,
    context: ParameterInferenceContext,
) -> ConnectorActionPlan:
    """Fill confidently inferrable args before validation; never infer sensitive fields."""
    session = context.connector_session or load_connector_session(context.task_state)
    plan = bind_plan_from_session(plan, session)
    if plan.invoke_action == "asana.tasks.create":
        return _infer_asana_task_create(plan, context)
    return plan


def _infer_asana_task_create(
    plan: ConnectorActionPlan,
    context: ParameterInferenceContext,
) -> ConnectorActionPlan:
    args = dict(plan.args or {})
    inferred: list[str] = list(plan.inferred_fields)
    sources = dict(plan.inference_sources)

    if not _arg_present(args, "project") and not _arg_present(args, "project_id"):
        project, source = _infer_project(context)
        if project and source:
            args["project"] = project
            inferred.append("project")
            sources["project"] = source

    if not _has_task_title(args):
        title, source = _infer_task_title(context)
        if title and source:
            args["name"] = title
            inferred.append("name")
            sources["name"] = source

    if not inferred:
        return plan
    return replace(
        plan,
        args=args,
        inferred_fields=tuple(dict.fromkeys([*plan.inferred_fields, *inferred])),
        inference_sources=sources,
    )


def _arg_present(args: dict[str, Any], key: str) -> bool:
    return bool(str(args.get(key) or "").strip())


def _has_task_title(args: dict[str, Any]) -> bool:
    name = str(args.get("name") or "").strip()
    assignee_hint = str(args.get("assignee_hint") or "").strip()
    return bool(name) and name.lower() != assignee_hint.lower()


def _infer_project(context: ParameterInferenceContext) -> tuple[str | None, str | None]:
    for text in _context_texts(context):
        match = PROJECT_IN_MESSAGE.search(text) or PROJECT_NAMED.search(text)
        if match:
            project = match.group(1).strip(" \"'")
            if project:
                return project[:120], "your last message"

    connector_project = _single_asana_project(context)
    if connector_project:
        return connector_project, "only open project in Asana"

    return None, None


def _infer_task_title(context: ParameterInferenceContext) -> tuple[str | None, str | None]:
    for text in reversed(_context_texts(context)):
        match = TASK_PHRASE.search(text)
        if match:
            title = match.group(1).strip(" .")
            if title and len(title.split()) >= 2:
                source = "your last message" if text == context.message.strip() else "recent conversation"
                return title[:200], source
    return None, None


def _context_texts(context: ParameterInferenceContext) -> list[str]:
    texts = [context.message.strip()]
    texts.extend(str(item).strip() for item in context.conversation_history if str(item).strip())
    session = context.connector_session or load_connector_session(context.task_state)
    if session.session_summary.strip():
        texts.append(session.session_summary.strip())
    resolved = session.resolved_entities or (context.task_state or {}).get("resolved_entities") or {}
    if isinstance(resolved, dict):
        for value in resolved.values():
            if isinstance(value, str) and value.strip():
                texts.append(value.strip())
    return texts


def _single_asana_project(context: ParameterInferenceContext) -> str | None:
    if not context.client or not context.org_id or not context.settings:
        return None
    from app.services.asana_tools import fetch_single_asana_project_name

    return fetch_single_asana_project_name(
        context.client,
        context.org_id,
        context.settings,
        environment_name=context.environment_name,
    )
