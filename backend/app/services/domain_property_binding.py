"""Bind a discovered connector resource to the tenant's website — unique match only."""
from __future__ import annotations

import re
from typing import Any

from app.services.connector_resource_resolver import ResourceResolution
from app.services.org_business_identity import merge_business_identity, normalize_host

_TOKEN = re.compile(r"[a-z0-9]{4,}")


def _candidate_org_id(raw: dict[str, Any], fallback_org_id: str) -> str:
    return str(raw.get("org_id") or raw.get("tenant_id") or fallback_org_id).strip()


def _candidate_hosts(raw: dict[str, Any]) -> set[str]:
    hosts: set[str] = set()
    for key in (
        "site_url",
        "website",
        "url",
        "default_uri",
        "defaultUri",
        "web_stream_uri",
        "display_name",
        "property_id",
    ):
        host = normalize_host(str(raw.get(key) or ""))
        if host:
            hosts.add(host)
    for uri in raw.get("web_stream_uris") or ():
        host = normalize_host(str(uri))
        if host:
            hosts.add(host)
    return hosts


def _host_matches(target: str, candidate_host: str) -> bool:
    if not target or not candidate_host:
        return False
    if candidate_host == target:
        return True
    return candidate_host.endswith("." + target)


def _label_tokens(raw: dict[str, Any]) -> set[str]:
    blob = " ".join(
        str(raw.get(key) or "")
        for key in ("display_name", "account_name", "name", "site_url")
    ).lower()
    return set(_TOKEN.findall(blob))


def match_resource_to_domain(
    candidates: tuple[dict[str, Any], ...] | list[dict[str, Any]],
    *,
    host: str,
    org_id: str,
) -> dict[str, Any] | None:
    """Tenant-scoped domain match. Never auto-select a cross-tenant or non-unique candidate."""
    target = normalize_host(host)
    if not target or not org_id:
        return None
    eligible: list[dict[str, Any]] = []
    for raw in candidates:
        if not isinstance(raw, dict):
            continue
        candidate_org = _candidate_org_id(raw, org_id)
        if candidate_org != str(org_id):
            continue
        hosts = _candidate_hosts(raw)
        if any(_host_matches(target, item) for item in hosts):
            eligible.append(raw)
    if len(eligible) == 1:
        return eligible[0]
    if eligible:
        return None

    label = target.split(".", 1)[0]
    if len(label) < 4:
        return None
    labeled: list[dict[str, Any]] = []
    for raw in candidates:
        if not isinstance(raw, dict):
            continue
        if _candidate_org_id(raw, org_id) != str(org_id):
            continue
        if label in _label_tokens(raw):
            labeled.append(raw)
    if len(labeled) == 1:
        return labeled[0]
    return None


def bound_resolution(
    resolution: ResourceResolution,
    matched: dict[str, Any],
) -> ResourceResolution:
    resource_id = str(
        matched.get("property_id")
        or matched.get("site_url")
        or matched.get("resource_id")
        or ""
    )
    return ResourceResolution(
        status="resolved",
        connector_id=resolution.connector_id,
        connection_id=resolution.connection_id,
        resource_type=resolution.resource_type,
        resource_id=resource_id,
        display_name=str(matched.get("display_name") or matched.get("site_url") or resource_id),
        confidence=0.9,  # confidence-honesty-ok: domain bind prior, not user-facing
        resolution_reason="tenant_domain_binding",
        candidate_count=1,
        candidates=(matched,),
    )


def _stamp_org(candidates: tuple[dict[str, Any], ...], org_id: str) -> tuple[dict[str, Any], ...]:
    stamped: list[dict[str, Any]] = []
    for raw in candidates:
        if not isinstance(raw, dict):
            continue
        item = dict(raw)
        item.setdefault("org_id", org_id)
        stamped.append(item)
    return tuple(stamped)


def _enrich_ga4_stream_uris(
    candidates: tuple[dict[str, Any], ...],
    *,
    access_token: str | None,
) -> tuple[dict[str, Any], ...]:
    if not access_token:
        return candidates
    from app.connectors.google_analytics import list_ga4_web_stream_uris

    enriched: list[dict[str, Any]] = []
    for index, raw in enumerate(candidates):
        item = dict(raw)
        if index >= 8:
            enriched.append(item)
            continue
        property_id = str(item.get("property_id") or "")
        try:
            uris = list_ga4_web_stream_uris(access_token, property_id)
        except Exception:  # noqa: BLE001
            uris = []
        if uris:
            item["web_stream_uris"] = tuple(uris)
            item["default_uri"] = uris[0]
        enriched.append(item)
    return tuple(enriched)


def apply_tenant_domain_binding(
    resolution: ResourceResolution,
    *,
    org_id: str,
    conversation_context: dict[str, Any] | None = None,
    client: Any = None,
    user_message: str = "",
    environment_name: str = "production",
    access_token: str | None = None,
) -> ResourceResolution:
    if resolution.status != "ambiguous" or not resolution.candidates or not org_id:
        return resolution
    ctx = dict(conversation_context or {})
    identity = merge_business_identity(
        org_id=org_id,
        context=ctx,
        user_message=user_message or str(ctx.get("user_message") or ctx.get("message") or ""),
        client=client,
        environment_name=environment_name,
    )
    host = str(identity.get("host") or "")
    if not host:
        return resolution

    stamped = _stamp_org(tuple(resolution.candidates), org_id)
    matched = match_resource_to_domain(stamped, host=host, org_id=org_id)
    if matched is None and resolution.resource_type in {"property", ""}:
        stamped = _enrich_ga4_stream_uris(stamped, access_token=access_token)
        matched = match_resource_to_domain(stamped, host=host, org_id=org_id)
    if matched is None:
        return ResourceResolution(
            status=resolution.status,
            connector_id=resolution.connector_id,
            connection_id=resolution.connection_id,
            resource_type=resolution.resource_type,
            resource_id=resolution.resource_id,
            display_name=resolution.display_name,
            confidence=resolution.confidence,
            resolution_reason=resolution.resolution_reason,
            candidate_count=resolution.candidate_count,
            candidates=stamped,
        )
    return bound_resolution(resolution, matched)
