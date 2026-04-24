"""BE-10: Minimal admin CLI for RAG ingestion. Service role; idempotent per document."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Run from backend/: python -m scripts.rag_ingest ...
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from supabase import create_client

from app.config import get_settings
from app.rag.embedding import get_embedding


def register_source(org_id: str, title: str, type_: str) -> str:
    """Insert rag_sources row; return source id."""
    settings = get_settings()
    client = create_client(settings.supabase_url, settings.supabase_service_role_key)
    r = client.table("rag_sources").insert({
        "org_id": org_id,
        "title": title,
        "type": type_,
    }).execute()
    if not r.data or len(r.data) == 0:
        raise RuntimeError("rag_sources insert returned no row")
    return str(r.data[0]["id"])


def upsert_document(org_id: str, source_id: str, external_id: str | None, title: str | None) -> str:
    """Upsert rag_documents on (source_id, external_id); return document id."""
    settings = get_settings()
    client = create_client(settings.supabase_url, settings.supabase_service_role_key)
    row = {
        "org_id": org_id,
        "source_id": source_id,
        "external_id": external_id,
        "title": title,
    }
    r = client.table("rag_documents").upsert(row, on_conflict="source_id, external_id").execute()
    if not r.data or len(r.data) == 0:
        raise RuntimeError("rag_documents upsert returned no row")
    return str(r.data[0]["id"])


def replace_chunks_and_embeddings(
    org_id: str,
    document_id: str,
    source_id: str,
    chunks: list[str],
) -> None:
    """Delete existing chunks for document (CASCADE removes embeddings), insert chunks + embeddings."""
    settings = get_settings()
    if not settings.openai_api_key:
        raise ValueError("OPENAI_API_KEY required for embeddings")
    client = create_client(settings.supabase_url, settings.supabase_service_role_key)

    # Delete existing chunks for this document (CASCADE removes rag_embeddings)
    client.table("rag_chunks").delete().eq("document_id", document_id).execute()

    model_version = settings.openai_embedding_model
    chunk_rows = []
    for i, content in enumerate(chunks):
        chunk_rows.append({
            "org_id": org_id,
            "document_id": document_id,
            "source_id": source_id,
            "content": content,
            "chunk_index": i,
        })
    if not chunk_rows:
        return
    r = client.table("rag_chunks").insert(chunk_rows).execute()
    if not r.data:
        raise RuntimeError("rag_chunks insert returned no rows")
    chunk_ids = [c["id"] for c in r.data]

    for chunk_id, content in zip(chunk_ids, chunks):
        embedding = get_embedding(content, settings)
        client.table("rag_embeddings").insert({
            "chunk_id": chunk_id,
            "org_id": org_id,
            "embedding": embedding,
            "model_version": model_version,
        }).execute()


def main() -> None:
    parser = argparse.ArgumentParser(description="BE-10 RAG ingestion (service role)")
    sub = parser.add_subparsers(dest="command", required=True)
    # register-source --org-id UUID --title "..." --type manual
    p1 = sub.add_parser("register-source")
    p1.add_argument("--org-id", required=True)
    p1.add_argument("--title", required=True)
    p1.add_argument("--type", dest="type_", required=True, help="e.g. manual, upload")
    # ingest-document --org-id UUID --source-id UUID [--external-id ID] [--title "..."] --chunks-file path
    p2 = sub.add_parser("ingest-document")
    p2.add_argument("--org-id", required=True)
    p2.add_argument("--source-id", required=True)
    p2.add_argument("--external-id", default=None)
    p2.add_argument("--title", default=None)
    p2.add_argument("--chunks-file", required=True, help="JSON array of chunk text strings")
    args = parser.parse_args()

    if args.command == "register-source":
        sid = register_source(args.org_id, args.title, args.type_)
        print(sid)
    elif args.command == "ingest-document":
        path = Path(args.chunks_file)
        chunks = json.loads(path.read_text())
        if not isinstance(chunks, list) or not all(isinstance(s, str) for s in chunks):
            raise SystemExit("--chunks-file must be a JSON array of strings")
        doc_id = upsert_document(args.org_id, args.source_id, args.external_id, args.title)
        replace_chunks_and_embeddings(args.org_id, doc_id, args.source_id, chunks)
        print(doc_id)


if __name__ == "__main__":
    main()
