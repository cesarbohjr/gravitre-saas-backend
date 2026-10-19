"""MSP partner program: client workspaces, consent, and rebilling figures.

Authorization model (checked on every call, never cached):
- MSP actions (add, change plan, resale price, statement, billing): caller is an
  owner or admin of the MSP org, and the relationship row belongs to that MSP.
- Client actions (approve, decline): caller is the OWNER of the client org.
- Detach: either of the above.
The parent link (organizations.parent_org_id) never grants access by itself.
What an MSP can see about a client beyond plan and billing depends on the
access the client owner chose: membership (full) or a live health delegation.
"""
from __future__ import annotations

import csv
import io
from datetime import date, datetime, timedelta, timezone
from typing import Any, Iterable
from uuid import uuid4

from fastapi import HTTPException

from app.billing import msp_billing
from app.billing.service import DEFAULT_PLANS, get_current_period, get_usage_totals
from app.core.logging import get_logger
from app.core.org_state_cache import invalidate_org_and_users, invalidate_org_state
from app.services.msp_delegation_preflight import _member_role
from app.workflows.audit import write_audit_event

logger = get_logger(__name__)

MSP_MANAGER_ROLES = frozenset({"owner", "admin"})
PROVIDER_MEMBER_ROLES = frozenset({"owner", "admin", "member"})
HEALTH_ONLY_ACTIONS = ("account.health.read", "billing.summary.read", "usage.aggregate.read")
HEALTH_ONLY_GRANT_DAYS = 365
MAX_CLIENTS = 200
LIVE_STATUSES = ("pending_client_approval", "active")


def _now() -> datetime:
    return datetime.now(timezone.utc)


# ---------------------------------------------------------------------------
# Lookups and role checks
# ---------------------------------------------------------------------------


def member_role(client: Any, org_id: str, user_id: str) -> str | None:
    return _member_role(client, org_id=org_id, user_id=user_id)


def require_msp_manager(client: Any, msp_org_id: str, user_id: str) -> dict[str, Any]:
    org = org_row(client, msp_org_id)
    if not org or org.get("account_type") != "msp":
        raise HTTPException(403, "This workspace isn't in the partner program")
    if member_role(client, msp_org_id, user_id) not in MSP_MANAGER_ROLES:
        raise HTTPException(403, "Only owners and admins of the partner workspace can manage clients")
    return org


def require_client_owner(client: Any, client_org_id: str, user_id: str) -> None:
    if member_role(client, client_org_id, user_id) != "owner":
        raise HTTPException(403, "Only the workspace owner can decide this")


