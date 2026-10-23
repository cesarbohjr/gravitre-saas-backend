#!/usr/bin/env python3
"""Read-only preflight before billing tests can create disposable users.

This intentionally refuses every Supabase project except the dedicated
gravitre-acceptance project. No live customer data or credentials are logged.
"""
from __future__ import annotations

import json
import os
import sys
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

ACCEPTANCE_URL = "https://aadnwmjzrmbvadszroqt.supabase.co"
REQUIRED_TABLES = (
    "organizations",
    "organization_members",
    "org_billing",
    "org_commercial_profiles",
    "platform_admins",
)


def check_schema(url: str, service_key: str, *, open_request=urlopen) -> tuple[str, ...]:
    if url.rstrip("/") != ACCEPTANCE_URL:
        raise ValueError("Refusing schema preflight against any non-acceptance project")
    parsed = urlparse(url)
    if parsed.scheme != "https" or parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise ValueError("Invalid acceptance project URL")
    if not service_key:
        raise ValueError("Missing acceptance service-role key")
    errors = []
    for table in REQUIRED_TABLES:
        request = Request(
            f"{ACCEPTANCE_URL}/rest/v1/{table}?select=*&limit=0",
            headers={
                "apikey": service_key,
                "Authorization": f"Bearer {service_key}",
                "Accept": "application/json",
            },
            method="GET",
        )
        try:
            with open_request(request, timeout=10) as response:
                if response.status != 200:
                    errors.append(table)
        except (HTTPError, URLError, OSError, TimeoutError):
            errors.append(table)
    if errors:
        raise RuntimeError("Acceptance schema missing/inaccessible required tables: " + ", ".join(errors))
    return REQUIRED_TABLES


def main() -> int:
    try:
        tables = check_schema(
            os.getenv("E2E_SUPABASE_URL", ""),
            os.getenv("E2E_SUPABASE_SERVICE_ROLE_KEY", ""),
        )
    except (ValueError, RuntimeError) as exc:
        print(json.dumps({"status": "BLOCKED", "reason": str(exc), "target": "gravitre-acceptance"}))
        return 2
    print(json.dumps({"status": "SCHEMA_READY", "target": "gravitre-acceptance", "tables": list(tables)}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
