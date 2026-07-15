"""SEMrush / Ahrefs BYO labeling — catalog honesty (no shared Gravitree key).

v1 read executors are live when the org connects its own API key.
Labeling stays BYO-tier (same transparency bar as ZoomInfo / LinkedIn Sales Navigator).
"""
from __future__ import annotations

SEMRUSH_REQUIREMENT_NOTE = (
    "SEMrush requires your own SEMrush API subscription (BYO). "
    "Gravitre never uses a shared platform key. "
    "Connect your API key to run domain overview, organic keywords, and backlinks."
)

AHREFS_REQUIREMENT_NOTE = (
    "Ahrefs requires your own Ahrefs API subscription (BYO). "
    "Gravitre never uses a shared platform key. "
    "Connect your API key to run domain rating, organic keywords, and backlinks."
)

SEMRUSH_CAPABILITY_NOTES = (
    "Can run SEO reports? requires: your own SEMrush API plan (BYO — no shared Gravitree key)",
    "Executor status: v1 reads live — domain.overview, keywords.list, backlinks.list",
)

AHREFS_CAPABILITY_NOTES = (
    "Can run SEO reports? requires: your own Ahrefs API plan (BYO — no shared Gravitree key)",
    "Executor status: v1 reads live — domain.rating, keywords.list, backlinks.list",
)

BYO_SEO_REQUIREMENT_NOTES: dict[str, str] = {
    "semrush": SEMRUSH_REQUIREMENT_NOTE,
    "ahrefs": AHREFS_REQUIREMENT_NOTE,
}

BYO_SEO_CAPABILITY_NOTES: dict[str, tuple[str, ...]] = {
    "semrush": SEMRUSH_CAPABILITY_NOTES,
    "ahrefs": AHREFS_CAPABILITY_NOTES,
}


def byo_seo_requirement_note(vendor: str) -> str | None:
    return BYO_SEO_REQUIREMENT_NOTES.get(str(vendor or "").strip().lower())


def byo_seo_capability_notes(vendor: str) -> list[str]:
    notes = BYO_SEO_CAPABILITY_NOTES.get(str(vendor or "").strip().lower())
    return list(notes) if notes else []
