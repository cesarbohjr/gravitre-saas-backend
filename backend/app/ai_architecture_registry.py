"""
Gravitre Enterprise Cognitive Architecture registry.

Four layers:
  PERCEPTION — connectors, RAG, event hooks
  MEMORY — pgvector, agent_memories, entity graph, glossary, clusters
  REASONING — AgentIntelligence, company intelligence, ML catalog, decision intelligence
  AUTONOMY — approvals, execution, v10 optimization, continuous learning
"""
from __future__ import annotations

from typing import Any

AI_ARCHITECTURE_REGISTRY: dict[str, dict[str, Any]] = {
    "enterprise_knowledge_graph": {
        "status": "live",
        "service": "KnowledgeGraphService",
        "module": "app.services.knowledge_graph_service",
        "backed_by": "org_entity_relationships (v6)",
        "new_capability": (
            "multi-hop max 3, per-hop confidence decay, graph recommendations, graph explanation"
        ),
        "risk_level": "low",
        "approval_required": False,
        "advisory_only": True,
    },
    "event_driven_intelligence": {
        "status": "live",
        "service": "EventIntelligenceService",
        "module": "app.services.event_intelligence_service",
        "risk_level": "low",
        "approval_required": False,
        "advisory_only": True,
    },
    "digital_twin": {
        "status": "partial",
        "service": "DigitalTwinService",
        "module": "app.services.digital_twin_service",
        "note": "Admin-entered organization_process_inventory only. No simulation.",
        "risk_level": "low",
        "advisory_only": True,
    },
    "business_digital_twin": {
        "status": "partial",
        "service": "BusinessDigitalTwinEngine",
        "module": "app.services.business_digital_twin_engine",
        "scope_boundary": (
            "PERMANENT — evidence-based domain scenarios only. "
            "No general org simulation. V9 boundary preserved."
        ),
        "risk_level": "medium",
        "advisory_only": True,
        "approval_required": True,
    },
    "process_mining": {
        "status": "live",
        "service": "ProcessMiningService",
        "module": "app.services.process_mining_service",
        "new_capability": (
            "health scores, efficiency scores, business impact, connector telemetry"
        ),
        "note": "Pattern detection live. Conformance checking planned.",
        "risk_level": "low",
        "advisory_only": True,
    },
    "consensus_engine": {
        "status": "live",
        "service": "ConsensusEngine",
        "module": "app.operators.consensus_engine",
        "risk_level": "low",
        "advisory_only": True,
        "approval_required": True,
    },
    "multi_agent_swarms": {
        "status": "live",
        "service": "SwarmOrchestrator",
        "module": "app.operators.swarm_orchestrator",
        "backed_by": "SwarmCoordinatorService + ExecutionCore",
        "risk_level": "medium",
        "approval_required": True,
        "advisory_only": False,
    },
    "model_routing": {
        "status": "live",
        "service": "ModelRouter",
        "module": "app.services.model_router",
        "risk_level": "low",
        "advisory_only": False,
    },
    "synthetic_workforce": {
        "status": "live",
        "service": "AGENT_PERSONAS + DEPARTMENT_PERSONA_METADATA",
        "module": "app.operators.agent_prompts",
        "risk_level": "medium",
        "approval_required": True,
        "advisory_only": False,
    },
    "decision_intelligence": {
        "status": "live",
        "service": "DecisionIntelligenceService",
        "module": "app.services.decision_intelligence_service",
        "risk_level": "low",
        "advisory_only": True,
    },
    "autonomous_optimization": {
        "status": "live",
        "service": "OptimizationSuggestionService",
        "module": "app.services.optimization_suggestion_service",
        "note": "Human-gated permanently. Auto-apply scope: slow_step only (v10.1).",
        "risk_level": "medium",
        "approval_required": True,
        "advisory_only": False,
    },
    "ai_trust_layer": {
        "status": "live",
        "service": "AITrustLayer",
        "module": "app.services.ai_trust_layer",
        "risk_level": "low",
        "advisory_only": False,
    },
    "hybrid_memory": {
        "status": "live",
        "service": "HybridMemoryService",
        "module": "app.services.hybrid_memory_service",
        "risk_level": "low",
        "advisory_only": False,
    },
    "predictive_operations": {
        "status": "live",
        "service": "PredictiveOperationsEngine",
        "module": "app.services.predictive_operations_engine",
        "endpoint": "/api/admin/intelligence/predictive-ops",
        "risk_level": "low",
        "advisory_only": True,
    },
    "organizational_memory": {
        "status": "live",
        "service": "AgentMemoryIntelligenceService",
        "module": "app.services.agent_memory_service",
        "new_capability": (
            "memory lineage, freshness scoring, why-gravitre-knows-this query, "
            "conflict detection with human-review flag"
        ),
        "risk_level": "low",
        "advisory_only": False,
    },
    "tabular_bandit_v2": {
        "status": "live",
        "service": "StrategyPerformanceLedger",
        "module": "app.services.strategy_performance_ledger",
        "new_capability": "UCB exploration over strategy_performance_records (v2 base segment fallback)",
        "note": "Superseded as primary policy by tabular_bandit_v3 — still used for fallback",
        "risk_level": "low",
        "advisory_only": True,
    },
    "tabular_bandit_v3": {
        "status": "live",
        "service": "StrategyPerformanceLedger",
        "module": "app.services.strategy_performance_ledger",
        "new_capability": "Cluster-segment UCB via org_query_clusters with v2 fallback",
        "note": "Default policy layer — not neural RL",
        "risk_level": "low",
        "advisory_only": True,
    },
    "federated_learning": {
        "status": "disabled",
        "service": "FederatedLearningCoordinator",
        "module": "app.ml.federated_learning",
        "note": "UNCHANGED — prerequisites not met. Do not activate without legal review.",
        "risk_level": "high",
        "advisory_only": True,
    },
    "world_models": {
        "status": "planned",
        "service": "WorldModelScaffold",
        "module": "app.ml.world_models",
        "new_capability": (
            "auto-checked activation checklist — becomes config change when prerequisites met"
        ),
        "activation": "500 outcome trajectories + causal_impact_analyzer trained + WORLD_MODEL_ENABLED",
        "risk_level": "high",
        "approval_required": True,
        "advisory_only": True,
    },
    "generative_agents": {
        "status": "live",
        "service": "GenerativeAgentCoordinator",
        "module": "app.operators.generative_agent_coordinator",
        "risk_level": "medium",
        "approval_required": True,
        "advisory_only": False,
    },
    "agent_protocols": {
        "status": "live",
        "service": "AgentHandoffProtocol",
        "module": "app.operators.agent_protocol",
        "risk_level": "low",
        "advisory_only": False,
    },
    "ai_os_layer": {
        "status": "live",
        "endpoint": "/api/admin/ai-os/status",
        "module": "app.services.ai_architecture_status_service",
        "risk_level": "low",
        "advisory_only": False,
    },
    "autonomous_research": {
        "status": "live",
        "service": "AutonomousResearchService",
        "module": "app.services.research_service",
        "new_capability": (
            "continuous monitoring, trend detection, source credibility scoring, executive briefs"
        ),
        "risk_level": "low",
        "advisory_only": True,
    },
    "continuous_learning": {
        "status": "live",
        "endpoint": "/api/admin/learning/status",
        "backed_by": "v1-v11 ML roadmap + company intelligence orchestrator",
        "module": "app.services.ai_architecture_status_service",
        "risk_level": "low",
        "advisory_only": False,
    },
    "rads": {
        "status": "live",
        "service": "RetrievalAugmentedDecisionService",
        "module": "app.services.rads_service",
        "risk_level": "low",
        "advisory_only": True,
    },
    "cognitive_architecture": {
        "status": "live",
        "documentation": "backend/app/ai_architecture_registry.py",
        "endpoint": "/api/admin/ai-architecture/registry",
        "risk_level": "low",
        "advisory_only": False,
    },
}


def get_registry() -> dict[str, dict[str, Any]]:
    return {key: dict(value) for key, value in AI_ARCHITECTURE_REGISTRY.items()}


def count_by_status() -> dict[str, int]:
    counts: dict[str, int] = {}
    for meta in AI_ARCHITECTURE_REGISTRY.values():
        status = str(meta.get("status") or "unknown")
        counts[status] = counts.get(status, 0) + 1
    return counts
