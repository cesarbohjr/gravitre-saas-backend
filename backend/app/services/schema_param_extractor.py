"""Schema-constrained parameter extraction (Module B Phase 2).

Replaces per-vendor regex in chat_action_mapper with structured output
constrained to each action's workflow / JSON schema. Routes through the
FAST/low model tier (TaskType.CLASSIFICATION) — bounded extraction, not
reasoning.
"""
from __future__ import annotations

import json
import re
from typing import Any

from pydantic import BaseModel, Field

from app.config import Settings, get_settings
from app.core.logging import get_logger
from app.services.parameter_ledger import (
    ParameterLedger,
    bind_args_from_ledger,
    get_ledger,
    upsert_slots,
)

logger = get_logger(__name__)


class ExtractedActionArgs(BaseModel):
    """Loose bag of action arguments — keys constrained by prompt/schema list."""

    arguments: dict[str, str] = Field(default_factory=dict)


def _schema_field_keys(invoke_action: str) -> list[tuple[str, str]]:
    """Return (label, primary_arg_key) for required + optional workflow fields."""
    from app.connectors.action_catalog.action_workflow_schema import get_workflow_schema

    schema = get_workflow_schema(invoke_action)
    if not schema:
        return []
    out: list[tuple[str, str]] = []
    for field in (*schema.required_fields, *schema.optional_fields):
        if field.arg_keys:
            out.append((field.label, field.arg_keys[0]))
    return out


