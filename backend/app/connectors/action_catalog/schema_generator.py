"""Infer per-action JSON Schema from catalog action keys (Claude/MCP-style)."""
from __future__ import annotations

import re
from typing import Any
from app.core.safe_dict import safe_normalize_stored_dict

_CONNECTOR_ID: dict[str, Any] = {
    "type": "string",
    "description": "Optional connector instance id when multiple connections exist.",
}

_PROPERTIES: dict[str, Any] = {
    "type": "object",
    "description": "Vendor-specific property map for create/update operations.",
    "additionalProperties": True,
}

# resource plural/slug -> singular id prefix
_RESOURCE_SINGULAR: dict[str, str] = {
    "contacts": "contact",
    "contact": "contact",
    "people": "person",
    "persons": "person",
    "person": "person",
    "leads": "lead",
    "lead": "lead",
    "deals": "deal",
    "deal": "deal",
    "companies": "company",
    "company": "company",
    "accounts": "account",
    "account": "account",
    "tickets": "ticket",
    "ticket": "ticket",
    "issues": "issue",
    "issue": "issue",
    "tasks": "task",
    "task": "task",
    "items": "item",
    "item": "item",
    "messages": "message",
    "message": "message",
    "files": "file",
    "file": "file",
    "documents": "document",
    "document": "document",
    "folders": "folder",
    "folder": "folder",
    "projects": "project",
    "project": "project",
    "campaigns": "campaign",
    "campaign": "campaign",
    "invoices": "invoice",
    "invoice": "invoice",
    "customers": "customer",
    "customer": "customer",
    "users": "user",
    "user": "user",
    "events": "event",
    "event": "event",
    "pages": "page",
    "page": "page",
    "reports": "report",
    "report": "report",
    "orders": "order",
    "order": "order",
    "products": "product",
    "product": "product",
    "notes": "note",
    "note": "note",
    "lists": "list",
    "list": "list",
    "channels": "channel",
    "channel": "channel",
    "conversations": "conversation",
    "conversation": "conversation",
    "incidents": "incident",
    "incident": "incident",
    "opportunities": "opportunity",
    "opportunity": "opportunity",
    "organizations": "organization",
    "organization": "organization",
    "teams": "team",
    "team": "team",
    "boards": "board",
    "board": "board",
    "records": "record",
    "record": "record",
}


def _singular(resource: str) -> str:
    key = resource.lower().strip()
    if key in _RESOURCE_SINGULAR:
        return _RESOURCE_SINGULAR[key]
    if key.endswith("ies"):
        return key[:-3] + "y"
    if key.endswith("s") and len(key) > 3:
        return key[:-1]
    return key


def _id_field(resource: str) -> str:
    return f"{_singular(resource)}_id"


def _base_props(**extra: dict[str, Any]) -> dict[str, Any]:
    props = {"connector_id": _CONNECTOR_ID, **extra}
    return props


def _schema(*, properties: dict[str, Any], required: list[str] | None = None) -> dict[str, Any]:
    return {
        "type": "object",
        "properties": properties,
        "required": required or [],
    }


def _parse_action_key(action_key: str) -> tuple[str, str, str]:
    """Return vendor, resource, operation from `vendor.resource.operation`."""
    parts = action_key.split(".")
    if len(parts) >= 3:
        return parts[0], parts[1], ".".join(parts[2:])
    if len(parts) == 2:
        return parts[0], "record", parts[1]
    return action_key, "record", "execute"


