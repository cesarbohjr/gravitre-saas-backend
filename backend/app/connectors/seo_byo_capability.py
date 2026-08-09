"""SEMrush / Ahrefs BYO labeling — catalog honesty (no shared Gravitre key).

v1 read executors are live when the org connects its own API key.
Labeling stays BYO-tier (same transparency bar as ZoomInfo / LinkedIn Sales Navigator).
"""
from __future__ import annotations

SEMRUSH_REQUIREMENT_NOTE = (
    "SEMrush requires your own SEMrush API subscription (BYO). "
    "Gravitre never uses a shared platform key. "
    "Connect your API key for domain/keyword/backlink reads plus projects and position tracking."
)

AHREFS_REQUIREMENT_NOTE = (
    "Ahrefs requires your own Ahrefs API subscription (BYO). "
    "Gravitre never uses a shared platform key. "
    "Connect your API key for domain rating/keywords/backlinks plus projects and rank tracker."
)

SEMRUSH_CAPABILITY_NOTES = (
    "Can run SEO reports? requires: your own SEMrush API plan (BYO — no shared Gravitre key)",
    "Executor status: v1–v3 live — domain/keywords/backlinks + projects/tracking + competitors/exports",
)

AHREFS_CAPABILITY_NOTES = (
    "Can run SEO reports? requires: your own Ahrefs API plan (BYO — no shared Gravitre key)",
    "Executor status: v1–v3 live — DR/keywords/backlinks + projects/rank tracker + competitors/top pages",
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