def extract_action_args_heuristic(
    invoke_action: str,
    message: str,
    *,
    ledger: ParameterLedger | None = None,
    existing_args: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Cheap schema-driven fill without a model call (tests + offline fallback)."""
    from app.services.chat_message_normalize import strip_assistant_scope_prefix
    from app.services.parameter_ledger import (
        EMAIL_RE,
        PROJECT_KEY_RE,
        QUOTED_RE,
        ingest_message_slots,
    )

    text = strip_assistant_scope_prefix(message or "")
    active = ledger or ParameterLedger()
    active = ingest_message_slots(text, ledger=active)
    args = bind_args_from_ledger(invoke_action, dict(existing_args or {}), active)

    field_keys = _schema_field_keys(invoke_action)
    if not field_keys:
        return args

    quoted = QUOTED_RE.findall(text)
    email = EMAIL_RE.search(text)
    project = PROJECT_KEY_RE.search(text)

    for label, key in field_keys:
        if str(args.get(key) or "").strip():
            continue
        label_l = label.lower()
        if key in {"to", "email"} or "recipient" in label_l or "email" in label_l:
            if email:
                args[key] = email.group(0)
        elif key in {"channel", "channel_id"} or "channel" in label_l:
            value = active.get("channel")
            if value:
                args[key] = value
        elif key in {"project_key", "project"} or "project" in label_l:
            if project:
                args[key] = project.group(1).upper()
            elif active.get("project_key"):
                args[key] = active.get("project_key")
        elif key in {"list_id"} or label_l in {"list id", "list"}:
            list_m = re.search(r"\bin\s+list\s+(\w[\w-]*)", text, re.I) or re.search(
                r"\blist\s+(\w[\w-]*)",
                text,
                re.I,
            )
            if list_m:
                args[key] = list_m.group(1)
            elif active.get("list_id"):
                args[key] = active.get("list_id")  # type: ignore[assignment]
        elif key in {"summary", "title", "name"} or any(
            tok in label_l for tok in ("summary", "title", "name", "list name")
        ):
            if quoted:
                args[key] = quoted[0].strip()
            else:
                # Unquoted Jira/title: "create an issue login page broken in project ENG"
                titled = re.search(
                    r"\b(?:titled|called|named|summary|title)\s+(?:is\s+)?(.+?)"
                    r"(?:\s+in\s+list\b|\s+in\s+project\b|\s+project\s+\S+\s*$|$)",
                    text,
                    re.I,
                )
                if not titled:
                    titled = re.search(
                        r"\b(?:issue|ticket|task)\s+(.+?)(?:\s+in\s+project\b|\s+project\s+[A-Z0-9_-]+\s*$)",
                        text,
                        re.I,
                    )
                if titled:
                    args[key] = titled.group(1).strip(" .\"'")[:200]
                elif active.get("quoted"):
                    args[key] = active.get("quoted")  # type: ignore[assignment]
                else:
                    # Follow-up turn that is mostly the title itself.
                    cleaned = re.sub(
                        r"^(?:sure|ok|okay|yes|the\s+title\s+is|title[:\s]+)\s*",
                        "",
                        text,
                        flags=re.I,
                    ).strip()
                    cleaned = re.sub(
                        r"\s+(?:in\s+)?project\s+[A-Za-z0-9_-]+\s*$",
                        "",
                        cleaned,
                        flags=re.I,
                    ).strip()
                    if (
                        cleaned
                        and len(cleaned.split()) >= 2
                        and not re.search(
                            r"\b(create|send|post)\s+(?:an?\s+)?(?:issue|email|message)\b",
                            cleaned,
                            re.I,
                        )
                    ):
                        if cleaned:
                            args[key] = cleaned[:200]
        elif key in {"subject"} or "subject" in label_l:
            if quoted:
                args[key] = quoted[0].strip()
            elif active.get("subject"):
                args[key] = active.get("subject")  # type: ignore[assignment]
            else:
                # "subject is X" / "ticket about X" / "ticket for X"
                subj = re.search(
                    r"\bsubject\s*(?:is|=|:)\s*(.+?)(?:\s+priority\b|\s+body\b|$)",
                    text,
                    re.I,
                )
                if not subj:
                    subj = re.search(
                        r"\b(?:ticket|issue)\s+(?:for|about|regarding)\s+(.+?)(?:\s+priority\b|$)",
                        text,
                        re.I,
                    )
                if not subj:
                    # "create a ticket checkout fails on mobile priority high"
                    subj = re.search(
                        r"\b(?:create|open|file)\s+(?:a\s+)?(?:support\s+)?(?:ticket|issue)\s+(.+?)(?:\s+priority\b|$)",
                        text,
                        re.I,
                    )
                if subj:
                    args[key] = subj.group(1).strip(" .\"'")[:300]
        elif key in {"body", "message", "text", "description", "comment"} or any(
            tok in label_l for tok in ("body", "message", "description", "comment")
        ):
            if len(quoted) > 1:
                args[key] = quoted[-1].strip()
            elif active.get(key) or active.get("body") or active.get("message") or active.get(
                "description"
            ):
                args[key] = (
                    active.get(key)
                    or active.get("body")
                    or active.get("message")
                    or active.get("description")  # type: ignore[assignment]
                )
            else:
                # Zendesk/Freshdesk/Intercom: reuse subject text as description seed
                # when the user only supplied one free-text blob.
                seed = args.get("subject") or active.get("subject") or active.get("quoted")
                if seed and ("ticket" in text.lower() or "zendesk" in text.lower()
                             or "freshdesk" in text.lower() or "intercom" in text.lower()):
                    args[key] = str(seed)
        elif key in {"item_name", "name"} or any(
            tok in label_l for tok in ("item name", "task name", "page title")
        ):
            if quoted:
                args[key] = quoted[0].strip()[:200]
            else:
                named = re.search(
                    r"\b(?:called|named|titled)\s+[\"']?([^\"'.]+?)[\"']?"
                    r"(?:\s+on\s+board\b|\s+in\s+list\b|\s+board\b|\s+list\b|$)",
                    text,
                    re.I,
                )
                if not named:
                    named = re.search(
                        r"\b(?:create|add)\s+(?:a\s+)?(?:task|item|page|deal|issue)\s+(.+?)"
                        r"(?:\s+on\s+board\b|\s+in\s+list\b|\s+board\b|\s+list\b|$)",
                        text,
                        re.I,
                    )
                if named:
                    args[key] = named.group(1).strip(" .\"'")[:200]
                elif active.get("name") or active.get("summary") or active.get("quoted"):
                    args[key] = (
                        active.get("name") or active.get("summary") or active.get("quoted")  # type: ignore[assignment]
                    )
        elif key in {"board_id"} or "board" in label_l:
            board = re.search(r"\bboard\s+(\w[\w-]*)", text, re.I)
            if board:
                args[key] = board.group(1)
            elif active.get("board_id"):
                args[key] = active.get("board_id")  # type: ignore[assignment]
        elif key in {"title"} or "title" in label_l or "pr title" in label_l or "deal" in label_l:
            if quoted:
                args[key] = quoted[0].strip()[:200]
            else:
                titled = re.search(
                    r"\b(?:titled|called|named|title)\s*(?:is|=|:)?\s*[\"']?([^\"'.]+)[\"']?",
                    text,
                    re.I,
                )
                if titled:
                    args[key] = titled.group(1).strip()[:200]
                elif active.get("title") or active.get("summary") or active.get("name") or active.get(
                    "quoted"
                ):
                    args[key] = (
                        active.get("title")
                        or active.get("summary")
                        or active.get("name")
                        or active.get("quoted")  # type: ignore[assignment]
                    )

    return {k: v for k, v in args.items() if v is not None and str(v).strip()}


async def extract_action_args(
    invoke_action: str,
    message: str,
    *,
    ledger: ParameterLedger | None = None,
    existing_args: dict[str, Any] | None = None,
    settings: Settings | None = None,
    org_id: str | None = None,
    use_model: bool = True,
) -> dict[str, Any]:
    """Extract args constrained to the action schema; FAST-tier model + heuristic merge."""
    heuristic = extract_action_args_heuristic(
        invoke_action,
        message,
        ledger=ledger,
        existing_args=existing_args,
    )
    field_keys = _schema_field_keys(invoke_action)
    if not field_keys or not use_model:
        return heuristic

    missing = [label for label, key in field_keys if not str(heuristic.get(key) or "").strip()]
    # If heuristics already filled all required-looking keys, skip the model call.
    from app.connectors.action_catalog.action_workflow_schema import get_workflow_schema

    schema = get_workflow_schema(invoke_action)
    if schema:
        required_missing = [
            f.label
            for f in schema.required_fields
            if f.arg_keys and not str(heuristic.get(f.arg_keys[0]) or "").strip()
        ]
        if not required_missing:
            return heuristic
        missing = required_missing

    try:
        from app.services.model_router import TaskType, get_model_router

        ledger_snapshot = {}
        active = ledger or ParameterLedger()
        for key, slot in active.slots.items():
            ledger_snapshot[key] = slot.value

        field_lines = "\n".join(f"- {label} (arg: {key})" for label, key in field_keys)
        prompt = (
            "Extract action arguments from the user message and parameter ledger.\n"
            "Return ONLY keys that have a confident value. Do not invent ids.\n\n"
            f"Action: {invoke_action}\n"
            f"Fields:\n{field_lines}\n\n"
            f"Parameter ledger (prior turns): {json.dumps(ledger_snapshot)}\n"
            f"Still missing: {', '.join(missing) or 'none'}\n"
            f"Current message: {message}\n"
        )
        response = await get_model_router(settings or get_settings()).complete(
            task_type=TaskType.CLASSIFICATION,
            prompt=prompt,
            system_prompt=(
                "You extract structured connector action arguments. "
                "Respond as JSON object: {\"arguments\": {\"arg_key\": \"value\", ...}}."
            ),
            temperature=0.0,
            max_tokens=400,
            response_format=ExtractedActionArgs,
            org_id=org_id,
        )
        parsed = response.parsed if isinstance(response.parsed, dict) else None
        if not parsed:
            try:
                parsed = json.loads(response.content or "{}")
            except json.JSONDecodeError:
                parsed = {}
        model_args = parsed.get("arguments") if isinstance(parsed, dict) else None
        if not isinstance(model_args, dict):
            # Flat dict of args
            model_args = {
                k: v
                for k, v in (parsed or {}).items()
                if k != "arguments" and isinstance(v, (str, int, float))
            }
        allowed = {key for _, key in field_keys}
        for key, value in (model_args or {}).items():
            if key not in allowed:
                continue
            text_val = str(value or "").strip()
            if text_val and not str(heuristic.get(key) or "").strip():
                heuristic[key] = text_val
    except Exception as exc:  # noqa: BLE001
        logger.debug("schema_param_extractor model skipped: %s", exc)

    return heuristic


async def enrich_plan_args_from_schema(
    plan: Any,
    message: str,
    *,
    task_state: dict[str, Any] | None = None,
    settings: Settings | None = None,
    org_id: str | None = None,
    use_model: bool = True,
) -> Any:
    """Merge schema extraction into a ConnectorActionPlan and update ledger slots."""
    from dataclasses import replace

    from app.services.chat_connector_models import ConnectorActionPlan
    from app.services.parameter_ledger import ledger_patch

    if not isinstance(plan, ConnectorActionPlan) or not plan.invoke_action:
        return plan, {}
    ledger = get_ledger(task_state)
    extracted = await extract_action_args(
        plan.invoke_action,
        message,
        ledger=ledger,
        existing_args=dict(plan.args or {}),
        settings=settings,
        org_id=org_id,
        use_model=use_model,
    )
    if not extracted:
        return plan, {}
    merged = {**(plan.args or {}), **extracted}
    # Mirror string args into ledger.
    string_slots = {
        str(k): str(v)
        for k, v in merged.items()
        if isinstance(v, str) and str(v).strip()
    }
    upsert_slots(ledger, string_slots, source="schema_param_extractor")
    return replace(plan, args=merged), ledger_patch(ledger)
