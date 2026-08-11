"""Ingest licensed platform knowledge into knowledge_* tables (not rag_*)."""
from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from typing import Any

from app.config import Settings, get_settings
from app.core.logging import get_logger
from app.knowledge_fabric.license_types import assert_ingest_allowed
from app.knowledge_fabric.registry import KnowledgeSourceSpec, get_spec, ingestible_specs
from app.rag.embedding import get_embedding
from app.rag.ingest import chunk_document_text

logger = get_logger(__name__)


def _checksum(text: str) -> str:
    return hashlib.sha256((text or "").encode("utf-8")).hexdigest()


def upsert_source(client: Any, spec: KnowledgeSourceSpec) -> dict[str, Any]:
    spec.validate()
    row = spec.to_row()
    row["updated_at"] = datetime.now(timezone.utc).isoformat()
    existing = (
        client.table("knowledge_sources")
        .select("*")
        .eq("source_id", spec.source_id)
        .limit(1)
        .execute()
    )
    if existing.data:
        updated = (
            client.table("knowledge_sources")
            .update(row)
            .eq("id", existing.data[0]["id"])
            .execute()
        )
        return (updated.data or existing.data)[0]
    inserted = client.table("knowledge_sources").insert(row).execute()
    if not inserted.data:
        raise RuntimeError(f"Failed to insert knowledge_sources row for {spec.source_id}")
    return inserted.data[0]


def replace_document_chunks(
    client: Any,
    *,
    source_row: dict[str, Any],
    external_id: str,
    title: str,
    content: str,
    citation: str,
    jurisdiction: str | None,
    topics: list[str],
    published_at: str | None = None,
    effective_at: str | None = None,
    metadata: dict[str, Any] | None = None,
    settings: Settings | None = None,
    embed: bool = True,
) -> dict[str, Any]:
    """Upsert one document and replace its chunks (+ optional embeddings)."""
    settings = settings or get_settings()
    license_type = str(source_row.get("license_type") or "")
    commercial = source_row.get("commercial_use_allowed")
    assert_ingest_allowed(
        license_type,
        ingestion_method=str(source_row.get("ingestion_method") or "api"),
        crawl_allowed=bool(source_row.get("crawl_allowed")),
        commercial_use_allowed=commercial if isinstance(commercial, bool) else None,
    )
    source_uuid = source_row["id"]
    authority = float(source_row.get("authority_score") or 0.8)
    checksum = _checksum(content)
    doc_payload = {
        "source_id": source_uuid,
        "external_id": external_id,
        "title": title,
        "published_at": published_at,
        "effective_at": effective_at,
        "checksum": checksum,
        "citation": citation,
        "jurisdiction": jurisdiction,
        "topics": topics,
        "metadata": metadata or {},
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    existing = (
        client.table("knowledge_documents")
        .select("id,checksum")
        .eq("source_id", source_uuid)
        .eq("external_id", external_id)
        .limit(1)
        .execute()
    )
    if existing.data and existing.data[0].get("checksum") == checksum:
        return {"document_id": existing.data[0]["id"], "skipped": True, "chunks": 0}

    if existing.data:
        document_id = existing.data[0]["id"]
        client.table("knowledge_documents").update(doc_payload).eq("id", document_id).execute()
        client.table("knowledge_chunks").delete().eq("document_id", document_id).execute()
    else:
        inserted = client.table("knowledge_documents").insert(doc_payload).execute()
        if not inserted.data:
            raise RuntimeError(f"document insert failed for {external_id}")
        document_id = inserted.data[0]["id"]

    pieces = chunk_document_text(content, settings=settings)
    model_version = getattr(settings, "rag_embedding_model", None) or "text-embedding-3-small"
    rows: list[dict[str, Any]] = []
    for idx, piece in enumerate(pieces):
        embedding = None
        if embed:
            try:
                embedding = get_embedding(piece, settings)
            except Exception as exc:  # noqa: BLE001
                logger.warning("knowledge_fabric.embed_failed", extra={"error": str(exc)[:200]})
                embedding = None
        rows.append(
            {
                "document_id": document_id,
                "source_id": source_uuid,
                "chunk_index": idx,
                "content": piece,
                "embedding": embedding,
                "model_version": model_version if embedding is not None else None,
                "topics": topics,
                "jurisdiction": jurisdiction,
                "authority_score": authority,
                "freshness_score": 0.95,
                "citation": citation,
                "metadata": {"external_id": external_id, "title": title},
            }
        )
    if rows:
        # supabase-py may not accept raw vectors as lists — store as list[float]
        client.table("knowledge_chunks").insert(rows).execute()
    client.table("knowledge_sources").update(
        {"last_refreshed_at": datetime.now(timezone.utc).isoformat()}
    ).eq("id", source_uuid).execute()
    return {"document_id": document_id, "skipped": False, "chunks": len(rows)}


def register_all_sources(client: Any) -> list[dict[str, Any]]:
    from app.knowledge_fabric.registry import PLATFORM_KNOWLEDGE_SOURCES

    out = []
    for spec in PLATFORM_KNOWLEDGE_SOURCES:
        out.append(upsert_source(client, spec))
    return out


async def ingest_pack(
    client: Any,
    pack_id: str,
    *,
    settings: Settings | None = None,
    embed: bool = True,
    limit: int = 5,
) -> dict[str, Any]:
    settings = settings or get_settings()
    specs = [s for s in ingestible_specs() if s.pack_id == pack_id]
    if not specs:
        return {"pack_id": pack_id, "error": "no_ingestible_sources", "documents": 0}

    results: list[dict[str, Any]] = []
    errors: list[dict[str, str]] = []
    for spec in specs:
        try:
            source_row = upsert_source(client, spec)
            docs = await _fetch_documents_for_spec(spec, limit=limit, settings=settings)
            for doc in docs:
                results.append(
                    replace_document_chunks(
                        client,
                        source_row=source_row,
                        external_id=doc["external_id"],
                        title=doc["title"],
                        content=doc["content"],
                        citation=doc["citation"],
                        jurisdiction=doc.get("jurisdiction"),
                        topics=doc.get("topics") or list(spec.topics),
                        published_at=doc.get("published_at"),
                        effective_at=doc.get("effective_at"),
                        metadata=doc.get("metadata") or {},
                        settings=settings,
                        embed=embed,
                    )
                )
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "knowledge_fabric.ingest_spec_failed",
                extra={"source_id": spec.source_id, "error": str(exc)[:240]},
            )
            errors.append({"source_id": spec.source_id, "error": str(exc)[:240]})
    return {
        "pack_id": pack_id,
        "documents": len(results),
        "chunks": sum(int(r.get("chunks") or 0) for r in results),
        "results": results,
        "errors": errors,
    }


