#!/usr/bin/env python3
"""F6 live proof: forced vendor re-read must VERIFIED (not write-response proof).

Smoke org Apollo + HubSpot. For each vendor:
  1. Create list → before membership read (expect 0)
  2. Membership write
  3. Strip write-response proof fields
  4. verify_collection_population → must follow_up_membership_confirmed
  5. After membership read non-empty

Writes docs/delivery/f6-collection-population-verify-live.json
"""
from __future__ import annotations

import json
import os
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

from dotenv import dotenv_values

REPO = Path(__file__).resolve().parent.parent
BACKEND = REPO / "backend"
sys.path.insert(0, str(BACKEND))

ORG = "cbbf993b-b22f-41ce-964b-1fc25e0dd9ea"
ACTOR = "f7e32f06-49df-4e73-8962-f41c21850762"
OUT = REPO / "docs" / "delivery" / "f6-collection-population-verify-live.json"

_PROOF_KEYS = (
    "contact_count",
    "contacts_count",
    "member_count",
    "added_count",
    "contacts",
    "people",
    "entity_ids",
    "contact_ids",
    "contact_id",
    "size",
    "membershipCount",
    "memberships",
    "results",
)


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def _load_env() -> None:
    merged: dict[str, str] = {}
    for p in (BACKEND / ".env", BACKEND / ".env.operator.local", REPO / ".env"):
        if not p.is_file():
            continue
        loaded = None
        for enc in ("utf-8", "utf-8-sig", "cp1252", "latin-1"):
            try:
                loaded = dotenv_values(p, encoding=enc)
                break
            except UnicodeDecodeError:
                continue
        if loaded:
            merged.update({k: v for k, v in loaded.items() if v})
    for k, v in merged.items():
        os.environ.setdefault(k, v)


_SB = None
_SETTINGS = None


def _sb():
    global _SB, _SETTINGS
    if _SB is None:
        from app.config import get_settings
        from supabase import create_client

        _SETTINGS = get_settings()
        _SB = create_client(_SETTINGS.supabase_url, _SETTINGS.supabase_service_role_key)
    return _SB


def _connector_id(vendor: str) -> str | None:
    rows = (
        _sb()
        .table("connectors")
        .select("id, type, status")
        .eq("org_id", ORG)
        .eq("type", vendor)
        .is_("deleted_at", "null")
        .limit(5)
        .execute()
    ).data or []
    for row in rows:
        if str(row.get("status") or "").lower() in {"active", "connected", "healthy"}:
            return str(row["id"])
    return None


def _ctx(vendor: str):
    from app.config import get_settings
    from app.services.tool_types import ToolContext

    connector_id = _connector_id(vendor)
    return ToolContext(
        settings=_SETTINGS or get_settings(),
        client=_sb(),
        org_id=ORG,
        actor_id=ACTOR,
        connector_id=connector_id,
    ), connector_id


def _invoke(action: str, params: dict, ctx=None, connector_id: str | None = None):
    from app.services.tool_service import invoke_tool

    vendor = action.split(".", 1)[0]
    if ctx is None:
        ctx, connector_id = _ctx(vendor)
    payload = dict(params)
    if connector_id:
        payload.setdefault("connector_id", connector_id)
    last = None
    for attempt in range(1, 4):
        last = invoke_tool(ctx, action, payload)
        if last.success:
            return last, ctx, connector_id
        time.sleep(attempt)
    return last, ctx, connector_id


def _strip_proof(data: dict, *, list_id: str) -> dict:
    out = {k: v for k, v in data.items() if k not in _PROOF_KEYS}
    out["list_id"] = list_id
    out["success"] = True
    return out


