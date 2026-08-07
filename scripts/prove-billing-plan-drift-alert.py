"""Disposable-org proof that billing_plan_drift fires on stale stripe_price_id."""
from __future__ import annotations

import os
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

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
from app.services.golden_signals_service import _billing_plan_price_drift  # noqa: E402

# Live Stripe price ids confirmed in Phase 0 for this account.
NODE_PRICE = "price_1TbcngGkcGZTLqrPy3N5B60J"
CMD_PRICE = "price_1TbcniGkcGZTLqrPGRwaFxgZ"


def main() -> int:
    settings = get_settings()
    client = create_client(settings.supabase_url, settings.supabase_service_role_key)
    probe_settings = SimpleNamespace(
        stripe_price_id_node_monthly=NODE_PRICE,
        stripe_price_id_node_annual="",
        stripe_price_id_control_monthly="",
        stripe_price_id_control_annual="",
        stripe_price_id_command_monthly=CMD_PRICE,
        stripe_price_id_command_annual="",
        stripe_price_id_starter="",
        stripe_price_id_growth="",
        stripe_price_id_scale="",
    )

    org_id = str(uuid.uuid4())
    name = f"billing-drift-probe-{org_id[:8]}"
    now = datetime.now(timezone.utc).isoformat()
    print(f"creating disposable org {org_id} ({name})")
    client.table("organizations").insert({"id": org_id, "name": name}).execute()
    client.table("org_billing").insert(
        {
            "org_id": org_id,
            "plan_code": "command",
            "billing_status": "active",
            "stripe_subscription_id": f"sub_probe_{org_id[:8]}",
            "stripe_price_id": NODE_PRICE,  # intentional incomplete upgrade record
            "updated_at": now,
        }
    ).execute()

    try:
        drift = _billing_plan_price_drift(client, probe_settings)
        hit = [row for row in drift.get("drifts", []) if row.get("org_id") == org_id]
        alert = f"billing_plan_price_drift>{drift.get('drift_count', 0)}"
        print(
            {
                "sample_size": drift.get("sample_size"),
                "drift_count": drift.get("drift_count"),
                "probe_hit": hit,
                "alert": alert if hit else None,
                "pass": bool(hit),
            }
        )
        return 0 if hit else 1
    finally:
        client.table("org_billing").delete().eq("org_id", org_id).execute()
        client.table("organizations").delete().eq("id", org_id).execute()
        print(f"cleaned {org_id}")


if __name__ == "__main__":
    raise SystemExit(main())
