#!/usr/bin/env python3
"""F6 live proof: Apollo list membership write + collection_population_verify follow-up.

Uses the smoke-org Apollo connector (same as list-populate-honesty). Reports:
  - before/after vendor membership counts
  - verify_collection_population() detail (follow_up_attempted / membership_count)
  - mini-run id after honesty finalize

Writes docs/delivery/f6-collection-population-verify-live.json
"""
from __future__ import annotations

import json
import os
import sys
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
_CONNECTORS: dict[str, str] = {}


def _sb():
    global _SB, _SETTINGS
    if _SB is None:
        from app.config import get_settings
        from supabase import create_client

        _SETTINGS = get_settings()
        _SB = create_client(_SETTINGS.supabase_url, _SETTINGS.supabase_service_role_key)
    return _SB


def _connector_id(vendor: str) -> str | None:
    if vendor in _CONNECTORS:
        return _CONNECTORS[vendor]
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
            _CONNECTORS[vendor] = str(row["id"])
            return _CONNECTORS[vendor]
    return None


def _ctx(action: str):
    from app.config import get_settings
    from app.services.tool_types import ToolContext

    vendor = action.split(".", 1)[0]
    connector_id = _connector_id(vendor)
    return ToolContext(
        settings=_SETTINGS or get_settings(),
        client=_sb(),
        org_id=ORG,
        actor_id=ACTOR,
        connector_id=connector_id,
    ), connector_id


def _invoke(action: str, params: dict):
    from app.services.tool_service import invoke_tool

    ctx, connector_id = _ctx(action)
    payload = dict(params)
    if connector_id:
        payload.setdefault("connector_id", connector_id)
    return invoke_tool(ctx, action, payload), ctx


def _membership_count(list_id: str, ctx) -> dict:
    from app.services.tool_service import invoke_tool

    out = invoke_tool(ctx, "apollo.lists.list", {"list_id": list_id})
    payload = out.data if isinstance(getattr(out, "data", None), dict) else {}
    count = None
    for key in ("contact_count", "contacts_count", "member_count", "count"):
        if payload.get(key) is not None:
            count = int(payload.get(key) or 0)
            break
    if count is None:
        contacts = payload.get("contacts") or payload.get("people") or []
        count = len(contacts) if isinstance(contacts, list) else None
    return {
        "success": bool(out.success),
        "error": out.error_message,
        "count": count,
        "raw_keys": sorted(payload.keys())[:40] if isinstance(payload, dict) else [],
    }