def _apollo_case(suffix: str) -> dict:
    from app.services.collection_population_verify import verify_collection_population

    ctx, cid = _ctx("apollo")
    list_name = f"F6-FollowUp-{suffix}"
    create, ctx, cid = _invoke(
        "apollo.lists.create",
        {"name": list_name, "modality": "contacts"},
        ctx=ctx,
        connector_id=cid,
    )
    cdata = create.data if isinstance(create.data, dict) else {}
    list_id = str(cdata.get("list_id") or cdata.get("id") or "").strip()
    before, _, _ = _invoke("apollo.lists.list", {"list_id": list_id}, ctx=ctx, connector_id=cid)
    bdata = before.data if isinstance(before.data, dict) else {}
    before_n = int(bdata.get("contact_count") or 0)

    contact, ctx, cid = _invoke(
        "apollo.contacts.create",
        {
            "first_name": "F6",
            "last_name": f"FU{suffix}",
            "email": f"f6.fu.{suffix}@example.com",
        },
        ctx=ctx,
        connector_id=cid,
    )
    ccd = contact.data if isinstance(contact.data, dict) else {}
    entity_id = str(
        ccd.get("id") or ccd.get("contact_id") or (ccd.get("contact") or {}).get("id") or ""
    ).strip()

    add = None
    for attempt in range(1, 4):
        time.sleep(attempt)
        add, ctx, cid = _invoke(
            "apollo.lists.add",
            {
                "entity_ids": [entity_id],
                "label_names": [list_name],
                "modality": "contacts",
                "list_id": list_id,
            },
            ctx=ctx,
            connector_id=cid,
        )
        if add.success:
            break
    adata = add.data if add and isinstance(add.data, dict) else {}
    time.sleep(2)
    stripped = _strip_proof(adata, list_id=list_id)
    verify = verify_collection_population(
        invoke_action="apollo.lists.add",
        result_data=stripped,
        client=_sb(),
        org_id=ORG,
        settings=_SETTINGS,
        environment_name="production",
        ctx=ctx,
    )
    after, _, _ = _invoke("apollo.lists.list", {"list_id": list_id}, ctx=ctx, connector_id=cid)
    adata_after = after.data if isinstance(after.data, dict) else {}
    after_n = int(adata_after.get("contact_count") or len(adata_after.get("contacts") or []) or 0)

    return {
        "vendor": "apollo",
        "connector_id": cid,
        "list_name": list_name,
        "list_id": list_id,
        "entity_id": entity_id,
        "create_success": bool(create.success),
        "add_success": bool(add and add.success),
        "add_error": add.error_message if add else None,
        "before_membership": before_n,
        "after_membership": after_n,
        "after_read_keys": sorted(adata_after.keys())[:30],
        "membership_source": adata_after.get("membership_source"),
        "population_verify": {
            "verified": verify.verified,
            "effect": verify.effect,
            "membership_count": verify.membership_count,
            "detail": verify.detail,
            "follow_up_attempted": verify.follow_up_attempted,
        },
        "pass": bool(
            add
            and add.success
            and verify.follow_up_attempted
            and verify.verified
            and verify.detail == "follow_up_membership_confirmed"
            and after_n > before_n
        ),
    }


