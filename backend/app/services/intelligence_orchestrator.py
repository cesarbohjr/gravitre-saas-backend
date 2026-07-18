"""Unified intelligence orchestrator — single assistant entry facade (Wave 0)."""
from __future__ import annotations

import json
import asyncio
from dataclasses import dataclass, field, replace
from typing import Any

from app.config import Settings, get_settings
from app.core.logging import get_logger
from app.operators.agent_intelligence import resolve_agent_record
from app.operators.agent_prompts import build_synthetic_agent_for_task
from app.services.company_intelligence_orchestrator import get_company_intelligence_orchestrator
from app.services.context_prioritization_engine import (
    ContextPrioritizationEngine,
    ContextSource,
    get_context_prioritization_engine,
)
from app.services.context_registry import filter_context_sources, plan_context_registry
from app.services.conversation_memory_engine import (
    ConversationMemoryEngine,
    get_conversation_memory_engine,
)
from app.services.entity_relationship_service import build_entity_context_section
from app.services.execution_confidence_engine import (
    ExecutionConfidenceEngine,
    get_execution_confidence_engine,
)
from app.services.advisor_mode_engine import AdvisorModeEngine, get_advisor_mode_engine
from app.services.explainability_engine import ExplainabilityEngine, get_explainability_engine
from app.services.agent_knowledge_assignment_service import (
    AgentKnowledgeAssignmentService,
    get_agent_knowledge_assignment_service,
)
from app.services.pack_operational_state_service import (
    build_pack_operational_section,
    extract_pack_ids,
)
from app.services.business_signals_engine import BusinessSignalsEngine, get_business_signals_engine
from app.services.conversational_planning_engine import (
    ConversationalPlanningEngine,
    get_conversational_planning_engine,
)
from app.services.recommendation_quality_engine import (
    RecommendationQualityEngine,
    get_recommendation_quality_engine,
)
from app.services.specialist_reasoning_engine import (
    SpecialistReasoningEngine,
    get_specialist_reasoning_engine,
)
from app.services.org_context_service import get_org_context_service
from app.services.unified_retrieval_service import UnifiedRetrievalBundle, UnifiedRetrievalService, get_unified_retrieval_service
from app.services.tool_registry import get_tool_registry
from app.services.operational_intelligence_layer import get_operational_intelligence_layer

logger = get_logger(__name__)


@dataclass
class AssistantTurnContext:
    retrieval: UnifiedRetrievalBundle
    agent: dict[str, Any] = field(default_factory=dict)
    org_context_block: str = ""
    memory_block: str = ""
    company_block: str = ""
    entity_block: str = ""
    task_state_section: str = ""
    connected_integrations: list[str] = field(default_factory=list)
    context_profile: dict[str, Any] = field(default_factory=dict)
    context_registry: dict[str, Any] = field(default_factory=dict)
    context_explanation: str = ""
    conversation_memory: dict[str, Any] = field(default_factory=dict)
    business_signals: list[dict[str, Any]] = field(default_factory=list)
    strategic_plan: dict[str, Any] | None = None
    knowledge_assignments: list[dict[str, Any]] = field(default_factory=list)
    knowledge_section: str = ""
    knowledge_gap_message: str | None = None
    assigned_sources_used: list[dict[str, Any]] = field(default_factory=list)
    missing_assignment_labels: list[str] = field(default_factory=list)
    memory_conflicts: list[dict[str, Any]] = field(default_factory=list)
    specialist_modifier: str = ""
    pre_execution_confidence: dict[str, Any] = field(default_factory=dict)
    execution_gate: dict[str, Any] = field(default_factory=dict)
    advisor_brief: dict[str, Any] | None = None
    explainability: dict[str, Any] = field(default_factory=dict)
    research_cascade: dict[str, Any] = field(default_factory=dict)
    working_memory: dict[str, Any] = field(default_factory=dict)
    distillation_meta: dict[str, Any] = field(default_factory=dict)
    operational_envelope: dict[str, Any] = field(default_factory=dict)


