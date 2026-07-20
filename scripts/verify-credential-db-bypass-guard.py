#!/usr/bin/env python3
"""Prod proof: raw service-role inserts by smoke SA into Cesar org are refused at DB.

Re-runs the Round 2 bypass (conversations.insert with service role, no app guard)
plus the v2 tables (audit_events, notifications, workflow_runs).
"""
from __future__ import annotations

import json
import os
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "backend"))
sys.path.insert(0, str(REPO / "scripts"))

from dotenv import dotenv_values  # noqa: E402

from app.services.conversation_write_guard import (  # noqa: E402
    DEFAULT_ISOLATED_CONVERSATION_TEST_ORG_ID,
    DEFAULT_ISOLATED_CONVERSATION_TEST_USER_ID,
    FORBIDDEN_OPERATOR_ORG_ID,
)

OUT = REPO / "docs" / "delivery" / "module-0-db-guard-live.json"


def _load_env() -> dict[str, str]:
    merged: dict[str, str] = {}
    for path in (REPO / "backend" / ".env", REPO / "backend" / ".env.operator.local", REPO / ".env"):
        if not path.is_file():
            continue
        for enc in ("utf-8", "utf-8-sig", "cp1252", "latin-1"):
            try:
                merged.update({k: v for k, v in dotenv_values(path, encoding=enc).items() if v})
                break
            except UnicodeDecodeError:
                continue
    merged.update({k: v for k, v in os.environ.items() if v})
    return merged


def _is_db_refuse(exc: BaseException) -> bool:
    text = str(exc).lower()
    return (
        "refusing" in text
        and "isolated" in text
        and ("test/service credential" in text or "test credential" in text)
    ) or ("check_violation" in text and "isolated" in text)


def _probe_insert(client, table: str, row: dict) -> dict:
    try:
        client.table(table).insert(row).execute()
        leaked = client.table(table).select("id").eq("id", row["id"]).limit(1).execute()
        if leaked.data:
            try:
                client.table(table).delete().eq("id", row["id"]).execute()
            except Exception:  # noqa: BLE001
                pass
        return {
            "table": table,
            "status": "FAIL_BYPASS",
            "refused": False,
            "leaked_row": bool(leaked.data),
            "error": None,
        }
    except Exception as exc:  # noqa: BLE001
        leaked = client.table(table).select("id").eq("id", row["id"]).limit(1).execute()
        refused = _is_db_refuse(exc)
        return {
            "table": table,
            "status": "PASS" if refused and not leaked.data else "FAIL",
            "refused": refused,
            "leaked_row": bool(leaked.data),
            "error": str(exc)[:500],
        }


def _probe_isolated_ok(client, table: str, row: dict) -> dict:
    try:
        client.table(table).insert(row).execute()
        got = client.table(table).select("id").eq("id", row["id"]).limit(1).execute()
        ok = bool(got.data)
        if got.data:
            client.table(table).delete().eq("id", row["id"]).execute()
        return {
            "table": table,
            "status": "PASS" if ok else "FAIL",
            "allowed": ok,
            "error": None,
        }
    except Exception as exc:  # noqa: BLE001
        return {
            "table": table,
            "status": "FAIL",
            "allowed": False,
            "error": str(exc)[:500],
        }


def main() -> int:
    env = _load_env()
    for k, v in env.items():
        os.environ.setdefault(k, v)

    from app.config import get_settings
    from app.workflows.repository import get_supabase_client

    settings = get_settings()
    client = get_supabase_client(settings)
    sa = DEFAULT_ISOLATED_CONVERSATION_TEST_USER_ID
    bad_org = FORBIDDEN_OPERATOR_ORG_ID
    good_org = DEFAULT_ISOLATED_CONVERSATION_TEST_ORG_ID
    now = datetime.now(timezone.utc).isoformat()

    results: list[dict] = []

    # --- Round 2: raw conversations.insert into Cesar org ---
    conv_bad = {
        "id": str(uuid.uuid4()),
        "org_id": bad_org,
        "user_id": sa,
        "title": f"db-guard-bypass-probe {uuid.uuid4().hex[:8]}",
        "preview": None,
        "message_count": 0,
        "created_at": now,
        "updated_at": now,
    }
    results.append(_probe_insert(client, "conversations", conv_bad))

    # --- v2 tables: same bypass pattern ---
    audit_bad = {
        "id": str(uuid.uuid4()),
        "org_id": bad_org,
        "action": "db.guard.probe",
        "actor_id": sa,
        "resource_type": "probe",
        "resource_id": str(uuid.uuid4()),
        "metadata": {"probe": "module_0_db_guard"},
        "created_at": now,
    }
    results.append(_probe_insert(client, "audit_events", audit_bad))

    notif_bad = {
        "id": str(uuid.uuid4()),
        "org_id": bad_org,
        "user_id": sa,
        "type": "system",
        "title": "db-guard-bypass-probe",
        "body": "must refuse",
        "is_read": False,
        "is_archived": False,
        "created_at": now,
    }
    results.append(_probe_insert(client, "notifications", notif_bad))

    run_bad = {
        "id": str(uuid.uuid4()),
        "org_id": bad_org,
        "run_type": "dry_run",
        "status": "running",
        "triggered_by": sa,
        "definition_snapshot": {"nodes": []},
        "parameters": {},
        "run_hash": f"db-guard-{uuid.uuid4().hex[:12]}",
        "created_at": now,
    }
    results.append(_probe_insert(client, "workflow_runs", run_bad))

    # --- Legitimate: smoke SA into isolated org must still work ---
    conv_ok = {
        "id": str(uuid.uuid4()),
        "org_id": good_org,
        "user_id": sa,
        "title": f"db-guard-isolated-ok {uuid.uuid4().hex[:8]}",
        "preview": None,
        "message_count": 0,
        "created_at": now,
        "updated_at": now,
    }
    isolated = _probe_isolated_ok(client, "conversations", conv_ok)
    results.append({"probe": "isolated_org_allow", **isolated})

    all_pass = all(r.get("status") == "PASS" for r in results)
    payload = {
        "probe": "module_0_db_credential_bypass_guard",
        "verified_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "sa": sa,
        "forbidden_org": bad_org,
        "isolated_org": good_org,
        "results": results,
        "status": "PASS" if all_pass else "FAIL",
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(payload, indent=2))
    return 0 if all_pass else 2


if __name__ == "__main__":
    raise SystemExit(main())
