"""Hourly cron entrypoint: report metered AI usage for all active orgs to Stripe.

Intended to be run by a Railway Cron service (Cron Schedule `0 * * * *`, start
command `python scripts/sync_usage_cron.py`, root dir /backend). Runs the same
logic as POST /api/internal/billing/sync-usage but directly (no HTTP, no shared
secret) using the service's own env (Supabase + live Stripe key).

Idempotent: only usage_tracking rows with stripe_reported_at IS NULL are sent,
then marked, so repeated runs never double-report.
"""
from __future__ import annotations

import json
import sys

from app.billing.service import get_current_period
from app.billing.stripe_metering import report_usage_for_active_orgs
from app.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)


def main() -> int:
    settings = get_settings()
    period_start, period_end = get_current_period()
    summary = report_usage_for_active_orgs(period_start, period_end, settings)
    out = {
        "period_start": period_start.isoformat(),
        "period_end": period_end.isoformat(),
        "orgs": summary.get("orgs"),
        "reported_rows": summary.get("reported_rows"),
        "error": summary.get("error"),
    }
    logger.info("usage_sync_cron %s", json.dumps(out, default=str))
    print(json.dumps(out, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())
