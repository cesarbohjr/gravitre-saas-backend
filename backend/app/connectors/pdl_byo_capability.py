"""People Data Labs BYO labeling — catalog honesty (no shared Gravitree key).

Tenant connects their own API key from https://dashboard.peopledatalabs.com/
Live enrich tools may run with that key; contact-level Memory/KG persistence
stays pack-guardrailed (STA-312).
"""
from __future__ import annotations

PDL_REQUIREMENT_NOTE = (
    "People Data Labs requires your own PDL API subscription (BYO). "
    "Gravitre never uses a shared platform key. "
    "Connect your API key from https://dashboard.peopledatalabs.com/ "
    "for person/company enrich. Contact-level Memory/KG writes remain gated."
)

PDL_CAPABILITY_NOTES = (
    "Can enrich people/companies? requires: your own People Data Labs API plan "
    "(BYO — no shared Gravitree key)",
    "Executor status: v1 live — person.enrich + company.enrich (session/cache only; no Memory/KG)",
)

BYO_PDL_REQUIREMENT_NOTES: dict[str, str] = {
    "pdl": PDL_REQUIREMENT_NOTE,
}

BYO_PDL_CAPABILITY_NOTES: dict[str, tuple[str, ...]] = {
    "pdl": PDL_CAPABILITY_NOTES,
}


def byo_pdl_requirement_note(vendor: str) -> str | None:
    return BYO_PDL_REQUIREMENT_NOTES.get(str(vendor or "").strip().lower())


def byo_pdl_capability_notes(vendor: str) -> list[str]:
    notes = BYO_PDL_CAPABILITY_NOTES.get(str(vendor or "").strip().lower())
    return list(notes) if notes else []
