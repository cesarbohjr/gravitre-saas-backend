"""Context distillation — compress oversized sources into summaries + findings.

Keeps raw RAG chunks intact when under budget; only distills when content
exceeds thresholds so token spend drops without inventing facts.
"""
from __future__ import annotations

import re
from typing import Any

_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+")
_ENTITY_HINT = re.compile(
    r"\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,3}|[A-Z]{2,}|\b[\w.-]+@[\w.-]+\.\w+)\b"
)


def _top_sentences(text: str, *, limit: int = 4) -> list[str]:
    cleaned = re.sub(r"\s+", " ", (text or "").strip())
    if not cleaned:
        return []
    sentences = [s.strip() for s in _SENTENCE_SPLIT.split(cleaned) if len(s.strip()) > 20]
    if not sentences:
        return [cleaned[:240]]
    # Prefer denser middle-length sentences (heuristic, no LLM).
    ranked = sorted(sentences, key=lambda s: min(len(s), 220), reverse=True)
    out: list[str] = []
    for sent in ranked:
        if sent not in out:
            out.append(sent[:280])
        if len(out) >= limit:
            break
    return out


def _extract_entities(text: str, *, limit: int = 12) -> list[str]:
    hits = _ENTITY_HINT.findall(text or "")
    seen: set[str] = set()
    out: list[str] = []
    for hit in hits:
        key = hit.strip()
        if len(key) < 3 or key.lower() in seen:
            continue
        seen.add(key.lower())
        out.append(key)
        if len(out) >= limit:
            break
    return out


def distill_text(
    text: str,
    *,
    max_chars: int = 1800,
    label: str = "context",
) -> dict[str, Any]:
    """Return page summary / entities / key findings. Pass-through when small."""
    raw = (text or "").strip()
    if not raw:
        return {
            "distilled": False,
            "label": label,
            "page_summary": "",
            "entity_summary": [],
            "key_findings": [],
            "content": "",
        }
    if len(raw) <= max_chars:
        return {
            "distilled": False,
            "label": label,
            "page_summary": raw[:400],
            "entity_summary": _extract_entities(raw, limit=8),
            "key_findings": _top_sentences(raw, limit=3),
            "content": raw,
        }

    findings = _top_sentences(raw, limit=6)
    entities = _extract_entities(raw, limit=12)
    page_summary = findings[0] if findings else raw[:400]
    content_parts = [
        f"[{label} distilled]",
        f"Summary: {page_summary}",
    ]
    if entities:
        content_parts.append("Entities: " + ", ".join(entities[:10]))
    if findings:
        content_parts.append("Key findings:")
        content_parts.extend(f"- {f}" for f in findings[:5])
    content = "\n".join(content_parts)
    if len(content) > max_chars:
        content = content[: max_chars - 1].rstrip() + "…"
    return {
        "distilled": True,
        "label": label,
        "page_summary": page_summary,
        "entity_summary": entities,
        "key_findings": findings,
        "content": content,
        "original_chars": len(raw),
    }


def distill_context_sources(
    sources: list[Any],
    *,
    per_source_max: int = 1800,
) -> tuple[list[Any], dict[str, Any]]:
    """Distill oversized ContextSource.content fields in-place copies."""
    from app.services.context_prioritization_engine import ContextSource

    distilled_count = 0
    out: list[Any] = []
    for source in sources:
        if not isinstance(source, ContextSource):
            out.append(source)
            continue
        result = distill_text(
            source.content,
            max_chars=per_source_max,
            label=str(source.label or source.source_type or "context"),
        )
        if result["distilled"]:
            distilled_count += 1
            meta = dict(source.metadata or {})
            meta["distilled"] = True
            meta["original_chars"] = result.get("original_chars")
            meta["key_findings"] = result.get("key_findings")
            out.append(
                ContextSource(
                    source_id=source.source_id,
                    source_type=source.source_type,
                    label=source.label,
                    score=source.score,
                    content=str(result["content"]),
                    metadata=meta,
                )
            )
        else:
            out.append(source)
    return out, {"distilledSourceCount": distilled_count, "sourceCount": len(sources)}
