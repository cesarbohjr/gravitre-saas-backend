"""G1 — Canonical Intelligence State: projection, graph, context compiler, trust tests."""
from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.schemas.intelligence_projection import (
    CanonicalAgent,
    IntelligenceMetrics,
    IntelligenceProvenance,
    IntelligenceSnapshot,
)
from app.services.intelligence_agent_roster import load_canonical_agents
from app.services.intelligence_context_compiler import (
    FORBIDDEN_UNAVAILABLE_AGENT_PHRASES,
    active_agent_trust_answer,
    compile_intelligence_context_for_query,
    current_activity_trust_answer,
    learning_trust_answer,
    prediction_trust_answer,
    resolve_intelligence_hub_deterministic_answer,
    running_agent_trust_answer,
)
from app.services.intelligence_graph_builder import (
    build_intelligence_graph,
    filter_graph_for_lens,
)
from app.services.intelligence_prediction_dedup import normalize_signals_to_predictions
from app.services.intelligence_projection_service import IntelligenceProjectionService


def _agent(
    agent_id: str,
    name: str,
    *,
    configured: str = "active",
    running: bool = False,
) -> CanonicalAgent:
    now = datetime.now(timezone.utc).isoformat()
    return CanonicalAgent(
        id=agent_id,
        name=name,
        department="Sales",
        businessLabel=name,
        technicalLabel=agent_id,
        configuredStatus=configured,  # type: ignore[arg-type]
        executionStatus="running" if running else "idle",
        isConfiguredActive=configured in {"active", "processing"},
        isCurrentlyRunning=running,
        source=IntelligenceProvenance(system="agent_roster", recordId=agent_id, fetchedAt=now),
    )


def _snapshot(agents: list[CanonicalAgent] | None = None) -> IntelligenceSnapshot:
    now = datetime.now(timezone.utc).isoformat()
    agent_list = agents or []
    configured = sum(1 for a in agent_list if a.isConfiguredActive)
    running = sum(1 for a in agent_list if a.isCurrentlyRunning)
    return IntelligenceSnapshot(
        generatedAt=now,
        tenantId="org-g1-test",
        timeWindowHours=24,
        coreState="idle",
        agents=agent_list,
        metrics=IntelligenceMetrics(
            execution={
                "configuredActiveAgents": configured,
                "currentlyRunningAgents": running,
                "concurrentSwarmRuns": 0,
            },
            predictions={"activePredictions": 0},
            knowledge={"knownEntities": 0},
            learning={"recentLearnings": 0},
            outcomes={"measuredOutcomes": 0},
        ),
    )


def test_prediction_dedup_collapses_semantic_duplicates():
    fetched = datetime.now(timezone.utc).isoformat()
    signals = [
        {
            "id": "sig-1",
            "title": "OAuth token expiring",
            "summary": "Salesforce connector needs refresh",
            "department": "operations",
            "confidence": 0.8,
            "source": "connector_health",
        },
        {
            "id": "sig-2",
            "title": "OAuth token expiring",
            "summary": "Salesforce connector needs refresh",
            "department": "operations",
            "confidence": 0.9,
            "source": "connector_health",
        },
    ]
    preds = normalize_signals_to_predictions(signals, fetched_at=fetched)
    assert len(preds) == 1
    assert preds[0].confidence == 0.9


def test_prediction_dedup_flags_unscoped():
    fetched = datetime.now(timezone.utc).isoformat()
    signals = [{"id": "x", "title": "", "summary": "unscoped alert", "source": "test"}]
    preds = normalize_signals_to_predictions(signals, fetched_at=fetched)
    assert len(preds) == 1
    assert "UNSCOPED_PREDICTION" in preds[0].qualityFlags


def test_running_agent_trust_answer_lists_swarm_running_only():
    agents = [
        _agent("a1", "Email Campaign Reporting Agent"),
        _agent("a2", "Idle Analyst", configured="active", running=False),
    ]
    snapshot = _snapshot(agents)
    answer = running_agent_trust_answer(snapshot)
    assert "No agents are currently running" in answer
    assert "2 agents are configured active" in answer


def test_resolve_intelligence_hub_deterministic_active_vs_running():
    agents = [
        _agent("a1", "Email Campaign Reporting Agent"),
        _agent("a2", "Lead Enrichment", running=True),
    ]
    snapshot = _snapshot(agents)
    active_q = resolve_intelligence_hub_deterministic_answer(
        snapshot, "What agents are currently active?"
    )
    running_q = resolve_intelligence_hub_deterministic_answer(
        snapshot, "Which agents are running?"
    )
    assert active_q is not None
    assert "Email Campaign Reporting Agent" in active_q
    assert "Lead Enrichment" in active_q
    assert running_q is not None
    assert "Lead Enrichment" in running_q
    assert "Email Campaign Reporting Agent" not in running_q


