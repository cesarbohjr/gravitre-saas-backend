"""Settings > Security: workspace access controls.

Two factor, IP allowlist and session timeout live in
``organizations.settings["securityControls"]`` (merged, never replaced, so
other keys survive). They are saved and audited here; sign in does not enforce
them yet, which the response states in ``enforced`` so the page never claims
otherwise.
"""
from __future__ import annotations

import ipaddress
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from supabase import create_client

from app.auth.dependencies import get_current_user, get_org_context, require_admin
from app.config import Settings, get_settings
from app.core.db import shared_service_client
from app.core.safe_dict import safe_normalize_stored_dict
from app.core.org_state_cache import invalidate_org_state
from app.workflows.audit import write_audit_event

router = APIRouter(prefix="/api/settings/security", tags=["settings"])

SETTINGS_KEY = "securityControls"
SESSION_TIMEOUTS: tuple[str, ...] = ("never", "8h", "24h", "7d")
MAX_IP_RANGES = 50

DEFAULT_SECURITY_CONTROLS: dict[str, Any] = {
    "requireTwoFactor": False,
    "ipAllowlist": {"enabled": False, "ranges": []},
    "sessionTimeout": "never",
}

# Nothing in sign in reads these yet. Flip a flag only when enforcement ships.
ENFORCED: dict[str, bool] = {"requireTwoFactor": False, "ipAllowlist": False, "sessionTimeout": False}


class IpAllowlistUpdate(BaseModel):
    enabled: bool | None = None
    ranges: list[str] | None = None


class SecurityControlsUpdateRequest(BaseModel):
    requireTwoFactor: bool | None = None
    ipAllowlist: IpAllowlistUpdate | None = None
    sessionTimeout: str | None = None


def normalize_ip_range(value: str) -> str:
    """Return the canonical CIDR for an IPv4/IPv6 address or network, or raise ValueError."""
    text = str(value or "").strip()
    if not text:
        raise ValueError("empty")
    if "/" in text:
        network = ipaddress.ip_network(text, strict=False)
        return network.with_prefixlen
    address = ipaddress.ip_address(text)
    return f"{address}/{address.max_prefixlen}"


def normalize_security_controls(raw: Any) -> dict[str, Any]:
    """Coerce whatever is stored into the public shape, dropping anything invalid."""
    source = raw if isinstance(raw, dict) else {}
    allow = source.get("ipAllowlist") if isinstance(source.get("ipAllowlist"), dict) else {}
    ranges: list[str] = []
    for item in allow.get("ranges") or []:
        try:
            cidr = normalize_ip_range(str(item))
        except ValueError:
            continue
        if cidr not in ranges:
            ranges.append(cidr)
    timeout = str(source.get("sessionTimeout") or "never")
    return {
        "requireTwoFactor": source.get("requireTwoFactor") is True,
        "ipAllowlist": {"enabled": allow.get("enabled") is True, "ranges": ranges[:MAX_IP_RANGES]},
        "sessionTimeout": timeout if timeout in SESSION_TIMEOUTS else "never",
    }


def _payload(controls: dict[str, Any]) -> dict[str, Any]:
    return {"security": {**controls, "enforced": dict(ENFORCED)}}


def _org_settings(client: Any, org_id: str) -> dict[str, Any]:
    rows = client.table("organizations").select("id, settings").eq("id", org_id).limit(1).execute().data or []
    if not rows:
        raise HTTPException(status_code=404, detail="Organization not found")
    raw = rows[0].get("settings")
    return dict(raw) if isinstance(raw, dict) else {}


@router.get("")
def get_security_controls_route(
    _user: Annotated[dict, Depends(get_current_user)],
    org_id: Annotated[str | None, Depends(get_org_context)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict:
    if org_id is None:
        raise HTTPException(status_code=403, detail="Organization context required")
    client = shared_service_client(settings, create_client)
    return _payload(normalize_security_controls(_org_settings(client, org_id).get(SETTINGS_KEY)))


@router.patch("")
def update_security_controls_route(
    body: SecurityControlsUpdateRequest,
    admin: Annotated[tuple, Depends(require_admin)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict:
    user, org_id = admin
    client = shared_service_client(settings, create_client)
    org_settings = _org_settings(client, org_id)
    controls = normalize_security_controls(org_settings.get(SETTINGS_KEY))
    changed: dict[str, Any] = {}

    if body.requireTwoFactor is not None:
        controls["requireTwoFactor"] = bool(body.requireTwoFactor)
        changed["requireTwoFactor"] = controls["requireTwoFactor"]
    if body.ipAllowlist is not None:
        allow = safe_normalize_stored_dict(controls, key="ipAllowlist")
        if body.ipAllowlist.ranges is not None:
            ranges: list[str] = []
            for item in body.ipAllowlist.ranges:
                try:
                    cidr = normalize_ip_range(item)
                except ValueError as exc:
                    raise HTTPException(
                        status_code=400,
                        detail=f"{str(item).strip() or 'An empty value'} is not a valid IP address or CIDR range",
                    ) from exc
                if cidr not in ranges:
                    ranges.append(cidr)
            if len(ranges) > MAX_IP_RANGES:
                raise HTTPException(status_code=400, detail=f"Add at most {MAX_IP_RANGES} ranges")
            allow["ranges"] = ranges
        if body.ipAllowlist.enabled is not None:
            allow["enabled"] = bool(body.ipAllowlist.enabled)
        controls["ipAllowlist"] = allow
        changed["ipAllowlist"] = allow
    if body.sessionTimeout is not None:
        if body.sessionTimeout not in SESSION_TIMEOUTS:
            raise HTTPException(status_code=400, detail="sessionTimeout must be one of never, 8h, 24h, 7d")
        controls["sessionTimeout"] = body.sessionTimeout
        changed["sessionTimeout"] = body.sessionTimeout

    if changed:
        org_settings[SETTINGS_KEY] = controls
        client.table("organizations").update({"settings": org_settings}).eq("id", org_id).execute()
        invalidate_org_state(org_id)
        write_audit_event(
            client,
            org_id=org_id,
            actor_id=user["user_id"],
            action="settings.security_updated",
            resource_type="org_settings",
            resource_id=str(org_id),
            metadata=changed,
        )
    return _payload(controls)
