#!/usr/bin/env python3
"""Encrypt plaintext Salesforce/Segment/PagerDuty trigger secrets in connectors.config.

Dry run by default; pass --apply to write. Prints counts only, never a secret.
Needs SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY and CONNECTOR_SECRETS_ENCRYPTION_KEY.
"""
from __future__ import annotations

import argparse
import os
import sys
from types import SimpleNamespace

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.services.connector_webhook_secret_store import seal_plaintext_webhook_secrets
from supabase import create_client


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="write the encrypted values")
    args = parser.parse_args()
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    enc = os.environ.get("CONNECTOR_SECRETS_ENCRYPTION_KEY")
    if not url or not key or not enc:
        print("SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY and CONNECTOR_SECRETS_ENCRYPTION_KEY are required", file=sys.stderr)
        return 1
    settings = SimpleNamespace(connector_secrets_encryption_key=enc)
    out = seal_plaintext_webhook_secrets(create_client(url, key), settings, dry_run=not args.apply)
    print(out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
