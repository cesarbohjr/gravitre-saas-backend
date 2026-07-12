"""Live Memory opt-out / no-raw-PII probe (STA-316) — stop-ship if ambiguous."""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
for p in [BACKEND / ".env", BACKEND / ".env.operator.local"]:
    if p.is_file():
        for k, v in dotenv_values(p).items():
            if v:
                os.environ.setdefault(k, v)

sys.path.insert(0, str(BACKEND))

from app.config import get_settings
from app.connectors.action_catalog.models import WorkflowFieldSpec
from app.services.memory_entity_embeddings_service import embed_opaque_token
from app.services.memory_entity_embeddings_settings import load_memory_entity_embeddings_settings
from app.services.memory_field_resolver import resolve_sensitive_field_mention
from app.services.memory_opaque_tokens import MemoryOpaqueTokenError
from app.workflows.repository import get_supabase_client

OUT = ROOT / "docs" / "delivery" / "reaudit-memory-opt-out-live.json"
SMOKE_ORG = "cbbf993b-b22f-41ce-964b-1fc25e0dd9ea"


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


async def main() -> int:
    settings = get_settings()
    client = get_supabase_client(settings)

    orgs = (
        client.table("organizations")
        .select("id,settings")
        .neq("id", SMOKE_ORG)
        .limit(50)
        .execute()
        .data
        or []
    )
    off_org = None
    for row in orgs:
        policy = load_memory_entity_embeddings_settings(client, str(row["id"]))
        if not policy.get("enabled"):
            off_org = str(row["id"])
            break
    if not off_org and orgs:
        # Explicit: empty settings ⇒ default off
        off_org = str(orgs[0]["id"])

    provider_calls: list[str] = []

    def _fake_get_embedding(text: str, *args, **kwargs):
        provider_calls.append(str(text))
        return [0.0] * 8

    field = WorkflowFieldSpec("Assignee", ("assignee_hint", "assignee"), sensitive=True)

    with patch(
        "app.services.providers.openai_adapter.OpenAIAdapter.embed",
        side_effect=_fake_get_embedding,
    ):
        # 1) Raw PII must never reach provider
        raw_blocked = True
        raw_errors: list[str] = []
        for raw in ("sarah@acme.com", "Sarah Smith", "Sarah"):
            try:
                embed_opaque_token(raw, settings, org_id=off_org or SMOKE_ORG)
                raw_blocked = False
                raw_errors.append(f"accepted:{raw}")
            except MemoryOpaqueTokenError:
                pass

        # 2) Default-off org: resolver must skip without provider call
        before = len(provider_calls)
        result = await resolve_sensitive_field_mention(
            client=client,
            settings=settings,
            org_id=off_org or "00000000-0000-0000-0000-000000000099",
            integration="asana",
            field=field,
            mention="Sarah",
            entity_type="assignee",
        )
        after = len(provider_calls)
        opt_out_ok = result.status == "skipped" and result.reason == "org_opt_in_off" and after == before

        # 3) Smoke org is opted-in — confirm policy reads enabled (governance inventory)
        smoke_policy = load_memory_entity_embeddings_settings(client, SMOKE_ORG)

    report = {
        "ticket": "STA-316",
        "kind": "reaudit-memory-opt-out-live",
        "ran_at": utcnow(),
        "git_tip": os.popen("git rev-parse --short HEAD").read().strip(),
        "off_org_id": off_org,
        "smoke_org_policy": smoke_policy,
        "raw_pii_blocked": raw_blocked,
        "raw_errors": raw_errors,
        "provider_calls": provider_calls,
        "opt_out_resolver": {
            "status": result.status,
            "reason": result.reason,
            "provider_calls_during": after - before,
            "pass": opt_out_ok,
        },
        "pass": {
            "raw_pii_never_embedded": raw_blocked and not provider_calls,
            "default_off_skips_without_provider": opt_out_ok,
            "smoke_org_explicit_opt_in": bool(smoke_policy.get("enabled")),
        },
    }
    overall = all(report["pass"].values())
    report["verdict"] = "PASS" if overall else "FAIL"
    OUT.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"wrote": str(OUT), "verdict": report["verdict"], "pass": report["pass"]}, indent=2))
    return 0 if overall else 1


if __name__ == "__main__":
    import asyncio

    raise SystemExit(asyncio.run(main()))
