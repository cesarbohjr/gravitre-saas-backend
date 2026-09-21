"""2.0-M bounded proactive operator: signal → investigate → recommend.

Never auto-writes. Dedupes identical alerts. Low-evidence signals stay silent.
"""
from __future__ import annotations

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
        if significance == "low" and not raw.get("notify_low"):
            continue
        seen.add(key)
        out.append(
            ProactiveRecommendation(
                signal_id=key,
                significance=significance,
                evidence=evidence,
                recommendation=rec,
                notify=significance in {"medium", "high"},
                write_allowed=False,
            )
        )
    return out
