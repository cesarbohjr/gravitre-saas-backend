"""Proactive business signals — alerts, opportunities, risks, and briefs."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from app.config import Settings, get_settings
from app.core.logging import get_logger
from app.services.confidence_honesty import (
    CONFIDENCE_SOURCE_INSUFFICIENT,
    CONFIDENCE_SOURCE_SIGNAL_HEURISTIC,
    label_confidence,
)
from app.services.event_intelligence_service import get_event_intelligence_service
from app.services.knowledge_graph_service import get_knowledge_graph_service
from app.services.optimization_suggestion_service import get_optimization_suggestion_service
from app.services.org_context_service import get_org_context_service
from app.services.predictive_operations_engine import get_predictive_operations_engine
from app.services.recommendation_quality_engine import get_recommendation_quality_engine
from app.services.workflow_failure_prediction_service import list_failure_alerts
from app.workflows.repository import get_supabase_client

logger = get_logger(__name__)

DEPARTMENT_DOMAINS: dict[str, str] = {
    "marketing": "marketing",
    "sales": "sales",
    "support": "support",
    "operations": "operations",
    "finance": "finance",
    "hr": "hr",
    "engineering": "engineering",
}


class BusinessSignalsEngine:
    """Aggregates CRM, finance, support, workflow, connector, and prediction signals."""

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self._predictive = get_predictive_operations_engine(self.settings)
        self._quality = get_recommendation_quality_engine(self.settings)
        self._events = get_event_intelligence_service(self.settings)

    def _client(self) -> Any:
        return get_supabase_client(self.settings)

    async def collect_signals(
        self,
        org_id: str,
        *,
        department: str | None = None,
        query: str | None = None,
        client: Any | None = None,
    ) -> dict[str, Any]:
        signals: list[dict[str, Any]] = []
        graph_payload: dict[str, Any] = {}

        if query:
            try:
                graph_payload = await get_knowledge_graph_service().answer_business_question(org_id, query)
                for signal in list((graph_payload.get("explanation") or {}).get("businessSignals") or [])[:5]:
                    signals.append(self._normalize_signal(signal, source="knowledge_graph", signal_type="insight"))
            except Exception as exc:  # noqa: BLE001
                logger.debug("business_signals_graph_skipped org_id=%s error=%s", org_id, exc)

        domain = DEPARTMENT_DOMAINS.get((department or "operations").lower(), "operations")
        try:
            predictions = await self._predictive.run_domain_predictions(org_id, domain)
            for model_name, payload in (predictions.get("predictions") or {}).items():
                if payload.get("status") != "ok":
                    continue
                risk = float(payload.get("risk_score") or 0.0)
                if risk < 0.55:
                    continue
                prediction = payload.get("prediction") or {}
                signals.append(
                    self._normalize_signal(
                        {
                            "title": f"{domain.title()} risk — {model_name}",
                            "summary": str(prediction.get("summary") or prediction.get("headline") or model_name),
                            "confidence": risk,
                            "estimated_impact": "high" if risk >= 0.75 else "medium",
                        },
                        source="predictive_operations",
                        signal_type="risk" if risk >= 0.65 else "opportunity",
                    )
                )
        except Exception as exc:  # noqa: BLE001
            logger.debug("business_signals_predictive_skipped org_id=%s error=%s", org_id, exc)

        try:
            alerts = await self._predictive.generate_early_warning_alerts(org_id)
            for alert in alerts[:5]:
                signals.append(
                    self._normalize_signal(
                        {
                            "title": f"Early warning: {alert.get('model')}",
                            "summary": f"{alert.get('domain')} domain risk score {alert.get('riskScore')}",
                            "confidence": alert.get("riskScore"),
                            "estimated_impact": "high",
                        },
                        source="predictive_operations",
                        signal_type="alert",
                    )
                )
        except Exception as exc:  # noqa: BLE001
            logger.debug("business_signals_alerts_skipped org_id=%s error=%s", org_id, exc)

        try:
            suggestions = await get_optimization_suggestion_service(self.settings).list_suggestions(
                org_id,
                status="pending_review",
                limit=5,
            )
            for row in suggestions.get("suggestions") or []:
                signals.append(
                    self._normalize_signal(
                        {
                            "title": row.get("title") or row.get("suggestionType"),
                            "summary": row.get("description") or row.get("rationale"),
                            "confidence": row.get("confidence"),
                            "estimated_impact": row.get("estimatedImpact"),
                        },
                        source="optimization",
                        signal_type="opportunity",
                    )
                )
        except Exception as exc:  # noqa: BLE001
            logger.debug("business_signals_optimization_skipped org_id=%s error=%s", org_id, exc)

        if client is not None:
            try:
                snapshot = get_org_context_service().get_snapshot(client, org_id, depth="minimal")
                for alert in list(snapshot.get("alerts") or [])[:3]:
                    signals.append(
                        self._normalize_signal(
                            {
                                "title": alert.get("title") or "Workflow alert",
                                "summary": alert.get("message") or alert.get("summary") or "",
                                **label_confidence(0.7, source=CONFIDENCE_SOURCE_SIGNAL_HEURISTIC),
                            },
                            source="org_context",
                            signal_type="alert",
                        )
                    )
            except Exception as exc:  # noqa: BLE001
                logger.debug("business_signals_org_context_skipped org_id=%s error=%s", org_id, exc)

        try:
            db_client = client or self._client()
            failure_alerts = list_failure_alerts(db_client, org_id, limit=5)
            for alert in failure_alerts:
                signals.append(
                    self._normalize_signal(
                        {
                            "title": alert.get("title") or "Workflow failure risk",
                            "summary": alert.get("message") or alert.get("summary") or "",
                            **label_confidence(0.65, source=CONFIDENCE_SOURCE_SIGNAL_HEURISTIC),
                        },
                        source="workflow_prediction",
                        signal_type="risk",
                    )
                )
        except Exception as exc:  # noqa: BLE001
            logger.debug("business_signals_workflow_skipped org_id=%s error=%s", org_id, exc)

        if query:
            try:
                from app.services.decision_intelligence_service import get_decision_intelligence_service

                decision_payload = await get_decision_intelligence_service(self.settings).recommend_next_action(
                    org_id,
                    query,
                )
                for row in decision_payload.get("recommendations") or []:
                    signals.append(
                        self._normalize_signal(
                            {
                                "title": row.get("action") or row.get("title"),
                                "summary": row.get("reasoning") or row.get("reason"),
                                "confidence": row.get("confidence"),
                                "estimated_impact": row.get("estimated_impact"),
                            },
                            source="decision_intelligence",
                            signal_type="opportunity",
                        )
                    )
            except Exception as exc:  # noqa: BLE001
                logger.debug("business_signals_decision_skipped org_id=%s error=%s", org_id, exc)

        ranked = await self._quality.rank_recommendations(
            signals,
            org_id=org_id,
            department=department,
        )
        return {"signals": ranked[:10], "graph": graph_payload, "collected_at": datetime.now(timezone.utc).isoformat()}

    async def generate_department_brief(
        self,
        org_id: str,
        department: str,
        *,
        client: Any | None = None,
    ) -> dict[str, Any]:
        payload = await self.collect_signals(org_id, department=department, client=client)
        signals = payload.get("signals") or []
        risks = [row for row in signals if row.get("signal_type") in {"risk", "alert"}][:3]
        opportunities = [row for row in signals if row.get("signal_type") == "opportunity"][:3]
        return {
            "department": department,
            "what_changed": [row.get("title") for row in signals[:5]],
            "risks": risks,
            "opportunities": opportunities,
            "recommended_actions": [
                {
                    "action": row.get("title"),
                    "reason": row.get("summary"),
                    "confidence": row.get("quality_score") or row.get("confidence"),
                }
                for row in opportunities
            ],
            "confidence": round(
                sum(float(row.get("quality_score") or row.get("confidence") or 0.5) for row in signals[:5])
                / max(len(signals[:5]), 1),
                4,
            )
            if signals
            else 0.5,
            "evidence": [{"source": row.get("source"), "title": row.get("title")} for row in signals[:5]],
            "generated_at": payload.get("collected_at"),
        }

    async def generate_executive_brief(self, org_id: str, *, client: Any | None = None) -> dict[str, Any]:
        departments = list(DEPARTMENT_DOMAINS.keys())
        sections: list[dict[str, Any]] = []
        all_signals: list[dict[str, Any]] = []
        for dept in departments:
            brief = await self.generate_department_brief(org_id, dept, client=client)
            if brief.get("what_changed"):
                sections.append(brief)
                all_signals.extend(brief.get("risks") or [])
                all_signals.extend(brief.get("opportunities") or [])
        return {
            "title": "Executive business brief",
            "departments": sections,
            "top_risks": sorted(all_signals, key=lambda row: float(row.get("quality_score") or 0), reverse=True)[:5],
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }

    async def record_connector_signal(
        self,
        org_id: str,
        connector: str,
        event_type: str,
        entity_id: str,
        payload: dict[str, Any],
    ) -> None:
        await self._events.handle_connector_event(org_id, connector, event_type, entity_id, payload)

    @staticmethod
    def _normalize_signal(raw: dict[str, Any], *, source: str, signal_type: str) -> dict[str, Any]:
        raw_conf = raw.get("confidence")
        if raw_conf is None:
            raw_conf = raw.get("risk_score")
        if raw_conf is None:
            labeled = label_confidence(None, source=CONFIDENCE_SOURCE_INSUFFICIENT)
        else:
            labeled = label_confidence(
                float(raw_conf),
                source=str(raw.get("confidence_source") or CONFIDENCE_SOURCE_SIGNAL_HEURISTIC),
                is_estimate=bool(raw.get("confidence_is_estimate", True)),
            )
        return {
            "id": str(raw.get("id") or uuid4()),
            "title": str(raw.get("title") or raw.get("summary") or "Business signal")[:200],
            "summary": str(raw.get("summary") or raw.get("description") or raw.get("title") or "")[:500],
            **labeled,
            "estimated_impact": raw.get("estimated_impact") or raw.get("estimatedImpact"),
            "source": source,
            "signal_type": signal_type,
        }


_engine: BusinessSignalsEngine | None = None


def get_business_signals_engine(settings: Settings | None = None) -> BusinessSignalsEngine:
    global _engine
    if _engine is None or settings is not None:
        _engine = BusinessSignalsEngine(settings)
    return _engine
