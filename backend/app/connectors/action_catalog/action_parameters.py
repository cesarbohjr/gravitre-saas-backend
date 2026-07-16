"""Per-action JSON Schema parameters for LLM tool definitions (Claude/MCP-style)."""
from __future__ import annotations

from functools import lru_cache
from typing import Any

from app.connectors.action_catalog.schema_generator import infer_action_schema, normalize_schema

_CONNECTOR_ID = {
    "type": "string",
    "description": "Optional connector instance id when multiple connections exist.",
}

_COMMON_READ = {
    "query": {"type": "string", "description": "Search keywords or natural language query."},
    "limit": {"type": "integer", "description": "Maximum number of results.", "default": 25},
    "connector_id": _CONNECTOR_ID,
}

_HUBSPOT_PROPERTIES = {
    "type": "object",
    "description": "HubSpot property map (e.g. email, firstname, dealstage, amount).",
    "additionalProperties": True,
}

# Hand-tuned overrides for high-traffic actions (take precedence over inference).
ACTION_PARAMETERS: dict[str, dict[str, Any]] = {    "hubspot.contacts.get": {
        "type": "object",
        "properties": {
            "contact_id": {"type": "string", "description": "HubSpot contact id."},
            "email": {"type": "string", "description": "Lookup by email when id is unknown."},
            "connector_id": _CONNECTOR_ID,
        },
        "required": [],
    },
    "hubspot.contacts.search": {
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "Free-text search (name, email, company)."},
            "filter_groups": {
                "type": "array",
                "description": "HubSpot filterGroups payload for advanced search.",
                "items": {"type": "object"},
            },
            "limit": {"type": "integer", "default": 25},
            "connector_id": _CONNECTOR_ID,
        },
        "required": [],
    },
    "hubspot.contacts.list": {
        "type": "object",
        "properties": {
            "limit": {"type": "integer", "default": 10, "description": "Max contacts to return (1–100)."},
            "properties": {
                "type": "array",
                "items": {"type": "string"},
                "description": "HubSpot contact property names to include.",
            },
            "connector_id": _CONNECTOR_ID,
        },
        "required": [],
    },
    "hubspot.associations.create": {
        "type": "object",
        "properties": {
            "from_type": {
                "type": "string",
                "description": "Source object type (contacts, deals, companies, tickets, notes).",
            },
            "from_id": {"type": "string", "description": "Source HubSpot object id."},
            "to_type": {
                "type": "string",
                "description": "Target object type (contacts, deals, companies, tickets, notes).",
            },
            "to_id": {"type": "string", "description": "Target HubSpot object id."},
            "connector_id": _CONNECTOR_ID,
        },
        "required": ["from_type", "from_id", "to_type", "to_id"],
    },
    "hubspot.contacts.create": {
        "type": "object",
        "properties": {
            "properties": _HUBSPOT_PROPERTIES,
            "email": {"type": "string"},
            "firstname": {"type": "string"},
            "lastname": {"type": "string"},
            "connector_id": _CONNECTOR_ID,
        },
        "required": ["properties"],
    },
    "hubspot.contacts.update": {
        "type": "object",
        "properties": {
            "contact_id": {"type": "string"},
            "properties": _HUBSPOT_PROPERTIES,
            "connector_id": _CONNECTOR_ID,
        },
        "required": ["contact_id", "properties"],
    },
    "hubspot.contacts.delete": {
        "type": "object",
        "properties": {
            "contact_id": {"type": "string"},
            "connector_id": _CONNECTOR_ID,
        },
        "required": ["contact_id"],
    },
    "hubspot.deals.get": {
        "type": "object",
        "properties": {
            "deal_id": {"type": "string"},
            "connector_id": _CONNECTOR_ID,
        },
        "required": ["deal_id"],
    },
    "hubspot.deals.search": {
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "Optional keywords to build a dealname CONTAINS filter."},
            "filter_groups": {"type": "array", "items": {"type": "object"}},
            "limit": {"type": "integer", "default": 25},
            "connector_id": _CONNECTOR_ID,
        },
        "required": [],
    },
    "hubspot.deals.list": {
        "type": "object",
        "properties": {
            "limit": {"type": "integer", "default": 25},
            "connector_id": _CONNECTOR_ID,
        },
        "required": [],
    },
    "hubspot.companies.get": {
        "type": "object",
        "properties": {
            "company_id": {"type": "string"},
            "domain": {"type": "string"},
            "connector_id": _CONNECTOR_ID,
        },
        "required": [],
    },
    "hubspot.tickets.search": {
        "type": "object",
        "properties": {
            "query": {"type": "string"},
            "filter_groups": {"type": "array", "items": {"type": "object"}},
            "limit": {"type": "integer", "default": 25},
            "connector_id": _CONNECTOR_ID,
        },
        "required": [],
    },
    "hubspot.pipelines.list": {
        "type": "object",
        "properties": {"connector_id": _CONNECTOR_ID},
        "required": [],
    },
    "hubspot.tickets.create": {
        "type": "object",
        "properties": {
            "properties": _HUBSPOT_PROPERTIES,
            "subject": {"type": "string"},
            "content": {"type": "string"},
            "connector_id": _CONNECTOR_ID,
        },
        "required": ["properties"],
    },
    "hubspot.deals.create": {
        "type": "object",
        "properties": {
            "properties": _HUBSPOT_PROPERTIES,
            "dealname": {"type": "string"},
            "amount": {"type": "number"},
            "connector_id": _CONNECTOR_ID,
        },
        "required": ["properties"],
    },
    "hubspot.deals.update": {
        "type": "object",
        "properties": {
            "deal_id": {"type": "string"},
            "properties": _HUBSPOT_PROPERTIES,
            "connector_id": _CONNECTOR_ID,
        },
        "required": ["deal_id", "properties"],
    },
    "hubspot.deals.delete": {
        "type": "object",
        "properties": {
            "deal_id": {"type": "string"},
            "connector_id": _CONNECTOR_ID,
        },
        "required": ["deal_id"],
    },
    "hubspot.deals.update_stage": {
        "type": "object",
        "properties": {
            "deal_id": {"type": "string"},
            "stage": {"type": "string", "description": "Target pipeline stage id or label."},
            "connector_id": _CONNECTOR_ID,
        },
        "required": ["deal_id", "stage"],
    },
    "hubspot.companies.search": {
        "type": "object",
        "properties": {
            "query": {"type": "string"},
            "filter_groups": {"type": "array", "items": {"type": "object"}},
            "limit": {"type": "integer", "default": 25},
            "connector_id": _CONNECTOR_ID,
        },
        "required": [],
    },
    "hubspot.sequences.enroll": {
        "type": "object",
        "properties": {
            "sequence_id": {"type": "string"},
            "contact_id": {"type": "string"},
            "connector_id": _CONNECTOR_ID,
        },
        "required": ["sequence_id", "contact_id"],
    },
    "hubspot.lists.add_contact": {
        "type": "object",
        "properties": {
            "list_id": {"type": "string"},
            "contact_id": {"type": "string"},
            "connector_id": _CONNECTOR_ID,
        },
        "required": ["list_id", "contact_id"],
    },
    "hubspot.lists.create": {
        "type": "object",
        "properties": {
            "name": {"type": "string", "description": "List name"},
            "object_type_id": {"type": "string", "description": "HubSpot object type id (default 0-1 contacts)"},
            "processing_type": {"type": "string", "description": "MANUAL or DYNAMIC"},
            "connector_id": _CONNECTOR_ID,
        },
        "required": ["name"],
    },
    "fred.series.get": {
        "type": "object",
        "properties": {
            "series_id": {"type": "string", "description": "FRED series id (e.g. GDP, UNRATE)."},
            "connector_id": _CONNECTOR_ID,
        },
        "required": ["series_id"],
    },
    "platform.health.snapshot": {
        "type": "object",
        "properties": {
            "lookback_days": {
                "type": "integer",
                "description": "Optional lookback window in days (default 30).",
            },
        },
        "required": [],
    },
    "nvd.cve.get": {
        "type": "object",
        "properties": {
            "cve_id": {"type": "string", "description": "CVE id (e.g. CVE-2024-1234)."},
            "connector_id": _CONNECTOR_ID,
        },
        "required": ["cve_id"],
    },
    "cisa_kev.feed.get": {
        "type": "object",
        "properties": {
            "connector_id": _CONNECTOR_ID,
        },
        "required": [],
    },
    "sec_edgar.filings.search": {
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "Company name or ticker for SEC EDGAR search."},
            "company": {"type": "string", "description": "Alias for query."},
            "connector_id": _CONNECTOR_ID,
        },
        "required": ["query"],
    },
    "hubspot.notes.create": {
        "type": "object",
        "properties": {
            "body": {"type": "string", "description": "Note body (HTML or plain text)."},
            "contact_id": {"type": "string"},
            "deal_id": {"type": "string"},
            "company_id": {"type": "string"},
            "connector_id": _CONNECTOR_ID,
        },
        "required": ["body"],
    },
    "hubspot.notes.delete": {
        "type": "object",
        "properties": {
            "note_id": {"type": "string"},
            "connector_id": _CONNECTOR_ID,
        },
        "required": ["note_id"],
    },
    "slack.post_message": {
        "type": "object",
        "properties": {
            "channel": {"type": "string", "description": "Channel id or #name."},
            "text": {"type": "string", "description": "Message body (mrkdwn supported)."},
            "message": {"type": "string", "description": "Alias for text."},
            "connector_id": _CONNECTOR_ID,
        },
        "required": ["channel"],
    },
    "slack.conversations.list": {
        "type": "object",
        "properties": {**_COMMON_READ},
        "required": [],
    },
    "google_drive.files.list": {
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "Drive query (e.g. name contains 'Q3')."},
            "folder_id": {"type": "string"},
            "limit": {"type": "integer", "default": 25},
            "connector_id": _CONNECTOR_ID,
        },
        "required": [],
    },
    "drive.files.list": {
        "type": "object",
        "properties": {
            "query": {"type": "string"},
            "folder_id": {"type": "string"},
            "limit": {"type": "integer", "default": 25},
            "connector_id": _CONNECTOR_ID,
        },
        "required": [],
    },
    "gmail.messages.send": {
        "type": "object",
        "properties": {
            "to": {"type": "string"},
            "subject": {"type": "string"},
            "body": {"type": "string"},
            "connector_id": _CONNECTOR_ID,
        },
        "required": ["to", "subject", "body"],
    },
    "apollo.people.search": {
        "type": "object",
        "properties": {
            "query": {"type": "string"},
            "person_titles": {"type": "array", "items": {"type": "string"}},
            "organization_domains": {"type": "array", "items": {"type": "string"}},
            "limit": {"type": "integer", "default": 25},
            "connector_id": _CONNECTOR_ID,
        },
        "required": [],
    },
    "apollo.people.match": {
        "type": "object",
        "properties": {
            "email": {"type": "string"},
            "first_name": {"type": "string"},
            "last_name": {"type": "string"},
            "name": {"type": "string"},
            "organization_name": {"type": "string"},
            "domain": {"type": "string"},
            "linkedin_url": {"type": "string"},
            "id": {"type": "string", "description": "Apollo person id when known."},
            "payload": {"type": "object", "additionalProperties": True},
            "connector_id": _CONNECTOR_ID,
        },
        "required": [],
    },
    "apollo.organizations.enrich": {
        "type": "object",
        "properties": {
            "domain": {"type": "string"},
            "name": {"type": "string"},
            "organization_name": {"type": "string"},
            "linkedin_url": {"type": "string"},
            "website_url": {"type": "string"},
            "connector_id": _CONNECTOR_ID,
        },
        "required": [],
    },
    "apollo.lists.list": {
        "type": "object",
        "properties": {"connector_id": _CONNECTOR_ID},
        "required": [],
    },
    "apollo.lists.create": {
        "type": "object",
        "properties": {
            "name": {"type": "string", "description": "Contact list name (Apollo label)."},
            "list_name": {"type": "string", "description": "Alias for name."},
            "modality": {
                "type": "string",
                "enum": ["contacts", "accounts"],
                "default": "contacts",
            },
            "connector_id": _CONNECTOR_ID,
        },
        "required": ["name"],
    },
    "engagebay.contacts.search": {
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "Name, email, or tag search."},
            "email": {"type": "string"},
            "limit": {"type": "integer", "default": 25},
            "connector_id": _CONNECTOR_ID,
        },
        "required": [],
    },
    "engagebay.contacts.get": {
        "type": "object",
        "properties": {
            "contact_id": {"type": "string"},
            "email": {"type": "string"},
            "connector_id": _CONNECTOR_ID,
        },
        "required": [],
    },
    "engagebay.contacts.create": {
        "type": "object",
        "properties": {
            "email": {"type": "string"},
            "firstname": {"type": "string"},
            "lastname": {"type": "string"},
            "properties": {"type": "object", "additionalProperties": True},
            "connector_id": _CONNECTOR_ID,
        },
        "required": ["email"],
    },
    "engagebay.contacts.update": {
        "type": "object",
        "properties": {
            "contact_id": {"type": "string"},
            "properties": {"type": "object", "additionalProperties": True},
            "connector_id": _CONNECTOR_ID,
        },
        "required": ["contact_id", "properties"],
    },
    "engagebay.deals.list": {
        "type": "object",
        "properties": {**_COMMON_READ},
        "required": [],
    },
    "engagebay.tasks.create": {
        "type": "object",
        "properties": {
            "subject": {"type": "string"},
            "contact_id": {"type": "string"},
            "due_date": {"type": "string", "description": "ISO date or datetime."},
            "connector_id": _CONNECTOR_ID,
        },
        "required": ["subject"],
    },
}


