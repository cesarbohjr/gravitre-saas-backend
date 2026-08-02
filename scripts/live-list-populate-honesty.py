#!/usr/bin/env python3
"""Live proof: list populate honesty (empty shell vs populated) + HubSpot link.

Runs against the smoke-org Apollo/HubSpot connectors with LOCAL code (pre-merge).

Cases:
  a) Populate-intent empty shell → partial_success + "list created, 0 contacts added"
  b) Create + lists.add with real contacts → COMPLETED
  c) HubSpot lists.create → Open-in-source URL is a real https HubSpot object URL

Writes docs/delivery/list-populate-honesty-live.json
"""
from __future__ import annotations

import json
import os
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

import httpx
from dotenv import dotenv_values

REPO = Path(__file__).resolve().parent.parent
BACKEND = REPO / "backend"
sys.path.insert(0, str(BACKEND))

BASE = os.environ.get(
    "BACKEND_URL",
    "https://gravitre-saas-backend-production.up.railway.app",
).rstrip("/")
ORG = "cbbf993b-b22f-41ce-964b-1fc25e0dd9ea"
ACTOR = "f7e32f06-49df-4e73-8962-f41c21850762"
OUT = REPO / "docs" / "delivery" / "list-populate-honesty-live.json"


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


def _invoke(action: str, params: dict):
    from app.config import get_settings
    from app.services.tool_service import invoke_tool
    from app.services.tool_types import ToolContext

    vendor = action.split(".", 1)[0]
    connector_id = _connector_id(vendor)
    ctx = ToolContext(
        settings=_SETTINGS or get_settings(),
        client=_sb(),
        org_id=ORG,
        actor_id=ACTOR,
        connector_id=connector_id,
    )
    payload = dict(params)
    if connector_id:
        payload.setdefault("connector_id", connector_id)
    return invoke_tool(ctx, action, payload)


def _finalize_mini_run(
    *,
    label: str,
    step_rows: list[dict],
    parameters: dict,
    final_status: str = "completed",
) -> dict:
    """Persist a mini run + steps, then Module A finalize through honesty gate."""
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
            "name": label,
            "source": "list_populate_honesty_live",
            "steps": [
                {
                    "id": f"s{i}",
                    "name": s.get("name") or f"step-{i}",
                    "type": s.get("type") or "invoke_tool",
                }
                for i, s in enumerate(step_rows)
            ],
        },
        parameters=parameters,
        run_hash=f"list-honesty-{uuid.uuid4().hex[:16]}",
        workflow_id=None,
        environment_name="production",
        trigger_type="api",
        run_type="execute",
    )
    run_id = str(created["id"])
    now = utcnow()
    for i, step in enumerate(step_rows):
        row = create_step(
            client,
            run_id,
            ORG,
            step_id=f"s{i}",
            step_index=i,
            step_name=str(step.get("name") or f"step-{i}"),
            step_type=str(step.get("type") or "invoke_tool"),
        )
        update_step(
            client,
            str(row["id"]),
            status=str(step.get("status") or "completed"),
            output_snapshot=step.get("output_snapshot") or {},
            started_at=now,
            completed_at=now,
            error_message=None,
        )
        # Preserve agent metadata for populate detection on re-fetch if needed.
        if step.get("metadata"):
            try:
                client.table("workflow_steps").update({"metadata": step["metadata"]}).eq(
                    "id", row["id"]
                ).execute()
            except Exception:
                pass

    loaded = get_run_with_steps(client, ORG, run_id, "production") or {}
    loaded_steps = loaded.get("steps") or step_rows
    # Merge agent metadata from our constructed rows (DB may drop unknown cols).
    for i, step in enumerate(step_rows):
        if i < len(loaded_steps) and step.get("metadata"):
            loaded_steps[i] = {**loaded_steps[i], "metadata": step["metadata"]}

    refs = collect_connector_output_refs(loaded_steps)
    vendor_url = primary_vendor_url(refs)
    coerced, reason = apply_connector_run_honesty(
        status=final_status,
        step_rows=loaded_steps,
        output_refs=refs,
        parameters=parameters,
        workflow_name=parameters.get("workflow_name"),
        workflow_slug=parameters.get("workflow_slug"),
    )
    summary = reason or "; ".join(str(r.get("summary") or "") for r in refs if r.get("summary"))[:2000]
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
            summary=summary or None,
        ),
        metadata={
            "path": "list_populate_honesty_live",
            "step_results": refs,
            "connector_output_refs": refs,
            "list_populate_honesty_reason": reason,
            "outcome_honesty_reason": reason,
        },
    )
    refreshed = get_run_with_steps(client, ORG, run_id, "production") or {}
    persisted_status = refreshed.get("status")
    return {
        "run_id": run_id,
        "status": persisted_status if persisted_status not in {None, "running"} else coerced,
        "persisted_status": persisted_status,
        "coerced_status": coerced,
        "run_persisted_ok": str(persisted_status or "").lower() == str(coerced or "").lower(),
        "honesty_reason": reason,
        "vendor_url": vendor_url,
        "connector_output_refs": refs,
        "summary": summary,
    }