def test_active_agent_trust_answer_lists_configured_active():
    agents = [
        _agent("a1", "Lead Scouting Analyst"),
        _agent("a2", "Lead Enrichment"),
        _agent("a3", "AI Visibility Analyst"),
        _agent("a4", "Idle Bot", configured="idle"),
    ]
    snapshot = _snapshot(agents)
    answer = active_agent_trust_answer(snapshot)
    assert "3 agent" in answer
    assert "Lead Scouting Analyst" in answer
    assert "Lead Enrichment" in answer
    assert "AI Visibility Analyst" in answer
    assert "Idle Bot" not in answer


def test_context_compiler_agent_query_returns_acts_visualization():
    agents = [
        _agent("a1", "Lead Scouting Analyst"),
        _agent("a2", "Lead Enrichment"),
    ]
    snapshot = _snapshot(agents)
    ctx, viz = compile_intelligence_context_for_query(
        snapshot, "What agents are currently active?"
    )
    assert "CONFIGURED ACTIVE AGENTS" in ctx
    assert "Lead Scouting Analyst" in ctx
    assert "do NOT say agent status is unavailable" in ctx
    assert viz is not None
    assert viz.lens == "acts"
    assert "agent:a1" in viz.highlightNodeIds
    assert "agent:a2" in viz.highlightNodeIds


def test_graph_builder_agent_nodes_match_snapshot():
    agents = [_agent("a1", "Lead Scouting Analyst"), _agent("a2", "Lead Enrichment")]
    graph = build_intelligence_graph(_snapshot(agents))
    agent_nodes = [n for n in graph.nodes if n.type == "agent"]
    assert len(agent_nodes) == 2
    labels = {n.businessLabel for n in agent_nodes}
    assert labels == {"Lead Scouting Analyst", "Lead Enrichment"}


def test_lens_filter_same_graph_not_separate_topology():
    agents = [
        _agent("a1", "Lead Scouting Analyst"),
        _agent("a2", "Lead Enrichment"),
    ]
    snapshot = _snapshot(agents)
    snapshot.predictions = normalize_signals_to_predictions(
        [
            {
                "id": "p1",
                "title": "Churn risk rising",
                "summary": "Customer segment A",
                "department": "sales",
                "confidence": 0.7,
            }
        ],
        fetched_at=snapshot.generatedAt,
    )
    full = build_intelligence_graph(snapshot)
    acts = filter_graph_for_lens(full, "acts")
    predicts = filter_graph_for_lens(full, "predicts")
    assert any(n.type == "agent" for n in acts.nodes)
    assert not any(n.type == "prediction" for n in acts.nodes)
    assert any(n.type == "prediction" for n in predicts.nodes)
    assert not any(n.type == "agent" for n in predicts.nodes)
    # Core always present
    assert any(n.type == "core" for n in acts.nodes)
    assert any(n.type == "core" for n in predicts.nodes)


def test_tool_agent_status_matches_snapshot_counts():
    from app.services.assistant_tools import tool_agent_status

    canonical = [
        _agent("a1", "Lead Scouting Analyst"),
        _agent("a2", "Lead Enrichment"),
        _agent("a3", "AI Visibility Analyst"),
    ]
    with patch(
        "app.services.assistant_tools.get_supabase_client",
        return_value=MagicMock(),
    ), patch(
        "app.services.intelligence_agent_roster.load_canonical_agents",
        return_value=(canonical, set()),
    ):
        result = tool_agent_status("org-g1", MagicMock())
    assert result["configuredActiveCount"] == 3
    assert result["canonical"] is True
    assert len(result["agents"]) == 3


def test_load_canonical_agents_merges_agents_and_operators():
    client = MagicMock()
    agents_chain = MagicMock()
    agents_chain.select.return_value = agents_chain
    agents_chain.eq.return_value = agents_chain
    agents_chain.order.return_value = agents_chain
    agents_chain.limit.return_value = agents_chain
    agents_chain.execute.return_value = MagicMock(
        data=[
            {
                "id": "agent-1",
                "name": "Lead Scouting Analyst",
                "role": "Analyst",
                "department": "Sales",
                "status": "active",
            }
        ]
    )

    def _table(name: str):
        if name == "agents":
            return agents_chain
        return MagicMock()

    client.table.side_effect = _table

    with patch(
        "app.services.intelligence_agent_roster.list_swarm_runs",
        return_value=[],
    ), patch(
        "app.services.intelligence_agent_roster.list_operators",
        return_value=[
            {
                "id": "op-1",
                "name": "Lead Enrichment",
                "role": "Enrichment",
                "status": "active",
            }
        ],
    ), patch(
        "app.services.intelligence_agent_roster.get_agent",
        return_value=None,
    ):
        agents, running = load_canonical_agents(client, "org-g1")

    assert len(agents) == 2
    names = {a.businessLabel for a in agents}
    assert names == {"Lead Scouting Analyst", "Lead Enrichment"}
    assert sum(1 for a in agents if a.isConfiguredActive) == 2
    assert running == set()


