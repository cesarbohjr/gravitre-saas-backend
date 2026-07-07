"""External knowledge connectors — Wikipedia, PubMed, and industry-specific public sources."""
from __future__ import annotations

import re
from typing import Any

import httpx

from app.config import Settings, get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)

WIKIPEDIA_API = "https://en.wikipedia.org/api/rest_v1/page/summary/"
PUBMED_ESEARCH = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
PUBMED_ESUMMARY = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi"

# Industry packs map to external provider ids used by gather_external_knowledge().
INDUSTRY_KNOWLEDGE_SOURCES: dict[str, list[str]] = {
    "general": ["wikipedia"],
    "healthcare": ["wikipedia", "pubmed"],
    "life_sciences": ["wikipedia", "pubmed"],
    "pharma": ["wikipedia", "pubmed"],
    "legal": ["wikipedia"],
    "finance": ["wikipedia", "sec_edgar"],
}

FINANCE_TOPIC_HINTS = re.compile(
    r"\b(sec|edgar|10-k|10-q|8-k|filing|earnings|revenue|stock|ticker|investor)\b",
    re.I,
)
MEDICAL_TOPIC_HINTS = re.compile(
    r"\b("
    r"clinical|patient|diagnosis|treatment|drug|medication|therapy|disease|symptom|"
    r"pubmed|medical|healthcare|hospital|physician|fda|trial|biomarker|oncology|"
    r"cardiology|pathology|epidemiology|pharma|pharmaceutical"
    r")\b",
    re.I,
)


def infer_external_knowledge_domain(topic: str, *, explicit_domain: str | None = None) -> str:
    if explicit_domain:
        normalized = explicit_domain.strip().lower().replace("-", "_")
        if normalized in INDUSTRY_KNOWLEDGE_SOURCES:
            return normalized
    if MEDICAL_TOPIC_HINTS.search(topic):
        return "healthcare"
    if FINANCE_TOPIC_HINTS.search(topic):
        return "finance"
    return "general"


def resolve_external_providers(domain: str) -> list[str]:
    return list(INDUSTRY_KNOWLEDGE_SOURCES.get(domain) or INDUSTRY_KNOWLEDGE_SOURCES["general"])


async def fetch_wikipedia_summary(topic: str, *, max_chars: int = 400) -> dict[str, Any] | None:
    slug = topic.strip().replace(" ", "_")[:120]
    if not slug:
        return None
    try:
        async with httpx.AsyncClient(timeout=8.0) as client:
            resp = await client.get(f"{WIKIPEDIA_API}{slug}")
            if resp.status_code != 200:
                return None
            data = resp.json()
            extract = str(data.get("extract") or "")[:max_chars]
            if not extract:
                return None
            return {
                "type": "external_wikipedia",
                "title": data.get("title") or topic,
                "summary": extract,
                "source": data.get("content_urls", {}).get("desktop", {}).get("page")
                or f"https://en.wikipedia.org/wiki/{slug}",
                "freshness_score": 0.7,
                "trust_score": 0.75,
                "provider": "wikipedia",
            }
    except Exception as exc:  # noqa: BLE001
        logger.debug("wikipedia_fetch_failed topic=%s error=%s", topic, exc)
        return None


