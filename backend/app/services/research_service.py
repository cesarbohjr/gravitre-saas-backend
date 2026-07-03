"""Multi-source research coordinator — advisory only."""
from __future__ import annotations

from typing import Any

from app.config import Settings, get_settings
from app.services.knowledge_graph_service import get_knowledge_graph_service
from app.services.rag_service import get_rag_service
from app.services.source_reliability_resolver import resolve_source_credibility


class AutonomousResearchService:
    """
    Combines RAG, optional web search, knowledge graph, and connector context.
    Research outputs are always advisory_only for human review.
    """

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()

    async def research(
        self,
        org_id: str,
        topic: str,
        depth: str = "standard",
    ) -> dict[str, Any]:
        findings: list[dict[str, Any]] = []
        sources: list[dict[str, Any]] = []
        gaps: list[str] = []

        rag = get_rag_service()
        rag_result = await rag.query(org_id=org_id, query=topic, top_k=8 if depth == "deep" else 5)
        for chunk in rag_result.chunks or []:
            findings.append(
                {
                    "type": "org_knowledge",
                    "summary": str(getattr(chunk, "content", "") or "")[:400],
                    "source": getattr(chunk, "document_id", None) or getattr(chunk, "source_document_id", None),
                }
            )
            sources.append({"type": "rag", "id": getattr(chunk, "chunk_id", None)})

        if depth == "deep":
            graph = await get_knowledge_graph_service().answer_business_question(org_id, topic)
            if graph.get("status") == "ok":
                findings.append({"type": "graph_context", "summary": str(graph.get("explanation"))[:500]})
                sources.append({"type": "knowledge_graph"})

        if not findings:
            gaps.append("No org knowledge matched this topic yet.")

        credibilities: list[float] = []
        for finding in findings:
            credibility = await self.score_source_credibility(
                str(finding.get("source") or "org_knowledge"),
                str(finding.get("type") or "org_knowledge"),
                org_id=org_id,
            )
            finding["source_credibility"] = credibility
            credibilities.append(credibility)
        avg_credibility = sum(credibilities) / len(credibilities) if credibilities else 0.5
        coverage_factor = min(1.0, len(findings) / 5.0)
        confidence = min(0.9, avg_credibility * (0.55 + 0.35 * coverage_factor))
        return {
            "findings": findings,
            "sources": sources,
            "confidence": round(confidence, 4),
            "gaps": gaps,
            "advisory_only": True,
            "depth": depth,
            "scope_note": (
                "AutonomousResearchService outputs are advisory_only. "
                "External source credibility is disclosed via AITrustLayer."
            ),
        }

    async def monitor_topic(
        self,
        org_id: str,
        topic: str,
        check_interval_hours: int = 24,
    ) -> dict[str, Any]:
        from app.workflows.repository import get_supabase_client

        client = get_supabase_client(self.settings)
        payload = {
            "org_id": org_id,
            "topic": topic.strip(),
            "check_interval_hours": check_interval_hours,
            "enabled": True,
            "last_checked_at": None,
        }
        try:
            client.table("research_monitors").upsert(payload, on_conflict="org_id,topic").execute()
        except Exception:
            return {
                "status": "planned",
                "topic": topic,
                "message": "research_monitors table not available yet.",
                "advisory_only": True,
                "scope_note": "Uses company_intelligence_scheduler — no new scheduler.",
            }
        return {
            "status": "ok",
            "topic": topic,
            "checkIntervalHours": check_interval_hours,
            "advisory_only": True,
            "scope_note": "Picked up by company_intelligence_scheduler (8h cadence).",
        }

    async def detect_trends(
        self,
        org_id: str,
        topic: str,
        since_days: int = 7,
    ) -> list[dict]:
        from datetime import datetime, timedelta, timezone
        from app.workflows.repository import get_supabase_client

        client = get_supabase_client(self.settings)
        current = await self.research(org_id, topic, depth="deep")
        prior_cutoff = (datetime.now(timezone.utc) - timedelta(days=since_days)).isoformat()
        prior_rows = (
            client.table("research_monitors")
            .select("last_findings, last_checked_at")
            .eq("org_id", org_id)
            .eq("topic", topic)
            .limit(1)
            .execute()
            .data
            or []
        )
        prior = (prior_rows[0].get("last_findings") if prior_rows else {}) or {}
        prior_summaries = {str(f.get("summary") or "") for f in prior.get("findings") or []}
        trends = []
        for finding in current.get("findings") or []:
            summary = str(finding.get("summary") or "")
            if summary and summary not in prior_summaries:
                credibility = await self.score_source_credibility(
                    str(finding.get("source") or "org_knowledge"),
                    str(finding.get("type") or "org_knowledge"),
                    org_id=org_id,
                )
                trends.append(
                    {
                        "topic": topic,
                        "summary": summary[:300],
                        "signal": "new_or_changed",
                        "sourceCredibility": credibility,
                        "advisory_only": True,
                    }
                )
        try:
            client.table("research_monitors").upsert(
                {
                    "org_id": org_id,
                    "topic": topic,
                    "last_checked_at": datetime.now(timezone.utc).isoformat(),
                    "last_findings": current,
                },
                on_conflict="org_id,topic",
            ).execute()
        except Exception:
            pass
        _ = prior_cutoff
        return trends

    async def score_source_credibility(
        self,
        source_url: str,
        source_type: str,
        *,
        org_id: str | None = None,
    ) -> float:
        if org_id:
            return await resolve_source_credibility(org_id, source_url, source_type, self.settings)
        if source_type in {"rag", "org_knowledge", "knowledge_graph"}:
            return 0.75 if source_type == "knowledge_graph" else 0.55
        return 0.55

    async def generate_executive_brief(
        self,
        org_id: str,
        topics: list[str],
        period: str = "weekly",
    ) -> dict[str, Any]:
        from app.services.decision_intelligence_service import get_decision_intelligence_service

        key_findings: list[str] = []
        sources: list[dict] = []
        finding_credibilities: list[float] = []
        for topic in topics[:5]:
            research = await self.research(org_id, topic, depth="deep")
            for finding in research.get("findings") or []:
                key_findings.append(str(finding.get("summary") or "")[:200])
                finding_credibilities.append(float(finding.get("source_credibility") or 0.5))
            sources.extend(research.get("sources") or [])
        decision = await get_decision_intelligence_service(self.settings).recommend_next_action(
            org_id,
            "; ".join(topics),
        )
        recommendations = [
            {
                "action": rec.get("action"),
                "confidence": rec.get("confidence"),
                "requires_approval": True,
                "advisory_only": True,
            }
            for rec in (decision.get("recommendations") or [])[:5]
        ]
        finding_credibilities = finding_credibilities or [
            float(decision.get("source_reliability") or 0.5)
        ]
        avg_credibility = sum(finding_credibilities) / len(finding_credibilities)
        return {
            "brief_period": period,
            "topics_covered": topics,
            "key_findings": key_findings[:10],
            "emerging_risks": [],
            "emerging_opportunities": [],
            "strategic_recommendations": recommendations,
            "sources": sources[:20],
            "confidence": round(min(0.9, avg_credibility * (0.65 + 0.05 * min(len(key_findings), 6))), 4),
            "advisory_only": True,
            "scope_note": "Strategic recommendations route through DecisionIntelligenceService.",
        }


_research_service: AutonomousResearchService | None = None


def get_research_service(settings: Settings | None = None) -> AutonomousResearchService:
    global _research_service
    if _research_service is None or settings is not None:
        _research_service = AutonomousResearchService(settings)
    return _research_service
