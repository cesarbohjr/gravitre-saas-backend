"""Seed public Gravitre product docs into each org's RAG corpus."""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from app.config import Settings
from app.core.logging import get_logger
from app.rag.ingest import (
    activate_document,
    chunk_document_text,
    create_source,
    replace_chunks_and_embeddings,
    upsert_document,
)

logger = get_logger(__name__)

PLATFORM_SOURCE_TITLE = "Gravitre Platform Guide"
PLATFORM_SOURCE_EXTERNAL = "gravitre-platform-guide"
_FRONTMATTER = re.compile(r"^---\s*\n.*?\n---\s*\n", re.DOTALL)

PLATFORM_DOC_SPECS: tuple[tuple[str, str, str], ...] = (
    ("gravitre-platform-introduction", "Introduction to Gravitre", "apps/web/content/docs/public/concepts/introduction.mdx"),
    ("gravitre-platform-overview", "Platform overview", "apps/web/content/docs/public/concepts/platform-overview.mdx"),
    ("gravitre-platform-assistant", "Assistant", "apps/web/content/docs/public/concepts/assistant.mdx"),
    ("gravitre-platform-quickstart", "Quickstart", "apps/web/content/docs/public/getting-started/quickstart.mdx"),
    ("gravitre-platform-connectors", "Connectors guide", "apps/web/content/docs/public/guides/how-to/connectors.mdx"),
)


def repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def strip_mdx_frontmatter(text: str) -> str:
    return _FRONTMATTER.sub("", text, count=1).strip()


def load_platform_document_text(relative_path: str) -> str:
    path = repo_root() / relative_path
    if not path.is_file():
        raise FileNotFoundError(relative_path)
    return strip_mdx_frontmatter(path.read_text(encoding="utf-8", errors="replace"))


def _source_exists(client: Any, org_id: str) -> dict[str, Any] | None:
    rows = (
        client.table("rag_sources")
        .select("id,title,environment")
        .eq("org_id", org_id)
        .eq("title", PLATFORM_SOURCE_TITLE)
        .limit(1)
        .execute()
        .data
        or []
    )
    return rows[0] if rows else None


def _ensure_platform_source(
    client: Any,
    org_id: str,
    *,
    environment_name: str,
) -> dict[str, Any]:
    existing = _source_exists(client, org_id)
    if existing:
        return existing
    return create_source(
        client,
        org_id,
        PLATFORM_SOURCE_TITLE,
        "manual",
        {"seed": "platform-guide", "scope": "platform"},
        created_by="system",
        environment_name=environment_name,
    )


def seed_platform_knowledge_for_org(
    client: Any,
    org_id: str,
    settings: Settings,
    *,
    environment_name: str = "production",
) -> dict[str, Any]:
    """Idempotently ingest public Gravitre docs for one organization."""
    if not (settings.openai_api_key or "").strip():
        raise ValueError("OPENAI_API_KEY is required to embed platform knowledge")

    source = _ensure_platform_source(client, org_id, environment_name=environment_name)
    source_id = str(source["id"])
    document_ids: list[str] = []
    chunk_total = 0

    for external_id, title, relative_path in PLATFORM_DOC_SPECS:
        try:
            body = load_platform_document_text(relative_path)
        except FileNotFoundError:
            logger.warning("platform_knowledge_missing_file org_id=%s path=%s", org_id, relative_path)
            continue
        if not body.strip():
            continue

        doc = upsert_document(
            client,
            org_id=org_id,
            source_id=source_id,
            external_id=external_id,
            title=title,
            metadata={"seed": "platform-guide", "path": relative_path},
            is_active=False,
            environment_name=environment_name,
        )
        chunks = chunk_document_text(body, settings=settings)
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
        document_ids.append(str(doc["id"]))
        chunk_total += chunk_count

    return {
        "org_id": org_id,
        "source_id": source_id,
        "document_ids": document_ids,
        "chunk_count": chunk_total,
        "environment": environment_name,
    }
