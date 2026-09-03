"""Contextual chunk enrichment: situate a chunk before embedding it.

The failure this addresses is specific. Chunking destroys referents. A chunk
reading "revenue grew 3% over the prior quarter" is a perfectly good answer to
"how did ACME do in Q2 2026" and will not be retrieved for it, because the
embedding contains neither "ACME" nor "Q2 2026" -- those words were in the
document's title and opening paragraph, three chunks earlier. Anthropic
published this as Contextual Retrieval and measured a 35% reduction in
retrieval failures from enrichment alone.

WHAT THIS IS, PRECISELY, because the difference matters and the published number
attaches to the other variant:

  Anthropic's version makes one LLM call PER CHUNK, asking a model to situate
  that chunk within the whole document, and leans on prompt caching to make the
  cost bearable.

  This version makes one LLM call PER DOCUMENT to produce a synopsis, then
  composes each chunk's context deterministically from that synopsis, the
  document title, the chunk's position, and its immediate neighbours.

That is a cheaper approximation, not a reproduction. It targets the same
failure -- lost referents -- at 1/N the model calls. The 35% figure is
Anthropic's result for their variant on their corpora and is NOT a measured
claim about this one. Gravitre's own before/after is in
docs/delivery/orgrag-contextual-enrichment.json, measured on a synthetic corpus
because the real corpus is one chunk platform-wide.

The original chunk text is what gets STORED and CITED. Enrichment affects only
the vector. A user must never be shown a generated synopsis as though it were
something their document said.
"""
from __future__ import annotations

from typing import Any

from app.config import Settings
from app.core.logging import get_logger

logger = get_logger(__name__)

# Recorded per chunk so the three cases stay distinguishable. "Enrichment is
# off", "enrichment ran and produced a context", and "enrichment was attempted
# and failed" would otherwise all leave the same trace -- an empty column --
# which is the Class C shape this program has now booked repeatedly.
ENRICH_DISABLED = "disabled"
ENRICH_OK = "ok"
ENRICH_NO_SYNOPSIS = "no_synopsis"  # deterministic context only; model unavailable
ENRICH_FAILED = "failed"

_SYNOPSIS_MAX_CHARS = 600
_SYNOPSIS_SOURCE_CHARS = 6000
_NEIGHBOUR_CHARS = 160
_CONTEXT_MAX_CHARS = 700


def enrichment_enabled(settings: Settings | None) -> bool:
    return bool(getattr(settings, "rag_contextual_enrichment_enabled", False))


async def build_document_synopsis(
    *,
    text: str,
    title: str,
    settings: Settings | None,
    org_id: str | None = None,
) -> tuple[str, str]:
    """One short synopsis for the whole document. Returns (synopsis, state).

    Returns ``("", ENRICH_NO_SYNOPSIS)`` rather than raising when the model is
    unavailable, because a failed synopsis must degrade to deterministic context
    (title + position + neighbours), not to no enrichment at all and not to a
    failed ingest. Which of those happened is reported, never inferred.
    """
    if not enrichment_enabled(settings):
        return "", ENRICH_DISABLED

    body = (text or "").strip()
    if not body:
        return "", ENRICH_NO_SYNOPSIS

    prompt = (
        "Write a factual, self-contained synopsis of this document in at most "
        "three sentences. It will be prepended to excerpts of the document so "
        "that each excerpt can be found by search on its own.\n\n"
        "Name the concrete things a reader would need in order to know what the "
        "excerpts are about: the organisation, product, jurisdiction, time "
        "period, document type. Do not editorialise, do not summarise "
        "conclusions, and do not add anything the document does not say.\n\n"
        f"Title: {(title or 'untitled')[:200]}\n\n"
        f"Document:\n{body[:_SYNOPSIS_SOURCE_CHARS]}"
    )

    try:
        from app.services.model_router import TaskType, get_model_router

        router = get_model_router()
        response = await router.complete(
            TaskType.SUMMARIZATION,
            prompt,
            org_id=org_id,
            max_tokens=220,
        )
        synopsis = " ".join(str(response.content or "").split())[:_SYNOPSIS_MAX_CHARS]
        if not synopsis:
            return "", ENRICH_NO_SYNOPSIS
        return synopsis, ENRICH_OK
    except Exception as exc:  # noqa: BLE001
        # Interpolated, not passed via `extra=`: the formatter drops `extra`, and
        # a keyword arm stayed dead for months behind exactly that.
        logger.warning(
            "rag_synopsis_failed org_id=%s title=%s error=%s",
            org_id,
            (title or "")[:60],
            exc,
        )
        return "", ENRICH_FAILED


def build_chunk_context(
    *,
    chunk_index: int,
    chunks: list[str],
    title: str,
    synopsis: str,
) -> str:
    """Deterministic context for one chunk. No model call.

    Composed from the pieces a chunk loses by being cut out of its document: what
    the document is, where in it this passage sits, and what immediately precedes
    and follows it.
    """
    total = max(1, len(chunks))
    parts: list[str] = []

    clean_title = " ".join((title or "").split())
    if clean_title:
        parts.append(f"Document: {clean_title[:200]}.")
    if synopsis:
        parts.append(synopsis)
    parts.append(f"This is passage {chunk_index + 1} of {total}.")

    if chunk_index > 0:
        prev = " ".join((chunks[chunk_index - 1] or "").split())
        if prev:
            parts.append(f"Preceded by: …{prev[-_NEIGHBOUR_CHARS:]}")
    if chunk_index + 1 < len(chunks):
        nxt = " ".join((chunks[chunk_index + 1] or "").split())
        if nxt:
            parts.append(f"Followed by: {nxt[:_NEIGHBOUR_CHARS]}…")

    return " ".join(parts)[:_CONTEXT_MAX_CHARS]


def text_for_embedding(*, content: str, context: str) -> str:
    """The string that actually gets embedded.

    Context first, chunk second, and the chunk is never truncated to make room:
    the excerpt is the thing being retrieved, and the context only exists to make
    it findable. An enrichment that displaced the content it was meant to
    describe would be strictly worse than no enrichment.
    """
    if not context:
        return content
    return f"{context}\n\n{content}"


def summarize_enrichment(states: list[str]) -> dict[str, Any]:
    """Per-document enrichment outcome, for the ingest result payload."""
    counts: dict[str, int] = {}
    for state in states:
        counts[state] = counts.get(state, 0) + 1
    return {
        "chunks": len(states),
        "enriched": counts.get(ENRICH_OK, 0),
        "states": counts,
        # True only when every chunk got a model-derived synopsis. Anything less
        # is reported as partial rather than rounded up to "enriched".
        "fully_enriched": bool(states) and counts.get(ENRICH_OK, 0) == len(states),
    }
