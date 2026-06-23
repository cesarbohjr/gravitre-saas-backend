#!/usr/bin/env python3
"""Re-index rag_embeddings with Voyage voyage-3 vectors (1024-dim).

Idempotent: only processes rows where embedding_voyage IS NULL.
See docs/voyage-reindex-runbook.md
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

# Allow running from repo root or backend/
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.config import get_settings
from app.core.logging import get_logger
from app.services.providers.anthropic_adapter import AnthropicAdapter
from app.workflows.repository import get_supabase_client

logger = get_logger(__name__)


def _voyage_adapter(settings) -> AnthropicAdapter:
    key = (getattr(settings, "voyage_api_key", "") or "").strip()
    if not key:
        raise SystemExit("VOYAGE_API_KEY is not configured")
    return AnthropicAdapter(
        api_key_getter=lambda: "",
        voyage_key_getter=lambda: key,
        timeout_s=60.0,
    )


def _fetch_batch(client, *, org_id: str | None, batch_size: int) -> list[dict]:
    q = (
        client.table("rag_embeddings")
        .select("chunk_id, org_id, rag_chunks!inner(content)")
        .is_("embedding_voyage", "null")
        .limit(batch_size)
    )
    if org_id:
        q = q.eq("org_id", org_id)
    return q.execute().data or []


def _write_embedding(client, chunk_id: str, vector: list[float], *, dry_run: bool) -> None:
    if dry_run:
        return
    vec_str = "[" + ",".join(str(x) for x in vector) + "]"
    client.table("rag_embeddings").update({"embedding_voyage": vec_str}).eq("chunk_id", chunk_id).execute()


def main() -> None:
    parser = argparse.ArgumentParser(description="Re-index corpus with Voyage embeddings")
    parser.add_argument("--batch-size", type=int, default=50)
    parser.add_argument("--delay-ms", type=int, default=100)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--org-id", type=str, default=None)
    parser.add_argument(
        "--max-batches",
        type=int,
        default=0,
        help="Stop after N batches (0 = all pending rows). Use 1 for a cheap dry-run probe.",
    )
    args = parser.parse_args()

    settings = get_settings()
    client = get_supabase_client(settings)
    adapter = _voyage_adapter(settings)

    processed = errors = 0
    batches = 0
    started = time.time()

    while True:
        if args.max_batches and batches >= args.max_batches:
            break
        batch = _fetch_batch(client, org_id=args.org_id, batch_size=args.batch_size)
        if not batch:
            break
        batches += 1
        for row in batch:
            chunk_id = str(row["chunk_id"])
            content = ""
            chunks = row.get("rag_chunks")
            if isinstance(chunks, dict):
                content = str(chunks.get("content") or "")
            elif isinstance(chunks, list) and chunks:
                content = str(chunks[0].get("content") or "")
            if not content.strip():
                errors += 1
                continue
            try:
                vector = adapter.embed(content, "voyage-3")
                _write_embedding(client, chunk_id, vector, dry_run=args.dry_run)
                processed += 1
                if processed % 100 == 0:
                    logger.info("reindex progress processed=%s errors=%s", processed, errors)
            except Exception as exc:  # noqa: BLE001
                errors += 1
                logger.warning("reindex failed chunk_id=%s error=%s", chunk_id, str(exc))
        if args.delay_ms > 0:
            time.sleep(args.delay_ms / 1000.0)

    elapsed = round(time.time() - started, 1)
    logger.info(
        "reindex complete processed=%s errors=%s batches=%s elapsed_s=%s dry_run=%s",
        processed,
        errors,
        batches,
        elapsed,
        args.dry_run,
    )
    print(f"processed={processed} errors={errors} batches={batches} elapsed_s={elapsed} dry_run={args.dry_run}")


if __name__ == "__main__":
    main()
