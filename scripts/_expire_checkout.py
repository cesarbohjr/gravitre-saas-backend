"""Expire a Checkout session (avoid leaving unpaid regression sessions)."""
from __future__ import annotations

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

SID = sys.argv[1] if len(sys.argv) > 1 else ""
if not SID:
    raise SystemExit("usage: _expire_checkout.py cs_live_...")
init_stripe(get_settings())
import stripe

r = stripe.checkout.Session.expire(SID)
print(r.id, r.status, r.payment_status)
