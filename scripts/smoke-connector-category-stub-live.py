#!/usr/bin/env python3
"""Live smoke: install connector-category stubs as needs_connection on PROD Supabase.

Soft-deletes prior probe stubs for the smoke org, installs two category templates,
asserts status/auth_mode, then soft-deletes newly created rows.

Writes docs/delivery/phase1-needs-connection-stub-live.json
"""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

from dotenv import dotenv_values

REPO = Path(__file__).resolve().parent.parent
BACKEND = REPO / "backend"
sys.path.insert(0, str(BACKEND))

ORG = "cbbf993b-b22f-41ce-964b-1fc25e0dd9ea"
ACTOR = "f7e32f06-49df-4e73-8962-f41c21850762"
PROBE_TYPES = [
    "fred",
    "zoominfo",
    "linkedin_sales_navigator",
    "sec_edgar",
    "world_bank",
    "oecd",
    "opencorporates",
]
TEMPLATES = [
    "executive-intelligence-sources",
    "byo-premium-prospecting",
]
OUT = REPO / "docs" / "delivery" / "phase1-needs-connection-stub-live.json"
FORBIDDEN_STATUSES = frozenset({"active", "connected", "healthy"})
EXPECTED_AUTH = {
    "fred": "gravitre_managed",
    "sec_edgar": "gravitre_managed",
    "world_bank": "gravitre_managed",
    "oecd": "gravitre_managed",
    "opencorporates": "gravitre_managed",
    "zoominfo": "byo_required",
    "linkedin_sales_navigator": "byo_required",
}


def _load_env() -> None:
    merged: dict[str, str] = {}
    for p in (BACKEND / ".env", BACKEND / ".env.operator.local", REPO / ".env"):
        if p.is_file():
            try:
                merged.update({k: v for k, v in dotenv_values(p).items() if v})
            except UnicodeDecodeError:
                pass
    for k, v in merged.items():
        os.environ.setdefault(k, v)


def _soft_delete_probe_stubs(client, org_id: str, types: list[str]) -> list[dict]:
    """Soft-delete non-deleted connectors of probe types for org (prior smoke rows)."""
    now = datetime.now(timezone.utc).isoformat()
    cleaned: list[dict] = []
    for ctype in types:
        rows = (
            client.table("connectors")
            .select("id, type, status, deleted_at")
            .eq("org_id", org_id)
            .eq("type", ctype)
            .is_("deleted_at", "null")
            .execute()
            .data
            or []
        )
        for row in rows:
            client.table("connectors").update({"deleted_at": now}).eq("id", row["id"]).eq(
                "org_id", org_id
            ).execute()
            cleaned.append(
                {
                    "id": row["id"],
                    "type": row.get("type"),
                    "priorStatus": row.get("status"),
                    "deleted_at": now,
                }
            )
    return cleaned


def _query_created(client, org_id: str, ids: list[str]) -> list[dict]:
    if not ids:
        return []
    rows = (
        client.table("connectors")
        .select("id, type, status, config, deleted_at")
        .eq("org_id", org_id)
        .in_("id", ids)
        .execute()
        .data
        or []
    )
    return [dict(r) for r in rows]


