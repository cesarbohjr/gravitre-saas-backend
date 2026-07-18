"""Phase 3 — ONE PackSourceDefinition registration path for cascade retrieval."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.core.logging import get_logger

logger = get_logger(__name__)


@dataclass(frozen=True)
class PackSourceDefinition:
    id: str
    vendor: str
    pack_id: str
    title: str
    keywords: tuple[str, ...] = ()
    reference_summary: str = ""
    preferred_source_types: tuple[str, ...] = ()


_REGISTRY: dict[str, PackSourceDefinition] = {}
_BOOTSTRAPPED = False

_PACK_VENDOR_PREFERENCES: dict[str, tuple[str, ...]] = {
    "msp-intelligence-pack": ("microsoft_docs", "cisa", "nvd", "vendor_kb"),
    "marketing-intelligence-pack": ("industry_report", "competitor_news", "market_research"),
    "executive-intelligence-pack": ("macro_indicator", "regulatory_filing", "industry_report"),
}

_VENDOR_KEYWORDS: dict[str, tuple[str, ...]] = {
    "fred": ("gdp", "unemployment", "inflation", "cpi", "macro", "economy", "interest", "rate"),
    "sec_edgar": ("sec", "filing", "10-k", "10-q", "8-k", "edgar", "regulatory", "earnings"),
    "world_bank": ("world bank", "gdp", "indicator", "country", "development"),
    "oecd": ("oecd", "mei", "economic", "indicator"),
    "nvd": ("cve", "vulnerability", "nvd", "security", "patch"),
    "cisa_kev": ("cisa", "kev", "exploit", "vulnerability", "zero-day"),
    "google_search_console": ("gsc", "search console", "seo", "organic", "keyword", "ranking"),
    "ahrefs": ("ahrefs", "backlink", "brand radar", "ai visibility"),
    "finseo": ("finseo", "ai visibility", "mentions", "geo"),
    "ai_visibility_ui": ("ai search", "chatgpt", "perplexity", "copilot", "visibility"),
    "gravitre_platform": ("platform", "integration", "approval", "health", "connector"),
}


def register_source(definition: PackSourceDefinition) -> None:
    """Register a pack source definition (idempotent by id)."""
    key = str(definition.id or "").strip()
    if not key:
        raise ValueError("PackSourceDefinition.id required")
    _REGISTRY[key] = definition


def registered_sources() -> frozenset[str]:
    return frozenset(_REGISTRY.keys())


def list_sources_for_pack(pack_id: str) -> list[PackSourceDefinition]:
    pid = str(pack_id or "").strip()
    return [d for d in _REGISTRY.values() if d.pack_id == pid]


def list_sources_for_vendor(vendor: str) -> list[PackSourceDefinition]:
    v = str(vendor or "").strip().lower()
    return [d for d in _REGISTRY.values() if d.vendor == v]


def get_source(source_id: str) -> PackSourceDefinition | None:
    return _REGISTRY.get(str(source_id or "").strip())


def ensure_pack_sources_registered() -> None:
    """Bootstrap registry from PACK_VENDOR_MAP + marketplace catalog assignments."""
    global _BOOTSTRAPPED
    if _BOOTSTRAPPED:
        return
    try:
        from app.intelligence_packs.shared.kpis import PACK_VENDOR_MAP
        from app.marketplace.intelligence_packs.catalog import list_intelligence_pack_specs

        for pack_id, vendors in PACK_VENDOR_MAP.items():
            pack_prefs = _PACK_VENDOR_PREFERENCES.get(pack_id, ())
            for vendor in vendors:
                v = str(vendor).strip().lower()
                keywords = _VENDOR_KEYWORDS.get(v, (v.replace("_", " "),))
                register_source(
                    PackSourceDefinition(
                        id=f"{pack_id}:{v}",
                        vendor=v,
                        pack_id=pack_id,
                        title=f"{v.replace('_', ' ').title()} ({pack_id})",
                        keywords=keywords,
                        preferred_source_types=pack_prefs,
                    )
                )

        for spec in list_intelligence_pack_specs():
            for assignment in spec.assignments:
                if assignment.source_type != "knowledge_pack":
                    continue
                source_id = f"{spec.pack_id}:{assignment.source_id}"
                label_words = tuple(
                    word.strip().lower()
                    for word in f"{assignment.label} {assignment.reference_summary}".split()
                    if len(word.strip()) > 2
                )[:12]
                register_source(
                    PackSourceDefinition(
                        id=source_id,
                        vendor=str(assignment.source_id).split("-")[0].lower(),
                        pack_id=spec.pack_id,
                        title=assignment.label,
                        keywords=label_words,
                        reference_summary=assignment.reference_summary,
                    )
                )
    except Exception as exc:  # noqa: BLE001
        logger.warning("pack_source_bootstrap_partial err=%s", exc)
    _BOOTSTRAPPED = True


def pack_source_catalog() -> list[dict[str, Any]]:
    """Serializable catalog for tests and explainability."""
    ensure_pack_sources_registered()
    return [
        {
            "id": d.id,
            "vendor": d.vendor,
            "pack_id": d.pack_id,
            "title": d.title,
            "keywords": list(d.keywords),
            "preferred_source_types": list(d.preferred_source_types),
        }
        for d in sorted(_REGISTRY.values(), key=lambda row: row.id)
    ]
