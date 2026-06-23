"""Seed sample RAG knowledge for Voyage reindex dry-run (STA-279).

Uses backend/.env + .env.operator.local. Requires OPENAI_API_KEY for OpenAI embeddings.
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
BACKEND = REPO / "backend"
sys.path.insert(0, str(BACKEND))

SAMPLE_EXTERNAL_ID = "sta-279-sample-playbook"
SAMPLE_TITLE = "Gravitre Operator Sample Playbook"
SAMPLE_TEXT = """
Gravitre Operator helps teams automate workflows with AI agents connected to business systems.

Pipeline hygiene: review stale opportunities weekly, flag deals with no activity in fourteen days,
and summarize next-best actions for revenue operations.

Knowledge retrieval uses hybrid search combining vector similarity, BM25 keyword ranking,
and optional cross-encoder reranking for higher precision answers.

Connector knowledge sync ingests Notion, Confluence, HubSpot, and Zendesk content into the
organization knowledge base for agent and assistant retrieval.

Incident response: when PagerDuty alerts fire, agents can summarize severity, recent deploys,
and customer impact using connected observability and ticketing data.

Financial operations teams use read-only QuickBooks and NetSuite connectors during pilots
before write access is approved by customer finance leadership.
""".strip()


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


def resolve_org_id(client) -> str:
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


def pick_or_create_source(client, org_id: str, environment_name: str) -> tuple[dict, str]:
    from app.rag.ingest import create_source, list_sources

    existing = (
        client.table("rag_sources")
        .select("id,title,environment")
        .eq("org_id", org_id)
        .order("updated_at", desc=True)
        .limit(5)
        .execute()
        .data
        or []
    )
    if existing:
        row = existing[0]
        return row, str(row.get("environment") or environment_name)

    sources = list_sources(client, org_id, environment_name=environment_name)
    if sources:
        row = sources[0]
        return row, environment_name
    row = create_source(
        client,
        org_id,
        "STA-279 Sample Source",
        "manual",
        {"seed": "sta-279"},
        created_by="system",
        environment_name=environment_name,
    )
    return row, environment_name


def seed_sample(
    *,
    environment_name: str = "production",
    org_id: str | None = None,
) -> dict[str, int | str]:
    for key, value in load_operator_env().items():
        os.environ[key] = value

    from app.config import get_settings
    from app.rag.ingest import (
        activate_document,
        chunk_document_text,
        replace_chunks_and_embeddings,
        upsert_document,
    )
    from app.workflows.repository import get_supabase_client

    settings = get_settings()
    if not (settings.openai_api_key or "").strip():
        raise SystemExit("OPENAI_API_KEY is required to create OpenAI embeddings for the sample corpus")

    client = get_supabase_client(settings)
    org_id = org_id or resolve_org_id(client)
    source, environment_name = pick_or_create_source(client, org_id, environment_name)
    source_id = str(source["id"])

    doc = upsert_document(
        client,
        org_id=org_id,
        source_id=source_id,
        external_id=SAMPLE_EXTERNAL_ID,
        title=SAMPLE_TITLE,
        metadata={"seed": "sta-279", "kind": "sample_playbook"},
        is_active=False,
        environment_name=environment_name,
    )
    chunks = chunk_document_text(SAMPLE_TEXT, settings=settings)
    chunk_count = replace_chunks_and_embeddings(
        client,
        settings,
        org_id,
        source_id=source_id,
        document_id=str(doc["id"]),
        chunks=chunks,
        environment_name=environment_name,
    )
    activate_document(client, org_id, str(doc["id"]))

    pending = (
        client.table("rag_embeddings")
        .select("chunk_id", count="exact")
        .eq("org_id", org_id)
        .is_("embedding_voyage", "null")
        .limit(1)
        .execute()
    )
    total = (
        client.table("rag_embeddings")
        .select("chunk_id", count="exact")
        .eq("org_id", org_id)
        .limit(1)
        .execute()
    )
    return {
        "org_id": org_id,
        "source_id": source_id,
        "document_id": str(doc["id"]),
        "chunk_count": chunk_count,
        "total_embeddings": int(getattr(total, "count", 0) or 0),
        "pending_voyage": int(getattr(pending, "count", 0) or 0),
        "environment": environment_name,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Seed sample RAG knowledge")
    parser.add_argument("--org-id", default=None)
    parser.add_argument("--environment", default="production")
    args = parser.parse_args()
    result = seed_sample(org_id=args.org_id, environment_name=args.environment)
    print("=== Sample RAG knowledge seeded ===")
    for key, value in result.items():
        print(f"{key}: {value}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