async def _fetch_documents_for_spec(
    spec: KnowledgeSourceSpec,
    *,
    limit: int,
    settings: Settings,
) -> list[dict[str, Any]]:
    if spec.source_id.startswith("cyber.nist"):
        from app.knowledge_fabric.sources.nist import fetch_nist_documents

        return await fetch_nist_documents(spec, limit=limit)
    if spec.source_id.startswith("legal.courtlistener"):
        from app.knowledge_fabric.sources.courtlistener import fetch_courtlistener_opinions

        return await fetch_courtlistener_opinions(limit=limit)
    if spec.source_id.startswith("legal.us.constitution"):
        from app.knowledge_fabric.sources.us_constitution import fetch_constitution_documents

        return await fetch_constitution_documents(limit=limit)
    if spec.source_id.startswith("finance.sec"):
        from app.knowledge_fabric.sources.sec_edgar import fetch_sec_edgar_documents

        return await fetch_sec_edgar_documents(limit=limit, settings=settings)
    if spec.source_id.startswith("hr.dol"):
        from app.knowledge_fabric.sources.dol import fetch_dol_documents

        return await fetch_dol_documents(limit=limit)
    if spec.source_id.startswith("marketing.ftc"):
        from app.knowledge_fabric.sources.ftc import fetch_ftc_documents

        return await fetch_ftc_documents(spec, limit=limit)
    if spec.source_id.startswith("marketing.sba"):
        from app.knowledge_fabric.sources.sba import fetch_sba_documents

        return await fetch_sba_documents(spec, limit=limit)
    if spec.source_id.startswith("sales.census"):
        from app.knowledge_fabric.sources.census import fetch_census_documents

        return await fetch_census_documents(spec, limit=limit)
    if ".saylor." in spec.source_id:
        from app.knowledge_fabric.sources.saylor import fetch_saylor_documents

        return await fetch_saylor_documents(spec, limit=limit)
    if spec.source_id.startswith("marketing.openstax"):
        from app.knowledge_fabric.sources.openstax import fetch_openstax_documents

        return await fetch_openstax_documents(spec, limit=limit)
    if spec.license_type == "D" or spec.ingestion_method == "live_only":
        raise ValueError(f"{spec.source_id}: live_only / type D — refuse permanent ingest")
    return []
