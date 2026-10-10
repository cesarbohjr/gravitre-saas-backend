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

# Things a read returns as rows. Only these are checked against the read's
# result count; traffic metrics (sessions, users, clicks) are values inside a
# report, not rows, so comparing them to a row count is meaningless.
_RECORD_NOUNS = (
    r"deals?|invoices?|tickets?|customers?|contacts?|companies|"
    r"records?|results?|workflows?|runs?"
)
_CLAIM_NOUNS = (
    _RECORD_NOUNS + r"|sessions?|visitors?|users?|pageviews?|clicks?|impressions?"
)
_FOUND_COUNT = re.compile(
    rf"(?is)\b(?:found|listed|returned|pulled|there\s+are|i\s+(?:found|see))\s+"
    rf"(?:\*\*)?(\d+)(?:\*\*)?\s+(?:matching\s+)?(?:{_CLAIM_NOUNS})"
)
_FOUND_RECORD_COUNT = re.compile(
    rf"(?is)\b(?:found|listed|returned|pulled|there\s+are|i\s+(?:found|see))\s+"
    rf"(?:\*\*)?(\d+)(?:\*\*)?\s+(?:matching\s+)?(?:{_RECORD_NOUNS})"
)
_RECORD_COUNT = re.compile(
    rf"(?is)(?<![\d,.])(\d+)\s+(?:matching\s+)?(?:{_RECORD_NOUNS})\b"
)
# Report reads return metric values, not records; their row count says
# nothing about the numbers in the answer.
_REPORT_ACTION_PREFIXES = ("google_analytics.", "google_search_console.")

UNGROUNDED_FALLBACK = (
    "I don't have confirmed numbers for that yet, so I'd rather not guess. "
    "Want me to check the live data now?"
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


def claimed_record_counts(text: str) -> list[int]:
    """Counts of records the text claims (deals, tickets...), not metric values."""
    found: list[int] = []
    for pattern in (_FOUND_RECORD_COUNT, _RECORD_COUNT):
        for match in pattern.finditer(text or ""):
            raw = match.group(1)
            if raw.isdigit() and int(raw) not in found:
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
    if path in {"catalog_search_eligible", "listing_f2_read", "entity_join_store"}:
        return cleaned
    evidence = extract_provider_result_evidence(envelope)
    if not looks_like_business_result_claim(cleaned):
        return cleaned
    if evidence is None:
        return UNGROUNDED_FALLBACK
    if str(evidence.get("action_key") or "").startswith(_REPORT_ACTION_PREFIXES):
        return cleaned
    count = evidence.get("result_count")
    if isinstance(count, int):
        claimed = claimed_record_counts(cleaned)
        if claimed and any(n != count for n in claimed):
            if count == 0:
                return "I checked, and there are no matching records right now."
            return (
                f"I checked, and there {'are' if count != 1 else 'is'} {count} matching "
                f"record{'s' if count != 1 else ''}."
            )
    return cleaned