def main() -> int:
    _load_env()
    suffix = uuid.uuid4().hex[:8]
    list_name = f"F6-PopVerify-{suffix}"
    evidence: dict = {
        "started_at": utcnow(),
        "org_id": ORG,
        "list_name": list_name,
        "live_health_git_sha": None,
        "pass": False,
    }

    try:
        import urllib.request

        with urllib.request.urlopen("https://api.gravitre.app/health", timeout=20) as resp:
            health = json.loads(resp.read().decode("utf-8"))
            evidence["live_health_git_sha"] = health.get("git_sha")
    except Exception as exc:  # noqa: BLE001
        evidence["live_health_error"] = str(exc)

    create = _invoke("apollo.lists.create", {"name": list_name, "modality": "contacts"})
    create_result, ctx = create
    create_data = create_result.data if isinstance(create_result.data, dict) else {}
    list_id = str(
        create_data.get("list_id")
        or create_data.get("listId")
        or create_data.get("id")
        or (create_data.get("list") or {}).get("id")
        or ""
    ).strip()
    evidence["create"] = {
        "success": bool(create_result.success),
        "error": create_result.error_message,
        "list_id": list_id or None,
        "data_keys": sorted(create_data.keys())[:40],
    }
    if not create_result.success or not list_id:
        evidence["error"] = "apollo.lists.create failed or missing list_id"
        OUT.write_text(json.dumps(evidence, indent=2), encoding="utf-8")
        print(json.dumps(evidence, indent=2))
        return 1

    before = _membership_count(list_id, ctx)
    evidence["before_vendor"] = before

    # Find or create a contact to add.
    entity_ids: list[str] = []
    search, _ = _invoke(
        "apollo.contacts.search",
        {"q_keywords": "gravitre", "page": 1, "per_page": 5},
    )
    search_data = search.data if isinstance(search.data, dict) else {}
    for bag_key in ("contacts", "people", "results"):
        for c in search_data.get(bag_key) or []:
            if not isinstance(c, dict):
                continue
            cid = str(c.get("id") or c.get("contact_id") or c.get("person_id") or "").strip()
            if cid:
                entity_ids.append(cid)
            if len(entity_ids) >= 1:
                break
        if entity_ids:
            break
    if not entity_ids:
        created_contact, _ = _invoke(
            "apollo.contacts.create",
            {
                "first_name": "F6",
                "last_name": f"Verify{suffix}",
                "email": f"f6.verify.{suffix}@example.com",
            },
        )
        cdata = created_contact.data if isinstance(created_contact.data, dict) else {}
        cid = str(
            cdata.get("id")
            or cdata.get("contact_id")
            or (cdata.get("contact") or {}).get("id")
            or ""
        ).strip()
        evidence["contact_create"] = {
            "success": bool(created_contact.success),
            "error": created_contact.error_message,
            "contact_id": cid or None,
        }
        if cid:
            entity_ids.append(cid)

    if not entity_ids:
        evidence["error"] = "no entity_ids for apollo.lists.add"
        OUT.write_text(json.dumps(evidence, indent=2), encoding="utf-8")
        print(json.dumps(evidence, indent=2))
        return 1

    add_result, add_ctx = _invoke(
        "apollo.lists.add",
        {
            "entity_ids": entity_ids,
            "label_names": [list_name],
            "modality": "contacts",
            "list_id": list_id,
        },
    )
    add_data = add_result.data if isinstance(add_result.data, dict) else {}
    # Ensure follow-up path has list_id even if vendor omits it from add response.
    verify_payload = {**add_data, "list_id": list_id}
    # Strip inline membership proof so verify must follow up (the F6 claim).
    for k in ("contact_count", "contacts_count", "member_count", "added_count", "contacts", "people"):
        verify_payload.pop(k, None)

    from app.services.collection_population_verify import (
        apply_population_verify_to_status,
        verify_collection_population,
    )

    verify = verify_collection_population(
        invoke_action="apollo.lists.add",
        result_data=verify_payload,
        client=_sb(),
        org_id=ORG,
        settings=_SETTINGS,
        environment_name="production",
        ctx=add_ctx,
    )
    status, effect, pop = apply_population_verify_to_status(
        status="completed",
        invoke_action="apollo.lists.add",
        result_data=verify_payload,
        client=_sb(),
        org_id=ORG,
        settings=_SETTINGS,
        environment_name="production",
        ctx=add_ctx,
    )

    after = _membership_count(list_id, add_ctx)
    evidence["add"] = {
        "success": bool(add_result.success),
        "error": add_result.error_message,
        "entity_ids": entity_ids,
        "data_keys": sorted(add_data.keys())[:40],
    }
    evidence["population_verify"] = {
        "verified": verify.verified,
        "effect": verify.effect,
        "membership_count": verify.membership_count,
        "detail": verify.detail,
        "follow_up_attempted": verify.follow_up_attempted,
        "status_after_apply": status,
        "effect_override": effect,
        "apply_detail": None if pop is None else pop.detail,
    }
    evidence["after_vendor"] = after

    # Persist a mini run id for evidence trail (finalize via connector honesty).
    from app.services.connector_output_refs import collect_connector_output_refs, primary_vendor_url
    from app.services.execution_outcome import VerifiedOutputRef, finalize_execution_outcome
    from app.services.list_populate_honesty import apply_connector_run_honesty
    from app.workflows.repository import create_run, create_step, update_step, get_run_with_steps

    client = _sb()
    created = create_run(
        client,
        org_id=ORG,
        triggered_by=ACTOR,
        definition_snapshot={
            "name": f"F6 population verify {suffix}",
            "source": "f6_collection_population_verify_live",
            "steps": [
                {"id": "s0", "name": "Create list", "type": "invoke_tool"},
                {"id": "s1", "name": "Add contacts", "type": "invoke_tool"},
            ],
        },
        parameters={
            "source": "f6_collection_population_verify_live",
            "expects_list_population": True,
            "list_id": list_id,
            "list_name": list_name,
        },
        run_hash=f"f6-pop-{uuid.uuid4().hex[:16]}",
        workflow_id=None,
        environment_name="production",
        trigger_type="api",
        run_type="execute",
    )
    run_id = str(created["id"])
    now = utcnow()
    for i, (name, action, data, ok) in enumerate(
        [
            ("Create list", "apollo.lists.create", create_data, create_result.success),
            ("Add contacts", "apollo.lists.add", {**add_data, "list_id": list_id}, add_result.success),
        ]
    ):
        row = create_step(
            client,
            run_id,
            ORG,
            step_id=f"s{i}",
            step_index=i,
            step_name=name,
            step_type="invoke_tool",
        )
        update_step(
            client,
            str(row["id"]),
            status="completed" if ok else "failed",
            output_snapshot={
                "invoke_action": action,
                "success": bool(ok),
                **(data if isinstance(data, dict) else {}),
                "population_verify": evidence["population_verify"],
            },
            started_at=now,
            completed_at=now,
            error_message=None,
        )

    loaded = get_run_with_steps(client, ORG, run_id, "production") or {}
    steps = loaded.get("steps") or []
    refs = collect_connector_output_refs(steps)
    vendor_url = primary_vendor_url(refs)
    coerced, reason = apply_connector_run_honesty(
        status="completed" if add_result.success else "failed",
        step_rows=steps,
        output_refs=refs,
        parameters={"expects_list_population": True},
    )
    finalize_execution_outcome(
        client,
        org_id=ORG,
        status=coerced,
        source="api",
        actor_id=ACTOR,
        run_id=run_id,
        verified_output=VerifiedOutputRef(
            result_url=f"/runs/{run_id}",
            external_url=vendor_url,
            entity_type="workflow_run",
            entity_id=run_id,
            summary=f"F6 population verify list_id={list_id}",
        ),
        metadata={
            "path": "f6_collection_population_verify_live",
            "population_verify": evidence["population_verify"],
            "list_populate_honesty_reason": reason,
        },
    )
    evidence["run_id"] = run_id
    evidence["coerced_status"] = coerced
    evidence["honesty_reason"] = reason
    evidence["finished_at"] = utcnow()
    evidence["pass"] = bool(
        add_result.success
        and verify.follow_up_attempted
        and verify.verified
        and verify.detail == "follow_up_membership_confirmed"
        and (after.get("count") or 0) > (before.get("count") or 0)
    )
    # Soft pass: follow-up ran and after > before even if verify detail differs.
    if not evidence["pass"] and add_result.success and verify.follow_up_attempted:
        evidence["pass_partial"] = bool(
            verify.verified or ((after.get("count") or 0) > (before.get("count") or 0))
        )
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(evidence, indent=2), encoding="utf-8")
    print(json.dumps(evidence, indent=2))
    return 0 if evidence["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
