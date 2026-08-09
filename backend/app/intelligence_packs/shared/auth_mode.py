"""Connector auth_mode catalog — single enum, framework-enforced.

customer_owned: tenant credentials only (never use platform keys).
gravitre_managed: platform env keys; tenant never sees the secret.
byo_required: customer must bring their own subscription; fail closed —
  NEVER substitute a Gravitre-managed key or shared cache approximation.
"""
from __future__ import annotations

from enum import StrEnum
from typing import Any


class AuthMode(StrEnum):
    CUSTOMER_OWNED = "customer_owned"
    GRAVITRE_MANAGED = "gravitre_managed"
    BYO_REQUIRED = "byo_required"


# Persisted connector config may still store the pre-rename spelling.
LEGACY_AUTH_MODE_GRAVITREE_MANAGED = "gravitree_managed"

GRAVITRE_SOURCE_UNAVAILABLE = "GRAVITRE_SOURCE_UNAVAILABLE"
LEGACY_GRAVITREE_SOURCE_UNAVAILABLE = "GRAVITREE_SOURCE_UNAVAILABLE"


def is_gravitre_managed_mode(value: Any) -> bool:
    """True for canonical gravitre_managed and legacy gravitree_managed."""
    normalized = str(value or "").strip().lower()
    return normalized in {
        AuthMode.GRAVITRE_MANAGED.value,
        LEGACY_AUTH_MODE_GRAVITREE_MANAGED,
    }


def normalize_auth_mode_value(value: Any) -> str | None:
    """Map legacy gravitree_managed → gravitre_managed; pass through other modes."""
    raw = str(value or "").strip()
    if not raw:
        return None
    if is_gravitre_managed_mode(raw):
        return AuthMode.GRAVITRE_MANAGED.value
    return raw.lower()


def is_gravitre_source_unavailable_code(value: Any) -> bool:
    """Accept canonical and legacy SOURCE_UNAVAILABLE error codes when parsing."""
    code = str(value or "").strip().upper()
    return code in {GRAVITRE_SOURCE_UNAVAILABLE, LEGACY_GRAVITREE_SOURCE_UNAVAILABLE}


class ActivationGate(StrEnum):
    """Sources that may ship as code but must not activate for tenants yet."""

    NONE = "none"
    COMMERCIAL_LICENSE_PENDING = "commercial_license_pending"
    GOVERNANCE_STOP_LINE = "governance_stop_line"


# Tool/registry short prefixes → Connectors hub vendor key (DB `connectors.type`).
CONNECTOR_VENDOR_ALIASES: dict[str, str] = {
    "searchconsole": "google_search_console",
    "gsc": "google_search_console",
    "googlesearchconsole": "google_search_console",
    "webmasters": "google_search_console",
    "analytics": "google_analytics",
    "googleanalytics": "google_analytics",
    "googleads": "google_ads",
    "adwords": "google_ads",
    "ads": "google_ads",
    "calendar": "google_calendar",
    "googlecalendar": "google_calendar",
    "drive": "google_drive",
    "googledrive": "google_drive",
    "docs": "google_docs",
    "googledocs": "google_docs",
    "sheets": "google_sheets",
    "googlesheets": "google_sheets",
}