def org_row(client: Any, org_id: str) -> dict[str, Any] | None:
    try:
        rows = (
            client.table("organizations")
            .select("id,name,account_type,status,parent_org_id,settings")
            .eq("id", org_id)
            .limit(1)
            .execute()
            .data
            or []
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("msp_org_lookup_failed org_id=%s error=%s", org_id, type(exc).__name__)
        return None
    if not rows or str(rows[0].get("id")) != str(org_id):
        return None
    row = dict(rows[0])
    row["account_type"] = row.get("account_type") or "standard"
    return row


def org_names(client: Any, org_ids: Iterable[str]) -> dict[str, str]:
    ids = sorted({str(i) for i in org_ids if i})
    if not ids:
        return {}
    rows = client.table("organizations").select("id,name").in_("id", ids).execute().data or []
    return {str(r["id"]): str(r.get("name") or "Workspace") for r in rows}


def user_labels(client: Any, user_ids: Iterable[str]) -> dict[str, dict[str, str | None]]:
    """Name and email for auth user ids (organization_members.user_id)."""
    ids = sorted({str(i) for i in user_ids if i})
    if not ids:
        return {}
    try:
        rows = (
            client.table("users")
            .select("auth_user_id,email,full_name")
            .in_("auth_user_id", ids)
            .execute()
            .data
            or []
        )
    except Exception:  # noqa: BLE001
        rows = []
    labels: dict[str, dict[str, str | None]] = {}
    for row in rows:
        uid = str(row.get("auth_user_id") or "")
        if uid:
            labels[uid] = {"name": row.get("full_name") or None, "email": row.get("email") or None}
    return labels


def org_members(client: Any, org_id: str, roles: frozenset[str] = PROVIDER_MEMBER_ROLES) -> list[dict[str, Any]]:
    rows = (
        client.table("organization_members")
        .select("user_id,role")
        .eq("org_id", org_id)
        .limit(200)
        .execute()
        .data
        or []
    )
    members = [
        {"user_id": str(r["user_id"]), "role": str(r.get("role") or "member")}
        for r in rows
        if r.get("user_id") and str(r.get("role") or "") in roles
    ]
    labels = user_labels(client, [m["user_id"] for m in members])
    for m in members:
        label = labels.get(m["user_id"], {})
        m["name"] = label.get("name")
        m["email"] = label.get("email")
    return members


def relationship(client: Any, relationship_id: str) -> dict[str, Any]:
    rows = client.table("msp_clients").select("*").eq("id", relationship_id).limit(1).execute().data or []
    if not rows or str(rows[0].get("id")) != str(relationship_id):
        raise HTTPException(404, "Client not found")
    return dict(rows[0])


def live_relationship_for_client(client: Any, client_org_id: str) -> dict[str, Any] | None:
    rows = (
        client.table("msp_clients")
        .select("*")
        .eq("client_org_id", client_org_id)
        .in_("status", list(LIVE_STATUSES))
        .limit(1)
        .execute()
        .data
        or []
    )
    return dict(rows[0]) if rows else None


def _audit(client: Any, org_id: str, actor: str, action: str, rel_id: str, metadata: dict[str, Any]) -> None:
    write_audit_event(
        client,
        org_id=org_id,
        actor_id=actor,
        action=action,
        resource_type="msp_client",
        resource_id=rel_id,
        metadata=metadata,
    )


def _plan_name(code: str) -> str:
    return str((DEFAULT_PLANS.get(code) or {}).get("name") or code.title())


def _resale_monthly(row: dict[str, Any]) -> int | None:
    cents = row.get("resale_price_cents")
    if cents is None:
        return None
    return round(int(cents) / 12) if row.get("resale_interval") == "year" else int(cents)


# ---------------------------------------------------------------------------
# Enrollment
# ---------------------------------------------------------------------------


def enroll(client: Any, org_id: str, user_id: str) -> dict[str, Any]:
    org = org_row(client, org_id)
    if not org:
        raise HTTPException(404, "Workspace not found")
    if member_role(client, org_id, user_id) != "owner":
        raise HTTPException(403, "Only the workspace owner can join the partner program")
    if org.get("account_type") == "msp":
        return {"account_type": "msp", "changed": False}
    if live_relationship_for_client(client, org_id):
        raise HTTPException(
            409, "This workspace is managed by a partner. Detach it first, or use a separate workspace for your MSP."
        )
    client.table("organizations").update({"account_type": "msp"}).eq("id", org_id).execute()
    invalidate_org_state(org_id)
    _audit(client, org_id, user_id, "msp.program.enrolled", org_id, {"account_type": "msp"})
    return {"account_type": "msp", "changed": True}


# ---------------------------------------------------------------------------
# Adding clients
# ---------------------------------------------------------------------------


def _validate_terms(plan_code: str, resale_price_cents: int | None, resale_interval: str) -> None:
    if plan_code not in msp_billing.MSP_TIERS:
        raise HTTPException(422, "Choose Node, Control or Command")
    if resale_interval not in {"month", "year"}:
        raise HTTPException(422, "Resale interval must be month or year")
    if resale_price_cents is not None and not (0 <= int(resale_price_cents) <= 100_000_000):
        raise HTTPException(422, "Resale price is out of range")


def create_client_workspace(
    client: Any,
    settings: Any,
    *,
    msp_org_id: str,
    user: dict[str, Any],
    name: str,
    plan_code: str,
    resale_price_cents: int | None,
    resale_interval: str,
    create_org: Any,
) -> dict[str, Any]:
    """New org owned by the calling MSP user, active immediately.

    ``create_org`` is the existing organization-creation route function, so
    slugging, membership and cache invalidation stay in one place.
    """
    require_msp_manager(client, msp_org_id, user["user_id"])
    _validate_terms(plan_code, resale_price_cents, resale_interval)
    created = create_org(name)
    client_org_id = str(created["id"])
    now = _now().isoformat()
    inserted = (
        client.table("msp_clients")
        .insert(
            {
                "msp_org_id": msp_org_id,
                "client_org_id": client_org_id,
                "plan_code": plan_code,
                "resale_price_cents": resale_price_cents,
                "resale_interval": resale_interval,
                "status": "active",
                "access_level": "full",
                "origin": "created",
                "created_by": user["user_id"],
                "approved_by": user["user_id"],
                "approved_at": now,
            }
        )
        .execute()
        .data
        or []
    )
    if not inserted:
        raise HTTPException(503, "Client workspace was created but could not be linked; try linking it")
    rel = dict(inserted[0])
    client.table("organizations").update({"parent_org_id": msp_org_id}).eq("id", client_org_id).execute()
    msp_billing.write_client_entitlement(
        client,
        msp_org_id=msp_org_id,
        client_org_id=client_org_id,
        plan_code=plan_code,
        account=msp_billing.get_billing_account(client, msp_org_id),
    )
    sync = msp_billing.sync_wholesale_quantities(client, settings, msp_org_id)
    invalidate_org_and_users(client_org_id, [user["user_id"]])
    _audit(client, msp_org_id, user["user_id"], "msp.client.created", rel["id"], {"client_org_id": client_org_id, "plan_code": plan_code})
    _audit(client, client_org_id, user["user_id"], "msp.client.created", rel["id"], {"msp_org_id": msp_org_id, "plan_code": plan_code})
    return {"client": {"id": rel["id"], "client_org_id": client_org_id, "name": created.get("name"), "status": "active"}, "billing": sync}


def request_link(
    client: Any,
    *,
    msp_org_id: str,
    user_id: str,
    client_org_id: str,
    plan_code: str,
    resale_price_cents: int | None,
    resale_interval: str,
) -> dict[str, Any]:
    require_msp_manager(client, msp_org_id, user_id)
    _validate_terms(plan_code, resale_price_cents, resale_interval)
    if client_org_id == msp_org_id:
        raise HTTPException(422, "Your partner workspace can't be its own client")
    target = org_row(client, client_org_id)
    # One answer for "missing" and "not eligible" so IDs can't be probed for details.
    if not target or target.get("account_type") != "standard":
        raise HTTPException(404, "No workspace that can be linked was found with that ID")
    if live_relationship_for_client(client, client_org_id):
        raise HTTPException(409, "That workspace already has a partner, or a request is waiting")
    inserted = (
        client.table("msp_clients")
        .insert(
            {
                "msp_org_id": msp_org_id,
                "client_org_id": client_org_id,
                "plan_code": plan_code,
                "resale_price_cents": resale_price_cents,
                "resale_interval": resale_interval,
                "status": "pending_client_approval",
                "origin": "linked",
                "created_by": user_id,
            }
        )
        .execute()
        .data
        or []
    )
    if not inserted:
        raise HTTPException(503, "Request was not saved; try again")
    rel = dict(inserted[0])
    _audit(client, msp_org_id, user_id, "msp.client.link_requested", rel["id"], {"client_org_id": client_org_id})
    _audit(client, client_org_id, user_id, "msp.client.link_requested", rel["id"], {"msp_org_id": msp_org_id})
    return {"client": {"id": rel["id"], "client_org_id": client_org_id, "status": rel["status"]}}


# ---------------------------------------------------------------------------
# Client owner decisions
# ---------------------------------------------------------------------------


def approve(
    client: Any,
    settings: Any,
    *,
    relationship_id: str,
    user_id: str,
    access_level: str,
    member_user_ids: list[str],
) -> dict[str, Any]:
    rel = relationship(client, relationship_id)
    client_org_id, msp_org_id = str(rel["client_org_id"]), str(rel["msp_org_id"])
    require_client_owner(client, client_org_id, user_id)
    if rel.get("status") != "pending_client_approval":
        raise HTTPException(409, "This request was already answered")
    if access_level not in {"full", "health_only"}:
        raise HTTPException(422, "Choose full access or health only")
    msp = org_row(client, msp_org_id)
    if not msp or msp.get("account_type") != "msp":
        raise HTTPException(409, "That partner is no longer in the partner program")
    conflict = msp_billing.own_subscription_conflict(client, client_org_id)
    if conflict:
        raise HTTPException(409, conflict)
    chosen = sorted({str(u) for u in member_user_ids if u})
    if len(chosen) > 25:
        raise HTTPException(422, "Choose up to 25 people")
    for uid in chosen:
        if member_role(client, msp_org_id, uid) not in PROVIDER_MEMBER_ROLES:
            raise HTTPException(422, "Everyone you choose must be on the partner's team")

    now = _now()
    granted: list[str] = []
    if access_level == "full":
        for uid in chosen:
            if member_role(client, client_org_id, uid) is None:
                granted.append(uid)
    activated = client.table("msp_clients").update(
        {
            "status": "active",
            "access_level": access_level,
            "approved_by": user_id,
            "approved_at": now.isoformat(),
            "granted_user_ids": granted,
        }
    ).eq("id", relationship_id).eq("status", "pending_client_approval").execute()
    if not activated.data:
        # Answered concurrently (approved, declined or withdrawn): grant nothing.
        raise HTTPException(409, "This request was already answered")
    client.table("organizations").update({"parent_org_id": msp_org_id}).eq("id", client_org_id).execute()
    if access_level == "full":
        for uid in granted:
            client.table("organization_members").insert(
                {"id": str(uuid4()), "org_id": client_org_id, "user_id": uid, "role": "admin"}
            ).execute()
    else:
        expires = (now + timedelta(days=HEALTH_ONLY_GRANT_DAYS)).isoformat()
        for uid in chosen:
            client.table("msp_delegations").insert(
                {
                    "provider_org_id": msp_org_id,
                    "customer_org_id": client_org_id,
                    "grantee_user_id": uid,
                    "tier": 1,
                    "actions": sorted(HEALTH_ONLY_ACTIONS),
                    "approved_by_customer_user_id": user_id,
                    "expires_at": expires,
                }
            ).execute()
    msp_billing.write_client_entitlement(
        client,
        msp_org_id=msp_org_id,
        client_org_id=client_org_id,
        plan_code=str(rel["plan_code"]),
        account=msp_billing.get_billing_account(client, msp_org_id),
    )
    sync = msp_billing.sync_wholesale_quantities(client, settings, msp_org_id)
    invalidate_org_and_users(client_org_id, granted)
    meta = {"access_level": access_level, "members": chosen}
    _audit(client, client_org_id, user_id, "msp.client.approved", relationship_id, {**meta, "msp_org_id": msp_org_id})
    _audit(client, msp_org_id, user_id, "msp.client.approved", relationship_id, {**meta, "client_org_id": client_org_id})
    return {"id": relationship_id, "status": "active", "access_level": access_level, "billing": sync}


def decline(client: Any, *, relationship_id: str, user_id: str) -> dict[str, Any]:
    rel = relationship(client, relationship_id)
    require_client_owner(client, str(rel["client_org_id"]), user_id)
    if rel.get("status") != "pending_client_approval":
        raise HTTPException(409, "This request was already answered")
    client.table("msp_clients").update(
        {"status": "detached", "detached_at": _now().isoformat(), "detached_by": user_id}
    ).eq("id", relationship_id).execute()
    _audit(client, str(rel["client_org_id"]), user_id, "msp.client.declined", relationship_id, {"msp_org_id": str(rel["msp_org_id"])})
    _audit(client, str(rel["msp_org_id"]), user_id, "msp.client.declined", relationship_id, {"client_org_id": str(rel["client_org_id"])})
    return {"id": relationship_id, "status": "detached"}


def detach(client: Any, settings: Any, *, relationship_id: str, user_id: str) -> dict[str, Any]:
    rel = relationship(client, relationship_id)
    client_org_id, msp_org_id = str(rel["client_org_id"]), str(rel["msp_org_id"])
    is_client_owner = member_role(client, client_org_id, user_id) == "owner"
    is_msp_manager = (
        member_role(client, msp_org_id, user_id) in MSP_MANAGER_ROLES
        and (org_row(client, msp_org_id) or {}).get("account_type") == "msp"
    )
    if not (is_client_owner or is_msp_manager):
        raise HTTPException(403, "Only the client's owner or the partner's owners and admins can detach")
    if rel.get("status") == "detached":
        return {"id": relationship_id, "status": "detached"}
    was_active = rel.get("status") == "active"
    client.table("msp_clients").update(
        {"status": "detached", "detached_at": _now().isoformat(), "detached_by": user_id}
    ).eq("id", relationship_id).execute()
    client.table("organizations").update({"parent_org_id": None}).eq("id", client_org_id).eq(
        "parent_org_id", msp_org_id
    ).execute()
    removed: list[str] = []
    for uid in rel.get("granted_user_ids") or []:
        uid = str(uid)
        # Only remove access this relationship added, and never an owner.
        if member_role(client, client_org_id, uid) == "admin":
            client.table("organization_members").delete().eq("org_id", client_org_id).eq("user_id", uid).execute()
            removed.append(uid)
    _revoke_delegations(client, msp_org_id, client_org_id, user_id)
    sync: dict[str, Any] = {"status": "no_change"}
    if was_active:
        msp_billing.release_client_entitlement(client, client_org_id=client_org_id, msp_org_id=msp_org_id)
        sync = msp_billing.sync_wholesale_quantities(client, settings, msp_org_id)
    invalidate_org_and_users(client_org_id, removed)
    meta = {"by": "client" if is_client_owner else "partner", "removed_members": removed}
    _audit(client, client_org_id, user_id, "msp.client.detached", relationship_id, {**meta, "msp_org_id": msp_org_id})
    _audit(client, msp_org_id, user_id, "msp.client.detached", relationship_id, {**meta, "client_org_id": client_org_id})
    return {"id": relationship_id, "status": "detached", "billing": sync}


def _revoke_delegations(client: Any, msp_org_id: str, client_org_id: str, actor: str) -> None:
    try:
        grants = (
            client.table("msp_delegations")
            .select("id")
            .eq("provider_org_id", msp_org_id)
            .eq("customer_org_id", client_org_id)
            .is_("revoked_at", "null")
            .execute()
            .data
            or []
        )
        for grant in grants:
            client.rpc(
                "msp_revoke_delegation_atomic",
                {"p_delegation_id": str(grant["id"]), "p_customer_org_id": client_org_id, "p_actor_user_id": actor},
            ).execute()
    except Exception as exc:  # noqa: BLE001 - parent link is gone, so live checks already fail closed
        logger.warning("msp_detach_revoke_failed client_org_id=%s error=%s", client_org_id, type(exc).__name__)


def update_terms(
    client: Any,
    settings: Any,
    *,
    msp_org_id: str,
    relationship_id: str,
    user_id: str,
    plan_code: str | None,
    resale_price_cents: int | None,
    resale_interval: str | None,
    clear_resale: bool = False,
) -> dict[str, Any]:
    require_msp_manager(client, msp_org_id, user_id)
    rel = relationship(client, relationship_id)
    if str(rel["msp_org_id"]) != msp_org_id:
        raise HTTPException(404, "Client not found")
    if rel.get("status") == "detached":
        raise HTTPException(409, "This client is detached")
    new_plan = plan_code or str(rel["plan_code"])
    new_interval = resale_interval or str(rel.get("resale_interval") or "month")
    new_price = None if clear_resale else (resale_price_cents if resale_price_cents is not None else rel.get("resale_price_cents"))
    _validate_terms(new_plan, new_price, new_interval)
    client.table("msp_clients").update(
        {"plan_code": new_plan, "resale_price_cents": new_price, "resale_interval": new_interval}
    ).eq("id", relationship_id).eq("msp_org_id", msp_org_id).execute()
    sync: dict[str, Any] = {"status": "no_change"}
    if rel.get("status") == "active" and new_plan != rel.get("plan_code"):
        msp_billing.write_client_entitlement(
            client,
            msp_org_id=msp_org_id,
            client_org_id=str(rel["client_org_id"]),
            plan_code=new_plan,
            account=msp_billing.get_billing_account(client, msp_org_id),
        )
        sync = msp_billing.sync_wholesale_quantities(client, settings, msp_org_id)
    _audit(
        client, msp_org_id, user_id, "msp.client.terms_updated", relationship_id,
        {"plan_code": new_plan, "resale_price_cents": new_price, "resale_interval": new_interval},
    )
    return {"id": relationship_id, "plan_code": new_plan, "resale_price_cents": new_price, "resale_interval": new_interval, "billing": sync}


# ---------------------------------------------------------------------------
# Rebilling view
# ---------------------------------------------------------------------------


def _visibility(client: Any, *, msp_org_id: str, client_org_id: str, user_id: str) -> dict[str, bool]:
    """What this MSP user may see about a client beyond plan and billing."""
    if member_role(client, client_org_id, user_id) is not None:
        return {"member": True, "health": True, "usage": True}
    from app.services.msp_delegated_access import authorize_live_action

    health = authorize_live_action(
        client, provider_org_id=msp_org_id, customer_org_id=client_org_id,
        grantee_user_id=user_id, action="account.health.read",
    )
    usage = authorize_live_action(
        client, provider_org_id=msp_org_id, customer_org_id=client_org_id,
        grantee_user_id=user_id, action="usage.aggregate.read",
    )
    return {"member": False, "health": health, "usage": usage}


def _member_count(client: Any, org_id: str) -> int | None:
    try:
        resp = client.table("organization_members").select("id", count="exact").eq("org_id", org_id).limit(1).execute()
    except Exception:  # noqa: BLE001
        return None
    count = getattr(resp, "count", None)
    return int(count) if isinstance(count, int) else None


def _health(client: Any, client_org_id: str) -> dict[str, Any]:
    org = org_row(client, client_org_id) or {}
    billing = (
        client.table("org_billing").select("billing_status").eq("org_id", client_org_id).limit(1).execute().data or []
    )
    status = str(org.get("status") or "active")
    billing_status = str((billing[0] if billing else {}).get("billing_status") or "trialing")
    if status != "active":
        label = "attention"
    elif billing_status in {"past_due", "cancelled", "canceled"}:
        label = "attention"
    else:
        label = "healthy"
    return {"label": label, "org_status": status, "billing_status": billing_status}


def list_clients(
    client: Any,
    settings: Any,
    *,
    msp_org_id: str,
    user_id: str,
    period: tuple[date, date] | None = None,
    include_detached: bool = False,
) -> dict[str, Any]:
    require_msp_manager(client, msp_org_id, user_id)
    query = client.table("msp_clients").select("*").eq("msp_org_id", msp_org_id)
    if not include_detached:
        query = query.in_("status", list(LIVE_STATUSES))
    rows = query.order("created_at", desc=False).limit(MAX_CLIENTS).execute().data or []
    period_start, period_end = period or get_current_period()
    # Names only for workspaces whose owner approved (or that the MSP created).
    active_ids = [str(r["client_org_id"]) for r in rows if r.get("approved_at")]
    names = org_names(client, active_ids)
    prices = {tier: msp_billing.wholesale_price_info(settings, tier) for tier in msp_billing.MSP_TIERS}
    items: list[dict[str, Any]] = []
    totals = {"wholesale_monthly_cents": 0, "resale_monthly_cents": 0, "margin_monthly_cents": 0, "active_clients": 0}
    totals_complete = True
    for row in rows:
        cid = str(row["client_org_id"])
        tier = str(row["plan_code"])
        wholesale = (prices.get(tier) or {}).get("monthly_cents")
        resale = _resale_monthly(row)
        margin = resale - wholesale if (resale is not None and wholesale is not None) else None
        item: dict[str, Any] = {
            "id": str(row["id"]),
            "client_org_id": cid,
            # Name stays hidden until the client owner approves the link.
            "name": names.get(cid, "Workspace") if row.get("approved_at") else None,
            "plan_code": tier,
            "plan_name": _plan_name(tier),
            "list_price_usd": (DEFAULT_PLANS.get(tier) or {}).get("price_usd"),
            "status": row.get("status"),
            "origin": row.get("origin"),
            "access_level": row.get("access_level"),
            "resale_price_cents": row.get("resale_price_cents"),
            "resale_interval": row.get("resale_interval") or "month",
            "resale_currency": row.get("resale_currency") or "usd",
            "resale_monthly_cents": resale,
            "wholesale_monthly_cents": wholesale,
            "margin_monthly_cents": margin,
            "approved_at": row.get("approved_at"),
            "detached_at": row.get("detached_at"),
            "created_at": row.get("created_at"),
            "can_open": False,
            "members": None,
            "usage": None,
            "health": None,
        }
        if row.get("status") == "active":
            vis = _visibility(client, msp_org_id=msp_org_id, client_org_id=cid, user_id=user_id)
            item["can_open"] = vis["member"]
            if vis["usage"]:
                item["members"] = _member_count(client, cid)
                try:
                    item["usage"] = get_usage_totals(client, cid, period_start, period_end)
                except Exception:  # noqa: BLE001
                    item["usage"] = None
            if vis["health"]:
                item["health"] = _health(client, cid)
            totals["active_clients"] += 1
            if wholesale is not None:
                totals["wholesale_monthly_cents"] += wholesale
            else:
                totals_complete = False
            if resale is not None:
                totals["resale_monthly_cents"] += resale
            else:
                totals_complete = False
            if margin is not None:
                totals["margin_monthly_cents"] += margin
        items.append(item)
    return {
        "clients": items,
        "totals": {**totals, "complete": totals_complete},
        "period": {"start": period_start.isoformat(), "end": period_end.isoformat()},
        "wholesale": {
            **msp_billing.wholesale_setup(settings),
            "prices": {
                tier: (
                    {"monthly_cents": info["monthly_cents"], "currency": info["currency"]} if info else None
                )
                for tier, info in prices.items()
            },
        },
        "truncated": len(rows) >= MAX_CLIENTS,
    }


def parse_period(value: str | None) -> tuple[date, date]:
    if not value:
        return get_current_period()
    try:
        year, month = (int(part) for part in value.split("-", 1))
        start = date(year, month, 1)
    except (ValueError, TypeError):
        raise HTTPException(422, "Period must look like 2026-10") from None
    end = (date(year + (month == 12), (month % 12) + 1, 1)) - timedelta(days=1)
    return start, end


def statement_csv(client: Any, settings: Any, *, msp_org_id: str, user_id: str, period: str | None) -> tuple[str, str]:
    start, end = parse_period(period)
    data = list_clients(client, settings, msp_org_id=msp_org_id, user_id=user_id, period=(start, end), include_detached=True)
    out = io.StringIO()
    writer = csv.writer(out)
    writer.writerow([
        "client", "workspace_id", "plan", "status", "wholesale_monthly", "resale_price", "resale_interval",
        "resale_monthly", "margin_monthly", "currency", "ai_credits", "workflow_runs",
    ])

    def money(cents: int | None) -> str:
        return "" if cents is None else f"{cents / 100:.2f}"

    for item in data["clients"]:
        if item["status"] == "pending_client_approval":
            continue
        approved = str(item.get("approved_at") or "")[:10]
        detached = str(item.get("detached_at") or "")[:10]
        # Only clients that were active at some point in the period.
        if approved and approved > end.isoformat():
            continue
        if detached and detached < start.isoformat():
            continue
        usage = item.get("usage") or {}
        writer.writerow([
            item.get("name") or "Workspace", item["client_org_id"], item["plan_name"], item["status"],
            money(item["wholesale_monthly_cents"]), money(item["resale_price_cents"]), item["resale_interval"],
            money(item["resale_monthly_cents"]), money(item["margin_monthly_cents"]), item["resale_currency"],
            usage.get("ai_credits", ""), usage.get("workflow_runs", ""),
        ])
    totals = data["totals"]
    writer.writerow([])
    writer.writerow([
        "TOTAL (active now)", "", "", "", money(totals["wholesale_monthly_cents"]), "", "",
        money(totals["resale_monthly_cents"]), money(totals["margin_monthly_cents"]), "usd", "", "",
    ])
    return out.getvalue(), f"gravitre-rebilling-{start.strftime('%Y-%m')}.csv"


# ---------------------------------------------------------------------------
# Overview for the current workspace
# ---------------------------------------------------------------------------


def overview(client: Any, settings: Any, *, org_id: str, user_id: str) -> dict[str, Any]:
    org = org_row(client, org_id)
    if not org:
        raise HTTPException(404, "Workspace not found")
    role = member_role(client, org_id, user_id)
    if role is None:
        raise HTTPException(403, "Not a member of this workspace")
    is_msp = org.get("account_type") == "msp"
    live = live_relationship_for_client(client, org_id)
    result: dict[str, Any] = {
        "org": {"id": org_id, "name": org.get("name"), "account_type": org.get("account_type")},
        "role": role,
        "is_msp": is_msp,
        "can_manage": is_msp and role in MSP_MANAGER_ROLES,
        "can_enroll": (not is_msp) and role == "owner" and live is None,
        "wholesale": msp_billing.wholesale_setup(settings),
        "billing_account": None,
        "managed_by": None,
        "pending_request": None,
    }
    if is_msp and role in MSP_MANAGER_ROLES:
        account = msp_billing.get_billing_account(client, org_id)
        if account:
            result["billing_account"] = {
                "status": account.get("status"),
                "current_period_end": account.get("current_period_end"),
                "cancel_at_period_end": bool(account.get("cancel_at_period_end")),
            }
        result["wholesale"]["prices"] = {
            tier: (
                {"monthly_cents": info["monthly_cents"], "currency": info["currency"]}
                if (info := msp_billing.wholesale_price_info(settings, tier))
                else None
            )
            for tier in msp_billing.MSP_TIERS
        }
    if live:
        msp_id = str(live["msp_org_id"])
        msp_name = org_names(client, [msp_id]).get(msp_id, "Your partner")
        if live.get("status") == "active":
            result["managed_by"] = {
                "relationship_id": str(live["id"]),
                "msp_org_id": msp_id,
                "msp_name": msp_name,
                "plan_code": live.get("plan_code"),
                "plan_name": _plan_name(str(live.get("plan_code"))),
                "access_level": live.get("access_level"),
                "can_detach": role == "owner",
            }
        elif role == "owner":
            result["pending_request"] = {
                "relationship_id": str(live["id"]),
                "msp_org_id": msp_id,
                "msp_name": msp_name,
                "plan_code": live.get("plan_code"),
                "plan_name": _plan_name(str(live.get("plan_code"))),
                "requested_at": live.get("created_at"),
                "msp_members": org_members(client, msp_id),
                "own_subscription_conflict": msp_billing.own_subscription_conflict(client, org_id),
            }
    return result


def billed_by(client: Any, org_id: str) -> dict[str, Any] | None:
    """For Settings › Billing: who pays for this workspace, if a partner does."""
    rows = (
        client.table("org_billing")
        .select("billing_source,billed_by_org_id,plan_code,billing_status")
        .eq("org_id", org_id)
        .limit(1)
        .execute()
        .data
        or []
    )
    if not rows or rows[0].get("billing_source") != "msp" or not rows[0].get("billed_by_org_id"):
        return None
    msp_id = str(rows[0]["billed_by_org_id"])
    return {
        "msp_org_id": msp_id,
        "msp_name": org_names(client, [msp_id]).get(msp_id, "your partner"),
        "plan_code": rows[0].get("plan_code"),
        "plan_name": _plan_name(str(rows[0].get("plan_code") or "")),
        "billing_status": rows[0].get("billing_status"),
    }
