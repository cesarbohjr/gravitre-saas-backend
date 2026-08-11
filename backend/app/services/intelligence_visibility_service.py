"""IntelligenceVisibilityService — single read-only aggregation for Wave E visibility."""
from __future__ import annotations

from typing import Any

from app.config import Settings, get_settings
from app.schemas.intelligence_visibility import (
    AlternativePathsConsidered,
    DecisionTransparencyEnvelope,
    DomainHealthEntry,
    ExecutiveIntelligenceSummary,
    IntelligenceMaturityView,
    LearningConfidenceView,
)
from app.services.executive_intelligence_scoring_service import get_executive_intelligence_scoring_service
from app.services.confidence_honesty import (
    CONFIDENCE_SOURCE_HEURISTIC,
    annotate_confidence,
    estimated_confidence,
)
from app.services.intelligence_maturity_service import get_intelligence_maturity_service
from app.services.intelligence_visibility_sanitizer import sanitize_envelope


class IntelligenceVisibilityService:
    """Aggregates explainability, trust, learning, freshness, optimization, and executive reporting."""

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()

    def is_enabled(self) -> bool:
        return bool(getattr(self.settings, "intelligence_visibility_enabled", False))

    async def build_decision_envelope(
        self,
        org_id: str,
        *,
        decision_type: str,
        confidence: float | None,
        sources: list[dict[str, Any]] | None = None,
        classification: dict[str, Any] | None = None,
        context: dict[str, Any] | None = None,
        response: dict[str, Any] | None = None,
        summary: str | None = None,
        missing_context: list[str] | None = None,
    ) -> dict[str, Any]:
        from app.services.ai_trust_layer import get_ai_trust_layer

        trust = get_ai_trust_layer()
        score_raw = confidence
        if score_raw is None:
            score_raw = (response or {}).get("confidence")
        if score_raw is None:
            score = 0.0
            band = "insufficient"
        else:
            score = round(float(score_raw), 4)
            band = trust.confidence_band(score)
        ctx = context or {}
        resp = response or {}
        cls = classification or resp.get("classification") or {}

        retrieval_effectiveness = (
            resp.get("retrieval_effectiveness")
            or ctx.get("retrieval_effectiveness")
            or cls.get("retrieval_effectiveness")
            or {}
        )
        retrieval_plan = resp.get("retrieval_plan") or ctx.get("retrieval_plan") or {}
        domain = cls.get("domain") or resp.get("domain") or {}

        evidence_used = self._build_evidence(sources, ctx, retrieval_effectiveness)
        sources_used = self._build_sources_used(sources, ctx, retrieval_effectiveness)
        learning_confidence = await self._segment_learning_confidence(org_id, resp.get("segment_key"), cls)
        optimization_signals = await self._optimization_signals(org_id)
        alternative_paths = self._alternative_paths(resp)
        freshness_status = self._freshness_status(retrieval_plan, resp)
        retrieval_summary = self._retrieval_summary(retrieval_effectiveness, retrieval_plan, domain)
        trust_health = await self.get_trust_health(org_id, response=resp, retrieval_plan=retrieval_plan)

        envelope = DecisionTransparencyEnvelope(
            decision_type=decision_type,
            confidence=score,
            confidence_band=band,
            evidence_used=evidence_used,
            sources_used=sources_used,
            freshness_status=freshness_status,
            domain_context=self._domain_context(domain, cls),
            optimization_signals=optimization_signals,
            learning_confidence=learning_confidence,
            known_gaps=list(missing_context or resp.get("missing_context") or []),
            alternative_paths_considered=alternative_paths,
            retrieval_summary=retrieval_summary,
            trust_health=trust_health,
            advisory_only=True,
            summary=summary,
            missing_context=list(missing_context or []),
        )
        payload = envelope.to_dict()
        # Pass through knowledge-fabric citation honesty fields for KnowledgeCitationCard
        citations = self._extract_knowledge_citations(sources, ctx, resp)
        if citations:
            payload["knowledge_citations"] = citations
            payload["sources"] = citations
        if not self.is_enabled():
            return sanitize_envelope({"status": "disabled", **payload})
        return sanitize_envelope(payload)

    async def build_decision_envelope_from_response(
        self,
        org_id: str,
        response: dict[str, Any],
        classification: dict[str, Any],
        context: dict[str, Any],
        *,
        decision_type: str = "answer",
    ) -> dict[str, Any]:
        sources = list(response.get("sources") or context.get("rag_context") or [])
        raw_conf = response.get("confidence")
        return await self.build_decision_envelope(
            org_id,
            decision_type=decision_type,
            confidence=float(raw_conf) if raw_conf is not None else None,
            sources=sources,
            classification=classification,
            context=context,
            response=response,
            summary=response.get("reasoning_summary"),
            missing_context=list(response.get("missing_context") or []),
        )

    async def enrich_legacy_explainability(
        self,
        org_id: str,
        legacy_envelope: dict[str, Any],
        *,
        classification: dict[str, Any] | None = None,
        context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        if not self.is_enabled():
            return sanitize_envelope(legacy_envelope)
        score_text = legacy_envelope.get("confidence_note") or ""
        if "High confidence" in score_text:
            score = float(estimated_confidence(0.8, source=CONFIDENCE_SOURCE_HEURISTIC)["confidence"])
        elif "Moderate confidence" in score_text:
            score = float(estimated_confidence(0.6, source=CONFIDENCE_SOURCE_HEURISTIC)["confidence"])
        elif "Lower confidence" in score_text:
            score = float(estimated_confidence(0.4, source=CONFIDENCE_SOURCE_HEURISTIC)["confidence"])
        else:
            score = float(estimated_confidence(0.55, source=CONFIDENCE_SOURCE_HEURISTIC)["confidence"])
        full = await self.build_decision_envelope(
            org_id,
            decision_type=str(legacy_envelope.get("response_type") or "answer"),
            confidence=score,
            sources=legacy_envelope.get("evidence") or [],
            classification=classification,
            context=context,
            summary=legacy_envelope.get("summary"),
            missing_context=list(legacy_envelope.get("missing_context") or []),
        )
        merged = {**legacy_envelope, **full}
        return sanitize_envelope(
            annotate_confidence(
                merged,
                is_estimate=True,
                source=CONFIDENCE_SOURCE_HEURISTIC,
                value=score,
            )
        )

    async def get_learning_health(self, org_id: str) -> dict[str, Any]:
        if not self.is_enabled():
            return {"status": "disabled", "org_id": org_id}
        adaptive = await self._safe_admin_call("adaptive_learning", org_id)
        meta = await self._safe_admin_call("meta_learning", org_id)
        return sanitize_envelope(
            {
                "status": "ok",
                "org_id": org_id,
                "adaptive_learning": adaptive,
                "meta_learning": meta,
                "segment_maturity": adaptive.get("segment_summaries") or [],
                "insufficient_data_warnings": list(
                    set(
                        (adaptive.get("insufficient_data_warnings") or [])
                        + (meta.get("insufficient_data_warnings") or [])
                    )
                ),
            }
        )

    async def get_domain_health(self, org_id: str) -> dict[str, Any]:
        if not self.is_enabled():
            return {"status": "disabled", "org_id": org_id}
        entries = await self._compute_domain_health_entries(org_id)
        return sanitize_envelope(
            {
                "status": "ok",
                "org_id": org_id,
                "domains": [entry.model_dump() for entry in entries],
                "healthy_domains": [e.domain for e in entries if e.health_label in {"healthy", "strong"}],
                "needs_attention_domains": [e.domain for e in entries if e.health_label == "needs_attention"],
                "improving_domains": [e.domain for e in entries if e.health_label == "developing"],
            }
        )

    async def get_knowledge_health(self, org_id: str) -> dict[str, Any]:
        if not self.is_enabled():
            return {"status": "disabled", "org_id": org_id}
        from app.services.knowledge_freshness_service import get_knowledge_freshness_service

        summary = await get_knowledge_freshness_service(self.settings).load_admin_summary(org_id)
        return sanitize_envelope({"status": "ok", "org_id": org_id, **summary})

    async def get_trust_health(
        self,
        org_id: str,
        *,
        response: dict[str, Any] | None = None,
        retrieval_plan: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        from app.services.ai_trust_layer import get_ai_trust_layer
        from app.services.outcome_learning_service import get_outcome_learning_service

        trust = get_ai_trust_layer()
        events = await get_outcome_learning_service(self.settings)._fetch_events(org_id, since_days=7)
        confidences = [float(r["confidence_score"]) for r in events if r.get("confidence_score") is not None]
        avg_confidence = round(sum(confidences) / len(confidences), 4) if confidences else None
        plan = retrieval_plan or (response or {}).get("retrieval_plan") or {}
        _, stale_warnings, freshness_envelope = trust.build_knowledge_freshness_envelope(plan)
        optimization = await self._safe_admin_call("domain_optimization", org_id)
        learning = await self._segment_learning_confidence(org_id, (response or {}).get("segment_key"))
        payload = {
            "status": "ok" if self.is_enabled() else "disabled",
            "org_id": org_id,
            "confidence": {
                "average": avg_confidence,
                "band": trust.confidence_band(float(avg_confidence)) if avg_confidence is not None else "insufficient",
            },
            "freshness": freshness_envelope,
            "stale_source_warnings": stale_warnings,
            "learning_confidence": learning.model_dump() if learning else None,
            "optimization_state": {
                "pending_recommendations": optimization.get("pending_count", 0),
                "advisory_only": True,
                "auto_execution_enabled": False,
            },
            "provenance_quality": self._provenance_quality(response),
            "missing_context_rate": None,
            "data_coverage": self._data_coverage(response, events),
            "known_limitations": stale_warnings[:5],
            "trust_metadata": trust.build_optimization_trust_metadata(
                freshness_envelope=freshness_envelope,
                optimization_summary=optimization,
            ),
        }
        return sanitize_envelope(payload)

    async def get_executive_summary(self, org_id: str) -> dict[str, Any]:
        if not self.is_enabled():
            return {"status": "disabled", "org_id": org_id, "advisory_only": True}
        maturity_raw = await get_intelligence_maturity_service().compute_maturity(org_id, settings=self.settings)
        maturity = IntelligenceMaturityView(**maturity_raw)
        domain_entries = await self._compute_domain_health_entries(org_id)
        trust = await self.get_trust_health(org_id)
        learning = await self._safe_admin_call("adaptive_learning", org_id)
        freshness = await self._safe_admin_call("knowledge_freshness", org_id)
        optimization = await self._safe_admin_call("domain_optimization", org_id)
        from app.services.ai_architecture_status_service import get_ai_architecture_status_service

        learning_status = await get_ai_architecture_status_service(self.settings).get_learning_status(org_id)

        trust_score = self._normalize_band_score((trust.get("confidence") or {}).get("band"))
        learning_score = self._learning_score(learning)
        freshness_score = self._freshness_score(freshness)
        optimization_score = self._optimization_score(optimization)
        domain_score = self._domain_aggregate_score(domain_entries)

        scoring = get_executive_intelligence_scoring_service().compute_score(
            trust_score=trust_score,
            learning_score=learning_score,
            freshness_score=freshness_score,
            optimization_score=optimization_score,
            domain_health_score=domain_score,
        )
        summary = ExecutiveIntelligenceSummary(
            org_id=org_id,
            intelligence_score=scoring.get("intelligence_score"),
            score_label=str(scoring.get("score_label") or "insufficient_data"),
            score_breakdown=scoring.get("score_breakdown") or {},
            score_weights=scoring.get("score_weights") or {},
            maturity=maturity,
            domain_health=domain_entries,
            top_performing_domains=[e.domain for e in domain_entries if (e.health_score or 0) >= 0.75][:5],
            weak_domains=[e.domain for e in domain_entries if e.health_label == "needs_attention"][:5],
            missing_knowledge_areas=list({str(g.get("department") or "general") for g in (freshness.get("recommended_actions") or [])})[:5],
            optimization_opportunities=int(optimization.get("pending_count") or 0),
            learning_velocity=str(learning_status.get("learning_velocity") or "unknown"),
            retrieval_ranker_examples=int(learning_status.get("retrieval_ranker_examples") or 0),
            advisory_only=True,
        )
        return sanitize_envelope(summary.model_dump())

    async def get_agent_visibility(self, org_id: str, agent_id: str) -> dict[str, Any]:
        if not self.is_enabled():
            return {"status": "disabled", "org_id": org_id, "agent_id": agent_id, "advisory_only": True}

        from app.services.agent_capability_profile_service import get_agent_capability_profile_service
        from app.services.agent_memory_service import ensure_agent_in_org
        from app.services.learning_confidence_service import get_learning_confidence_service
        from app.services.outcome_learning_service import get_outcome_learning_service
        from app.workflows.repository import get_supabase_client

        client = get_supabase_client(self.settings)
        agent = ensure_agent_in_org(client, org_id, agent_id)
        department = str(agent.get("department") or "").lower()
        capability = get_agent_capability_profile_service(self.settings).build_profile(client, org_id, agent_id)
        assignments = capability.get("connectedKnowledgeSources") or []

        stale_assignments = [
            {"label": row.get("label"), "freshness_status": row.get("freshnessStatus")}
            for row in assignments
            if str(row.get("freshnessStatus") or "").lower() in {"stale", "expired"}
        ]

        domain_entries = await self._compute_domain_health_entries(org_id)
        domain_entry = next((entry for entry in domain_entries if str(entry.department or "").lower() == department), None)
        if domain_entry is None and department:
            domain_entry = next(
                (entry for entry in domain_entries if department in str(entry.domain or "").lower()),
                None,
            )

        outcome = await get_outcome_learning_service(self.settings).get_agent_success_rate(org_id, agent_id)

        sample_count = positive_count = negative_count = 0
        adaptive = await self._safe_admin_call("adaptive_learning", org_id)
        for row in adaptive.get("segment_summaries") or []:
            segment_key = str(row.get("segment_key") or "")
            if department and f":{department}:" not in segment_key and not segment_key.startswith(f"default:{department}:"):
                continue
            sample_count += int(row.get("sample_count") or 0)
            positive_count += int(row.get("positive_count") or 0)
            negative_count += int(row.get("negative_count") or 0)

        learning_assessment = get_learning_confidence_service(self.settings).assess(
            sample_count=sample_count,
            positive_count=positive_count,
            negative_count=negative_count,
        )

        optimization_count = 0
        optimization = await self._safe_admin_call("domain_optimization", org_id)
        for row in optimization.get("pending_recommendations") or []:
            segment_key = str(row.get("segment_key") or "")
            if not department or f":{department}:" in segment_key or segment_key.startswith(f"default:{department}:"):
                optimization_count += 1

        payload = {
            "status": "ok",
            "org_id": org_id,
            "agent_id": agent_id,
            "agent_name": agent.get("name"),
            "department": agent.get("department"),
            "advisory_only": True,
            "knowledge_health": {
                "assignment_count": len(assignments),
                "stale_assignment_count": len(stale_assignments),
                "freshness_status": capability.get("freshnessStatus") or "unknown",
                "assignments": assignments[:12],
                "stale_assignments": stale_assignments[:8],
            },
            "learning_confidence": {
                "level": learning_assessment.level,
                "sample_count": learning_assessment.sample_count,
                "insufficient_data": learning_assessment.insufficient_data,
            },
            "freshness": capability.get("freshnessStatus")
            or (domain_entry.freshness if domain_entry else "unknown"),
            "domain_health": domain_entry.model_dump() if domain_entry else None,
            "capability_visibility": {
                "capabilities": capability.get("capabilities") or [],
                "connected_knowledge_sources": assignments,
                "allowed_connectors": capability.get("allowedConnectors") or [],
                "available_read_actions": (capability.get("availableReadActions") or [])[:12],
                "available_write_actions": (capability.get("availableWriteActions") or [])[:12],
                "approval_required_actions": (capability.get("approvalRequiredActions") or [])[:12],
                "memory_count": capability.get("memoryCount"),
                "can_recommend": capability.get("canRecommend"),
                "can_execute_with_approval": capability.get("canExecuteWithApproval"),
            },
            "outcome_summary": outcome,
            "optimization_recommendations": optimization_count,
        }
        return sanitize_envelope(payload)

    async def _compute_domain_health_entries(self, org_id: str) -> list[DomainHealthEntry]:
        from app.domain.loader import list_profile_ids, load_domain_profile
        from app.services.learning_confidence_service import get_learning_confidence_service

        adaptive = await self._safe_admin_call("adaptive_learning", org_id)
        freshness = await self._safe_admin_call("knowledge_freshness", org_id)
        optimization = await self._safe_admin_call("domain_optimization", org_id)
        segments = {str(row.get("segment_key") or ""): row for row in (adaptive.get("segment_summaries") or [])}
        confidence_svc = get_learning_confidence_service(self.settings)
        stale_by_dept: dict[str, int] = {}
        for row in freshness.get("stale_sources") or []:
            dept = str(row.get("department") or "general").lower()
            stale_by_dept[dept] = stale_by_dept.get(dept, 0) + 1
        pending_by_segment = {}
        for row in optimization.get("pending_recommendations") or []:
            key = str(row.get("segment_key") or "")
            pending_by_segment[key] = pending_by_segment.get(key, 0) + 1

        entries: list[DomainHealthEntry] = []
        for profile_id in list_profile_ids():
            profile = load_domain_profile(profile_id) or {}
            label = str(profile.get("label") or profile_id).title()
            dept = str(profile.get("department") or profile_id).lower()
            matching_segments = [key for key in segments if f":{dept}:" in key or key.startswith(f"default:{dept}:")]
            sample_total = sum(int(segments[key].get("sample_count") or 0) for key in matching_segments)
            assessment = confidence_svc.assess(sample_count=sample_total)
            stale_count = stale_by_dept.get(dept, 0)
            freshness_label = "good" if stale_count == 0 else "mixed" if stale_count <= 2 else "needs_attention"
            opt_count = sum(pending_by_segment.get(key, 0) for key in matching_segments)
            retrieval = None
            for key in matching_segments:
                outcome = float(segments[key].get("outcome_multiplier") or 1.0)
                retrieval = outcome if retrieval is None else max(retrieval, outcome)
            health_score = self._domain_health_score(assessment.level, freshness_label, retrieval, opt_count)
            entries.append(
                DomainHealthEntry(
                    domain=label,
                    department=dept,
                    health_score=health_score,
                    health_label=self._health_label(health_score),
                    learning_confidence=assessment.level,
                    freshness=freshness_label,
                    retrieval_effectiveness=retrieval,
                    optimization_recommendations=opt_count,
                )
            )
        if not entries:
            entries.append(
                DomainHealthEntry(
                    domain="Organization",
                    health_score=None,
                    health_label="insufficient_data",
                    learning_confidence="insufficient_data",
                    freshness=str(freshness.get("freshness_label") or "unknown"),
                )
            )
        return entries

    async def _safe_admin_call(self, kind: str, org_id: str) -> dict[str, Any]:
        try:
            if kind == "adaptive_learning":
                from app.services.adaptive_learning_service import get_adaptive_learning_service

                return await get_adaptive_learning_service(self.settings).get_admin_summary(org_id)
            if kind == "meta_learning":
                from app.services.meta_learning_service import get_meta_learning_service

                return await get_meta_learning_service(self.settings).get_meta_learning_summary(org_id)
            if kind == "knowledge_freshness":
                from app.services.knowledge_freshness_service import get_knowledge_freshness_service

                return await get_knowledge_freshness_service(self.settings).load_admin_summary(org_id)
            if kind == "domain_optimization":
                from app.services.domain_optimization_engine import get_domain_optimization_engine

                return await get_domain_optimization_engine(self.settings).get_admin_summary(org_id)
        except Exception:  # noqa: BLE001
            return {"status": "unavailable"}
        return {"status": "unknown"}

    async def _segment_learning_confidence(
        self,
        org_id: str,
        segment_key: str | None = None,
        classification: dict[str, Any] | None = None,
    ) -> LearningConfidenceView | None:
        from app.services.learning_confidence_service import get_learning_confidence_service
        from app.services.learning_strategy_keys import parse_segment_key

        key = segment_key or parse_segment_key(classification)
        try:
            from app.services.adaptive_learning_service import get_adaptive_learning_service

            state = await get_adaptive_learning_service(self.settings).load_segment_state(org_id, str(key))
        except Exception:  # noqa: BLE001
            state = {"sample_count": 0}
        assessment = get_learning_confidence_service(self.settings).assess(
            sample_count=int(state.get("sample_count") or 0),
            positive_count=int(state.get("positive_count") or 0),
            negative_count=int(state.get("negative_count") or 0),
            noise_score=float(state.get("noise_score") or 0),
        )
        noise = "high" if assessment.noise_score >= 0.5 else "medium" if assessment.noise_score >= 0.25 else "low"
        return LearningConfidenceView(
            level=assessment.level,
            sample_count=assessment.sample_count,
            noise=noise if not assessment.insufficient_data else None,
            insufficient_data=assessment.insufficient_data,
        )

    async def _optimization_signals(self, org_id: str) -> list[dict[str, Any]]:
        summary = await self._safe_admin_call("domain_optimization", org_id)
        signals = []
        for row in (summary.get("pending_recommendations") or [])[:5]:
            signals.append(
                {
                    "recommendation_type": row.get("recommendation_type"),
                    "title": row.get("title"),
                    "segment_key": row.get("segment_key"),
                    "advisory_only": True,
                }
            )
        return signals

    @staticmethod
    def _extract_knowledge_citations(
        sources: list[dict[str, Any]] | None,
        context: dict[str, Any],
        response: dict[str, Any],
    ) -> list[dict[str, Any]]:
        """Flatten knowledge-fabric provenance for citation honesty UI."""
        out: list[dict[str, Any]] = []
        for bucket in (
            response.get("knowledge_citations"),
            context.get("knowledge_citations"),
            sources,
        ):
            if not isinstance(bucket, list):
                continue
            for row in bucket:
                if not isinstance(row, dict):
                    continue
                # Nested list on context source metadata
                nested = row.get("metadata", {}).get("provenance") if isinstance(row.get("metadata"), dict) else None
                candidates = nested if isinstance(nested, list) else [row]
                for c in candidates:
                    if not isinstance(c, dict):
                        continue
                    if not (
                        c.get("citation")
                        or c.get("authority_score") is not None
                        or c.get("jurisdiction")
                        or c.get("content_mode")
                    ):
                        continue
                    out.append(c)
                    if len(out) >= 6:
                        return out
        return out

    @staticmethod
    def _build_evidence(
        sources: list[dict[str, Any]] | None,
        context: dict[str, Any],
        retrieval_effectiveness: dict[str, Any],
    ) -> list[dict[str, Any]]:
        evidence: list[dict[str, Any]] = []
        for row in (sources or [])[:8]:
            if not isinstance(row, dict):
                continue
            prov = row.get("provenance") if isinstance(row.get("provenance"), dict) else {}
            evidence.append(
                {
                    "label": prov.get("source_name") or row.get("title") or row.get("source") or row.get("kind"),
                    "kind": row.get("kind") or row.get("type") or prov.get("source_type"),
                    "relevance": row.get("score") or prov.get("confidence"),
                    "freshness_score": prov.get("freshness_score"),
                    "assignment_id": prov.get("assignment_id"),
                }
            )
        if not evidence:
            for row in (retrieval_effectiveness.get("top_sources") or [])[:5]:
                if isinstance(row, dict):
                    evidence.append(
                        {
                            "label": row.get("source_name"),
                            "kind": row.get("source_type"),
                            "relevance": row.get("score"),
                            "assignment_id": row.get("assignment_id"),
                        }
                    )
        used = context.get("sourcesUsed") if isinstance(context.get("sourcesUsed"), list) else []
        for row in used[:8]:
            if isinstance(row, dict) and len(evidence) < 8:
                evidence.append(
                    {
                        "label": row.get("label") or row.get("title"),
                        "kind": row.get("type") or row.get("kind"),
                        "relevance": row.get("score") or row.get("relevance"),
                    }
                )
        return evidence[:8]

    @staticmethod
    def _build_sources_used(
        sources: list[dict[str, Any]] | None,
        context: dict[str, Any],
        retrieval_effectiveness: dict[str, Any],
    ) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for row in (sources or [])[:10]:
            if not isinstance(row, dict):
                continue
            prov = row.get("provenance") if isinstance(row.get("provenance"), dict) else {}
            rows.append(
                {
                    "name": prov.get("source_name") or row.get("title") or row.get("source"),
                    "type": prov.get("source_type") or row.get("type") or row.get("kind"),
                    "score": row.get("score"),
                    "freshness_score": prov.get("freshness_score"),
                    "last_updated": prov.get("last_updated"),
                    "assignment_id": prov.get("assignment_id"),
                    "provenance": {
                        "source_system": prov.get("source_system"),
                        "match_tier": prov.get("match_tier"),
                        "retrieval_policy": prov.get("retrieval_policy"),
                    },
                }
            )
        if not rows:
            for row in (retrieval_effectiveness.get("top_sources") or [])[:5]:
                if isinstance(row, dict):
                    rows.append(
                        {
                            "name": row.get("source_name"),
                            "type": row.get("source_type"),
                            "score": row.get("score"),
                            "assignment_id": row.get("assignment_id"),
                            "match_tier": row.get("match_tier"),
                        }
                    )
        return rows

    @staticmethod
    def _alternative_paths(response: dict[str, Any]) -> AlternativePathsConsidered | None:
        model_selection = response.get("model_selection") or {}
        agent_selection = response.get("agent_selection") or {}
        guidance = (
            model_selection.get("meta_learning_guidance")
            or agent_selection.get("meta_learning_guidance")
            or {}
        )
        if not guidance and not response.get("segment_key"):
            return None
        ranked = guidance.get("ranked") or []
        recommended = guidance.get("recommended_key")
        selected = response.get("segment_key") or recommended
        if model_selection.get("llm_tier"):
            selected = f"llm:{model_selection.get('llm_tier')}"
        return AlternativePathsConsidered(
            alternative_strategy_count=len(ranked) if ranked else (1 if recommended else 0),
            selected_strategy=str(selected) if selected else None,
            guidance_strength=float(guidance.get("guidance_strength") or 0.0) or None,
        )

    @staticmethod
    def _freshness_status(retrieval_plan: dict[str, Any], response: dict[str, Any]) -> str | None:
        plan = retrieval_plan or {}
        label = plan.get("freshness_label")
        if label:
            return str(label)
        knowledge = (response.get("knowledge_freshness") or {}).get("freshness_label")
        return str(knowledge) if knowledge else None

    @staticmethod
    def _retrieval_summary(
        effectiveness: dict[str, Any],
        retrieval_plan: dict[str, Any],
        domain: dict[str, Any],
    ) -> dict[str, Any] | None:
        if not effectiveness and not retrieval_plan:
            return None
        dept = domain.get("department_key") or domain.get("department")
        sub = domain.get("subdomain_key") or domain.get("subdomain")
        domain_label = f"{dept} → {sub}" if dept and sub else str(dept or sub or "unknown")
        return {
            "domain": domain_label,
            "sources_searched": effectiveness.get("source_count"),
            "sources_used": len(effectiveness.get("top_sources") or []),
            "assignment_ids_used": effectiveness.get("assignment_ids_used") or [],
            "memory_segments_used": retrieval_plan.get("memory_category_boosts") or [],
            "knowledge_graph_used": bool(retrieval_plan.get("graph_weight")),
            "freshness": retrieval_plan.get("freshness_label") or effectiveness.get("learning_confidence"),
            "retrieval_score": effectiveness.get("retrieval_score"),
            "retrieval_policy": effectiveness.get("retrieval_policy") or retrieval_plan.get("policy_version"),
        }

    @staticmethod
    def _domain_context(domain: dict[str, Any], classification: dict[str, Any]) -> dict[str, Any] | None:
        if not domain:
            return None
        return {
            "industry": domain.get("industry") or domain.get("industry_key"),
            "department": domain.get("department") or domain.get("department_key") or classification.get("department"),
            "subdomain": domain.get("subdomain") or domain.get("subdomain_key"),
            "profile_id": domain.get("profile_id"),
            "confidence": domain.get("confidence"),
            "routing_active": domain.get("routing_active"),
        }

    @staticmethod
    def _provenance_quality(response: dict[str, Any] | None) -> dict[str, Any]:
        sources = (response or {}).get("sources") or []
        with_prov = sum(1 for row in sources if isinstance(row, dict) and row.get("provenance"))
        total = len(sources)
        return {
            "sources_with_provenance": with_prov,
            "total_sources": total,
            "quality": "strong" if total and with_prov == total else "partial" if with_prov else "unknown",
        }

    @staticmethod
    def _data_coverage(response: dict[str, Any] | None, events: list[dict[str, Any]]) -> str:
        if (response or {}).get("sources"):
            return "strong"
        if events:
            return "moderate"
        return "limited"

    @staticmethod
    def _normalize_band_score(band: str | None) -> float | None:
        mapping = {"high": 0.9, "medium": 0.65, "low": 0.4, "insufficient": None}
        return mapping.get(str(band or "").lower())

    @staticmethod
    def _learning_score(summary: dict[str, Any]) -> float | None:
        segments = summary.get("segment_summaries") or []
        if not segments:
            return None
        scored = [1.0 for row in segments if row.get("learning_confidence") in {"high", "medium"}]
        return round(len(scored) / len(segments), 4) if segments else None

    @staticmethod
    def _freshness_score(summary: dict[str, Any]) -> float | None:
        stale = len(summary.get("stale_sources") or [])
        inaccessible = len(summary.get("inaccessible_sources") or [])
        total = int(summary.get("assignment_count") or 0)
        if total <= 0:
            return None
        penalty = (stale * 0.15 + inaccessible * 0.35) / max(total, 1)
        return round(max(0.0, min(1.0, 1.0 - penalty)), 4)

    @staticmethod
    def _optimization_score(summary: dict[str, Any]) -> float | None:
        pending = int(summary.get("pending_count") or 0)
        if pending == 0:
            return 0.85
        if pending <= 3:
            return 0.7
        if pending <= 8:
            return 0.55
        return 0.4

    @staticmethod
    def _domain_aggregate_score(entries: list[DomainHealthEntry]) -> float | None:
        scores = [float(entry.health_score) for entry in entries if entry.health_score is not None]
        if not scores:
            return None
        return round(sum(scores) / len(scores), 4)

    @staticmethod
    def _domain_health_score(
        learning_level: str,
        freshness_label: str,
        retrieval: float | None,
        optimization_count: int,
    ) -> float | None:
        if learning_level == "insufficient_data" and freshness_label == "unknown":
            return None
        score = float(estimated_confidence(0.5, source=CONFIDENCE_SOURCE_HEURISTIC)["confidence"])
        if learning_level == "high":
            score += 0.25
        elif learning_level == "medium":
            score += 0.15
        elif learning_level == "low":
            score += 0.05
        if freshness_label == "good":
            score += 0.15
        elif freshness_label == "mixed":
            score += 0.05
        elif freshness_label == "needs_attention":
            score -= 0.1
        if retrieval is not None:
            score += min(0.15, max(-0.1, (retrieval - 1.0) * 0.5))
        score -= min(0.15, optimization_count * 0.03)
        return round(max(0.0, min(1.0, score)), 4)

    @staticmethod
    def _health_label(score: float | None) -> str:
        if score is None:
            return "insufficient_data"
        if score >= 0.8:
            return "healthy"
        if score >= 0.65:
            return "strong"
        if score >= 0.45:
            return "developing"
        return "needs_attention"


_service: IntelligenceVisibilityService | None = None


def get_intelligence_visibility_service(settings: Settings | None = None) -> IntelligenceVisibilityService:
    global _service
    if _service is None or settings is not None:
        _service = IntelligenceVisibilityService(settings)
    return _service