# Vendor key → auth_mode. Apollo confirmed customer_owned (existing OAuth).
CONNECTOR_AUTH_MODES: dict[str, AuthMode] = {
    # Customer-owned (existing + defaults)
    "apollo": AuthMode.CUSTOMER_OWNED,
    "hubspot": AuthMode.CUSTOMER_OWNED,
    "salesforce": AuthMode.CUSTOMER_OWNED,
    "slack": AuthMode.CUSTOMER_OWNED,
    "zendesk": AuthMode.CUSTOMER_OWNED,
    "linkedin": AuthMode.CUSTOMER_OWNED,  # distinct from Sales Navigator BYO
    "google_search_console": AuthMode.CUSTOMER_OWNED,
    "google_analytics": AuthMode.CUSTOMER_OWNED,
    "google_ads": AuthMode.CUSTOMER_OWNED,
    "google_calendar": AuthMode.CUSTOMER_OWNED,
    "google_drive": AuthMode.CUSTOMER_OWNED,
    "google_docs": AuthMode.CUSTOMER_OWNED,
    "google_sheets": AuthMode.CUSTOMER_OWNED,
    # Finance F3 — customer-owned accounting / banking
    "quickbooks": AuthMode.CUSTOMER_OWNED,
    "xero": AuthMode.CUSTOMER_OWNED,
    "netsuite": AuthMode.CUSTOMER_OWNED,
    "plaid": AuthMode.CUSTOMER_OWNED,
    # HR H3 — customer-owned HRIS / ATS / payroll
    "workday": AuthMode.CUSTOMER_OWNED,
    "bamboohr": AuthMode.CUSTOMER_OWNED,
    "greenhouse": AuthMode.CUSTOMER_OWNED,
    "gusto": AuthMode.CUSTOMER_OWNED,
    # Gravitre intelligence sources (public / aggregate first)
    "fred": AuthMode.GRAVITRE_MANAGED,
    "sec_edgar": AuthMode.GRAVITRE_MANAGED,
    "world_bank": AuthMode.GRAVITRE_MANAGED,
    "oecd": AuthMode.GRAVITRE_MANAGED,
    "opencorporates": AuthMode.GRAVITRE_MANAGED,
    "nvd": AuthMode.GRAVITRE_MANAGED,
    "cisa_kev": AuthMode.GRAVITRE_MANAGED,
    # Contact-level gravitre sources — activation gated
    "crunchbase": AuthMode.GRAVITRE_MANAGED,
    # BYO premium — fail closed, no shared key path
    "pdl": AuthMode.BYO_REQUIRED,  # Cesar clear 2026-07-15: tenant API key (dashboard.peopledatalabs.com)
    "zoominfo": AuthMode.BYO_REQUIRED,
    "linkedin_sales_navigator": AuthMode.BYO_REQUIRED,
    "semrush": AuthMode.BYO_REQUIRED,
    "ahrefs": AuthMode.BYO_REQUIRED,
    "finseo": AuthMode.BYO_REQUIRED,
    "ai_visibility_ui": AuthMode.BYO_REQUIRED,  # S2 scrape path — tenant runner/key, never shared
}

ACTIVATION_GATES: dict[str, ActivationGate] = {
    "opencorporates": ActivationGate.COMMERCIAL_LICENSE_PENDING,
    "crunchbase": ActivationGate.GOVERNANCE_STOP_LINE,
    # PDL: BYO connector allowed; Memory/KG contact persistence remains pack-guardrailed.
}

# Platform env var names for gravitre_managed sources (never used for BYO).
GRAVITRE_ENV_KEYS: dict[str, tuple[str, ...]] = {
    "fred": ("FRED_API_KEY",),
    "sec_edgar": ("SEC_USER_AGENT",),
    "world_bank": (),  # no key required
    "oecd": (),  # no key required
    "opencorporates": ("OPENCORPORATES_API_TOKEN",),
    "nvd": ("NVD_API_KEY",),
    "cisa_kev": (),  # public feed
    "crunchbase": ("CRUNCHBASE_API_KEY",),
}

LIVE_CONNECTOR_STATUSES = frozenset({"active", "connected", "healthy"})
STAGED_CONNECTOR_STATUSES = frozenset({"needs_connection", "pending_auth", "pending"})


class AuthModeError(RuntimeError):
    def __init__(self, message: str, *, code: str) -> None:
        super().__init__(message)
        self.code = code


def canonical_connector_vendor(vendor: str) -> str:
    """Normalize tool prefixes / aliases to the Connectors hub vendor key."""
    key = str(vendor or "").strip().lower().replace("-", "_").replace(" ", "_")
    if not key:
        return ""
    if key in CONNECTOR_VENDOR_ALIASES:
        return CONNECTOR_VENDOR_ALIASES[key]
    compact = key.replace("_", "")
    if compact in CONNECTOR_VENDOR_ALIASES:
        return CONNECTOR_VENDOR_ALIASES[compact]
    return key


def connector_type_lookup_keys(vendor: str) -> tuple[str, ...]:
    """Ordered unique type keys to try when matching a connectors row."""
    raw = str(vendor or "").strip().lower()
    canon = canonical_connector_vendor(vendor)
    keys: list[str] = []
    for candidate in (canon, raw, raw.replace("_", ""), canon.replace("_", "")):
        if candidate and candidate not in keys:
            keys.append(candidate)
    return tuple(keys)


def get_auth_mode(vendor: str) -> AuthMode:
    key = canonical_connector_vendor(vendor)
    return CONNECTOR_AUTH_MODES.get(key, AuthMode.CUSTOMER_OWNED)


def is_knowledge_base_source(vendor: str) -> bool:
    """Gravitre-managed packs (FRED, NVD, …) — Marketplace knowledge base, not Connectors hub."""
    return get_auth_mode(vendor) == AuthMode.GRAVITRE_MANAGED


