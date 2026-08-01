"""Connector auth_mode catalog — single enum, framework-enforced.

customer_owned: tenant credentials only (never use platform keys).
gravitree_managed: platform env keys; tenant never sees the secret.
byo_required: customer must bring their own subscription; fail closed —
  NEVER substitute a Gravitree-managed key or shared cache approximation.
"""
from __future__ import annotations

from enum import StrEnum
from typing import Any


class AuthMode(StrEnum):
    CUSTOMER_OWNED = "customer_owned"
    GRAVITREE_MANAGED = "gravitree_managed"
    BYO_REQUIRED = "byo_required"


class ActivationGate(StrEnum):
    """Sources that may ship as code but must not activate for tenants yet."""

    NONE = "none"
    COMMERCIAL_LICENSE_PENDING = "commercial_license_pending"
    GOVERNANCE_STOP_LINE = "governance_stop_line"


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
    # Gravitree intelligence sources (public / aggregate first)
    "fred": AuthMode.GRAVITREE_MANAGED,
    "sec_edgar": AuthMode.GRAVITREE_MANAGED,
    "world_bank": AuthMode.GRAVITREE_MANAGED,
    "oecd": AuthMode.GRAVITREE_MANAGED,
    "opencorporates": AuthMode.GRAVITREE_MANAGED,
    "nvd": AuthMode.GRAVITREE_MANAGED,
    "cisa_kev": AuthMode.GRAVITREE_MANAGED,
    # Contact-level gravitree sources — activation gated
    "crunchbase": AuthMode.GRAVITREE_MANAGED,
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

# Platform env var names for gravitree_managed sources (never used for BYO).
GRAVITREE_ENV_KEYS: dict[str, tuple[str, ...]] = {
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


def get_auth_mode(vendor: str) -> AuthMode:
    key = str(vendor or "").strip().lower()
    return CONNECTOR_AUTH_MODES.get(key, AuthMode.CUSTOMER_OWNED)


def is_knowledge_base_source(vendor: str) -> bool:
    """Gravitree-managed packs (FRED, NVD, …) — Marketplace knowledge base, not Connectors hub."""
    return get_auth_mode(vendor) == AuthMode.GRAVITREE_MANAGED


def requires_tenant_connector(vendor: str) -> bool:
    """True when a tenant must connect credentials in Connectors (OAuth / BYO API key).

    Knowledge-base / gravitree_managed sources use platform env keys and must never
    raise 'Missing {vendor} connector' alerts or link to the Connectors hub.
    """
    return get_auth_mode(vendor) != AuthMode.GRAVITREE_MANAGED


def get_activation_gate(vendor: str) -> ActivationGate:
    key = str(vendor or "").strip().lower()
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
    forbidden = {"platform_env", "gravitree_managed", "shared_cache", "platform"}
    if str(resolved_from or "").strip().lower() in forbidden:
        raise AuthModeError(
            f"BYO connector {vendor} cannot use a Gravitree-managed or shared credential path",
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
                "message": f"Connect your {vendor} account — Gravitree does not supply a shared key",
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

    if mode == AuthMode.GRAVITREE_MANAGED:
        required = GRAVITREE_ENV_KEYS.get(vendor, ())
        if required and not platform_env_present:
            return {
                "auth_mode": mode.value,
                "source": None,
                "ok": False,
                "error_code": "GRAVITREE_SOURCE_UNAVAILABLE",
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
