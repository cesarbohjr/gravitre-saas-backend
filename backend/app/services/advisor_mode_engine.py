"""Advisor mode — proactive business partner briefs (Wave 5)."""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Any

from app.config import Settings, get_settings
from app.core.logging import get_logger
from app.services.business_signals_engine import get_business_signals_engine
from app.services.confidence_honesty import (
    CONFIDENCE_SOURCE_ADVISOR,
    CONFIDENCE_SOURCE_INSUFFICIENT,
    label_confidence,
)
from app.services.decision_intelligence_service import get_decision_intelligence_service
from app.services.recommendation_quality_engine import get_recommendation_quality_engine
from app.services.research_service import get_research_service
from app.services.user_intelligence import get_user_intelligence_service

logger = get_logger(__name__)


class AdvisorModeEngine:
    """
    Signature advisor capability: what changed, why it matters, what to do,
    expected impact, confidence, and evidence — advisory only.
    """

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self._signals = get_business_signals_engine(self.settings)
        self._quality = get_recommendation_quality_engine(self.settings)
        self._decision = get_decision_intelligence_service(self.settings)
        self._research = get_research_service(self.settings)
        self._user_intel = get_user_intelligence_service()

    async def generate_brief(
        self,
        org_id: str,
        user_id: str,
        *,
        department: str | None = None,
        query: str | None = None,
        client: Any | None = None,
        include_predictive: bool = True,
    ) -> dict[str, Any]:
        dept = (department or "operations").strip().lower()
        # Single collect — department brief previously re-ran collect_signals (2–3× stack).
        signals_payload = await self._signals.collect_signals(
            org_id,
            department=dept,
            query=query,
            client=client,
            include_predictive=include_predictive,
        )
        signals = list(signals_payload.get("signals") or [])

        async def _decision_recs() -> list[dict[str, Any]]:
            if not query:
                return []
            try:
                decision_payload = await self._decision.recommend_next_action(org_id, query)
                return list(decision_payload.get("recommendations") or [])
            except Exception as exc:  # noqa: BLE001
                logger.debug("advisor_decision_skipped org_id=%s error=%s", org_id, exc)
                return []

        async def _daily() -> dict[str, Any]:
            try:
                return await self._user_intel.get_daily_briefing(
                    self.settings,
                    org_id=org_id,
                    user_id=user_id,
                )
            except Exception as exc:  # noqa: BLE001
                logger.debug("advisor_daily_skipped org_id=%s error=%s", org_id, exc)
                return {}

        decision_recs, daily, dept_brief = await asyncio.gather(
            _decision_recs(),
            _daily(),
            self._signals.generate_department_brief(
                org_id,
                dept,
                client=client,
                signals_payload=signals_payload,
            ),
        )

        ranked_actions = await self._quality.filter_advisor_actions(
            org_id,
            self._merge_actions(signals, decision_recs),
            department=dept,
        )

        what_changed = list(dept_brief.get("what_changed") or [])
        for bullet in daily.get("bullets") or []:
            if isinstance(bullet, dict) and bullet.get("text"):
                what_changed.append(str(bullet["text"]))

        risks = [row for row in signals if row.get("signal_type") in {"risk", "alert"}][:3]
        opportunities = [row for row in signals if row.get("signal_type") == "opportunity"][:3]

        if ranked_actions:
            confidence = round(
                sum(float(row.get("quality_score") or row.get("confidence") or 0.0) for row in ranked_actions[:5])
                / max(len(ranked_actions[:5]), 1),
                4,
            )
            conf_meta = label_confidence(confidence, source=CONFIDENCE_SOURCE_ADVISOR, is_estimate=True)
        elif dept_brief.get("confidence") is not None:
            conf_meta = label_confidence(
                float(dept_brief["confidence"]),
                source=str(dept_brief.get("confidence_source") or CONFIDENCE_SOURCE_ADVISOR),
                is_estimate=bool(dept_brief.get("confidence_is_estimate", True)),
            )
        else:
            conf_meta = label_confidence(None, source=CONFIDENCE_SOURCE_INSUFFICIENT)

        why_parts: list[str] = []
        if risks:
            why_parts.append(f"{len(risks)} risk signal(s) need attention in {dept}.")
        if opportunities:
            why_parts.append(f"{len(opportunities)} opportunity signal(s) surfaced from live org data.")
        if not why_parts:
            why_parts.append("Gravitre reviewed recent workflow, connector, and prediction signals for your org.")

        return {
            "mode": "advisor",
            "department": dept,
            "what_changed": what_changed[:8],
            "why": " ".join(why_parts),
            "recommended_actions": ranked_actions[:5],
            "risks": risks,
            "opportunities": opportunities,
            "impact_summary": self._impact_summary(ranked_actions),
            **conf_meta,
            "evidence": dept_brief.get("evidence") or [
                {"source": row.get("source"), "title": row.get("title")} for row in signals[:5]
            ],
            "advisory_only": True,
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }

    async def generate_executive_brief(
        self,
        org_id: str,
        user_id: str,
        *,
        client: Any | None = None,
    ) -> dict[str, Any]:
        _ = user_id
        exec_payload = await self._signals.generate_executive_brief(org_id, client=client)
        top_risks = list(exec_payload.get("top_risks") or [])
        sections = list(exec_payload.get("departments") or [])

        actions: list[dict[str, Any]] = []
        for section in sections:
            for row in section.get("recommended_actions") or []:
                if isinstance(row, dict):
                    actions.append(row)

        ranked = await self._quality.filter_advisor_actions(org_id, actions, department=None)

        research_brief: dict[str, Any] = {}
        try:
            research_brief = await self._research.generate_executive_brief(org_id, ["business health", "operations"])
        except Exception as exc:  # noqa: BLE001
            logger.debug("advisor_research_brief_skipped org_id=%s error=%s", org_id, exc)

        if ranked:
            confidence = round(
                sum(float(row.get("quality_score") or row.get("confidence") or 0.0) for row in ranked[:5])
                / max(len(ranked[:5]), 1),
                4,
            )
            conf_meta = label_confidence(confidence, source=CONFIDENCE_SOURCE_ADVISOR, is_estimate=True)
        else:
            conf_meta = label_confidence(None, source=CONFIDENCE_SOURCE_INSUFFICIENT)

        return {
            "mode": "advisor_executive",
            "title": exec_payload.get("title") or "Executive business brief",
            "what_changed": [
                title
                for section in sections
                for title in (section.get("what_changed") or [])[:2]
            ][:10],
            "why": "Cross-department signals aggregated from predictions, workflows, and connector activity.",
            "recommended_actions": ranked[:6],
            "top_risks": top_risks,
            "departments": sections,
            "research_summary": research_brief.get("summary") or research_brief.get("headline"),
            "impact_summary": self._impact_summary(ranked),
            **conf_meta,
            "evidence": [
                {"department": section.get("department"), "title": (section.get("what_changed") or ["Update"])[0]}
                for section in sections[:5]
            ],
            "advisory_only": True,
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }

    def format_brief_section(self, brief: dict[str, Any] | None) -> str:
        if not brief:
            return ""
        lines = [
            f"Advisor brief ({brief.get('department') or 'executive'}):",
            f"What changed: {'; '.join(str(item) for item in (brief.get('what_changed') or [])[:4])}",
            f"Why: {brief.get('why') or ''}",
        ]
        actions = brief.get("recommended_actions") or []
        if actions:
            lines.append("Recommended actions:")
            for row in actions[:4]:
                if isinstance(row, dict):
                    lines.append(
                        f"- {row.get('action') or row.get('title')}: "
                        f"{row.get('reason') or row.get('summary') or ''}"
                    )
        if brief.get("confidence") is not None:
            lines.append(f"Brief confidence: {brief['confidence']}")
        lines.append("All advisor guidance is advisory only — review before acting.")
        return "\n".join(lines)

    @staticmethod
    def _merge_actions(
        signals: list[dict[str, Any]],
        decision_recs: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        merged: list[dict[str, Any]] = []
        for row in signals:
            conf_val = row.get("quality_score") if row.get("quality_score") is not None else row.get("confidence")
            labeled = label_confidence(
                float(conf_val) if conf_val is not None else None,
                source=str(row.get("confidence_source") or CONFIDENCE_SOURCE_ADVISOR),
                is_estimate=bool(row.get("confidence_is_estimate", True)),
            )
            merged.append(
                {
                    "id": row.get("id"),
                    "action": row.get("title"),
                    "title": row.get("title"),
                    "reason": row.get("summary"),
                    "summary": row.get("summary"),
                    **labeled,
                    "estimated_impact": row.get("estimated_impact"),
                    "source": row.get("source"),
                }
            )
        for row in decision_recs:
            labeled = label_confidence(
                float(row["confidence"]) if row.get("confidence") is not None else None,
                source=str(row.get("confidence_source") or CONFIDENCE_SOURCE_ADVISOR),
                is_estimate=bool(row.get("confidence_is_estimate", True)),
            )
            merged.append(
                {
                    "id": row.get("id"),
                    "action": row.get("action") or row.get("title"),
                    "title": row.get("action") or row.get("title"),
                    "reason": row.get("reasoning") or row.get("reason"),
                    "summary": row.get("reasoning"),
                    **labeled,
                    "estimated_impact": row.get("estimated_impact"),
                    "source": "decision_intelligence",
                }
            )
        return merged

    @staticmethod
    def _impact_summary(actions: list[dict[str, Any]]) -> str:
        impacts = [
            str(row.get("estimated_impact") or row.get("impact") or "")
            for row in actions
            if row.get("estimated_impact") or row.get("impact")
        ]
        if not impacts:
            return "Impact varies by action — review each recommendation before approval."
        high = sum(1 for value in impacts if "high" in value.lower())
        if high:
            return f"{high} high-impact action(s) identified — prioritize review."
        return "Moderate-impact improvements identified across operational signals."


_engine: AdvisorModeEngine | None = None


def get_advisor_mode_engine(settings: Settings | None = None) -> AdvisorModeEngine:
    global _engine
    if _engine is None or settings is not None:
        _engine = AdvisorModeEngine(settings)
    return _engine
