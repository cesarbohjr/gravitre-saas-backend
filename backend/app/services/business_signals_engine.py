"""Proactive business signals — alerts, opportunities, risks, and briefs."""
from __future__ import annotations

import asyncio
import time
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

# Short TTL cache — mount hits both /business-signals and /advisor-brief;
# without this, advisor re-runs the full sequential predictive stack.
_SIGNALS_CACHE: dict[str, tuple[float, dict[str, Any]]] = {}
_SIGNALS_CACHE_TTL_S = 45.0
_SOURCE_TIMEOUT_S = 2.5


class BusinessSignalsEngine:
    """Aggregates CRM, finance, support, workflow, connector, and prediction signals."""

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self._predictive = get_predictive_operations_engine(self.settings)
        self._quality = get_recommendation_quality_engine(self.settings)
        self._events = get_event_intelligence_service(self.settings)

    def _client(self) -> Any:
        return get_supabase_client(self.settings)

    @staticmethod
    def _cache_key(org_id: str, department: str | None, query: str | None) -> str:
        return f"{org_id}|{(department or 'operations').lower()}|{(query or '').strip().lower()}"

    async def collect_signals(
        self,
        org_id: str,
        *,
        department: str | None = None,
        query: str | None = None,
        client: Any | None = None,
        use_cache: bool = True,
        include_predictive: bool = True,
    ) -> dict[str, Any]:
        cache_key = f"{self._cache_key(org_id, department, query)}|pred={int(include_predictive)}"
        if use_cache:
            hit = _SIGNALS_CACHE.get(cache_key)
            if hit and (time.monotonic() - hit[0]) < _SIGNALS_CACHE_TTL_S:
                return hit[1]

        domain = DEPARTMENT_DOMAINS.get((department or "operations").lower(), "operations")
        db_client = client or self._client()
        signals: list[dict[str, Any]] = []
        graph_payload: dict[str, Any] = {}

        async def _with_timeout(label: str, coro):
            try:
                return await asyncio.wait_for(coro, timeout=_SOURCE_TIMEOUT_S)
            except Exception as exc:  # noqa: BLE001
                logger.debug(
                    "business_signals_source_skipped org_id=%s source=%s error=%s",
                    org_id,
                    label,
                    exc,
                )
                return None

        async def _graph():
            if not query:
                return None
            return await get_knowledge_graph_service().answer_business_question(org_id, query)

        async def _domain_predictions():
            return await self._predictive.run_domain_predictions(org_id, domain)

        async def _early_warnings(precomputed_domain: dict[str, Any] | None):
            # Scope to the active department only — full-pack fan-out was the
            # multi-second mount tax (re-ran every domain sequentially).
            precomputed = {domain: precomputed_domain} if precomputed_domain else None
            return await self._predictive.generate_early_warning_alerts(
                org_id,
                domains=[domain],
                persist_suggestions=False,
                precomputed=precomputed,
            )

        async def _suggestions():
            return await get_optimization_suggestion_service(self.settings).list_suggestions(
                org_id,
                status="pending_review",
                limit=5,
            )

        async def _org_alerts():
            snapshot = await asyncio.to_thread(
                lambda: get_org_context_service().get_snapshot(db_client, org_id, depth="minimal")
            )
            return list(snapshot.get("alerts") or [])[:3]

        async def _failure_alerts():
            return await asyncio.to_thread(
                lambda: list_failure_alerts(db_client, org_id, limit=5)
            )

        async def _decision():
            if not query:
                return None
            from app.services.decision_intelligence_service import get_decision_intelligence_service

            return await get_decision_intelligence_service(self.settings).recommend_next_action(
                org_id,
                query,
            )

        domain_predictions = None
        early_warnings: list[Any] | None = None
        if include_predictive:
            # Predictions first (reuse for early warnings). Hard-timeout — ML
            # catalog status/load is the measured multi-second mount culprit.
            domain_predictions = await _with_timeout("domain_predictions", _domain_predictions())
            early_warnings = await _with_timeout(
                "early_warnings",
                _early_warnings(domain_predictions if isinstance(domain_predictions, dict) else None),
            )

        (
            graph_result,
            suggestions_payload,
            org_alerts,
            failure_alerts,
            decision_payload,
        ) = await asyncio.gather(
            _with_timeout("graph", _graph()),
            _with_timeout("suggestions", _suggestions()),
            _with_timeout("org_alerts", _org_alerts()),
            _with_timeout("failure_alerts", _failure_alerts()),
            _with_timeout("decision", _decision()),
        )

        if isinstance(graph_result, dict):
            graph_payload = graph_result
            for signal in list((graph_payload.get("explanation") or {}).get("businessSignals") or [])[:5]:
                signals.append(self._normalize_signal(signal, source="knowledge_graph", signal_type="insight"))

        if isinstance(domain_predictions, dict):
            for model_name, payload in (domain_predictions.get("predictions") or {}).items():
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

        for alert in list(early_warnings or [])[:5]:
            if not isinstance(alert, dict):
                continue
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

        if isinstance(suggestions_payload, dict):
            for row in suggestions_payload.get("suggestions") or []:
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

        for alert in list(org_alerts or []):
            if not isinstance(alert, dict):
                continue
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

        for alert in list(failure_alerts or []):
            if not isinstance(alert, dict):
                continue
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

        if isinstance(decision_payload, dict):
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

        signal_scoring_payload: dict[str, Any] | None = None
        source_audit_payload: dict[str, Any] | None = None
        scored_department = str(department or "").strip().lower()
        if scored_department in {"sales", "marketing", "finance", "hr", "msp"}:
            try:
                from app.services.department_signal_scoring_service import (
                    get_department_signal_scoring_service,
                )

                scorer = get_department_signal_scoring_service(self.settings)
                signal_scoring_payload = await asyncio.to_thread(
                    scorer.score_department,
                    org_id,
                    client=db_client,
                    department=scored_department,
                    limit=3,
                )
                source_audit_payload = await asyncio.to_thread(
                    scorer.audit_sources,
                    org_id,
                    client=db_client,
                    department=scored_department,
                )
                for row in list(signal_scoring_payload.get("priorities") or [])[:3]:
                    score = float(row.get("priorityScore") or 0.0)
                    summary = "; ".join(str(item) for item in (row.get("explanations") or [])[:2])
                    if not summary:
                        summary = "Score assembled from currently available connected and knowledge-fabric signals."
                    signals.append(
                        self._normalize_signal(
                            {
                                "title": f"Priority score — {row.get('title') or scored_department.title()}",
                                "summary": summary,
                                "confidence": max(0.0, min(1.0, score / 100.0)),
                                "estimated_impact": "high" if score >= 70 else "medium" if score >= 45 else "low",
                            },
                            source="signal_scoring_engine",
                            signal_type="opportunity",
                        )
                    )
            except Exception as exc:  # noqa: BLE001
                logger.debug("business_signals_scoring_skipped org_id=%s dept=%s error=%s", org_id, scored_department, exc)

        ranked = await self._quality.rank_recommendations(
            signals,
            org_id=org_id,
            department=department,
        )
        payload = {
            "signals": ranked[:10],
            "graph": graph_payload,
            "signal_scoring": signal_scoring_payload,
            "signal_source_audit": source_audit_payload,
            "collected_at": datetime.now(timezone.utc).isoformat(),
        }
        if use_cache:
            _SIGNALS_CACHE[cache_key] = (time.monotonic(), payload)
        return payload

    async def generate_department_brief(
        self,
        org_id: str,
        department: str,
        *,
        client: Any | None = None,
        signals_payload: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        payload = signals_payload or await self.collect_signals(
            org_id, department=department, client=client
        )
        signals = payload.get("signals") or []
        risks = [row for row in signals if row.get("signal_type") in {"risk", "alert"}][:3]
        opportunities = [row for row in signals if row.get("signal_type") == "opportunity"][:3]
        conf_values = []
        for row in signals[:5]:
            raw_conf = row.get("quality_score")
            if raw_conf is None:
                raw_conf = row.get("confidence")
            if raw_conf is not None:
                conf_values.append(float(raw_conf))
        if conf_values:
            brief_confidence = label_confidence(
                round(sum(conf_values) / len(conf_values), 4),
                source=CONFIDENCE_SOURCE_SIGNAL_HEURISTIC,
                is_estimate=True,
            )
        else:
            brief_confidence = label_confidence(None, source=CONFIDENCE_SOURCE_INSUFFICIENT)
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
            **brief_confidence,
            "evidence": [{"source": row.get("source"), "title": row.get("title")} for row in signals[:5]],
            "generated_at": payload.get("collected_at"),
        }

    async def generate_executive_brief(self, org_id: str, *, client: Any | None = None) -> dict[str, Any]:
        departments = list(DEPARTMENT_DOMAINS.keys())
        sections: list[dict[str, Any]] = []
        all_signals: list[dict[str, Any]] = []
        briefs = await asyncio.gather(
            *[self.generate_department_brief(org_id, dept, client=client) for dept in departments]
        )
        for brief in briefs:
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
