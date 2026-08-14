"""Print live Checkout URLs + finish disposable Setup session for orphan org."""
from __future__ import annotations

import json
import os
import sys
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

from app.billing.stripe import init_stripe
from app.config import get_settings

ORG = "47060f8d-702d-4939-ae10-35a24b1aca2a"
CUST = "cus_V2MXWRiXBrLILB"
STATE = ROOT / "docs" / "delivery" / "_phase_c_disposable_autotopup_state.json"


def main() -> int:
    settings = get_settings()
    init_stripe(settings)
    import stripe

    sessions = stripe.checkout.Session.list(customer="cus_UnCa4Z72rPXXu2", limit=5)
    open_sessions = []
    for sess in sessions.data:
        if sess.status == "open":
            open_sessions.append(
                {
                    "id": sess.id,
                    "amount_total": sess.amount_total,
                    "payment_status": sess.payment_status,
                    "url": sess.url,
                }
            )

    setup = stripe.checkout.Session.create(
        mode="setup",
        customer=CUST,
        currency="usd",
        success_url=f"https://gravitre.app/settings/billing?autotopup_setup=success&org={ORG}",
        cancel_url=f"https://gravitre.app/settings/billing?autotopup_setup=cancelled&org={ORG}",
        metadata={
            "org_id": ORG,
            "checkout_kind": "voice_autotopup_setup",
            "purpose": "phase_c_disposable",
        },
    )
    state = {
        "org_id": ORG,
        "org_name": "voice-autotopup-disposable-47060f8d",
        "stripe_customer_id": CUST,
        "setup_session_id": setup.id,
        "setup_url": setup.url,
        "auto_topup_minutes": 60,
        "auto_topup_threshold_minutes": 15,
        "max_charge_cents": 720,
        "expected_charge_usd": 7.2,
    }
    STATE.parent.mkdir(parents=True, exist_ok=True)
    STATE.write_text(json.dumps(state, indent=2), encoding="utf-8")
    print(
        json.dumps(
            {
                "manual_topup_open_sessions": open_sessions,
                "disposable_setup": state,
                "instructions": [
                    "1) Open the newest manual_topup url in your normal browser (not Cursor browser) and pay $7.20",
                    "2) Tell the agent when paid — watcher confirms prepaid + PI",
                    "3) Open disposable setup_url and attach a card (no charge yet)",
                    "4) Tell the agent — fire auto-top-up (~$7.20 off-session)",
                ],
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
