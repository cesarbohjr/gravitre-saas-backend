"""F1 WRITE slice — bounded governed-send compile (approval still required).

Does not auto-authorize. Does not expand READ HMAC. Catalog ActionSpec remains
the materialized owner (option B).
"""
from __future__ import annotations

from typing import Any

from app.connectors.action_catalog.f1_read_slice import catalog_action_key, registry_action_key
from app.connectors.action_catalog.models import ParameterSourceRule

F1_WRITE_CATALOG_ACTIONS: frozenset[str] = frozenset(
    {
        "email.send",
        "gmail.messages.send",
        "slack.post_message",
        "hubspot.contacts.create",
    }
)

# Never auto-approve these classes (2.0-F).
NON_AUTO_APPROVE_RISK_CLASSES: frozenset[str] = frozenset(
    {
        "external_send",
        "financial",
        "destructive",
        "hr",
        "security",
        "crm_create",
    }
)


def is_f1_write_action(action_key: str) -> bool:
    catalog = catalog_action_key(action_key)
    raw = str(action_key or "").strip()
    return catalog in F1_WRITE_CATALOG_ACTIONS or raw in F1_WRITE_CATALOG_ACTIONS


def _rule(
    parameter: str,
    *sources: str,
    required_by_api: bool = False,
    required_from_user: bool = False,
    aliases: tuple[str, ...] = (),
    default: Any = None,
) -> ParameterSourceRule:
    return ParameterSourceRule(
        parameter=parameter,
        sources=tuple(sources),  # type: ignore[arg-type]
        required_by_api=required_by_api,
        required_from_user=required_from_user,
        aliases=aliases,
        default=default,
    )


_OVERLAYS: dict[str, dict[str, Any]] = {
    "email.send": {
        "capabilities": ("communication.email.send", "email.send"),
        "required_parameters": ("to", "subject", "body"),
        "optional_parameters": ("connector_id",),
        "parameter_source_rules": (
            _rule(
                "to",
                "USER_EXPLICIT",
                "TASK_CONTEXT",
                "MODEL_INFERENCE",
                required_by_api=True,
                required_from_user=True,
                aliases=("email", "recipient"),
            ),
            _rule(
                "subject",
                "USER_EXPLICIT",
                "TASK_CONTEXT",
                "MODEL_INFERENCE",
                required_by_api=True,
                required_from_user=True,
            ),
            _rule(
                "body",
                "USER_EXPLICIT",
                "TASK_CONTEXT",
                "MODEL_INFERENCE",
                required_by_api=True,
                required_from_user=True,
                aliases=("text", "message"),
            ),
        ),
        "resource_requirements": (),
        "auth_scope_requirements": ("email:send", "email:*"),
        "availability_requirements": ("connector_connected", "auth_valid"),
        "governance_classification": "write",
        "risk_class": "external_send",
        "execution_adapter": "email.send",
        "observation_adapter": "email_send_observation",
    },
    "gmail.messages.send": {
        "capabilities": ("communication.email.send", "email.send"),
        "required_parameters": ("to", "subject", "body"),
        "optional_parameters": ("connector_id",),
        "parameter_source_rules": (
            _rule(
                "to",
                "USER_EXPLICIT",
                "TASK_CONTEXT",
                "MODEL_INFERENCE",
                required_by_api=True,
                required_from_user=True,
                aliases=("email", "recipient"),
            ),
            _rule(
                "subject",
                "USER_EXPLICIT",
                "TASK_CONTEXT",
                "MODEL_INFERENCE",
                required_by_api=True,
                required_from_user=True,
            ),
            _rule(
                "body",
                "USER_EXPLICIT",
                "TASK_CONTEXT",
                "MODEL_INFERENCE",
                required_by_api=True,
                required_from_user=True,
                aliases=("text", "message"),
            ),
        ),
        "resource_requirements": (),
        "auth_scope_requirements": ("gmail:send", "gmail:*"),
        "availability_requirements": ("connector_connected", "auth_valid"),
        "governance_classification": "write",
        "risk_class": "external_send",
        "execution_adapter": "gmail.messages.send",
        "observation_adapter": "gmail_send_observation",
    },
    "slack.post_message": {
        "capabilities": ("communication.slack.send",),
        "required_parameters": ("channel", "text"),
        "optional_parameters": ("message", "connector_id"),
        "parameter_source_rules": (
            _rule(
                "channel",
                "USER_EXPLICIT",
                "TASK_CONTEXT",
                "MODEL_INFERENCE",
                required_by_api=True,
                required_from_user=True,
            ),
            _rule(
                "text",
                "USER_EXPLICIT",
                "TASK_CONTEXT",
                "MODEL_INFERENCE",
                required_by_api=True,
                required_from_user=True,
                aliases=("message", "body"),
            ),
        ),
        "resource_requirements": ("workspace",),
        "auth_scope_requirements": ("slack:messages:write", "slack:*"),
        "availability_requirements": ("connector_connected", "auth_valid"),
        "governance_classification": "write",
        "risk_class": "external_send",
        "execution_adapter": "slack.post_message",
        "observation_adapter": "slack_post_message_observation",
    },
    "hubspot.contacts.create": {
        "capabilities": ("crm.contact.create",),
        "required_parameters": ("email",),
        "optional_parameters": ("firstname", "lastname", "properties", "connector_id"),
        "parameter_source_rules": (
            _rule("portal_id", "RESOURCE_RESOLVER", "CONNECTOR_METADATA", aliases=("portalId", "hub_id")),
            _rule(
                "email",
                "USER_EXPLICIT",
                "TASK_CONTEXT",
                "MODEL_INFERENCE",
                required_by_api=True,
                required_from_user=True,
                aliases=("to",),
            ),
            _rule("firstname", "USER_EXPLICIT", "TASK_CONTEXT", "MODEL_INFERENCE"),
            _rule("lastname", "USER_EXPLICIT", "TASK_CONTEXT", "MODEL_INFERENCE"),
        ),
        "resource_requirements": ("portal",),
        "auth_scope_requirements": ("hubspot:contacts:write", "hubspot:*"),
        "availability_requirements": ("connector_connected", "auth_valid"),
        "governance_classification": "write",
        "risk_class": "crm_create",
        "execution_adapter": "hubspot.contacts.create",
        "observation_adapter": "hubspot_contacts_create_observation",
    },
}


def write_overlay_for(action_id: str) -> dict[str, Any] | None:
    overlay = _OVERLAYS.get(action_id)
    return dict(overlay) if overlay else None


def requires_write_approval_always(action_key: str, *, risk_class: str | None = None) -> bool:
    if is_f1_write_action(action_key):
        return True
    return str(risk_class or "") in NON_AUTO_APPROVE_RISK_CLASSES


def registry_write_action_key(action_key: str) -> str:
    return registry_action_key(action_key)