class IntelligenceOrchestrator:
    """
    Facade coordinating context prioritization, memory, confidence, and existing execution core.
    Assistant chat routes through this layer before AgentIntelligence generation.
    """

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self._context_engine: ContextPrioritizationEngine = get_context_prioritization_engine()
        self._memory_engine: ConversationMemoryEngine = get_conversation_memory_engine(self.settings)
        self._confidence_engine: ExecutionConfidenceEngine = get_execution_confidence_engine()
        self._retrieval: UnifiedRetrievalService = get_unified_retrieval_service()
        self._planning: ConversationalPlanningEngine = get_conversational_planning_engine(self.settings)
        self._signals: BusinessSignalsEngine = get_business_signals_engine(self.settings)
        self._quality: RecommendationQualityEngine = get_recommendation_quality_engine(self.settings)
        self._knowledge: AgentKnowledgeAssignmentService = get_agent_knowledge_assignment_service(self.settings)
        self._specialist: SpecialistReasoningEngine = get_specialist_reasoning_engine(self.settings)
        self._advisor: AdvisorModeEngine = get_advisor_mode_engine(self.settings)
        self._explainability: ExplainabilityEngine = get_explainability_engine()
        self._registry = get_tool_registry()
        self._oil = get_operational_intelligence_layer()

    async def prepare_assistant_turn(
        self,
        *,
        org_id: str,
        user_id: str,
        conversation_id: str,
        query: str,
        classification: dict[str, Any],
        client: Any,
        agent_id: str | None,
        environment_name: str,
        engine_settings: Any,
        task_state: dict[str, Any],
        persona: dict[str, Any],
        conversation_history: list[dict[str, Any]] | None = None,
        routing_tier: str | None = None,
        mode: str | None = None,
        research_scope: str | None = None,
    ) -> AssistantTurnContext:
        _ = conversation_history, persona
        connected = self._registry.list_connected_integrations(client, org_id, environment_name=environment_name)
        registry_plan = plan_context_registry(
            query=query,
            classification=classification,
            connected_integrations=connected,
            task_state=task_state,
            routing_tier=routing_tier,
            mode=mode,
        )
        # Pattern 7 — predictive context preload (intent/confidence-driven slices).
        registry_plan = self._oil.predict_context_plan(
            registry_plan,
            classification=classification,
            query=query,
        )
        connected_labels = ", ".join(sorted(connected)) if connected else "none connected"
        if registry_plan.connector_names:
            focused = [c for c in connected if c in registry_plan.connector_names]
            if focused:
                connected_labels = ", ".join(sorted(focused))

        memory_ctx = await self._memory_engine.build_context_profile(
            org_id=org_id,
            user_id=user_id,
            conversation_id=conversation_id,
            query=query,
            client=client,
        )

        if agent_id:
            agent = resolve_agent_record(client, org_id, agent_id, environment_name=environment_name)
            if not agent:
                agent = build_synthetic_agent_for_task(query, context={"agent_id": agent_id})
                agent["id"] = agent_id
        else:
            agent = build_synthetic_agent_for_task(query, context={"surface": "assistant"})
            agent.setdefault("id", "assistant")

        classification = self._specialist.enrich_classification(classification, agent)
        suppression_keys = list(memory_ctx.get("suppressed_suggestion_keys") or [])
        resolved_agent_id = str(agent.get("id") or agent_id or "")
        if resolved_agent_id and resolved_agent_id not in {"assistant"}:
            try:
                knowledge_assignments = self._knowledge.list_assignments(client, org_id, resolved_agent_id)
            except Exception as exc:  # noqa: BLE001
                logger.debug("orchestrator knowledge assignments skipped agent_id=%s error=%s", resolved_agent_id, exc)
                knowledge_assignments = self._knowledge.resolve_assignments(agent)
        else:
            knowledge_assignments = self._knowledge.resolve_assignments(agent)
        knowledge_section = self._knowledge.build_prompt_section(knowledge_assignments)
        knowledge_gap_message = self._knowledge.assigned_knowledge_gap_message(knowledge_assignments, query)

        pack_state_section = ""
        if extract_pack_ids(knowledge_assignments):
            if not registry_plan.slice_enabled("pack_state"):
                registry_plan = replace(
                    registry_plan,
                    enabled_slices=frozenset(set(registry_plan.enabled_slices) | {"pack_state"}),
                )
            if registry_plan.slice_enabled("pack_state"):
                pack_state_section = build_pack_operational_section(
                    client,
                    org_id=org_id,
                    knowledge_assignments=knowledge_assignments,
                )

        async def _empty_org_bundle() -> tuple[Any, str]:
            return None, ""

        async def _empty_text() -> str:
            return ""

        async def _empty_signals() -> dict[str, Any]:
            return {"signals": []}

        retrieval, org_bundle, company_block, entity_block, signals_payload = await asyncio.gather(
            self._retrieval.retrieve(
                org_id=org_id,
                query=query,
                client=client,
                agent=agent,
                parameters={
                    "surface": "assistant",
                    "include_task_history": False,
                    "rag_top_k": registry_plan.rag_top_k if registry_plan.slice_enabled("rag") else 0,
                    "knowledge_assignments": knowledge_assignments if registry_plan.slice_enabled("rag") else [],
                    "classification": classification,
                    "research_scope": research_scope,
                },
                environment_name=environment_name,
                user_id=user_id,
            ),
            asyncio.to_thread(
                get_org_context_service().get_context_bundle,
                client,
                org_id,
                user_id=user_id,
                depth="standard",
                environment_name=environment_name,
            )
            if registry_plan.slice_enabled("company")
            else _empty_org_bundle(),
            get_company_intelligence_orchestrator().get_context_for_prompt(org_id)
            if registry_plan.slice_enabled("company")
            else _empty_text(),
            build_entity_context_section(org_id, query, settings=self.settings, client=client)
            if registry_plan.slice_enabled("graph")
            else _empty_text(),
            self._signals.collect_signals(
                org_id,
                department=str(classification.get("department") or ""),
                query=query if classification.get("requires_graph") else None,
                client=client,
            )
            if registry_plan.slice_enabled("signals")
            else _empty_signals(),
        )
        try:
            _, org_context_block = org_bundle
        except Exception:  # noqa: BLE001
            org_context_block = ""

        assigned_sources_used = [
            {
                "title": source.get("title") or source.get("source"),
                "score": source.get("score"),
                "documentId": source.get("document_id"),
                "assignmentId": (source.get("provenance") or {}).get("assignment_id"),
                "matchTier": source.get("match_tier"),
            }
            for source in retrieval.rag_sources
        ]
        _, missing_assignment_labels = self._knowledge.filter_rag_sources(
            retrieval.rag_sources,
            knowledge_assignments,
        )
        memory_conflicts = list(retrieval.memory_context.get("memory_conflicts") or [])
        if knowledge_assignments and not assigned_sources_used and not knowledge_gap_message:
            knowledge_gap_message = (
                "I could not find content in your assigned knowledge sources for this question. "
                "Try syncing the source or adjusting include rules."
            )

        task_state_section = ""
        if task_state:
            compact = {
                key: task_state[key]
                for key in ("clarified_params", "current_plan", "completed_steps", "pending_steps")
                if task_state.get(key)
            }
            if compact:
                task_state_section = json.dumps(compact, default=str)[:3000]

        business_signals = list(signals_payload.get("signals") or [])
        business_signals = [
            row
            for row in business_signals
            if not self._quality.should_suppress(
                suppression_keys,
                str(row.get("id") or ""),
                action_text=str(row.get("title") or row.get("summary") or ""),
            )
        ]
        specialist_modifier = self._specialist.build_modifier(
            agent,
            classification,
            business_signals=business_signals,
        )

        raw_sources = self._build_raw_sources(
            org_context_block=org_context_block,
            retrieval=retrieval,
            memory_section=memory_ctx.get("prompt_section") or retrieval.memory_section,
            company_block=company_block,
            entity_block=entity_block,
            connector_context=f"Connected integrations: {connected_labels}",
            task_state_section=task_state_section,
            business_signals=business_signals,
            knowledge_section=knowledge_section,
            knowledge_gap_message=knowledge_gap_message,
            memory_conflicts=memory_conflicts,
            pack_state_section=pack_state_section,
        )
        raw_sources = filter_context_sources(raw_sources, registry_plan)
        # Pattern 9 — distill oversized context before ranking/token budget.
        raw_sources, distillation_meta = self._oil.distill_sources(raw_sources)
        profile = self._context_engine.build_context_profile(
            raw_sources=raw_sources,
            classification=classification,
            department=str(classification.get("department") or ""),
            retrieval_plan=retrieval.retrieval_plan,
            token_budget=registry_plan.token_budget,
        )
        explanation = self._context_engine.explain_context_used(profile)
        sections = profile.prompt_sections
        pre_confidence = self._confidence_engine.assess_pre_execution(
            classification=classification,
            context_profile=profile.to_explanation_dict(),
        )
        mapped_sources = [
            {"title": row.get("label"), "kind": row.get("type"), "source": row.get("label")}
            for row in profile.to_explanation_dict().get("sourcesUsed") or []
            if isinstance(row, dict)
        ]
        generated = await self._explainability.explain_turn(
            response_type="answer",
            org_id=org_id,
            sources=mapped_sources,
            model_output={"reasoning_trace": []},
            classification=classification,
            context_profile=profile.to_explanation_dict(),
            confidence={"score": pre_confidence.get("confidence"), "missing_context": pre_confidence.get("missing_context")},
        )
        context_explanation = generated.get("summary") or explanation
        explainability = generated

        advisor_brief = None
        if classification.get("requires_graph") or classification.get("requires_action") or await self._planning.should_plan(
            classification,
            query,
        ):
            try:
                advisor_brief = await self._advisor.generate_brief(
                    org_id,
                    user_id,
                    department=str(classification.get("department") or ""),
                    query=query,
                    client=client,
                )
            except Exception as exc:  # noqa: BLE001
                logger.debug("orchestrator advisor brief skipped org_id=%s error=%s", org_id, exc)

        execution_gate = self._confidence_engine.assess_execution_gate(
            pre_confidence=pre_confidence,
            risk_evaluation={"requires_approval": bool(classification.get("requires_action"))},
        )

        strategic_plan = None
        if await self._planning.should_plan(classification, query):
            try:
                strategic_plan = await self._planning.create_plan(
                    org_id,
                    user_id,
                    conversation_id,
                    query,
                    {
                        "classification": classification,
                        "connected_integrations": connected,
                        "business_signals": business_signals,
                    },
                )
            except Exception as exc:  # noqa: BLE001
                logger.debug("orchestrator strategic plan skipped org_id=%s error=%s", org_id, exc)

        # Pattern 8 — human-like working memory (LTM / STM / scratchpad).
        working_memory_profile = self._oil.build_working_memory(
            conversation_memory=memory_ctx,
            task_state=task_state,
            org_context_block=org_context_block,
            query=query,
        )
        working_memory = working_memory_profile.to_dict()
        wm_section = working_memory_profile.prompt_section()
        memory_block = (
            sections.get("conversation_memory")
            or sections.get("agent_memory")
            or memory_ctx.get("prompt_section")
            or retrieval.memory_section
        )
        if wm_section and wm_section not in (memory_block or ""):
            memory_block = f"{(memory_block or '').rstrip()}\n\n{wm_section}".strip()

        operational_envelope = self._oil.build_operational_envelope(
            what_happened="assistant_turn_prepared",
            why=context_explanation,
            action={"connectedIntegrations": connected, "strategicPlan": bool(strategic_plan)},
            outcome={},
            confidence=pre_confidence,
            working_memory=working_memory_profile,
            patterns_invoked=[
                "intent_classification_before_llm",
                "retrieval_before_generation",
                "predictive_context_loading",
                "human_like_working_memory",
                "context_distillation",
                "confidence_scoring",
                "multi_stage_retrieval",
                "hierarchical_planning" if strategic_plan else "retrieval_before_generation",
            ],
        )

        research_cascade = dict(retrieval.research_cascade or {})
        from app.services.research_action_bridge import (
            attach_research_actions_to_cascade,
            suggest_research_actions,
        )

        research_actions = suggest_research_actions(
            query,
            research_cascade=research_cascade,
            connected_integrations=connected,
            research_scope=research_scope,
        )
        if research_actions:
            research_cascade = attach_research_actions_to_cascade(research_cascade, research_actions)

        return AssistantTurnContext(
            retrieval=retrieval,
            agent=agent,
            org_context_block=sections.get("org_context") or org_context_block,
            memory_block=memory_block,
            company_block=sections.get("company_intelligence") or company_block,
            entity_block=sections.get("entity_graph") or entity_block,
            task_state_section=sections.get("task_state") or task_state_section,
            connected_integrations=connected,
            context_profile={
                **profile.to_explanation_dict(),
                "contextRegistry": registry_plan.to_explanation_dict(),
                "distillation": distillation_meta,
            },
            context_registry=registry_plan.to_explanation_dict(),
            context_explanation=context_explanation,
            conversation_memory=memory_ctx,
            business_signals=await self._quality.rank_recommendations(
                business_signals,
                org_id=org_id,
                department=str(classification.get("department") or ""),
            ),
            strategic_plan=strategic_plan,
            knowledge_assignments=knowledge_assignments,
            knowledge_section=knowledge_section,
            knowledge_gap_message=knowledge_gap_message,
            assigned_sources_used=assigned_sources_used,
            missing_assignment_labels=missing_assignment_labels,
            memory_conflicts=memory_conflicts,
            specialist_modifier=specialist_modifier,
            pre_execution_confidence=pre_confidence,
            execution_gate=execution_gate,
            advisor_brief=advisor_brief,
            explainability=explainability,
            research_cascade=research_cascade,
            working_memory=working_memory,
            distillation_meta=distillation_meta,
            operational_envelope=operational_envelope,
        )

    def finalize_confidence(
        self,
        *,
        query: str,
        answer: str,
        rag_sources: list[dict[str, Any]] | None,
        validation_confidence: float | None,
        conflict_count: int,
        turn_context: AssistantTurnContext | None,
        risk_level: str | None = None,
    ) -> dict[str, Any]:
        return self._confidence_engine.assess_response(
            query=query,
            answer=answer,
            rag_sources=rag_sources,
            validation_confidence=validation_confidence,
            conflict_count=conflict_count,
            context_profile=turn_context.context_profile if turn_context else None,
            risk_level=risk_level,
        )

    @staticmethod
    def _build_raw_sources(
        *,
        org_context_block: str,
        retrieval: UnifiedRetrievalBundle,
        memory_section: str,
        company_block: str,
        entity_block: str,
        connector_context: str,
        task_state_section: str,
        business_signals: list[dict[str, Any]],
        knowledge_section: str = "",
        knowledge_gap_message: str | None = None,
        memory_conflicts: list[dict[str, Any]] | None = None,
        pack_state_section: str = "",
    ) -> list[ContextSource]:
        sources: list[ContextSource] = []
        if org_context_block.strip():
            sources.append(
                ContextSource(
                    source_id="org_context",
                    source_type="org_context",
                    label="Organization snapshot",
                    score=0.0,
                    content=org_context_block,
                )
            )
        if retrieval.rag_section.strip():
            sources.append(
                ContextSource(
                    source_id="rag",
                    source_type="rag",
                    label="Knowledge base",
                    score=0.0,
                    content=retrieval.rag_section,
                    metadata={"source_count": len(retrieval.rag_sources)},
                )
            )
        if memory_section.strip():
            sources.append(
                ContextSource(
                    source_id="conversation_memory",
                    source_type="conversation_memory",
                    label="Conversation memory",
                    score=0.0,
                    content=memory_section,
                )
            )
        if company_block.strip():
            sources.append(
                ContextSource(
                    source_id="company_intelligence",
                    source_type="company_intelligence",
                    label="Company intelligence",
                    score=0.0,
                    content=company_block,
                )
            )
        if entity_block.strip():
            sources.append(
                ContextSource(
                    source_id="entity_graph",
                    source_type="entity_graph",
                    label="Entity relationships",
                    score=0.0,
                    content=entity_block,
                )
            )
        if connector_context.strip():
            sources.append(
                ContextSource(
                    source_id="connector_context",
                    source_type="connector_context",
                    label="Connected systems",
                    score=0.0,
                    content=connector_context,
                )
            )
        if task_state_section.strip():
            sources.append(
                ContextSource(
                    source_id="task_state",
                    source_type="task_state",
                    label="Active task state",
                    score=0.0,
                    content=f"<task_state>\n{task_state_section}\n</task_state>",
                )
            )
        if business_signals:
            signal_lines = [
                f"- {row.get('title') or row.get('summary') or 'Signal'}"
                for row in business_signals[:5]
                if isinstance(row, dict)
            ]
            if signal_lines:
                sources.append(
                    ContextSource(
                        source_id="graph",
                        source_type="graph",
                        label="Business signals",
                        score=0.0,
                        content="<business_signals>\n" + "\n".join(signal_lines) + "\n</business_signals>",
                    )
                )
        if knowledge_section.strip():
            sources.append(
                ContextSource(
                    source_id="knowledge_assignments",
                    source_type="knowledge_assignments",
                    label="Agent knowledge sources",
                    score=0.0,
                    content=f"<knowledge_assignments>\n{knowledge_section}\n</knowledge_assignments>",
                )
            )
        if pack_state_section.strip():
            sources.append(
                ContextSource(
                    source_id="pack_state",
                    source_type="pack_state",
                    label="Intelligence pack operational state",
                    score=0.0,
                    content=pack_state_section,
                )
            )
        if knowledge_gap_message:
            sources.append(
                ContextSource(
                    source_id="knowledge_gap",
                    source_type="knowledge_gap",
                    label="Knowledge assignment gap",
                    score=0.0,
                    content=f"<knowledge_gap>\n{knowledge_gap_message}\n</knowledge_gap>",
                )
            )
        if memory_conflicts:
            lines = [
                f"- Memory {row.get('memory_a_id')} conflicts with {row.get('memory_b_id')} (human review required)"
                for row in memory_conflicts[:5]
                if isinstance(row, dict)
            ]
            if lines:
                sources.append(
                    ContextSource(
                        source_id="memory_conflicts",
                        source_type="memory_conflicts",
                        label="Agent memory conflicts",
                        score=0.0,
                        content="<memory_conflicts>\n" + "\n".join(lines) + "\n</memory_conflicts>",
                        metadata={"count": len(memory_conflicts)},
                    )
                )
        return sources


_orchestrator: IntelligenceOrchestrator | None = None


def get_intelligence_orchestrator(settings: Settings | None = None) -> IntelligenceOrchestrator:
    global _orchestrator
    if _orchestrator is None or settings is not None:
        _orchestrator = IntelligenceOrchestrator(settings)
    return _orchestrator
