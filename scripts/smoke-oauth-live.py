#!/usr/bin/env python3
"""Live OAuth smoke runner for top vendor connectors.

Uses stored OAuth connectors in Supabase (operator org) and invoke_tool against
real vendor APIs. Read actions run first; writes require --enable-writes and a
sandbox environment unless OAUTH_SMOKE_FORCE_SANDBOX_WRITES=1.

Usage:
  python scripts/smoke-oauth-live.py
  python scripts/smoke-oauth-live.py --enable-writes --environment sandbox
  python scripts/smoke-oauth-live.py --json docs/delivery/oauth-smoke-live-latest.json
  python scripts/smoke-oauth-live.py --csv docs/delivery/oauth-smoke-live-latest.csv
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
BACKEND = REPO / "backend"
sys.path.insert(0, str(BACKEND))

from dotenv import dotenv_values  # noqa: E402

from app.config import get_settings  # noqa: E402
from app.services.oauth_smoke_runner import (  # noqa: E402
    TOP10_VENDORS,
    export_smoke_csv,
    export_smoke_json,
    run_oauth_smoke,
)
from app.services.tool_types import ToolContext  # noqa: E402


def _load_env() -> dict[str, str]:
    merged: dict[str, str] = {}
    for path in (BACKEND / ".env", BACKEND / ".env.operator.local", REPO / ".env"):
        if not path.is_file():
            continue
        try:
            merged.update({k: v for k, v in dotenv_values(path).items() if v})
        except UnicodeDecodeError:
            text = path.read_text(encoding="utf-8", errors="replace")
            for line in text.splitlines():
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, value = line.split("=", 1)
                value = value.strip().strip('"')
                if value:
                    merged[key.strip()] = value
    merged.update({k: v for k, v in os.environ.items() if v})
    return merged


def _supabase_client(env: dict[str, str]):
    from supabase import create_client

    url = env.get("SUPABASE_URL") or os.environ.get("SUPABASE_URL")
    key = env.get("SUPABASE_SERVICE_ROLE_KEY") or os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    if not url or not key:
        raise SystemExit("SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY required")
    return create_client(url, key)


def _is_uuid(value: str) -> bool:
    import uuid

    try:
        uuid.UUID(str(value))
        return True
    except (TypeError, ValueError):
        return False


def _resolve_org_member_actor(client, org_id: str) -> str:
    """Pick a real auth.users UUID for audit_events.actor_id (NOT NULL + FK)."""
    for role_filter in ("admin", None):
        q = (
            client.table("organization_members")
            .select("user_id, role")
            .eq("org_id", org_id)
            .limit(5)
        )
        if role_filter:
            q = q.eq("role", role_filter)
        rows = q.execute()
        for row in rows.data or []:
            uid = str(row.get("user_id") or "").strip()
            if _is_uuid(uid):
                return uid
    raise SystemExit(
        f"No UUID org member for org {org_id}. Set OAUTH_SMOKE_USER_ID to an auth.users id."
    )


def _resolve_org_id(env: dict[str, str], client) -> tuple[str, str]:
    org_id = (
        env.get("OAUTH_SMOKE_ORG_ID")
        or env.get("SMOKE_ORG_ID")
        or env.get("OPERATOR_ORG_ID")
        or os.environ.get("OAUTH_SMOKE_ORG_ID")
        or os.environ.get("SMOKE_ORG_ID")
        or os.environ.get("OPERATOR_ORG_ID")
        or ""
    ).strip()
    actor_id = (
        env.get("OAUTH_SMOKE_USER_ID")
        or env.get("SMOKE_USER_ID")
        or os.environ.get("OAUTH_SMOKE_USER_ID")
        or os.environ.get("SMOKE_USER_ID")
        or ""
    ).strip()

    if not org_id:
        members = (
            client.table("organization_members")
            .select("org_id, user_id, role")
            .eq("role", "admin")
            .limit(1)
            .execute()
        )
        if not members.data:
            raise SystemExit(
                "No org id found. Set OAUTH_SMOKE_ORG_ID or connect an admin org in Supabase."
            )
        row = members.data[0]
        org_id = str(row["org_id"])
        if not actor_id:
            actor_id = str(row.get("user_id") or "")

    # audit_events.actor_id is uuid NOT NULL REFERENCES auth.users — never pass
    # the legacy "oauth-smoke-runner" label (caused dual_write_gap on invoke).
    if not _is_uuid(actor_id):
        actor_id = _resolve_org_member_actor(client, org_id)

    return org_id, actor_id


def main() -> int:
    parser = argparse.ArgumentParser(description="Live OAuth connector smoke runner")
    parser.add_argument(
        "--vendors",
        default=",".join(TOP10_VENDORS),
        help=f"Comma-separated vendors (default: all top 10). Options: {', '.join(TOP10_VENDORS)}",
    )
    parser.add_argument("--environment", default=os.environ.get("OAUTH_SMOKE_ENVIRONMENT", "production"))
    parser.add_argument("--org-id", default=None, help="Override target org UUID")
    parser.add_argument("--enable-writes", action="store_true", help="Include sandbox write smoke cases")
    parser.add_argument(
        "--allow-destructive",
        action="store_true",
        help="Allow destructive catalog actions (delete, etc.)",
    )
    parser.add_argument(
        "--skip-auth-check",
        action="store_true",
        help="Skip remote OAuth token validation before invoke",
    )
    parser.add_argument("--json", dest="json_path", default=None, help="Write JSON report path")
    parser.add_argument("--csv", dest="csv_path", default=None, help="Write CSV report path")
    args = parser.parse_args()

    env = _load_env()
    if args.org_id:
        env["OAUTH_SMOKE_ORG_ID"] = args.org_id
    for key, value in env.items():
        os.environ.setdefault(key, value)

    settings = get_settings()
    client = _supabase_client(env)
    org_id, actor_id = _resolve_org_id(env, client)
    vendors = [v.strip() for v in args.vendors.split(",") if v.strip()]

    ctx = ToolContext(
        settings=settings,
        client=client,
        org_id=org_id,
        actor_id=actor_id,
        environment_name=args.environment,
    )

    report = run_oauth_smoke(
        ctx,
        vendors=vendors,
        enable_writes=args.enable_writes,
        allow_destructive=args.allow_destructive,
        validate_remote_auth=not args.skip_auth_check,
        env=env,
    )

    summary = report["summary"]
    print(f"OAuth smoke run {report['runId']} — org {org_id} env {args.environment}")
    print(
        "  passed={passed} failed={failed} skipped={skipped} auth_failure={auth_failure} "
        "missing_scopes={missing_scopes} invalid_schema={invalid_schema} api_error={api_error}".format(
            **summary
        )
    )

    for row in report["results"]:
        if row["status"] != "passed":
            print(
                f"  [{row['status']}] {row['vendor']} {row['actionId']}: "
                f"{row.get('errorMessage') or row.get('detail') or ''}"
            )
            if row.get("suggestedFix"):
                print(f"           fix: {row['suggestedFix']}")

    json_path = args.json_path or str(REPO / "docs" / "delivery" / "oauth-smoke-live-latest.json")
    csv_path = args.csv_path or str(REPO / "docs" / "delivery" / "oauth-smoke-live-latest.csv")
    export_smoke_json(json_path, report)
    export_smoke_csv(csv_path, report)
    print(f"Wrote {json_path}")
    print(f"Wrote {csv_path}")

    hard_fail = summary.get("failed", 0) + summary.get("auth_failure", 0) + summary.get("api_error", 0)
    hard_fail += summary.get("missing_scopes", 0) + summary.get("invalid_schema", 0)

    # Wave 2 honesty: skipped ≠ passed. With --enable-writes, at least one write must pass
    # or the run is incomplete (not green).
    if args.enable_writes:
        write_rows = [r for r in report["results"] if r.get("kind") == "write"]
        write_passed = sum(1 for r in write_rows if r.get("status") == "passed")
        write_skipped = sum(1 for r in write_rows if r.get("status") == "skipped")
        print(
            f"  writes: passed={write_passed} skipped={write_skipped} "
            f"total_write_rows={len(write_rows)} (skipped is not pass)"
        )
        if write_rows and write_passed == 0:
            print(
                "ERROR: --enable-writes ran but zero write actions passed "
                "(skipped/auth_failure must not be reported as green)."
            )
            return 1

    return 1 if hard_fail else 0


if __name__ == "__main__":
    raise SystemExit(main())
