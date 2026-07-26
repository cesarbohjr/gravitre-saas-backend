"""Org membership resolution and auto-provisioning for authenticated users."""
from __future__ import annotations

from typing import Any
from uuid import uuid4

from supabase import Client

from app.core.logging import get_logger

logger = get_logger(__name__)

DEMO_ORG_IDS = frozenset(
    {
        "00000000-0000-0000-0000-000000000001",
        "11111111-1111-4111-8111-111111111111",
    }
)


def _slugify(value: str) -> str:
    slug = value.strip().lower()
    cleaned: list[str] = []
    prev_dash = False
    for ch in slug:
        if ("a" <= ch <= "z") or ("0" <= ch <= "9"):
            cleaned.append(ch)
            prev_dash = False
        elif not prev_dash:
            cleaned.append("-")
            prev_dash = True
    normalized = "".join(cleaned).strip("-")
    return normalized or "workspace"


def list_member_org_ids(client: Client, user_id: str) -> list[str]:
    """Return org ids for which user_id is a member (auth.users id)."""
    try:
        resp = (
            client.table("organization_members")
            .select("org_id, created_at")
            .eq("user_id", user_id)
            .order("created_at")
            .limit(100)
            .execute()
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("list_member_org_ids failed user_id=%s error=%s", user_id, exc)
        return []
    return [str(row["org_id"]) for row in (resp.data or []) if row.get("org_id")]


def load_user_primary_org_id(client: Client, user_id: str) -> str | None:
    """Primary org from public.users.org_id when present."""
    try:
        resp = (
            client.table("users")
            .select("org_id")
            .eq("auth_user_id", user_id)
            .limit(1)
            .execute()
        )
    except Exception:  # noqa: BLE001
        return None
    if not resp.data:
        return None
    org_id = resp.data[0].get("org_id")
    return str(org_id) if org_id else None


def pick_default_org_id(
    member_org_ids: list[str],
    *,
    primary_org_id: str | None = None,
    requested_org_id: str | None = None,
) -> str | None:
    """Choose the best default org from memberships."""
    if not member_org_ids:
        return None
    if requested_org_id and requested_org_id in member_org_ids:
        return requested_org_id
    if primary_org_id and primary_org_id in member_org_ids:
        return primary_org_id
    non_demo = [oid for oid in member_org_ids if oid not in DEMO_ORG_IDS]
    if non_demo:
        return non_demo[0]
    return member_org_ids[0]


def load_user_organizations(client: Client, user_id: str) -> list[dict[str, Any]]:
    """Organizations the user belongs to, with role."""
    try:
        memberships = (
            client.table("organization_members")
            .select("org_id, role, created_at")
            .eq("user_id", user_id)
            .order("created_at")
            .execute()
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("load_user_organizations memberships failed user_id=%s error=%s", user_id, exc)
        return []

    roles_by_org = {
        str(row["org_id"]): (row.get("role") or "member")
        for row in (memberships.data or [])
        if row.get("org_id")
    }
    if not roles_by_org:
        return []

    org_ids = list(roles_by_org.keys())
    try:
        orgs = (
            client.table("organizations")
            .select("id, name, slug, logo_url, plan, created_at")
            .in_("id", org_ids)
            .execute()
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("load_user_organizations orgs failed user_id=%s error=%s", user_id, exc)
        return [{"id": oid, "name": "Organization", "role": roles_by_org[oid]} for oid in org_ids]

    rows: list[dict[str, Any]] = []
    for row in orgs.data or []:
        org_id = str(row.get("id"))
        rows.append(
            {
                "id": org_id,
                "name": row.get("name"),
                "slug": row.get("slug"),
                "logo_url": row.get("logo_url"),
                "plan": row.get("plan"),
                "created_at": row.get("created_at"),
                "role": roles_by_org.get(org_id, "member"),
            }
        )
    return rows


def ensure_user_workspace(
    client: Client,
    user_id: str,
    *,
    email: str | None = None,
    full_name: str | None = None,
    company_name: str | None = None,
) -> str | None:
    """Create a personal workspace when signup trigger did not run (OAuth edge cases)."""
    existing = list_member_org_ids(client, user_id)
    if existing:
        return pick_default_org_id(existing, primary_org_id=load_user_primary_org_id(client, user_id))

    safe_email = (email or "").strip()
    display_name = (full_name or "").strip() or (safe_email.split("@")[0] if safe_email else "User")
    org_name = (company_name or "").strip() or f"{display_name}'s Workspace"
    slug_base = _slugify(org_name)
    slug = f"{slug_base}-{user_id.replace('-', '')[:8]}"

    try:
        org_resp = (
            client.table("organizations")
            .insert({"name": org_name, "slug": slug, "status": "active"})
            .select("id")
            .limit(1)
            .execute()
        )
    except Exception as exc:  # noqa: BLE001
        logger.error("ensure_user_workspace org insert failed user_id=%s error=%s", user_id, exc)
        return None

    if not org_resp.data:
        return None

    org_id = str(org_resp.data[0]["id"])
    try:
        client.table("organization_members").insert(
            {"id": str(uuid4()), "org_id": org_id, "user_id": user_id, "role": "owner"}
        ).execute()
        client.table("users").upsert(
            {
                "org_id": org_id,
                "auth_user_id": user_id,
                "email": safe_email or None,
                "full_name": display_name,
                "role": "owner",
                "status": "active",
            },
            on_conflict="auth_user_id",
        ).execute()
        client.table("org_billing").upsert(
            {
                "org_id": org_id,
                "plan_code": "node",
                "billing_status": "trialing",
                "cancel_at_period_end": False,
            },
            on_conflict="org_id",
        ).execute()
        ensure_default_production_environment(client, org_id)
    except Exception as exc:  # noqa: BLE001
        logger.error("ensure_user_workspace membership failed user_id=%s org_id=%s error=%s", user_id, org_id, exc)

    logger.info("ensure_user_workspace created org_id=%s user_id=%s", org_id, user_id)
    return org_id


def ensure_default_production_environment(client: Client, org_id: str) -> None:
    """Ensure every org has at least a production environment row."""
    org = str(org_id or "").strip()
    if not org:
        return
    try:
        existing = (
            client.table("environments")
            .select("id")
            .eq("org_id", org)
            .limit(1)
            .execute()
        )
        if existing.data:
            return
        client.table("environments").insert({"org_id": org, "name": "production", "is_active": True}).execute()
    except Exception as exc:  # noqa: BLE001
        logger.warning("ensure_default_production_environment failed org_id=%s error=%s", org, exc)


def resolve_user_id_by_email(client: Client, email: str | None) -> str | None:
    """Map checkout / Stripe email to auth user id when metadata.user_id is missing."""
    safe = str(email or "").strip().lower()
    if not safe:
        return None
    try:
        users = (
            client.table("users")
            .select("auth_user_id")
            .eq("email", safe)
            .limit(1)
            .execute()
        )
        if users.data and users.data[0].get("auth_user_id"):
            return str(users.data[0]["auth_user_id"])
    except Exception as exc:  # noqa: BLE001
        logger.warning("resolve_user_id_by_email failed email=%s error=%s", safe, exc)
    return None


def promote_user_to_org_owner(client: Client, org_id: str, user_id: str) -> None:
    """Grant full org admin to the billing contact / account creator (insert if missing)."""
    org = str(org_id or "").strip()
    uid = str(user_id or "").strip()
    if not org or not uid:
        return
    try:
        existing = (
            client.table("organization_members")
            .select("id, role")
            .eq("org_id", org)
            .eq("user_id", uid)
            .limit(1)
            .execute()
        )
        if existing.data:
            if str(existing.data[0].get("role") or "").strip().lower() != "owner":
                client.table("organization_members").update({"role": "owner"}).eq("org_id", org).eq(
                    "user_id", uid
                ).execute()
        else:
            client.table("organization_members").insert(
                {"id": str(uuid4()), "org_id": org, "user_id": uid, "role": "owner"}
            ).execute()
        client.table("users").update({"role": "owner"}).eq("org_id", org).eq("auth_user_id", uid).execute()
        ensure_default_production_environment(client, org)
    except Exception as exc:  # noqa: BLE001
        logger.warning("promote_user_to_org_owner failed org_id=%s user_id=%s error=%s", org, uid, exc)


# Master accounts that must always have org owner + platform_admins access.
# Kept in sync with supabase/migrations/20260726120000_platform_admin_cesar_gravitre_app.sql
FOUNDER_ADMIN_EMAILS = frozenset(
    {
        "cesar@gravitre.app",
        "cesar.bohorquez.jr@gmail.com",
    }
)


def ensure_founder_admin_access(
    client: Client,
    *,
    user_id: str,
    email: str | None,
    org_id: str | None,
) -> None:
    """Idempotent: promote known founder emails to owner + platform_admins on login."""
    uid = str(user_id or "").strip()
    safe_email = str(email or "").strip().lower()
    if not uid or safe_email not in FOUNDER_ADMIN_EMAILS:
        return
    try:
        client.table("platform_admins").upsert(
            {"user_id": uid, "email": safe_email, "notes": "Gravitre master admin"},
            on_conflict="user_id",
        ).execute()
    except Exception as exc:  # noqa: BLE001
        logger.warning("ensure_founder_admin_access platform_admins failed user_id=%s error=%s", uid, exc)
    if org_id:
        promote_user_to_org_owner(client, org_id, uid)

# deploy trigger 20260726T054923Z
