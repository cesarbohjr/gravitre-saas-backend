"""Seed Gravitre platform docs into org RAG (public /docs content)."""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
BACKEND = REPO / "backend"
sys.path.insert(0, str(BACKEND))


def load_operator_env() -> dict[str, str]:
    env: dict[str, str] = {}
    for path in (BACKEND / ".env", BACKEND / ".env.operator.local", REPO / ".env"):
        if not path.is_file():
            continue
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            value = value.strip().strip('"').strip("'")
            if value:
                env[key.strip()] = value
    return env


def resolve_org_id(client, org_id: str | None) -> str:
    if org_id:
        return org_id
    row = (
        client.table("organization_members")
        .select("org_id")
        .eq("role", "admin")
        .limit(1)
        .execute()
        .data
    )
    if not row:
        row = client.table("organization_members").select("org_id").limit(1).execute().data
    if not row:
        raise SystemExit("No organization_members row found")
    return str(row[0]["org_id"])


def main() -> int:
    parser = argparse.ArgumentParser(description="Seed Gravitre platform knowledge into org RAG")
    parser.add_argument("--org-id", default=None)
    parser.add_argument("--environment", default="production")
    parser.add_argument("--all-orgs", action="store_true", help="Seed every organization")
    args = parser.parse_args()

    for key, value in load_operator_env().items():
        os.environ[key] = value

    from app.config import get_settings
    from app.services.platform_knowledge_seed import seed_platform_knowledge_for_org
    from app.workflows.repository import get_supabase_client

    settings = get_settings()
    client = get_supabase_client(settings)

    org_ids: list[str]
    if args.all_orgs:
        rows = client.table("organizations").select("id").execute().data or []
        org_ids = [str(row["id"]) for row in rows]
    else:
        org_ids = [resolve_org_id(client, args.org_id)]

    print("=== Platform knowledge seed ===")
    for org_id in org_ids:
        result = seed_platform_knowledge_for_org(
            client,
            org_id,
            settings,
            environment_name=args.environment,
        )
        print(f"org_id={org_id} source_id={result['source_id']} chunks={result['chunk_count']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
