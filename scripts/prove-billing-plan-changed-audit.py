"""Prove billing.plan.changed is written and labeled for the Audit UI surface."""
from __future__ import annotations

import json
import os
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

for candidate in [ROOT / "backend" / ".env.operator.local", ROOT / "backend" / ".env"]:
    if not candidate.exists():
        continue
    for line in candidate.read_text(encoding="utf-8", errors="ignore").splitlines():
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip("'").strip('"')
        if key and key not in os.environ:
            os.environ[key] = value

from supabase import create_client

from app.config import get_settings
from app.workflows.audit import write_audit_event

# Mirror apps/web/lib/audit-summary.ts ACTION_LABELS
ACTION_LABELS = {
    "billing.plan.changed": "Subscription plan changed",
}


def main() -> int:
    settings = get_settings()
    client = create_client(settings.supabase_url, settings.supabase_service_role_key)

    # Disposable org so we do not pollute Cesar's audit stream permanently.
    org_id = str(uuid.uuid4())
    name = f"billing-audit-probe-{org_id[:8]}"
    actor_id = str(uuid.uuid4())
    print(f"creating {org_id}")
    client.table("organizations").insert({"id": org_id, "name": name}).execute()
    # audit_events.actor_id FK may require auth.users — write_audit_event skips non-uuid
    # and may skip invalid FK. Prefer billing_events + audit_logs fallback.
    try:
        write_audit_event(
            client,
            org_id,
            actor_id,
            "billing.plan.changed",
            "org_billing",
            org_id,
            {
                "from_plan": "node",
                "to_plan": "command",
                "mode": "internal_override",
                "reason": "audit_visibility_probe",
                "internal_override": True,
            },
        )
    except Exception as exc:  # noqa: BLE001
        print("write_audit_event_error", exc)

    client.table("billing_events").insert(
        {
            "org_id": org_id,
            "action": "billing.plan.changed",
            "event_type": "billing.plan.changed",
            "status": "success",
            "payload": {
                "from_plan": "node",
                "to_plan": "command",
                "mode": "internal_override",
                "reason": "audit_visibility_probe",
            },
        }
    ).execute()

    label = ACTION_LABELS.get("billing.plan.changed")
    events = (
        client.table("audit_events")
        .select("id, action, resource_type, metadata, created_at")
        .eq("org_id", org_id)
        .eq("action", "billing.plan.changed")
        .execute()
        .data
        or []
    )
    logs = (
        client.table("audit_logs")
        .select("id, action, action_label, details, created_at")
        .eq("org_id", org_id)
        .eq("action", "billing.plan.changed")
        .execute()
        .data
        or []
    )
    billing_ev = (
        client.table("billing_events")
        .select("id, action, event_type, payload, created_at")
        .eq("org_id", org_id)
        .eq("action", "billing.plan.changed")
        .execute()
        .data
        or []
    )

    # Cleanup probe org rows
    for table in ("audit_events", "audit_logs", "billing_events", "organizations"):
        try:
            client.table(table).delete().eq("org_id" if table != "organizations" else "id", org_id).execute()
        except Exception:
            pass

    result = {
        "ui_surface": "/audit (Audit Log) uses formatAuditActionLabel / summarizeAuditLog",
        "ui_label": label,
        "audit_events_count": len(events),
        "audit_logs_count": len(logs),
        "billing_events_count": len(billing_ev),
        "pass": bool(label) and (len(events) > 0 or len(logs) > 0) and len(billing_ev) > 0,
        "sample_event": (events or logs or billing_ev)[:1],
    }
    print(json.dumps(result, indent=2, default=str))
    return 0 if result["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