async def fetch_pubmed_summaries(topic: str, *, max_results: int = 3) -> list[dict[str, Any]]:
    """Best-effort PubMed summaries via NCBI E-utilities (no API key required)."""
    query = topic.strip()[:240]
    if not query:
        return []
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            search_resp = await client.get(
                PUBMED_ESEARCH,
                params={
                    "db": "pubmed",
                    "term": query,
                    "retmax": max(1, min(max_results, 5)),
                    "retmode": "json",
                },
            )
            if search_resp.status_code != 200:
                return []
            search_data = search_resp.json()
            id_list = search_data.get("esearchresult", {}).get("idlist") or []
            if not id_list:
                return []

            summary_resp = await client.get(
                PUBMED_ESUMMARY,
                params={
                    "db": "pubmed",
                    "id": ",".join(id_list),
                    "retmode": "json",
                },
            )
            if summary_resp.status_code != 200:
                return []
            summary_data = summary_resp.json()
            result_block = summary_data.get("result") or {}
            findings: list[dict[str, Any]] = []
            for pmid in id_list:
                row = result_block.get(str(pmid)) or {}
                title = str(row.get("title") or "").strip()
                if not title:
                    continue
                journal = ""
                source_meta = row.get("source") or row.get("fulljournalname")
                if isinstance(source_meta, str):
                    journal = source_meta
                findings.append(
                    {
                        "type": "external_pubmed",
                        "title": title[:240],
                        "summary": title[:400],
                        "source": f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/",
                        "provider": "pubmed",
                        "pubmed_id": str(pmid),
                        "journal": journal[:120] if journal else None,
                        "freshness_score": 0.85,
                        "trust_score": 0.9,
                    }
                )
            return findings
    except Exception as exc:  # noqa: BLE001
        logger.debug("pubmed_fetch_failed topic=%s error=%s", topic, exc)
        return []


async def fetch_sec_edgar_summaries(topic: str, *, max_results: int = 3) -> list[dict[str, Any]]:
    query = topic.strip()[:120]
    if not query:
        return []
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(
                "https://efts.sec.gov/LATEST/search-index",
                params={"q": query, "dateRange": "custom", "startdt": "2020-01-01", "forms": "10-K,10-Q,8-K"},
                headers={"User-Agent": "Gravitre Intelligence research@gravitre.ai"},
            )
            if resp.status_code != 200:
                return []
            data = resp.json()
            hits = ((data.get("hits") or {}).get("hits") or [])[:max_results]
            findings: list[dict[str, Any]] = []
            for hit in hits:
                source = hit.get("_source") or {}
                title = str(source.get("display_names") or source.get("entity_name") or query)[:240]
                form = str(source.get("form_type") or "SEC filing")
                findings.append(
                    {
                        "type": "external_sec_edgar",
                        "title": title,
                        "summary": f"{form} filing matched for {query}"[:400],
                        "source": f"https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&company={query}",
                        "provider": "sec_edgar",
                        "freshness_score": 0.8,
                        "trust_score": 0.88,
                    }
                )
            return findings
    except Exception as exc:  # noqa: BLE001
        logger.debug("sec_edgar_fetch_failed topic=%s error=%s", topic, exc)
        return []


async def gather_external_knowledge(
    topic: str,
    *,
    settings: Settings | None = None,
    include_wikipedia: bool = True,
    include_pubmed: bool | None = None,
    domain: str | None = None,
) -> list[dict[str, Any]]:
    """Best-effort public knowledge without duplicating Tavily web search."""
    _ = settings
    resolved_domain = infer_external_knowledge_domain(topic, explicit_domain=domain)
    providers = resolve_external_providers(resolved_domain)
    findings: list[dict[str, Any]] = []

    use_wikipedia = include_wikipedia and "wikipedia" in providers
    use_pubmed = include_pubmed if include_pubmed is not None else "pubmed" in providers
    use_sec = "sec_edgar" in providers

    if use_wikipedia:
        wiki = await fetch_wikipedia_summary(topic)
        if wiki:
            findings.append(wiki)

    if use_pubmed:
        findings.extend(await fetch_pubmed_summaries(topic))

    if use_sec:
        findings.extend(await fetch_sec_edgar_summaries(topic))

    return findings


def detect_source_contradictions(findings: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Lightweight contradiction flags across external findings."""
    from app.services.context_conflict_detection import _has_opposing_sentiment

    conflicts: list[dict[str, Any]] = []
    for index, left in enumerate(findings):
        left_text = str(left.get("summary") or "")
        for right in findings[index + 1 :]:
            right_text = str(right.get("summary") or "")
            if _has_opposing_sentiment(left_text, right_text):
                conflicts.append(
                    {
                        "source_a": left.get("source"),
                        "source_b": right.get("source"),
                        "requires_human_review": True,
                    }
                )
    return conflicts
