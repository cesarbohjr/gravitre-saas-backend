"""Invariant: no provider-derived business claim without evidenced results.

A proposed action, connected connector, pending plan, LIVE fallthrough,
or model expectation is not evidence. Applies to numeric and non-numeric
claims (deals, revenue, invoices, customers, tickets, traffic, workflows).
"""
from __future__ import annotations

import re
from typing import Any

EVIDENCE_PROVIDER = "provider_observation"
EVIDENCE_CACHE = "authorized_cache"
EVIDENCE_IDENTIFIED = "identified_source"

_CLAIM_NOUNS = (
    r"deals?|invoices?|tickets?|customers?|contacts?|companies|"
    r"sessions?|visitors?|users?|pageviews?|clicks?|impressions?|"
    r"records?|results?|workflows?|runs?"
)
_FOUND_COUNT = re.compile(
    rf"(?is)\b(?:found|listed|returned|pulled|there\s+are|i\s+(?:found|see))\s+"
    rf"(?:\*\*)?(\d+)(?:\*\*)?\s+(?:matching\s+)?(?:{_CLAIM_NOUNS})"
)
_NOUN_COUNT = re.compile(
    rf"(?is)\b(\d+)\s+(?:matching\s+)?(?:{_CLAIM_NOUNS})\b"
)
_REVENUE = re.compile(r"(?is)\b(?:revenue|pipeline\s+value|arr|mrr)\b.{0,24}\b(\d[\d,]*)")
_TRAFFIC_METRIC = re.compile(
    r"(?is)\b(\d[\d,]*)\s+(?:active\s+users|sessions|pageviews|clicks)\b"
)

UNGROUNDED_FALLBACK = (
    "I compiled that business read but I don't have a verified result from the "
    "connected system yet, so I can't report counts or outcomes. Ask again and "
    "I'll run the live read."
)


def extract_provider_result_evidence(envelope: dict[str, Any] | None) -> dict[str, Any] | None:
    env = envelope if isinstance(envelope, dict) else {}
    data = env.get("data") if isinstance(env.get("data"), dict) else {}
    raw = env.get("provider_result_evidence")
    if not isinstance(raw, dict):
        raw = data.get("provider_result_evidence") if isinstance(data, dict) else None
    if not isinstance(raw, dict):
        return None
    kind = str(raw.get("kind") or "").strip()
    if kind not in {EVIDENCE_PROVIDER, EVIDENCE_CACHE, EVIDENCE_IDENTIFIED}:
        return None
    if kind == EVIDENCE_PROVIDER and not raw.get("provider_invoked"):
        return None
    if kind == EVIDENCE_CACHE and not raw.get("freshness"):
        return None
    if kind == EVIDENCE_IDENTIFIED and not raw.get("source"):
        return None
    if raw.get("success") is False:
        return None
    return raw


def evidence_from_observation(
    *,
    action_key: str,
    result_count: int,
    observation_id: str | None,
    plan_id: str | None,
    step_id: str | None,
    success: bool,
    provider_invoked: bool,
) -> dict[str, Any]:
    return {
        "kind": EVIDENCE_PROVIDER,
        "action_key": action_key,
        "result_count": int(result_count),
        "observation_id": observation_id,
        "plan_id": plan_id,
        "step_id": step_id,
        "success": bool(success),
        "provider_invoked": bool(provider_invoked),
        "empty": int(result_count) == 0,
    }


def claimed_business_numbers(text: str) -> list[int]:
    found: list[int] = []
    for pattern in (_FOUND_COUNT, _NOUN_COUNT, _REVENUE, _TRAFFIC_METRIC):
        for match in pattern.finditer(text or ""):
            raw = match.group(1).replace(",", "")
            if raw.isdigit():
                found.append(int(raw))
    return found


def looks_like_business_result_claim(text: str) -> bool:
    low = (text or "").lower()
    if _FOUND_COUNT.search(text or ""):
        return True
    if any(token in low for token in (" in your crm", "in the connected crm", "pipeline")) and re.search(
        r"\b\d+\b", low
    ):
        return True
    if "deal" in low and re.search(r"\b\d+\b", low):
        return True
    if any(token in low for token in ("invoice", "ticket", "session", "visitor", "revenue")) and re.search(
        r"\b\d+\b", low
    ):
        return True
    return False


def terminal_status_for_read(
    *,
    step_status: str | None,
    fallthrough: bool,
    blocked_auth: bool,
    preflight_ok: bool,
    provider_error: bool,
    provider_invoked: bool,
    success: bool,
    result_count: int | None,
    partial: bool,
) -> str:
    if blocked_auth:
        return "blocked"
    if not preflight_ok:
        return "blocked"
    if provider_error:
        return "failed"
    if fallthrough and not provider_invoked:
        return "pending"
    if str(step_status or "").lower() == "pending" and not provider_invoked:
        return "pending"
    if partial:
        return "partial"
    if success and provider_invoked:
        return "completed"
    if result_count == 0 and provider_invoked and success:
        return "completed"
    return "pending"


def apply_provider_result_grounding(text: str, envelope: dict[str, Any] | None) -> str:
    """Drop unsupported business claims. Empty verified results stay complete."""
    cleaned = (text or "").strip()
    if not cleaned:
        return cleaned
    env = envelope if isinstance(envelope, dict) else {}
    data = env.get("data") if isinstance(env.get("data"), dict) else {}
    path = str(env.get("execution_path") or data.get("execution_path") or "")
    if path == "catalog_search_eligible":
        return cleaned
    evidence = extract_provider_result_evidence(envelope)
    if not looks_like_business_result_claim(cleaned):
        return cleaned
    if evidence is None:
        return UNGROUNDED_FALLBACK
    count = evidence.get("result_count")
    if isinstance(count, int):
        claimed = claimed_business_numbers(cleaned)
        if claimed and any(n != count for n in claimed):
            if count == 0:
                return "The connected system returned no matching records for that read."
            return (
                f"The connected system returned {count} matching record"
                f"{'s' if count != 1 else ''} for that read."
            )
    return cleaned
