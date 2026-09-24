"""2.0-M bounded proactive operator: signal → investigate → recommend.

Never auto-writes. Dedupes identical alerts. Low-evidence signals stay silent.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Literal

Significance = Literal["none", "low", "medium", "high"]


@dataclass(frozen=True)
class ProactiveRecommendation:
    signal_id: str
    significance: Significance
    evidence: tuple[str, ...]
    recommendation: str
    notify: bool
    write_allowed: bool = False
    investigation: str = "safe_read"
    rank_score: float = 0.0
    axes: dict[str, float] | None = None


ATTENTION_AXES = (
    "impact",
    "urgency",
    "confidence",
    "relevance",
    "actionability",
    "novelty",
)
_AXIS_WEIGHTS = {
    "impact": 0.25,
    "urgency": 0.20,
    "confidence": 0.20,  # confidence-honesty-ok: ranking weight, not user-facing
    "relevance": 0.15,
    "actionability": 0.10,
    "novelty": 0.10,
}
HIGH_RISK_WRITE_KINDS = frozenset(
    {
        "auto_write",
        "high_risk_write",
        "send_email",
        "create_list",
        "mutate",
        "execute_write",
    }
)
MAX_QUIET_NOTICES = 3


def _is_high_risk_write_signal(signal: dict[str, Any]) -> bool:
    kind = str(signal.get("kind") or "").strip().lower()
    if kind in HIGH_RISK_WRITE_KINDS:
        return True
    if signal.get("write_requested") or signal.get("auto_write"):
        return True
    return False


def attention_axes_for_signal(
    signal: dict[str, Any],
    *,
    significance: Significance,
    evidence: tuple[str, ...],
) -> dict[str, float]:
    """Score a notice for ranking. Confidence is evidence-backed, not a product claim."""
    kind = str(signal.get("kind") or "").strip().lower()
    connector = str(signal.get("connector") or "").strip()
    impact = {"high": 0.9, "medium": 0.55, "low": 0.2, "none": 0.0}[significance]
    if kind in {"auth_expired", "pending_auth", "token_expired"}:
        urgency = 0.85
        actionability = 0.7
    elif kind in {"metric_moved", "threshold"}:
        urgency = 0.55
        actionability = 0.5
    else:
        urgency = 0.25
        actionability = 0.35
    confidence = min(1.0, 0.35 + 0.2 * len(evidence))  # confidence-honesty-ok: ranking prior, not user-facing
    relevance = 0.85 if connector else 0.4
    return {
        "impact": impact,
        "urgency": urgency,
        "confidence": confidence,
        "relevance": relevance,
        "actionability": actionability,
        "novelty": 1.0,
    }


def _rank_score(axes: dict[str, float]) -> float:
    return round(
        sum(float(axes.get(axis, 0.0)) * _AXIS_WEIGHTS[axis] for axis in ATTENTION_AXES),
        4,
    )


def _dedupe_key(signal: dict[str, Any]) -> str:
    return str(
        signal.get("dedupe_key")
        or signal.get("id")
        or f"{signal.get('kind')}:{signal.get('connector')}:{signal.get('reason')}"
    )


def evaluate_business_signals(
    signals: list[dict[str, Any]] | None,
    *,
    prior_alert_ids: set[str] | frozenset[str] | None = None,
) -> list[ProactiveRecommendation]:
    seen = set(prior_alert_ids or ())
    out: list[ProactiveRecommendation] = []
    for raw in signals or []:
        if not isinstance(raw, dict):
            continue
        if _is_high_risk_write_signal(raw):
            continue
        key = _dedupe_key(raw)
        if key in seen:
            continue
        evidence = tuple(str(item) for item in (raw.get("evidence") or []) if str(item).strip())
        kind = str(raw.get("kind") or "").strip()
        if not evidence:
            continue
        if kind in {"auth_expired", "pending_auth", "token_expired"}:
            significance: Significance = "high"
            rec = (
                f"{raw.get('connector') or 'A connected system'} needs re-authorization "
                "before that source can be read. No substitute source was used."
            )
        elif kind in {"metric_moved", "threshold"}:
            significance = "medium"
            rec = str(raw.get("recommendation") or "Review the supporting evidence before acting.")
        else:
            significance = "low"
            rec = str(raw.get("recommendation") or "Investigate the supporting evidence.")
        if re.search(r"(?i)\b(enable|disable|certified|trained)\b|\$\d", rec):
            rec = "Review the supporting evidence before acting."
        if significance == "low" and not raw.get("notify_low"):
            continue
        seen.add(key)
        axes = attention_axes_for_signal(raw, significance=significance, evidence=evidence)
        out.append(
            ProactiveRecommendation(
                signal_id=key,
                significance=significance,
                evidence=evidence,
                recommendation=rec,
                notify=significance in {"medium", "high"},
                write_allowed=False,
                investigation="safe_read",
                rank_score=_rank_score(axes),
                axes=axes,
            )
        )
    out.sort(key=lambda item: item.rank_score, reverse=True)
    return out


def rank_safe_read_notices(
    signals: list[dict[str, Any]] | None,
    *,
    prior_alert_ids: set[str] | frozenset[str] | None = None,
    limit: int = MAX_QUIET_NOTICES,
) -> list[ProactiveRecommendation]:
    """3.0-J: ranked safe-READ notices. Never auto high-risk WRITE. Extra signals stay quiet."""
    recs = evaluate_business_signals(signals, prior_alert_ids=prior_alert_ids)
    cap = max(0, int(limit))
    return recs[:cap]


def format_ranked_read_notices(recommendations: list[ProactiveRecommendation]) -> str:
    if not recommendations:
        return "I don't have a source-backed condition that needs attention right now. I won't invent one."
    lines = ["I noticed a few items worth a safe read — I will not write anything:"]
    for rec in recommendations:
        lines.append(f"- {rec.recommendation}")
    return "\n".join(lines)


def signals_from_website_readiness(readiness: dict[str, dict[str, Any]] | None) -> list[dict[str, Any]]:
    signals: list[dict[str, Any]] = []
    for vendor, row in (readiness or {}).items():
        if not isinstance(row, dict) or row.get("executable"):
            continue
        if not row.get("present"):
            continue
        reason = str(row.get("blocking_reason") or row.get("auth_status") or "not_executable")
        kind = "pending_auth" if "pending" in reason else "token_expired"
        signals.append(
            {
                "id": f"{vendor}:{kind}",
                "kind": kind,
                "connector": vendor,
                "evidence": [reason],
            }
        )
    return signals


def patch_task_state_with_recommendations(
    task_state: dict[str, Any] | None,
    recommendations: list[ProactiveRecommendation],
) -> dict[str, Any]:
    state = dict(task_state or {})
    state["proactive_operator"] = [
        {
            "signal_id": rec.signal_id,
            "significance": rec.significance,
            "evidence": list(rec.evidence),
            "recommendation": rec.recommendation,
            "notify": rec.notify,
            "write_allowed": False,
            "investigation": "safe_read",
            "rank_score": rec.rank_score,
        }
        for rec in recommendations
    ]
    return state


_ATTENTION_INTENT = re.compile(
    r"(?is)\b("
    r"what(?:'s| is)?\s+(?:important|urgent)|"
    r"what needs (?:my )?attention|"
    r"anything (?:i should|to) (?:know|watch)|"
    r"what should i look at"
    r")\b"
)


def is_attention_intent(message: str) -> bool:
    return bool(_ATTENTION_INTENT.search(message or ""))


def try_ranked_attention_turn(
    *,
    message: str,
    org_id: str,
    client: Any,
    settings: Any,
    task_state: dict[str, Any] | None,
) -> dict[str, Any] | None:
    """3.0-J: ranked safe READ notices from eligible evidence. Never auto WRITE."""
    if not is_attention_intent(message):
        return None
    from app.services.website_source_status import website_source_readiness

    readiness = website_source_readiness(client, org_id, settings)
    recs = rank_safe_read_notices(signals_from_website_readiness(readiness))
    merged = patch_task_state_with_recommendations(task_state, recs)
    return {
        "stop_pipeline": True,
        "dialogue_mode": "answer",
        "message": format_ranked_read_notices(recs),
        "task_state": merged,
        "execution_path": "proactive_attention_3_0_j",
        "provider_write": False,
        "write_allowed": False,
    }


_ATTENTION_INTENT = re.compile(
    r"(?is)\b("
    r"what(?:'s| is)?\s+(?:important|urgent)|"
    r"what needs (?:my )?attention|"
    r"anything (?:i should|to) (?:know|watch)|"
    r"what should i look at"
    r")\b"
)


def is_attention_intent(message: str) -> bool:
    return bool(_ATTENTION_INTENT.search(message or ""))


def try_ranked_attention_turn(
    *,
    message: str,
    org_id: str,
    client: Any,
    settings: Any,
    task_state: dict[str, Any] | None,
) -> dict[str, Any] | None:
    """3.0-J: ranked safe READ notices from eligible evidence. Never auto WRITE."""
    if not is_attention_intent(message):
        return None
    from app.services.website_source_status import website_source_readiness

    readiness = website_source_readiness(client, org_id, settings)
    recs = rank_safe_read_notices(signals_from_website_readiness(readiness))
    merged = patch_task_state_with_recommendations(task_state, recs)
    return {
        "stop_pipeline": True,
        "dialogue_mode": "answer",
        "message": format_ranked_read_notices(recs),
        "task_state": merged,
        "execution_path": "proactive_attention_3_0_j",
        "provider_write": False,
        "write_allowed": False,
    }
