"""Deterministic user-facing answers for connector connection/support questions.

Uses canonical org connector state from ``connector_availability_service`` —
not LLM inference from an illustrative slug list.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum
from typing import Any

from app.capability_ontology.conversational_grace import vendor_display_label

# Mirrors clarification / channel-override resolution — extended with catalog vendors.
_IS_VENDOR_CONNECTED_RE = re.compile(
    r"(?i)^\s*(?:is|are|do\s+we\s+have|have\s+we\s+got)\s+"
    r"(?P<vendor>[\w][\w\s.&'-]{0,48}?)\s+"
    r"(?:connected|hooked\s+up|set\s+up|configured)\s*\??\s*$"
)
_SUPPORT_QUESTION_RE = re.compile(
    r"(?i)\b(?:does\s+gravitre\s+support|do\s+you\s+support|is\s+[\w\s.&'-]{1,48}\s+supported)\b"
)
_LIST_CONNECTED_RE = re.compile(
    r"(?i)\b(?:what|which)\s+(?:connectors?|integrations?)\b.{0,40}\b"
    r"(?:connected|have|currently\s+have)\b"
    r"|"
    r"\b(?:what|which)\s+(?:connectors?|integrations?)\s+(?:are|do\s+i\s+have)\s+connected\b"
    r"|"
    r"\bconnected\s+(?:connectors?|integrations?)\s+(?:for|in)\s+(?:this|my)\s+(?:org|organization|account)\b"
)


class ConnectorStatusQuestionKind(str, Enum):
    CONNECTION = "connection"
    SUPPORT = "support"
    LIST = "list"


class ConnectorConnectionState(str, Enum):
    CONNECTED_HEALTHY = "connected_healthy"
    CONNECTED_SYNCING = "connected_syncing"
    DEGRADED = "degraded"
    AUTH_EXPIRED = "auth_expired"
    NOT_CONNECTED = "not_connected"
    UNSUPPORTED = "unsupported"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class ConnectorStatusQuestion:
    kind: ConnectorStatusQuestionKind
    vendor_slug: str | None = None


@dataclass(frozen=True)
class ConnectorStatusAnswer:
    text: str
    kind: ConnectorStatusQuestionKind
    vendor_slug: str | None = None
    state: ConnectorConnectionState | None = None
    source: str = "connector_availability_service"


def _allowed_vendors() -> frozenset[str]:
    from app.routers.connectors import ALLOWED_CONNECTOR_VENDORS

    return ALLOWED_CONNECTOR_VENDORS


def _normalize_vendor(vendor: str) -> str:
    return str(vendor or "").strip().lower().replace(" ", "").replace("-", "")


def resolve_connector_slug_from_text(text: str) -> str | None:
    """Resolve a catalog vendor slug from user text (aliases + word-boundary match)."""
    from app.services.chat_connector_models import INTEGRATION_ALIASES

    lowered = (text or "").lower()
    best: tuple[str, int] | None = None
    for slug, aliases in INTEGRATION_ALIASES.items():
        needles = (slug, slug.replace("_", " ")) + tuple(aliases)
        for alias in needles:
            alias_norm = str(alias or "").strip().lower()
            if not alias_norm or len(alias_norm) < 2:
                continue
            if re.search(rf"\b{re.escape(alias_norm)}\b", lowered):
                score = len(alias_norm)
                if best is None or score > best[1]:
                    best = (slug, score)
                break
    if best:
        return best[0]

    match = _IS_VENDOR_CONNECTED_RE.match((text or "").strip())
    if match:
        return _slug_from_vendor_token(str(match.group("vendor") or ""))
    broad = re.search(
        r"(?i)\b(?:is|are|do\s+we\s+have|have\s+we\s+got)\s+"
        r"(?P<vendor>[\w][\w \t.&'-]{0,48}?)\s+(?:connected|hooked\s+up)\b",
        text or "",
    )
    if broad:
        return _slug_from_vendor_token(str(broad.group("vendor") or ""))
    return None


def _slug_from_vendor_token(token: str) -> str | None:
    from app.services.gravitre_voice import _resolve_integration_token

    cleaned = str(token or "").strip()
    if not cleaned:
        return None
    slug = _resolve_integration_token(cleaned)
    if slug:
        return slug
    normalized = _normalize_vendor(cleaned)
    return normalized or None


def _is_short_connector_status_utterance(text: str) -> bool:
    """Status questions are single-line asks — not clauses inside operator briefs."""
    stripped = (text or "").strip()
    if not stripped or "\n" in stripped:
        return False
    return len(stripped) <= 160


def parse_connector_status_question(message: str) -> ConnectorStatusQuestion | None:
    text = (message or "").strip()
    if not text or not _is_short_connector_status_utterance(text):
        return None
    if _LIST_CONNECTED_RE.search(text):
        return ConnectorStatusQuestion(kind=ConnectorStatusQuestionKind.LIST)
    if _SUPPORT_QUESTION_RE.search(text):
        slug = resolve_connector_slug_from_text(text)
        return ConnectorStatusQuestion(kind=ConnectorStatusQuestionKind.SUPPORT, vendor_slug=slug)
    if _IS_VENDOR_CONNECTED_RE.match(text):
        slug = resolve_connector_slug_from_text(text)
        return ConnectorStatusQuestion(kind=ConnectorStatusQuestionKind.CONNECTION, vendor_slug=slug)
    if re.search(
        r"(?i)\b(?:is|are|do\s+we\s+have|have\s+we\s+got)\s+"
        r"[\w][\w \t.&'-]{0,48}\s+(?:connected|hooked\s+up)\b",
        text,
    ):
        slug = resolve_connector_slug_from_text(text)
        if slug:
            return ConnectorStatusQuestion(kind=ConnectorStatusQuestionKind.CONNECTION, vendor_slug=slug)
    return None


def is_connector_status_question(message: str) -> bool:
    return parse_connector_status_question(message) is not None


def _vendor_is_supported(slug: str | None) -> bool:
    if not slug:
        return False
    return _normalize_vendor(slug) in {_normalize_vendor(v) for v in _allowed_vendors()}


def _classify_connection_state(availability: dict[str, Any] | None) -> ConnectorConnectionState:
    if not availability:
        return ConnectorConnectionState.NOT_CONNECTED
    auth = str(availability.get("auth_status") or "").strip().lower()
    reason = str(availability.get("blocking_reason") or "").strip().lower()
    display = str(availability.get("display_status") or "").strip().lower()
    if auth == "auth_expired" or reason == "token_expired":
        return ConnectorConnectionState.AUTH_EXPIRED
    if availability.get("execution_available"):
        if display == "syncing":
            return ConnectorConnectionState.CONNECTED_SYNCING
        return ConnectorConnectionState.CONNECTED_HEALTHY
    if display == "error" or str(availability.get("health_status") or "").lower() == "error":
        return ConnectorConnectionState.DEGRADED
    if reason in {"missing_scope", "unsupported_action", "misconfigured"}:
        return ConnectorConnectionState.DEGRADED
    if auth in {"pending_auth", "pending_property", "pending_site", "pending_customer"}:
        return ConnectorConnectionState.NOT_CONNECTED
    if availability.get("connected"):
        return ConnectorConnectionState.DEGRADED
    return ConnectorConnectionState.NOT_CONNECTED


def _offer_connect_phrase(label: str) -> str:
    return f" If you'd like, I can help you connect {label}."


def format_connection_answer(
    *,
    vendor_slug: str,
    state: ConnectorConnectionState,
    supported: bool,
) -> str:
    label = vendor_display_label(vendor_slug)
    if state == ConnectorConnectionState.UNKNOWN:
        return f"I couldn't verify {label}'s connection status right now."
    if not supported:
        return f"No. Gravitre doesn't currently support a {label} connector."
    if state == ConnectorConnectionState.CONNECTED_HEALTHY:
        return f"Yes, {label} is connected and healthy."
    if state == ConnectorConnectionState.CONNECTED_SYNCING:
        return f"Yes, {label} is connected and syncing."
    if state == ConnectorConnectionState.DEGRADED:
        return f"{label} is connected, but the connection needs attention."
    if state == ConnectorConnectionState.AUTH_EXPIRED:
        return f"{label} is configured, but its authentication has expired."
    return f"No, {label} isn't connected to your Gravitre account.{_offer_connect_phrase(label)}"


def format_support_answer(*, vendor_slug: str, supported: bool, state: ConnectorConnectionState) -> str:
    label = vendor_display_label(vendor_slug)
    if not supported:
        return f"No. Gravitre doesn't currently support a {label} connector."
    if state in {
        ConnectorConnectionState.CONNECTED_HEALTHY,
        ConnectorConnectionState.CONNECTED_SYNCING,
    }:
        return f"Yes, Gravitre supports {label}, and it's connected to your account."
    if state == ConnectorConnectionState.DEGRADED:
        return (
            f"Yes, Gravitre supports {label}. It's connected to your account, "
            "but the connection needs attention."
        )
    if state == ConnectorConnectionState.AUTH_EXPIRED:
        return (
            f"Yes, Gravitre supports {label}. It's configured on your account, "
            "but authentication has expired."
        )
    return (
        f"Yes. {label} is available as an integration, but it isn't connected to your account."
        f"{_offer_connect_phrase(label)}"
    )


def format_connected_list_answer(
    connectors: list[dict[str, Any]] | None,
    *,
    connected_slugs: list[str] | None = None,
) -> str:
    labels: list[str] = []
    if connectors:
        for row in connectors:
            if not row.get("execution_available"):
                continue
            vendor = str(row.get("vendor") or "").strip()
            if vendor:
                labels.append(vendor_display_label(vendor))
    elif connected_slugs:
        labels = [vendor_display_label(slug) for slug in connected_slugs if slug]
    labels = sorted({label for label in labels if label})
    if not labels:
        return "You don't have any connectors connected to this Gravitre account yet."
    if len(labels) == 1:
        return f"You have {labels[0]} connected."
    joined = ", ".join(labels[:-1]) + f", and {labels[-1]}"
    return f"You have {joined} connected."


def answer_connector_status_question(
    message: str,
    *,
    client: Any,
    org_id: str,
    settings: Any,
    connected_integrations: list[str] | None = None,
    environment_name: str = "production",
) -> ConnectorStatusAnswer | None:
    """Return a deterministic answer when the message is a connector status question."""
    parsed = parse_connector_status_question(message)
    if parsed is None:
        return None

    connectors: list[dict[str, Any]] | None = None
    service_error = False
    try:
        from app.connectors.connector_availability_service import list_connector_availability

        connectors = list_connector_availability(
            client,
            org_id,
            settings,
            environment_name=environment_name,
            force_live=False,
        )
    except Exception:  # noqa: BLE001
        service_error = True
        connectors = None

    if parsed.kind == ConnectorStatusQuestionKind.LIST:
        if service_error and not connected_integrations:
            return ConnectorStatusAnswer(
                text="I couldn't verify your connected connectors right now.",
                kind=parsed.kind,
                state=ConnectorConnectionState.UNKNOWN,
            )
        return ConnectorStatusAnswer(
            text=format_connected_list_answer(connectors, connected_slugs=connected_integrations),
            kind=parsed.kind,
            state=ConnectorConnectionState.CONNECTED_HEALTHY if connectors or connected_integrations else None,
        )

    slug = parsed.vendor_slug
    if not slug:
        return None

    supported = _vendor_is_supported(slug)
    availability: dict[str, Any] | None = None
    if connectors is not None:
        target = _normalize_vendor(slug)
        matches = [
            row
            for row in connectors
            if _normalize_vendor(str(row.get("vendor") or "")) == target
            or _normalize_vendor(str(row.get("vendor") or "")).replace("googleads", "google_ads") == target
        ]
        if matches:
            availability = max(matches, key=lambda row: bool(row.get("execution_available")))

    if service_error and availability is None:
        connected = {_normalize_vendor(c) for c in (connected_integrations or [])}
        if _normalize_vendor(slug) in connected:
            state = ConnectorConnectionState.CONNECTED_HEALTHY
        elif supported:
            state = ConnectorConnectionState.UNKNOWN
        else:
            state = ConnectorConnectionState.UNSUPPORTED
        if state == ConnectorConnectionState.UNKNOWN:
            label = vendor_display_label(slug)
            return ConnectorStatusAnswer(
                text=f"I couldn't verify {label}'s connection status right now.",
                kind=parsed.kind,
                vendor_slug=slug,
                state=state,
            )

    state = _classify_connection_state(availability)
    if not supported and availability is None:
        state = ConnectorConnectionState.UNSUPPORTED

    if parsed.kind == ConnectorStatusQuestionKind.SUPPORT:
        text = format_support_answer(vendor_slug=slug, supported=supported, state=state)
    else:
        text = format_connection_answer(vendor_slug=slug, state=state, supported=supported)

    return ConnectorStatusAnswer(
        text=text,
        kind=parsed.kind,
        vendor_slug=slug,
        state=state,
    )
