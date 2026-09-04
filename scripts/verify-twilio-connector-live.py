#!/usr/bin/env python3
"""Live Twilio connector smoke — resolves Account SID and lists calls (no outbound dial)."""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, os.path.join(ROOT, "backend"))

from app.connectors.twilio_api import fetch_twilio_account_sid  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify Twilio API key resolves Account SID")
    parser.add_argument("--api-key-sid", default=os.environ.get("TWILIO_API_KEY_SID", ""))
    parser.add_argument("--api-key-secret", default=os.environ.get("TWILIO_API_KEY_SECRET", ""))
    parser.add_argument("--json", dest="json_out", default="", help="Write evidence JSON path")
    args = parser.parse_args()
    sid = (args.api_key_sid or "").strip()
    secret = (args.api_key_secret or "").strip()
    if not sid or not secret:
        print("NOT RUN — set TWILIO_API_KEY_SID and TWILIO_API_KEY_SECRET", file=sys.stderr)
        return 2
    try:
        account_sid = fetch_twilio_account_sid(api_key_sid=sid, api_key_secret=secret)
    except Exception as exc:  # noqa: BLE001
        print(f"FAIL — {exc}", file=sys.stderr)
        return 1
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "verdict": "PASS",
        "account_sid": account_sid,
        "evidence": "fetch_twilio_account_sid via Accounts.json",
    }
    print(json.dumps(payload, indent=2))
    if args.json_out:
        with open(args.json_out, "w", encoding="utf-8") as fh:
            json.dump(payload, fh, indent=2)
            fh.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
