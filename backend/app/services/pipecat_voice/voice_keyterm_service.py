"""Voice 3.0 Phase 3 — contextual Deepgram Flux keyterms and turn-mode presets."""
from __future__ import annotations

import re
from typing import Any

# Presets align with HTTP turn-taking Eager/Normal/Patient semantics mapped to Flux EOT.
FLUX_TURN_PRESETS: dict[str, tuple[float, float]] = {
    "fast": (0.4, 0.55),
    "balanced": (0.5, 0.7),
    "patient": (0.6, 0.85),
}

_GRAVITRE_CORE = (
    "Gravitre",
    "operator",
    "workflow",
    "connector",
    "ActionSpec",
    "unified turn",
)

_VENDOR_LABELS: dict[str, str] = {
    "hubspot": "HubSpot",
    "salesforce": "Salesforce",
    "google_drive": "Google Drive",
    "google_calendar": "Google Calendar",
    "google_analytics": "Google Analytics",
    "microsoft_teams": "Microsoft Teams",
    "microsoft_outlook": "Microsoft Outlook",
    "quickbooks": "QuickBooks",
    "stripe": "Stripe",
    "slack": "Slack",
    "notion": "Notion",
    "zendesk": "Zendesk",
    "intercom": "Intercom",
    "apollo": "Apollo",
    "clay": "Clay",
    "linkedin": "LinkedIn",
    "github": "GitHub",
    "jira": "Jira",
    "asana": "Asana",
    "monday": "Monday.com",
    "airtable": "Airtable",
    "shopify": "Shopify",
    "twilio": "Twilio",
}

_DEPARTMENT_TERMS: dict[str, tuple[str, ...]] = {
    "sales": ("pipeline", "deal stage", "quota", "prospect", "close rate"),
    "marketing": ("campaign", "conversion rate", "lead generation", "attribution"),
    "finance": ("accounts receivable", "cash flow", "invoice", "reconciliation"),
    "legal": ("contract", "compliance", "NDA", "terms of service"),
    "hr": ("onboarding", "payroll", "benefits", "performance review"),
    "support": ("ticket", "escalation", "SLA", "customer success"),
    "operations": ("process", "SOP", "handoff", "runbook"),
    "engineering": ("deployment", "incident", "pull request", "API"),
    "security": ("SOC 2", "audit log", "access control", "vulnerability"),
}


def _vendor_label(vendor_id: str) -> str:
    key = vendor_id.strip().lower()
    if key in _VENDOR_LABELS:
        return _VENDOR_LABELS[key]
    return key.replace("_", " ").title()


def _normalize_term(term: str) -> str:
    cleaned = re.sub(r"\s+", " ", term.strip())
    return cleaned


def _dedupe_terms(terms: list[str], *, max_terms: int) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for raw in terms:
        term = _normalize_term(raw)
        if not term or len(term) > 80:
            continue
        key = term.casefold()
        if key in seen:
            continue
        seen.add(key)
        out.append(term)
        if len(out) >= max_terms:
            break
    return out


def resolve_flux_eot_settings(settings: Any) -> tuple[float | None, float | None]:
    """Resolve Flux eager/EOT thresholds — turn-mode preset wins when set."""
    mode = getattr(settings, "voice_flux_turn_mode", None)
    if mode:
        preset = FLUX_TURN_PRESETS.get(str(mode).strip().lower())
        if preset:
            return preset
    eager = getattr(settings, "voice_pipecat_flux_eager_eot", None)
    eot = getattr(settings, "voice_pipecat_flux_eot", None)
    return eager, eot


def resolve_flux_turn_mode_label(settings: Any) -> str | None:
    mode = getattr(settings, "voice_flux_turn_mode", None)
    if not mode:
        return None
    key = str(mode).strip().lower()
    return key if key in FLUX_TURN_PRESETS else None


def build_voice_keyterms(
    *,
    enabled: bool,
    org_name: str | None = None,
    agent: dict[str, Any] | None = None,
    connected_integrations: list[str] | None = None,
    max_terms: int = 50,
) -> tuple[list[str], dict[str, Any]]:
    """Build a bounded keyterm list for Deepgram Flux (no raw audio/PII)."""
    meta: dict[str, Any] = {
        "keyterms_enabled": bool(enabled),
        "keyterm_count": 0,
        "keyterm_sources": [],
    }
    if not enabled:
        return [], meta

    terms: list[str] = list(_GRAVITRE_CORE)
    sources: list[str] = ["gravitre_core"]

    org = _normalize_term(org_name or "")
    if org:
        terms.append(org)
        sources.append("org_name")

    agent_name = _normalize_term(str((agent or {}).get("name") or ""))
    if agent_name:
        terms.append(agent_name)
        sources.append("agent_name")

    department = str((agent or {}).get("department") or "").strip().lower()
    if department:
        for key, dept_terms in _DEPARTMENT_TERMS.items():
            if key in department:
                terms.extend(dept_terms)
                sources.append(f"department:{key}")
                break

    connected = [str(c).strip().lower() for c in (connected_integrations or []) if str(c).strip()]
    for vendor in connected:
        terms.append(_vendor_label(vendor))
    if connected:
        sources.append("connected_integrations")

    capped = _dedupe_terms(terms, max_terms=max(1, min(int(max_terms or 50), 100)))
    meta["keyterm_count"] = len(capped)
    meta["keyterm_sources"] = sorted(set(sources))
    return capped, meta
