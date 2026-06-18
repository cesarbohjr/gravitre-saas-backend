"""Creator publisher onboarding for public marketplace assets (MKT-AUDIT-11.1)."""
from __future__ import annotations

import logging
import re
from datetime import datetime, timezone
from typing import Any

from app.marketplace.crud import MarketplaceCrudError, resolve_org_publisher_id
from app.workflows.audit import write_audit_event

logger = logging.getLogger(__name__)

AUDIT_PUBLISHER_ONBOARDED = "marketplace.publisher.onboarded"
RESOURCE_TYPE_MARKETPLACE_PUBLISHER = "marketplace_publisher"
_SLUG_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


class MarketplacePublisherError(Exception):
    code = "MARKETPLACE_PUBLISHER_ERROR"

    def __init__(self, message: str, *, code: str | None = None) -> None:
        super().__init__(message)
        if code:
            self.code = code


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _normalize_publisher_slug(value: str) -> str:
    slug = value.strip().lower()
    slug = re.sub(r"[^a-z0-9]+", "-", slug)
    slug = slug.strip("-")
    if not slug or not _SLUG_RE.fullmatch(slug):
        raise MarketplacePublisherError(
            "publisher slug must be lowercase alphanumeric with hyphens",
            code="VALIDATION_ERROR",
        )
    return slug


def _serialize_publisher(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": row["id"],
        "slug": row["slug"],
        "displayName": row.get("display_name"),
        "description": row.get("description"),
        "logoUrl": row.get("logo_url"),
        "websiteUrl": row.get("website_url"),
        "verified": bool(row.get("verified")),
        "status": row.get("status"),
        "orgId": row.get("org_id"),
        "publicPublishingEnabled": bool(row.get("public_publishing_enabled")),
        "onboardedAt": row.get("onboarded_at"),
        "createdAt": row.get("created_at"),
        "updatedAt": row.get("updated_at"),
    }


def get_org_publisher_profile(client: Any, org_id: str) -> dict[str, Any] | None:
    result = (
        client.table("marketplace_publishers")
        .select("*")
        .eq("org_id", org_id)
        .limit(1)
        .execute()
    )
    if not result.data:
        return None
    return _serialize_publisher(dict(result.data[0]))


def onboard_org_publisher(
    client: Any,
    org_id: str,
    *,
    actor_id: str,
    display_name: str,
    slug: str | None = None,
    description: str | None = None,
    website_url: str | None = None,
    logo_url: str | None = None,
    org_name: str | None = None,
) -> dict[str, Any]:
    """Complete creator onboarding so the org can submit public marketplace assets."""
    display = display_name.strip()
    if not display:
        raise MarketplacePublisherError("display name is required", code="VALIDATION_ERROR")

    existing = (
        client.table("marketplace_publishers")
        .select("*")
        .eq("org_id", org_id)
        .limit(1)
        .execute()
    )
    now = _now()
    if existing.data:
        row = dict(existing.data[0])
        update: dict[str, Any] = {
            "display_name": display,
            "description": description,
            "website_url": website_url,
            "logo_url": logo_url,
            "public_publishing_enabled": True,
            "onboarded_at": row.get("onboarded_at") or now,
            "updated_at": now,
        }
        if slug:
            normalized = _normalize_publisher_slug(slug)
            if normalized != row.get("slug"):
                taken = (
                    client.table("marketplace_publishers")
                    .select("id")
                    .eq("slug", normalized)
                    .neq("id", row["id"])
                    .limit(1)
                    .execute()
                )
                if taken.data:
                    raise MarketplacePublisherError("publisher slug already taken", code="VALIDATION_ERROR")
                update["slug"] = normalized
        client.table("marketplace_publishers").update(update).eq("id", row["id"]).execute()
        refreshed = (
            client.table("marketplace_publishers")
            .select("*")
            .eq("id", row["id"])
            .limit(1)
            .execute()
        )
        publisher = _serialize_publisher(dict((refreshed.data or [row])[0]))
    else:
        publisher_id = resolve_org_publisher_id(client, org_id, org_name=org_name)
        normalized_slug = _normalize_publisher_slug(slug) if slug else None
        update: dict[str, Any] = {
            "display_name": display,
            "description": description,
            "website_url": website_url,
            "logo_url": logo_url,
            "public_publishing_enabled": True,
            "onboarded_at": now,
            "updated_at": now,
        }
        if normalized_slug:
            update["slug"] = normalized_slug
        client.table("marketplace_publishers").update(update).eq("id", publisher_id).execute()
        refreshed = (
            client.table("marketplace_publishers")
            .select("*")
            .eq("id", publisher_id)
            .limit(1)
            .execute()
        )
        publisher = _serialize_publisher(dict((refreshed.data or [{"id": publisher_id}])[0]))

    write_audit_event(
        client,
        org_id=org_id,
        actor_id=actor_id,
        action=AUDIT_PUBLISHER_ONBOARDED,
        resource_type=RESOURCE_TYPE_MARKETPLACE_PUBLISHER,
        resource_id=str(publisher["id"]),
        metadata={"slug": publisher.get("slug")},
    )
    return {"onboarded": True, "publisher": publisher}


def assert_org_can_publish_publicly(client: Any, org_id: str) -> dict[str, Any]:
    profile = get_org_publisher_profile(client, org_id)
    if not profile or not profile.get("publicPublishingEnabled"):
        raise MarketplacePublisherError(
            "Complete publisher onboarding before submitting public assets",
            code="FORBIDDEN",
        )
    if profile.get("status") != "active":
        raise MarketplacePublisherError("Publisher account is not active", code="FORBIDDEN")
    return profile


def publisher_error_to_publish(exc: MarketplacePublisherError):
    from app.marketplace.publish import MarketplacePublishError

    return MarketplacePublishError(str(exc), code=exc.code)