@lru_cache(maxsize=1)
def _catalog_explicit_schemas() -> dict[str, dict[str, Any]]:
    from app.connectors.action_catalog.registry import all_catalog_action_specs

    explicit: dict[str, dict[str, Any]] = {}
    for spec in all_catalog_action_specs():
        if spec.input_schema:
            explicit[spec.id.lower()] = spec.input_schema
    return explicit


_inferred_cache: dict[tuple[str, str], dict[str, Any]] = {}


def clear_catalog_schema_cache() -> None:
    _catalog_explicit_schemas.cache_clear()


def clear_action_schema_cache() -> None:
    _inferred_cache.clear()


def resolve_action_schema(
    action_key: str,
    *,
    kind: str,
    suffix: str,
    description: str | None = None,
    explicit_schema: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Resolve JSON Schema for an action: override → extension → catalog → inferred."""
    key = action_key.strip()
    if key in ACTION_PARAMETERS:
        return normalize_schema(ACTION_PARAMETERS[key])

    from app.connectors.action_catalog.extensions import ACTION_SCHEMA_EXTENSIONS

    if key in ACTION_SCHEMA_EXTENSIONS:
        return normalize_schema(ACTION_SCHEMA_EXTENSIONS[key])

    if explicit_schema:
        return normalize_schema(explicit_schema)

    catalog_schema = _catalog_explicit_schemas().get(key.lower())
    if catalog_schema:
        return normalize_schema(catalog_schema)

    cache_key = (key.lower(), kind)
    if cache_key in _inferred_cache:
        return _inferred_cache[cache_key]

    schema = normalize_schema(
        infer_action_schema(key, kind=kind, description=description or key)
    )
    _inferred_cache[cache_key] = schema
    return schema


def parameters_for_action(action_key: str, *, kind: str, suffix: str) -> dict[str, Any]:
    return resolve_action_schema(action_key, kind=kind, suffix=suffix)