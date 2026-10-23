#!/usr/bin/env python3
"""Read-only remote Supabase acceptance-project readiness, no schema modifications."""
from __future__ import annotations

import json
import os
from pathlib import Path
import sys
import urllib.request

ACCEPTANCE_PROJECT_REF = "aadnwmjzrmbvadszroqt"
SQL = """SELECT
 (SELECT count(*) FROM information_schema.tables WHERE table_schema='public' AND table_type='BASE TABLE') AS public_tables,
 (SELECT count(*) FROM supabase_migrations.schema_migrations) AS recorded_migrations;"""


def inspect(ref: str, token: str, *, open_request=urllib.request.urlopen) -> dict:
    if ref != ACCEPTANCE_PROJECT_REF:
        raise ValueError("Refusing non-acceptance Supabase project")
    if not token:
        raise ValueError("Missing Supabase management access token")
    request = urllib.request.Request(
        f"https://api.supabase.com/v1/projects/{ACCEPTANCE_PROJECT_REF}/database/query",
        data=json.dumps({"query": SQL, "read_only": True}).encode(),
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    with open_request(request, timeout=30) as response:
        rows = json.load(response)
    if not isinstance(rows, list) or len(rows) != 1:
        raise ValueError("Unexpected read-only Supabase query response")
    tables = int(rows[0]["public_tables"])
    migrations = int(rows[0]["recorded_migrations"])
    if tables != 0 or migrations != 0:
        raise ValueError("Acceptance database is not empty; review state before initialization")
    return {
        "status": "EMPTY_TARGET_VERIFIED",
        "target_project": ACCEPTANCE_PROJECT_REF,
        "public_tables": tables,
        "recorded_migrations": migrations,
        "read_only": True,
        "remote_write_performed": False,
    }


def main() -> int:
    path = Path("acceptance-baseline/readiness-report.json")
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        result = inspect(
            os.environ.get("ACCEPTANCE_PROJECT_REF", ""),
            os.environ.get("SUPABASE_ACCESS_TOKEN", ""),
        )
        if path.exists():
            baseline = json.loads(path.read_text())
            if baseline.get("status") != "VERIFIED_DATA_FREE_BASELINE":
                raise ValueError("CI baseline validation failed")
            result["baseline_sha256"] = baseline["sha256"]
        else:
            raise ValueError("Missing verified baseline report")
    except Exception as exc:
        result = {"status": "BLOCKED", "reason_type": type(exc).__name__, "remote_write_performed": False}
        path.write_text(json.dumps(result, indent=2) + "\n")
        print(json.dumps(result))
        return 2
    path.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result))
    return 0


if __name__ == "__main__":
    sys.exit(main())