def main() -> int:
    _load_env()
    tip = None
    try:
        tip = httpx.get(f"{BASE}/health", timeout=60.0).json().get("git_sha")
    except Exception as exc:  # noqa: BLE001
        tip = f"health_error:{exc}"

    suffix = uuid.uuid4().hex[:8]
    evidence: dict = {
        "generated_at": utcnow(),
        "prod_tip_at_run": tip,
        "org_id": ORG,
        "note": "Local code honesty gate + live Apollo/HubSpot invokes; merge only if both directions pass.",
        "cases": {},
    }

    # --- (a) empty shell, populate intent ---
    list_name = f"Honesty-Empty-{suffix}"
    create_empty = _invoke(
        "apollo.lists.create",
        {"name": list_name, "modality": "contacts"},
    )
    empty_data = create_empty.data if isinstance(create_empty.data, dict) else {}
    empty_list_id = str(
        empty_data.get("list_id")
        or empty_data.get("id")
        or (empty_data.get("label") or {}).get("id")
        or ""
    )
    empty_url = str(empty_data.get("result_url") or empty_data.get("external_url") or "")
    from app.services.connector_output_refs import enrich_invoke_tool_snapshot

    empty_snap = enrich_invoke_tool_snapshot(
        action="apollo.lists.create",
        data={**empty_data, "summary": f"Created list {list_name}"},
        success=bool(create_empty.success),
    )
    empty_result = _finalize_mini_run(
        label=f"List populate honesty empty shell {suffix}",
        step_rows=[
            {
                "name": "Create Apollo list",
                "type": "invoke_tool",
                "status": "completed" if create_empty.success else "failed",
                "output_snapshot": empty_snap,
            },
            {
                "name": "Populate Apollo list",
                "type": "agent",
                "status": "completed",
                "metadata": {
                    "task": (
                        "Ensure Apollo list membership for qualified contacts. "
                        f'If empty, call apollo.lists.add with entity_ids + label_names=["{list_name}"].'
                    ),
                },
                "output_snapshot": {"summary": "Agent skipped membership add"},
            },
        ],
        parameters={
            "workflow_slug": "msp-prospecting-list-builder",
            "workflow_name": "MSP Prospecting & List Builder",
            "expects_list_population": True,
            "source": "list_populate_honesty_live",
        },
    )
    evidence["cases"]["empty_shell"] = {
        "invoke_success": bool(create_empty.success),
        "list_name": list_name,
        "list_id": empty_list_id,
        "apollo_url": empty_url,
        "error": create_empty.error_message,
        **empty_result,
        "pass": (
            bool(create_empty.success)
            and str(empty_result.get("coerced_status") or empty_result.get("status") or "").lower()
            == "partial_success"
            and bool(empty_result.get("run_persisted_ok"))
            and "list created, 0 contacts added" in str(empty_result.get("honesty_reason") or "")
        ),
    }

    # --- (b) create + populate ---
    list_name_ok = f"Honesty-Populated-{suffix}"
    create_ok = _invoke(
        "apollo.lists.create",
        {"name": list_name_ok, "modality": "contacts"},
    )
    ok_data = create_ok.data if isinstance(create_ok.data, dict) else {}
    entity_ids: list[str] = []
    search_meta: dict = {}
    for action, params in (
        ("apollo.contacts.search", {"q_keywords": "manager", "per_page": 5}),
        ("apollo.people.search", {"q_keywords": "manager", "per_page": 5}),
    ):
        search = _invoke(action, params)
        search_data = search.data if isinstance(search.data, dict) else {}
        search_meta[action] = {
            "success": bool(search.success),
            "error": search.error_message,
            "keys": list(search_data.keys())[:12],
        }
        contacts = (
            search_data.get("contacts")
            or search_data.get("people")
            or search_data.get("data")
            or []
        )
        if not isinstance(contacts, list):
            contacts = []
        for c in contacts:
            if not isinstance(c, dict):
                continue
            cid = str(c.get("id") or c.get("contact_id") or c.get("person_id") or "").strip()
            if cid and cid not in entity_ids:
                entity_ids.append(cid)
            if len(entity_ids) >= 2:
                break
        if entity_ids:
            break
    # Last resort: create a disposable Apollo contact then add it.
    if not entity_ids and create_ok.success:
        created_contact = _invoke(
            "apollo.contacts.create",
            {
                "first_name": "Honesty",
                "last_name": f"Probe{suffix}",
                "email": f"honesty.probe.{suffix}@example.com",
            },
        )
        cdata = created_contact.data if isinstance(created_contact.data, dict) else {}
        cid = str(
            cdata.get("id")
            or cdata.get("contact_id")
            or (cdata.get("contact") or {}).get("id")
            or ""
        ).strip()
        search_meta["apollo.contacts.create"] = {
            "success": bool(created_contact.success),
            "error": created_contact.error_message,
            "contact_id": cid or None,
        }
        if cid:
            entity_ids.append(cid)
    add_result = None
    add_snap = None
    if entity_ids and create_ok.success:
        add_result = _invoke(
            "apollo.lists.add",
            {
                "entity_ids": entity_ids,
                "label_names": [list_name_ok],
                "modality": "contacts",
            },
        )
        add_data = add_result.data if isinstance(add_result.data, dict) else {}
        add_snap = enrich_invoke_tool_snapshot(
            action="apollo.lists.add",
            data={
                **add_data,
                "summary": f"Added {len(entity_ids)} contacts",
                "entity_ids": entity_ids,
                "added_count": len(entity_ids),
                "contact_count": len(entity_ids),
            },
            success=bool(add_result.success),
        )
    create_ok_snap = enrich_invoke_tool_snapshot(
        action="apollo.lists.create",
        data={**ok_data, "summary": f"Created list {list_name_ok}"},
        success=bool(create_ok.success),
    )
    pop_steps = [
        {
            "name": "Create Apollo list",
            "type": "invoke_tool",
            "status": "completed" if create_ok.success else "failed",
            "output_snapshot": create_ok_snap,
        },
    ]
    if add_snap is not None:
        pop_steps.append(
            {
                "name": "Add contacts to list",
                "type": "invoke_tool",
                "status": "completed" if add_result and add_result.success else "failed",
                "output_snapshot": add_snap,
            }
        )
    else:
        pop_steps.append(
            {
                "name": "Populate Apollo list",
                "type": "agent",
                "status": "failed",
                "metadata": {"task": "call apollo.lists.add with entity_ids"},
                "output_snapshot": {"summary": "No contact ids from search — cannot prove populate"},
            }
        )
    populated_result = _finalize_mini_run(
        label=f"List populate honesty populated {suffix}",
        step_rows=pop_steps,
        parameters={
            "workflow_slug": "msp-prospecting-list-builder",
            "workflow_name": "MSP Prospecting & List Builder",
            "expects_list_population": True,
            "source": "list_populate_honesty_live",
        },
    )
    evidence["cases"]["populated"] = {
        "invoke_create_success": bool(create_ok.success),
        "list_name": list_name_ok,
        "entity_ids": entity_ids,
        "search_meta": search_meta,
        "add_success": bool(add_result.success) if add_result else False,
        "add_error": (add_result.error_message if add_result else "no_entity_ids"),
        "added_count": (add_result.data or {}).get("added_count") if add_result and isinstance(add_result.data, dict) else None,
        **populated_result,
        "pass": (
            bool(create_ok.success)
            and bool(add_result and add_result.success)
            and len(entity_ids) > 0
            and str(populated_result.get("coerced_status") or populated_result.get("status") or "").lower()
            == "completed"
            and bool(populated_result.get("run_persisted_ok"))
            and not populated_result.get("honesty_reason")
        ),
    }

    # --- (c) HubSpot link check ---
    hs_name = f"Honesty-HS-{suffix}"
    hs = _invoke("hubspot.lists.create", {"name": hs_name})
    hs_data = hs.data if isinstance(hs.data, dict) else {}
    hs_url = str(hs_data.get("result_url") or hs_data.get("external_url") or "")
    hs_list_id = str(
        hs_data.get("list_id")
        or hs_data.get("listId")
        or (hs_data.get("list") or {}).get("listId")
        or hs_data.get("id")
        or ""
    )
    hs_http_ok = False
    hs_status = None
    if hs_url.startswith("https://") and "hubspot.com" in hs_url.lower():
        try:
            # Vendor pages often require auth; accept 200/302/401/403 as "real URL reachable".
            resp = httpx.get(hs_url, timeout=30.0, follow_redirects=False)
            hs_status = resp.status_code
            hs_http_ok = resp.status_code in {200, 301, 302, 303, 307, 308, 401, 403}
        except Exception as exc:  # noqa: BLE001
            hs_status = f"error:{exc}"
    evidence["cases"]["hubspot_link"] = {
        "invoke_success": bool(hs.success),
        "list_name": hs_name,
        "list_id": hs_list_id,
        "external_url": hs_url,
        "http_status": hs_status,
        "error": hs.error_message,
        "pass": (
            bool(hs.success)
            and hs_url.startswith("https://")
            and "hubspot.com" in hs_url.lower()
            and bool(hs_list_id)
            and hs_http_ok
        ),
    }

    evidence["all_pass"] = all(
        bool(evidence["cases"][k].get("pass")) for k in ("empty_shell", "populated", "hubspot_link")
    )
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(evidence, indent=2), encoding="utf-8")
    print(json.dumps(evidence, indent=2))
    return 0 if evidence["all_pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