def requires_tenant_connector(vendor: str) -> bool:
    """True when a tenant must connect credentials in Connectors (OAuth / BYO API key).

    Knowledge-base / gravitre_managed sources use platform env keys and must never
    raise 'Missing {vendor} connector' alerts or link to the Connectors hub.
    """
    return get_auth_mode(vendor) != AuthMode.GRAVITRE_MANAGED


def get_activation_gate(vendor: str) -> ActivationGate:
    key = canonical_connector_vendor(vendor)
    return ACTIVATION_GATES.get(key, ActivationGate.NONE)


def is_activation_allowed(vendor: str, *, settings: Any | None = None) -> bool:
    """Return False when code may exist but tenant enablement is blocked."""
    gate = get_activation_gate(vendor)
    if gate == ActivationGate.NONE:
        return True
    if gate == ActivationGate.COMMERCIAL_LICENSE_PENDING:
        if settings is not None and bool(getattr(settings, "opencorporates_license_confirmed", False)):
            return True
        return False
    if gate == ActivationGate.GOVERNANCE_STOP_LINE:
        return False
    return False


def assert_byo_never_uses_platform_key(
    vendor: str,
    *,
    resolved_from: str,
) -> None:
    """Hard rule: BYO resolution must never come from platform env / shared key."""
    if get_auth_mode(vendor) != AuthMode.BYO_REQUIRED:
        return
    forbidden = {
        "platform_env",
        AuthMode.GRAVITRE_MANAGED.value,
        LEGACY_AUTH_MODE_GRAVITREE_MANAGED,
        "shared_cache",
        "platform",
    }
    if str(resolved_from or "").strip().lower() in forbidden:
        raise AuthModeError(
            f"BYO connector {vendor} cannot use a Gravitre-managed or shared credential path",
            code="BYO_SHARED_KEY_FORBIDDEN",
        )


def resolve_credential_source(
    vendor: str,
    *,
    org_has_secret: bool,
    platform_env_present: bool,
    settings: Any | None = None,
) -> dict[str, Any]:
    """Declare where credentials must come from. Does not fetch secrets.

    Returns a dict with keys: auth_mode, source, ok, error_code, message.
    """
    mode = get_auth_mode(vendor)
    if not is_activation_allowed(vendor, settings=settings):
        gate = get_activation_gate(vendor)
        return {
            "auth_mode": mode.value,
            "source": None,
            "ok": False,
            "error_code": "SOURCE_ACTIVATION_BLOCKED",
            "message": f"{vendor} is not activated ({gate.value}); connect/licensing pending",
            "activation_gate": gate.value,
        }

    if mode == AuthMode.BYO_REQUIRED:
        if not org_has_secret:
            return {
                "auth_mode": mode.value,
                "source": None,
                "ok": False,
                "error_code": "BYO_CREDENTIAL_REQUIRED",
                "message": f"Connect your {vendor} account — Gravitre does not supply a shared key",
                "activation_gate": ActivationGate.NONE.value,
            }
        assert_byo_never_uses_platform_key(vendor, resolved_from="org_secret")
        return {
            "auth_mode": mode.value,
            "source": "org_secret",
            "ok": True,
            "error_code": None,
            "message": None,
            "activation_gate": ActivationGate.NONE.value,
        }

    if mode == AuthMode.GRAVITRE_MANAGED:
        required = GRAVITRE_ENV_KEYS.get(vendor, ())
        if required and not platform_env_present:
            return {
                "auth_mode": mode.value,
                "source": None,
                "ok": False,
                "error_code": GRAVITRE_SOURCE_UNAVAILABLE,
                "message": f"{vendor} is not yet available (platform credentials missing)",
                "activation_gate": get_activation_gate(vendor).value,
            }
        return {
            "auth_mode": mode.value,
            "source": "platform_env",
            "ok": True,
            "error_code": None,
            "message": None,
            "activation_gate": get_activation_gate(vendor).value,
        }

    # customer_owned
    if not org_has_secret:
        return {
            "auth_mode": mode.value,
            "source": None,
            "ok": False,
            "error_code": "CUSTOMER_CREDENTIAL_REQUIRED",
            "message": f"Connect {vendor} with your organization credentials",
            "activation_gate": ActivationGate.NONE.value,
        }
    return {
        "auth_mode": mode.value,
        "source": "org_secret",
        "ok": True,
        "error_code": None,
        "message": None,
        "activation_gate": ActivationGate.NONE.value,
    }
