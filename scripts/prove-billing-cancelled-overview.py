"""Prove billing overview returns Canceled (not Trial/Active) for cancelled orgs.

Creates a disposable org_billing row with cancelled + leftover command plan_code
(pre-fix webhook residue shape), invokes billing_overview against live DB,
then deletes the probe rows.
"""
from __future__ import annotations

import asyncio
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

from supabase import create_client  # noqa: E402

from app.config import get_settings  # noqa: E402
from app.routers import billing as billing_router  # noqa: E402


async def main() -> int:
    settings = get_settings()
    client = create_client(settings.supabase_url, settings.supabase_service_role_key)
    org_id = str(uuid.uuid4())
    name = f"billing-cancel-probe-{org_id[:8]}"
    now = datetime.now(timezone.utc).isoformat()
    print(f"creating disposable org {org_id} ({name})")
    client.table("organizations").insert({"id": org_id, "name": name}).execute()
    # Seed residual Command plan after cancel — the incomplete webhook shape.
    client.table("org_billing").insert(
        {
            "org_id": org_id,
            "plan_code": "command",
            "billing_status": "cancelled",
            "stripe_subscription_id": None,
            "stripe_price_id": "price_1TbcniGkcGZTLqrPGRwaFxgZ",
            "cancel_at_period_end": False,
            "updated_at": now,
        }
    ).execute()
    # Avoid unrelated supabase-py APIResponse.error attribute checks on usage paths.
    billing_router._usage_from_records = (  # type: ignore[attr-defined]
        lambda *_a, **_k: {
            "tier": "command",
            "period_start": now,
            "totals": {},
            "plan": {"code": "command"},
        }
    )
    billing_router._weekly_workflow_totals = lambda *_a, **_k: [0, 0, 0, 0]  # type: ignore[attr-defined]
    billing_router._fetch_invoices_and_payment_methods = lambda **_k: ([], [])  # type: ignore[attr-defined]

    try:
        result = await billing_router.billing_overview(
            _user={"id": "prove-cancelled"},
            org_id=org_id,
            settings=settings,
        )
        sub = result.get("subscription") or {}
        status = str(sub.get("status") or "")
        billing_status = str(result.get("billing_status") or "")
        tier = str(sub.get("tier") or "")
        ok = (
            status == "canceled"
            and billing_status == "cancelled"
            and status not in {"active", "trialing"}
        )
        print(
            {
                "org_id": org_id,
                "subscription.status": status,
                "subscription.tier": tier,
                "billing_status": billing_status,
                "pass": ok,
            }
        )
        return 0 if ok else 1
    finally:
        client.table("subscriptions").delete().eq("org_id", org_id).execute()
        client.table("org_billing").delete().eq("org_id", org_id).execute()
        client.table("organizations").delete().eq("id", org_id).execute()
        print(f"cleaned {org_id}")


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
