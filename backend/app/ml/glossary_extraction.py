"""Glossary extraction from queries and RAG documents (v3)."""
from __future__ import annotations

import re
from collections import Counter, defaultdict
from typing import Any

from app.core.logging import get_logger
from app.services.query_normalization import normalize_query

logger = get_logger(__name__)

_ACRONYM = re.compile(r"\b[A-Z]{2,6}\b")
_ACRONYM_LOWER = re.compile(r"\b[a-z]{2,6}\b")
_PHRASE = re.compile(r"\b[a-z]{3,}(?:\s+[a-z]{3,}){1,3}\b")

_nlp = None
_nlp_attempted = False


def _get_spacy_nlp():
    global _nlp, _nlp_attempted
    if _nlp_attempted:
        return _nlp
    _nlp_attempted = True
    try:
        import spacy

        try:
            _nlp = spacy.load("en_core_web_sm")
        except OSError:
            _nlp = spacy.blank("en")
            if "sentencizer" not in _nlp.pipe_names:
                _nlp.add_pipe("sentencizer")
        logger.info("glossary_spacy_loaded model=%s", _nlp.meta.get("name", "blank"))
    except Exception as exc:  # noqa: BLE001
        logger.warning("glossary_spacy_unavailable error=%s", exc)
        _nlp = None
    return _nlp


def _extract_acronyms(text: str) -> list[str]:
    found = _ACRONYM.findall(text or "")
    return [token for token in found if len(token) >= 2]


def _extract_named_entities(text: str) -> list[str]:
    nlp = _get_spacy_nlp()
    if nlp is None:
        return []
    doc = nlp(text[:5000])
    return [ent.text.strip() for ent in doc.ents if ent.text.strip()]


def _extract_repeated_phrases(texts: list[str], min_freq: int = 2) -> list[tuple[str, int]]:
    counts: Counter[str] = Counter()
    for text in texts:
        normalized = normalize_query(text)
        for match in _PHRASE.findall(normalized):
            if len(match) > 8:
                counts[match] += 1
    return [(phrase, count) for phrase, count in counts.items() if count >= min_freq]


async def extract_glossary_candidates(
    *,
    query_rows: list[dict[str, Any]],
    document_texts: list[str] | None = None,
) -> list[dict[str, Any]]:
    """
    Returns candidate terms: term, term_type, frequency, example_context, source.
    Department association applied separately via map_terms_to_departments().
    """
    candidates: dict[tuple[str, str, str], dict[str, Any]] = {}

    def bump(term: str, term_type: str, source: str, context: str) -> None:
        key = (term.lower(), term_type, source)
        if key not in candidates:
            candidates[key] = {
                "term": term,
                "term_type": term_type,
                "frequency": 0,
                "example_context": context[:240],
                "source": source,
            }
        candidates[key]["frequency"] += 1

    for row in query_rows:
        raw = str(row.get("normalized_query_text") or row.get("query_text") or "")
        if not raw:
            continue
        for acronym in _extract_acronyms(row.get("query_text") or raw):
            bump(acronym, "acronym", "query", raw)
        for ent in _extract_named_entities(raw):
            bump(ent, "named_entity", "query", raw)

    query_texts = [
        str(r.get("normalized_query_text") or r.get("query_text") or "")
        for r in query_rows
        if r.get("normalized_query_text") or r.get("query_text")
    ]
    for phrase, count in _extract_repeated_phrases(query_texts):
        bump(phrase, "repeated_phrase", "query", phrase)

    for doc_text in document_texts or []:
        text = (doc_text or "").strip()
        if not text:
            continue
        for acronym in _extract_acronyms(text):
            bump(acronym, "acronym", "document", text[:240])
        for ent in _extract_named_entities(text):
            bump(ent, "named_entity", "document", text[:240])

    return list(candidates.values())


def map_terms_to_departments(
    candidates: list[dict[str, Any]],
    query_rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Co-occurrence: associate each term with the department seen most in matching queries."""
    dept_by_term: dict[str, Counter[str]] = defaultdict(Counter)
    for row in query_rows:
        dept = str(row.get("department") or "").strip()
        if not dept:
            continue
        haystack = normalize_query(
            f"{row.get('normalized_query_text') or ''} {row.get('query_text') or ''}"
        )
        for cand in candidates:
            term = normalize_query(str(cand.get("term") or ""))
            if term and term in haystack:
                dept_by_term[term.lower()][dept] += 1

    enriched: list[dict[str, Any]] = []
    for cand in candidates:
        term_key = normalize_query(str(cand.get("term") or ""))
        dept_counts = dept_by_term.get(term_key.lower(), Counter())
        top_dept = dept_counts.most_common(1)[0][0] if dept_counts else None
        enriched.append({**cand, "associated_department": top_dept})
    return enriched