def _hubspot_case(suffix: str) -> dict:
    from app.services.collection_population_verify import verify_collection_population

    ctx, cid = _ctx("hubspot")
    list_name = f"F6-HS-{suffix}"
    create, ctx, cid = _invoke(
        "hubspot.lists.create",
        {"name": list_name},
        ctx=ctx,
        connector_id=cid,
    )
    cdata = create.data if isinstance(create.data, dict) else {}
    list_id = str(
        cdata.get("list_id")
        or cdata.get("listId")
        or (cdata.get("list") or {}).get("listId")
        or cdata.get("id")
        or ""
    ).strip()

    before, ctx, cid = _invoke(
        "hubspot.lists.get", {"list_id": list_id}, ctx=ctx, connector_id=cid
    )
    bdata = before.data if isinstance(before.data, dict) else {}
    before_n = int(bdata.get("size") or bdata.get("membershipCount") or 0)

    # Prefer an existing contact; create if list is empty.
    search, ctx, cid = _invoke(
        "hubspot.contacts.search",
        {"list_all": True, "limit": 5},
        ctx=ctx,
        connector_id=cid,
    )
    sdata = search.data if isinstance(search.data, dict) else {}
    contact_id = None
    for bag_key in ("contacts", "results", "data"):
        for row in sdata.get(bag_key) or []:
            if isinstance(row, dict):
                contact_id = str(row.get("id") or row.get("contact_id") or "").strip()
                if contact_id:
                    break
        if contact_id:
            break
    if not contact_id:
        created, ctx, cid = _invoke(
            "hubspot.contacts.create",
            {
                "properties": {
                    "email": f"f6.hs.{suffix}@example.com",
                    "firstname": "F6",
                    "lastname": f"HS{suffix}",
                }
            },
            ctx=ctx,
            connector_id=cid,
        )
        ccd = created.data if isinstance(created.data, dict) else {}
        contact_id = str(
            ccd.get("id")
            or (ccd.get("contact") or {}).get("id")
            or ccd.get("contact_id")
            or ""
        ).strip()

    add, ctx, cid = _invoke(
        "hubspot.lists.add_contact",
        {"list_id": list_id, "contact_id": contact_id},
        ctx=ctx,
        connector_id=cid,
    )
    adata = add.data if isinstance(add.data, dict) else {}
    time.sleep(2)
    stripped = _strip_proof(adata, list_id=list_id)
    verify = verify_collection_population(
        invoke_action="hubspot.lists.add_contact",
        result_data=stripped,
        client=_sb(),
        org_id=ORG,
        settings=_SETTINGS,
        environment_name="production",
        ctx=ctx,
    )
    after, _, _ = _invoke("hubspot.lists.get", {"list_id": list_id}, ctx=ctx, connector_id=cid)
    adata_after = after.data if isinstance(after.data, dict) else {}
    after_n = int(
        adata_after.get("size")
        or adata_after.get("membershipCount")
        or len(adata_after.get("memberships") or [])
        or 0
    )

    return {
        "vendor": "hubspot",
        "connector_id": cid,
        "list_name": list_name,
        "list_id": list_id,
        "contact_id": contact_id,
        "create_success": bool(create.success),
        "add_success": bool(add.success),
        "add_error": add.error_message,
        "before_membership": before_n,
        "after_membership": after_n,
        "after_read_keys": sorted(adata_after.keys())[:30],
        "population_verify": {
            "verified": verify.verified,
            "effect": verify.effect,
            "membership_count": verify.membership_count,
            "detail": verify.detail,
            "follow_up_attempted": verify.follow_up_attempted,
        },
        "pass": bool(
            add.success
            and verify.follow_up_attempted
            and verify.verified
            and verify.detail == "follow_up_membership_confirmed"
            and after_n > before_n
        ),
    }


def main() -> int:
    _load_env()
    suffix = uuid.uuid4().hex[:8]
    evidence: dict = {
        "started_at": utcnow(),
        "org_id": ORG,
        "requirement": "forced_re_read_follow_up_membership_confirmed",
        "live_health_git_sha": None,
    }
    try:
        import urllib.request

        with urllib.request.urlopen("https://api.gravitre.app/health", timeout=20) as resp:
            evidence["live_health_git_sha"] = json.loads(resp.read().decode()).get("git_sha")
    except Exception as exc:  # noqa: BLE001
        evidence["live_health_error"] = str(exc)

    evidence["apollo"] = _apollo_case(suffix)
    evidence["hubspot"] = _hubspot_case(suffix)
    evidence["finished_at"] = utcnow()
    evidence["pass"] = bool(evidence["apollo"].get("pass") and evidence["hubspot"].get("pass"))
    evidence["verdict"] = (
        "VERIFIED — both vendors follow_up_membership_confirmed with non-empty re-read"
        if evidence["pass"]
        else "FAIL — see vendor pass flags / population_verify.detail"
    )
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(evidence, indent=2), encoding="utf-8")
    print(json.dumps(evidence, indent=2))
    return 0 if evidence["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