@pytest.mark.asyncio
async def test_page_context_endpoint_returns_canonical_snapshot():
    from httpx import ASGITransport, AsyncClient

    from app.auth.dependencies import get_org_context, require_org_member
    from app.main import app

    org_id = "org-g1-page-context"

    async def _org_context():
        return org_id

    app.dependency_overrides[get_org_context] = _org_context
    app.dependency_overrides[require_org_member] = lambda: (
        {"user_id": "member-1"},
        org_id,
        "member",
    )

    mock_ctx = MagicMock()
    mock_ctx.model_dump.return_value = {
        "snapshot": {"tenantId": org_id, "agents": []},
        "graph": {"nodes": [], "edges": []},
        "activeLens": "knows",
        "metrics": {},
        "qualityFlags": [],
        "suggestedQuestions": ["What agents are currently active?"],
    }

    with patch(
        "app.routers.intelligence_engine.get_intelligence_projection_service"
    ) as mock_svc:
        mock_svc.return_value.build_page_context = AsyncMock(return_value=mock_ctx)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/api/intelligence/page-context")

    app.dependency_overrides.clear()
    assert resp.status_code == 200
    body = resp.json()
    assert body["snapshot"]["tenantId"] == org_id
    assert "What agents are currently active?" in body["suggestedQuestions"]


def test_prod_active_agent_regression_never_claims_status_unavailable():
    """Locks the prod failure: map showed active agents while chat claimed unavailable."""
    agents = [_agent("a1", "Email Campaign Reporting Agent", configured="active")]
    snapshot = _snapshot(agents)
    answer = resolve_intelligence_hub_deterministic_answer(
        snapshot, "What agents are currently active?"
    )
    assert answer is not None
    assert "Email Campaign Reporting Agent" in answer
    lowered = answer.lower()
    for phrase in FORBIDDEN_UNAVAILABLE_AGENT_PHRASES:
        assert phrase not in lowered


def test_section15_predictions_learning_and_activity_acceptance():
    fetched = datetime.now(timezone.utc).isoformat()
    agents = [
        _agent("a1", "Email Campaign Reporting Agent"),
        _agent("a2", "Lead Enrichment", running=True),
    ]
    snapshot = _snapshot(agents)
    snapshot.predictions = normalize_signals_to_predictions(
        [
            {
                "id": "p1",
                "title": "OAuth token expiring",
                "summary": "Salesforce connector needs refresh",
                "department": "operations",
                "confidence": 0.82,
            }
        ],
        fetched_at=fetched,
    )
    from app.schemas.intelligence_projection import IntelligenceProvenance, LearningInsight

    snapshot.learnings = [
        LearningInsight(
            id="l1",
            businessStatement="Customer churn risk elevated for segment A",
            source=IntelligenceProvenance(system="memory_promotion", recordId="l1", fetchedAt=fetched),
        )
    ]
    snapshot.metrics.predictions["activePredictions"] = len(snapshot.predictions)
    snapshot.metrics.learning["recentLearnings"] = len(snapshot.learnings)

    pred_answer = resolve_intelligence_hub_deterministic_answer(
        snapshot, "What predictions need attention?"
    )
    learn_answer = resolve_intelligence_hub_deterministic_answer(
        snapshot, "What has Gravitre learned recently?"
    )
    activity_answer = resolve_intelligence_hub_deterministic_answer(
        snapshot, "What is Gravitre doing right now?"
    )
    assert pred_answer is not None
    assert "OAuth token expiring" in pred_answer
    assert str(len(snapshot.predictions)) in pred_answer
    assert learn_answer is not None
    assert "Customer churn risk" in learn_answer
    assert activity_answer is not None
    assert "Lead Enrichment" in activity_answer
    assert "configured active" in activity_answer.lower()

    ctx, viz = compile_intelligence_context_for_query(snapshot, "What predictions need attention?")
    assert "ACTIVE PREDICTIONS" in ctx
    assert viz is not None and viz.lens == "predicts"
    assert snapshot.metrics.predictions["activePredictions"] == len(snapshot.predictions)