def main() -> int:
    _load_env()
    from app.config import get_settings
    from app.marketplace.connector_category_templates import install_connector_category_template
    from app.workflows.repository import get_supabase_client

    settings = get_settings()
    client = get_supabase_client(settings)

    ran_at = datetime.now(timezone.utc).isoformat()
    out: dict = {
        "pass": False,
        "ran_at": ran_at,
        "org_id": ORG,
        "actor_id": ACTOR,
        "prod_note": (
            "Live against PROD Supabase (service role) smoke org "
            f"{ORG}; stubs only — no credentials / no live connections."
        ),
        "pre_cleanup": [],
        "skipped": [],
        "created": [],
        "statuses": {},
        "auth_modes": {},
        "db_rows": [],
        "cleanup": {"ok": False, "soft_deleted": [], "error": None},
        "assertions": [],
        "errors": [],
    }

    try:
        out["pre_cleanup"] = _soft_delete_probe_stubs(client, ORG, PROBE_TYPES)
    except Exception as exc:  # noqa: BLE001
        out["errors"].append(f"pre_cleanup_failed: {exc}")
        out["assertions"].append({"name": "pre_cleanup", "ok": False, "detail": str(exc)})
        OUT.write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(out, indent=2))
        return 1

    created_ids: list[str] = []
    try:
        for template_id in TEMPLATES:
            result = install_connector_category_template(
                client,
                ORG,
                template_id,
                created_by=ACTOR,
                environment_name="production",
            )
            for row in result.get("created") or []:
                cid = row.get("id")
                if cid:
                    created_ids.append(str(cid))
                out["created"].append({**row, "templateId": template_id})
            for skip in result.get("skipped") or []:
                out["skipped"].append({**skip, "templateId": template_id})
    except Exception as exc:  # noqa: BLE001
        out["errors"].append(f"install_failed: {exc}")
        out["assertions"].append({"name": "install", "ok": False, "detail": str(exc)})
        # Best-effort cleanup of anything created before failure
        try:
            if created_ids:
                now = datetime.now(timezone.utc).isoformat()
                for cid in created_ids:
                    client.table("connectors").update({"deleted_at": now}).eq("id", cid).eq(
                        "org_id", ORG
                    ).execute()
                out["cleanup"] = {
                    "ok": True,
                    "soft_deleted": created_ids,
                    "error": None,
                    "note": "partial cleanup after install failure",
                }
        except Exception as cleanup_exc:  # noqa: BLE001
            out["cleanup"] = {
                "ok": False,
                "soft_deleted": [],
                "error": str(cleanup_exc),
            }
        OUT.write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(out, indent=2))
        return 1

    # Prefer create path: if everything skipped, document and fail (not a live create proof)
    if not created_ids and out["skipped"]:
        out["assertions"].append(
            {
                "name": "created_rows",
                "ok": False,
                "detail": "all types skipped — no new stubs to verify; pre_cleanup may have failed",
            }
        )
        out["errors"].append("no_created_rows")
        OUT.write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(out, indent=2))
        return 1

    # Assert install return payload
    created_ok = True
    for row in out["created"]:
        status = str(row.get("status") or "")
        ctype = str(row.get("connectorType") or "")
        out["statuses"][str(row.get("id"))] = status
        out["auth_modes"][str(row.get("id"))] = row.get("authMode")
        if status != "needs_connection":
            created_ok = False
            out["errors"].append(f"created_status_not_needs_connection:{ctype}:{status}")
        if status in FORBIDDEN_STATUSES:
            created_ok = False
            out["errors"].append(f"forbidden_live_status:{ctype}:{status}")
        expected = EXPECTED_AUTH.get(ctype)
        if expected and row.get("authMode") != expected:
            created_ok = False
            out["errors"].append(
                f"auth_mode_mismatch:{ctype}:got={row.get('authMode')}:want={expected}"
            )

    out["assertions"].append(
        {
            "name": "created_status_needs_connection",
            "ok": created_ok and bool(out["created"]),
            "createdCount": len(out["created"]),
        }
    )
    out["assertions"].append(
        {
            "name": "no_live_statuses_on_created",
            "ok": all(str(s) not in FORBIDDEN_STATUSES for s in out["statuses"].values()),
        }
    )

    # DB confirm
    db_ok = True
    try:
        db_rows = _query_created(client, ORG, created_ids)
        out["db_rows"] = [
            {
                "id": r.get("id"),
                "type": r.get("type"),
                "status": r.get("status"),
                "auth_mode": (r.get("config") or {}).get("auth_mode"),
                "deleted_at": r.get("deleted_at"),
            }
            for r in db_rows
        ]
        by_id = {str(r["id"]): r for r in db_rows}
        for cid in created_ids:
            row = by_id.get(cid)
            if not row:
                db_ok = False
                out["errors"].append(f"db_missing:{cid}")
                continue
            if str(row.get("status")) != "needs_connection":
                db_ok = False
                out["errors"].append(f"db_status:{cid}:{row.get('status')}")
            if str(row.get("status")) in FORBIDDEN_STATUSES:
                db_ok = False
                out["errors"].append(f"db_forbidden_status:{cid}:{row.get('status')}")
            ctype = str(row.get("type") or "")
            auth = (row.get("config") or {}).get("auth_mode")
            expected = EXPECTED_AUTH.get(ctype)
            if expected and auth != expected:
                db_ok = False
                out["errors"].append(f"db_auth_mode:{cid}:{ctype}:{auth}")
            # refresh maps from DB
            out["statuses"][cid] = row.get("status")
            out["auth_modes"][cid] = auth
    except Exception as exc:  # noqa: BLE001
        db_ok = False
        out["errors"].append(f"db_query_failed: {exc}")

    out["assertions"].append({"name": "db_status_and_auth_mode", "ok": db_ok})

    # Cleanup newly created stubs
    cleanup_ok = False
    try:
        now = datetime.now(timezone.utc).isoformat()
        soft_deleted: list[str] = []
        for cid in created_ids:
            client.table("connectors").update({"deleted_at": now}).eq("id", cid).eq(
                "org_id", ORG
            ).execute()
            soft_deleted.append(cid)
        # Confirm soft-deleted
        confirm = _query_created(client, ORG, created_ids)
        still_live = [r["id"] for r in confirm if not r.get("deleted_at")]
        cleanup_ok = len(still_live) == 0
        out["cleanup"] = {
            "ok": cleanup_ok,
            "soft_deleted": soft_deleted,
            "error": None if cleanup_ok else f"still_not_deleted:{still_live}",
            "deleted_at": now,
        }
    except Exception as exc:  # noqa: BLE001
        out["cleanup"] = {"ok": False, "soft_deleted": [], "error": str(exc)}

    out["assertions"].append({"name": "cleanup_soft_delete", "ok": cleanup_ok})

    all_ok = (
        created_ok
        and db_ok
        and cleanup_ok
        and bool(out["created"])
        and not out["errors"]
        and all(a.get("ok") for a in out["assertions"])
    )
    # Cleanup failure alone should not flip verification PASS if create assertions passed —
    # but prefer cleanup; treat cleanup fail as overall fail to avoid clutter.
    out["pass"] = all_ok
    out["finished_at"] = datetime.now(timezone.utc).isoformat()

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(out, indent=2))
    return 0 if out["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