def infer_action_schema(
    action_key: str,
    *,
    kind: str = "read",
    description: str | None = None,
) -> dict[str, Any]:
    """Build typed JSON Schema parameters for any catalog action key."""
    _vendor, resource, operation = _parse_action_key(action_key)
    op = operation.lower()
    rid = _id_field(resource)
    desc = description or action_key

    # --- Read operations ---
    if op in {"list", "query"}:
        return _schema(
            properties=_base_props(
                query={"type": "string", "description": f"Optional filter keywords for {resource}."},
                limit={"type": "integer", "description": "Maximum results.", "default": 25},
                offset={"type": "integer", "description": "Pagination offset.", "default": 0},
            )
        )

    if op == "search":
        return _schema(
            properties=_base_props(
                query={"type": "string", "description": f"Search keywords for {resource}."},
                filter_groups={
                    "type": "array",
                    "description": "Advanced filter groups (vendor-specific structure).",
                    "items": {"type": "object"},
                },
                limit={"type": "integer", "default": 25},
            )
        )

    if op == "get":
        props = _base_props(**{rid: {"type": "string", "description": f"{_singular(resource).title()} id."}})
        if resource in {"contacts", "contact", "people", "person", "users", "user", "leads", "lead"}:
            props["email"] = {"type": "string", "description": "Lookup by email when id is unknown."}
        if resource in {"companies", "company", "organizations", "organization"}:
            props["domain"] = {"type": "string", "description": "Lookup by domain when id is unknown."}
        return _schema(properties=props)

    if op in {"export", "download"}:
        return _schema(
            properties=_base_props(
                **{rid: {"type": "string"}},
                format={"type": "string", "description": "Export format when supported (csv, pdf, json)."},
            )
        )

    # --- Messaging / notifications ---
    if op in {"send", "post", "post_message", "reply"} or "message" in op:
        return _schema(
            properties=_base_props(
                channel={"type": "string", "description": "Channel, room, or thread id."},
                to={"type": "string", "description": "Recipient email, user id, or address."},
                subject={"type": "string"},
                text={"type": "string", "description": "Message body."},
                message={"type": "string", "description": "Alias for text."},
                body={"type": "string", "description": "Alias for text."},
            ),
            required=["text"] if op == "send" else [],
        )

    # --- Write: create ---
    if op == "create":
        props = _base_props(
            properties=_PROPERTIES,
            name={"type": "string"},
            title={"type": "string"},
        )
        if resource in {"contacts", "contact", "people", "person", "leads", "lead", "users", "user"}:
            props["email"] = {"type": "string"}
            props["firstname"] = {"type": "string"}
            props["lastname"] = {"type": "string"}
        if resource in {"deals", "deal", "opportunities", "opportunity"}:
            props["dealname"] = {"type": "string"}
            props["amount"] = {"type": "number"}
            props["stage"] = {"type": "string"}
        if resource in {"tasks", "task", "tickets", "ticket", "issues", "issue"}:
            props["subject"] = {"type": "string"}
            props["summary"] = {"type": "string"}
        req = ["properties"]
        if resource in {"tasks", "task"}:
            req = ["subject"]
        elif resource in {"contacts", "contact", "people", "person", "leads", "lead"}:
            req = ["email"]
        return _schema(properties=props, required=req)

    # --- Write: update / upsert / merge ---
    if op in {"update", "upsert", "merge", "patch", "set"}:
        return _schema(
            properties=_base_props(
                **{rid: {"type": "string", "description": f"{_singular(resource).title()} id."}},
                properties=_PROPERTIES,
            ),
            required=[rid, "properties"] if op == "update" else [rid],
        )

    if op == "delete" or op.endswith(".delete"):
        return _schema(
            properties=_base_props(**{rid: {"type": "string"}}),
            required=[rid],
        )

    if op in {"add", "add_contact", "enroll", "assign"}:
        props = _base_props(**{rid: {"type": "string"}})
        if op == "enroll":
            props["sequence_id"] = {"type": "string"}
        if "list" in op or op == "add":
            props["list_id"] = {"type": "string"}
        return _schema(properties=props)

    if op in {"upload", "import"}:
        return _schema(
            properties=_base_props(
                name={"type": "string"},
                file_id={"type": "string"},
                folder_id={"type": "string"},
                content={"type": "string", "description": "Base64 or text content when inline upload is supported."},
                mime_type={"type": "string"},
            ),
            required=["name"],
        )

    if op in {"run", "trigger", "execute", "start", "schedule"}:
        return _schema(
            properties=_base_props(
                **{rid: {"type": "string"}},
                parameters={"type": "object", "additionalProperties": True, "description": "Run parameters."},
                cron={"type": "string", "description": "Cron expression for scheduled runs."},
            )
        )

    if op in {"update_stage", "transition", "move"}:
        return _schema(
            properties=_base_props(
                **{rid: {"type": "string"}},
                stage={"type": "string", "description": "Target stage id or label."},
                pipeline_id={"type": "string"},
            ),
            required=[rid, "stage"],
        )

    if op == "batch" or resource == "batch":
        return _schema(
            properties=_base_props(
                operations={
                    "type": "array",
                    "description": "Batch operations to execute.",
                    "items": {"type": "object"},
                },
                inputs={"type": "array", "items": {"type": "object"}},
            )
        )

    if op in {"apply", "sync", "track", "submit", "approve", "reject", "close", "reopen"}:
        return _schema(
            properties=_base_props(
                **{rid: {"type": "string"}},
                comment={"type": "string"},
                status={"type": "string"},
                properties=_PROPERTIES,
            ),
            required=[rid] if kind != "read" else [],
        )

    # --- Kind-based fallback (no generic payload blob) ---
    if kind == "read":
        return _schema(
            properties=_base_props(
                query={"type": "string", "description": f"Filter or search for {resource}."},
                limit={"type": "integer", "default": 25},
                **{rid: {"type": "string"}},
            )
        )

    return _schema(
        properties=_base_props(
            **{rid: {"type": "string"}},
            properties=_PROPERTIES,
            data={"type": "object", "additionalProperties": True, "description": f"Fields for {desc}."},
        ),
    )


def normalize_schema(schema: dict[str, Any]) -> dict[str, Any]:
    """Ensure schema has object type and properties dict."""
    if not isinstance(schema, dict):
        return {"type": "object", "properties": {}}
    if schema.get("type") != "object":
        return {"type": "object", "properties": schema.get("properties") or {}}
    props = schema.get("properties")
    if not isinstance(props, dict):
        schema = dict(schema)
        schema["properties"] = {}
    if "connector_id" not in schema.get("properties", {}):
        merged = safe_normalize_stored_dict(schema, key='properties')
        merged["connector_id"] = _CONNECTOR_ID
        schema = dict(schema)
        schema["properties"] = merged
    return schema