def test_prediction_and_learning_trust_answers_match_metrics():
    fetched = datetime.now(timezone.utc).isoformat()
    snapshot = _snapshot([_agent("a1", "Test Agent")])
    snapshot.predictions = normalize_signals_to_predictions(
        [{"id": "p1", "title": "Risk", "summary": "Scoped risk", "confidence": 0.7}],
        fetched_at=fetched,
    )
    snapshot.metrics.predictions["activePredictions"] = 1
    assert "Scoped risk" in prediction_trust_answer(snapshot)
    assert "No validated business learning" in learning_trust_answer(snapshot)
    assert "No agents are currently running" in current_activity_trust_answer(snapshot)


@pytest.mark.asyncio
async def test_active_agent_trust_regression_map_chat_metric_alignment():
    """Mandatory G1 acceptance: map roster = chat answer = metric counts."""
    agents = [
        _agent("a1", "Lead Scouting Analyst"),
        _agent("a2", "Lead Enrichment"),
        _agent("a3", "AI Visibility Analyst"),
    ]
    snapshot = _snapshot(agents)
    graph = build_intelligence_graph(snapshot)

    # Map: configured active agents from snapshot
    map_active = [a for a in snapshot.agents if a.isConfiguredActive]
    assert len(map_active) == 3

    # Chat: context compiler + trust answer
    answer = active_agent_trust_answer(snapshot)
    ctx, viz = compile_intelligence_context_for_query(
        snapshot, "What agents are currently active?"
    )
    assert str(len(map_active)) in answer
    for agent in map_active:
        assert agent.businessLabel in ctx

    # Metrics: typed execution counts
    assert snapshot.metrics.execution["configuredActiveAgents"] == len(map_active)

    # Visualization: ACTS lens + matching node IDs
    assert viz is not None
    assert viz.lens == "acts"
    graph_agent_ids = {n.id for n in graph.nodes if n.type == "agent"}
    for hid in viz.highlightNodeIds:
        assert hid in graph_agent_ids

    # tool_agent_status alignment
    from app.services.assistant_tools import tool_agent_status

    with patch(
        "app.services.assistant_tools.get_supabase_client",
        return_value=MagicMock(),
    ), patch(
        "app.services.intelligence_agent_roster.load_canonical_agents",
        return_value=(agents, set()),
    ):
        tool_result = tool_agent_status("org-g1", MagicMock())
    assert tool_result["configuredActiveCount"] == len(map_active)


@pytest.mark.asyncio
async def test_projection_service_build_snapshot_uses_cache():
    service = IntelligenceProjectionService()
    service.invalidate("org-cache")

    mock_agents = [_agent("a1", "Test Agent")]
    empty_snapshot = _snapshot(mock_agents)

    with patch.object(
        service,
        "build_snapshot",
        wraps=service.build_snapshot,
    ) as mock_build, patch(
        "app.services.intelligence_projection_service.load_canonical_agents",
        return_value=(mock_agents, set()),
    ), patch(
        "app.services.intelligence_projection_service.get_outcome_learning_service"
    ) as mock_outcomes, patch(
        "app.services.intelligence_projection_service.get_knowledge_graph_service"
    ) as mock_kg, patch(
        "app.services.intelligence_projection_service.get_business_signals_engine"
    ) as mock_signals, patch(
        "app.services.intelligence_projection_service.get_training_signal_service"
    ) as mock_training, patch(
        "app.services.intelligence_projection_service.get_memory_promotion_service"
    ) as mock_memory, patch(
        "app.services.intelligence_projection_service.get_supabase_client",
        return_value=MagicMock(),
    ), patch(
        "app.services.intelligence_projection_service.list_swarm_runs",
        return_value=[],
    ):
        mock_outcomes.return_value.fetch_recent_events = AsyncMock(return_value=[])
        mock_kg.return_value.get_admin_summary = AsyncMock(
            return_value={"entity_count": 0, "relationship_count": 0}
        )
        mock_signals.return_value.collect_signals = AsyncMock(return_value={"signals": []})
        mock_training.return_value.get_training_readiness = AsyncMock(return_value={"by_model": {}})
        mock_memory.return_value.list_candidates = MagicMock(return_value={"total": 0, "candidates": []})

        snap1 = await service.build_snapshot("org-cache", use_cache=True)
        snap2 = await service.build_snapshot("org-cache", use_cache=True)

    assert snap1.generatedAt == snap2.generatedAt
    assert mock_build.call_count == 2  # wraps counts both calls; cache hit on second internal path
