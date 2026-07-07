"""Wave E — intelligence visibility envelope, scoring, maturity, and API tests."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.auth.dependencies import get_org_context, require_admin, require_org_member
from app.main import app
from app.schemas.intelligence_visibility import DecisionTransparencyEnvelope
from app.services.executive_intelligence_scoring_service import (
    DEFAULT_SCORE_WEIGHTS,
    ExecutiveIntelligenceScoringService,
)
from app.services.intelligence_maturity_service import MATURITY_LEVELS, IntelligenceMaturityService
from app.services.intelligence_visibility_sanitizer import sanitize_envelope
from app.services.intelligence_visibility_service import IntelligenceVisibilityService


def _settings(**overrides: object) -> MagicMock:
    base = MagicMock(
        app_env="dev",
        intelligence_visibility_enabled=True,
        domain_adaptive_learning_enabled=True,
    )
    for key, value in overrides.items():
        setattr(base, key, value)
    return base


def test_sanitizer_strips_chain_of_thought_and_consensus_internals():
    raw = {
        "summary": "Grounded answer from CRM data.",
        "chain_of_thought": "hidden reasoning",
        "reasoning_trace": [{"step": "think"}],
        "consensus_discussion": "agents debated",
        "minority_opinions": ["disagree"],
        "vote_breakdown": {"a": 2},
        "nested": {"system_prompt": "secret", "safe": "ok"},
    }
    cleaned = sanitize_envelope(raw)
    assert cleaned["advisory_only"] is True
    assert "chain_of_thought" not in cleaned
    assert "reasoning_trace" not in cleaned
    assert "consensus_discussion" not in cleaned
    assert "minority_opinions" not in cleaned
    assert "vote_breakdown" not in cleaned
    assert "system_prompt" not in cleaned["nested"]
    assert cleaned["nested"]["safe"] == "ok"


def test_executive_scoring_default_weights():
    svc = ExecutiveIntelligenceScoringService()
    assert svc.get_weights() == DEFAULT_SCORE_WEIGHTS
    assert DEFAULT_SCORE_WEIGHTS["trust"] == 0.30
    assert DEFAULT_SCORE_WEIGHTS["learning"] == 0.25
    assert DEFAULT_SCORE_WEIGHTS["freshness"] == 0.20
    assert DEFAULT_SCORE_WEIGHTS["optimization"] == 0.15
    assert DEFAULT_SCORE_WEIGHTS["domain_health"] == 0.10


def test_executive_scoring_weighted_composite():
    svc = ExecutiveIntelligenceScoringService()
    result = svc.compute_score(
        trust_score=0.9,
        learning_score=0.8,
        freshness_score=0.7,
        optimization_score=0.85,
        domain_health_score=0.75,
    )
    assert result["intelligence_score"] is not None
    assert 0.0 <= result["intelligence_score"] <= 1.0
    assert result["score_weights"] == DEFAULT_SCORE_WEIGHTS
    assert set(result["components_used"]) == {
        "trust",
        "learning",
        "freshness",
        "optimization",
        "domain_health",
    }


def test_decision_envelope_extension_points_reserved():
    envelope = DecisionTransparencyEnvelope()
    points = envelope.extension_points
    assert "wave_f_multi_agent_explainability" in points
    assert "wave_g_simulation_transparency" in points
    assert "wave_h_autonomous_research_visibility" in points
    assert envelope.advisory_only is True


def test_alternative_paths_evidence_only():
    svc = IntelligenceVisibilityService(settings=_settings())
    alt = svc._alternative_paths(
        {
            "segment_key": "default:marketing:seo:qa",
            "model_selection": {
                "meta_learning_guidance": {
                    "ranked": ["marketing:seo", "marketing:content", "marketing:ads"],
                    "recommended_key": "marketing:seo",
                    "guidance_strength": 0.22,
                }
            },
            "consensus_discussion": "must not appear",
            "minority_opinions": ["hidden"],
        }
    )
    assert alt is not None
    assert alt.alternative_strategy_count == 3
    assert alt.selected_strategy == "default:marketing:seo:qa"
    assert alt.guidance_strength == pytest.approx(0.22)


@pytest.mark.asyncio
async def test_build_decision_envelope_advisory_only_and_sanitized():
    svc = IntelligenceVisibilityService(settings=_settings())
    with patch.object(svc, "get_trust_health", new=AsyncMock(return_value={"status": "ok"})):
        with patch.object(svc, "_segment_learning_confidence", new=AsyncMock(return_value=None)):
            with patch.object(svc, "_optimization_signals", new=AsyncMock(return_value=[])):
                envelope = await svc.build_decision_envelope(
                    "org-a",
                    decision_type="answer",
                    confidence=0.82,
                    sources=[{"title": "CRM Guide", "kind": "document", "score": 0.9}],
                    classification={"domain": {"department": "marketing", "subdomain": "seo"}},
                    context={"retrieval_effectiveness": {"source_count": 3, "top_sources": []}},
                    response={
                        "reasoning_trace": [{"hidden": True}],
                        "minority_opinions": ["no"],
                        "model_selection": {
                            "meta_learning_guidance": {
                                "ranked": ["a", "b"],
                                "guidance_strength": 0.15,
                            }
                        },
                    },
                )
    assert envelope["advisory_only"] is True
    assert envelope["decision_type"] == "answer"
    assert "reasoning_trace" not in envelope
    assert "minority_opinions" not in envelope
    alt = envelope.get("alternative_paths_considered") or {}
    assert alt.get("alternative_strategy_count") == 2
    assert alt.get("guidance_strength") == pytest.approx(0.15)


@pytest.mark.asyncio
async def test_domain_health_entries_shape():
    svc = IntelligenceVisibilityService(settings=_settings())
    adaptive = {
        "segment_summaries": [
            {
                "segment_key": "default:marketing:seo:qa",
                "sample_count": 40,
                "outcome_multiplier": 1.1,
            }
        ]
    }
    freshness = {"stale_sources": [], "freshness_label": "fresh"}
    optimization = {"pending_recommendations": [{"segment_key": "default:marketing:seo:qa"}]}
    with patch.object(svc, "_safe_admin_call", new=AsyncMock(side_effect=[adaptive, freshness, optimization])):
        with patch("app.domain.loader.list_profile_ids", return_value=["marketing-seo"]):
            with patch(
                "app.domain.loader.load_domain_profile",
                return_value={"label": "Marketing", "department": "marketing"},
            ):
                entries = await svc._compute_domain_health_entries("org-a")
    assert entries
    row = entries[0]
    assert row.domain == "Marketing"
    assert row.learning_confidence in {"high", "medium", "low", "insufficient_data"}
    assert row.freshness in {"good", "mixed", "needs_attention", "unknown"}
    assert row.optimization_recommendations >= 0


@pytest.mark.asyncio
async def test_maturity_levels_defined():
    assert len(MATURITY_LEVELS) == 5
    labels = [row["label"] for row in MATURITY_LEVELS]
    assert labels == [
        "Connected",
        "Learning",
        "Adaptive",
        "Optimizing",
        "Autonomous Intelligence",
    ]


@pytest.mark.asyncio
async def test_maturity_connected_when_no_learning():
    svc = IntelligenceMaturityService()
    client = MagicMock()
    client.table.return_value.select.return_value.eq.return_value.execute.return_value = MagicMock(count=0)
    with patch("app.workflows.repository.get_supabase_client", return_value=client):
        with patch.object(svc, "_learning_segment_stats", new=AsyncMock(return_value={"segment_count": 0})):
            with patch.object(svc, "_freshness_stats", new=AsyncMock(return_value={"freshness_label": "unknown"})):
                with patch.object(svc, "_optimization_pending", new=AsyncMock(return_value=0)):
                    maturity = await svc.compute_maturity("org-a", settings=_settings())
    assert maturity["level"] == 1
    assert maturity["label"] == "Connected"


@pytest.fixture
async def member_client():
    org_id = "org-vis-1111"

    async def _org_context():
        return org_id

    app.dependency_overrides[get_org_context] = _org_context
    app.dependency_overrides[require_org_member] = lambda: ({"user_id": "user-1"}, org_id, "member")
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client, org_id
    app.dependency_overrides.clear()


@pytest.fixture
async def admin_client():
    org_id = "org-vis-1111"

    async def _org_context():
        return org_id

    app.dependency_overrides[get_org_context] = _org_context
    app.dependency_overrides[require_admin] = lambda: ({"user_id": "admin-1"}, org_id)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client, org_id
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_visibility_api_disabled_returns_404(member_client):
    from app.config import get_settings

    client, _org_id = member_client
    disabled = _settings(intelligence_visibility_enabled=False)
    app.dependency_overrides[get_settings] = lambda: disabled
    try:
        response = await client.get("/api/intelligence/visibility/trust-health")
    finally:
        app.dependency_overrides.pop(get_settings, None)
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_visibility_trust_health_member_route(member_client):
    client, org_id = member_client
    payload = {"status": "ok", "org_id": org_id, "advisory_only": True}
    with patch(
        "app.services.intelligence_visibility_service.IntelligenceVisibilityService.get_trust_health",
        new=AsyncMock(return_value=payload),
    ):
        response = await client.get("/api/intelligence/visibility/trust-health")
    assert response.status_code == 200
    assert response.json()["org_id"] == org_id


@pytest.mark.asyncio
async def test_visibility_agent_profile_route(member_client):
    client, org_id = member_client
    payload = {
        "status": "ok",
        "org_id": org_id,
        "agent_id": "agent-123",
        "agent_name": "Marketing Analyst",
        "advisory_only": True,
        "learning_confidence": {"level": "insufficient_data", "insufficient_data": True},
        "outcome_summary": {"status": "insufficient_data", "events_found": 1, "min_required": 5},
    }
    with patch(
        "app.services.intelligence_visibility_service.IntelligenceVisibilityService.get_agent_visibility",
        new=AsyncMock(return_value=payload),
    ):
        response = await client.get("/api/intelligence/visibility/agents/agent-123")
    assert response.status_code == 200
    body = response.json()
    assert body["agent_id"] == "agent-123"
    assert body["advisory_only"] is True
    assert "chain_of_thought" not in body


@pytest.mark.asyncio
async def test_get_agent_visibility_org_scoped():
    svc = IntelligenceVisibilityService(settings=_settings())
    with patch("app.workflows.repository.get_supabase_client") as mock_client:
        mock_client.return_value = MagicMock()
        with patch(
            "app.services.agent_memory_service.ensure_agent_in_org",
            return_value={"id": "agent-1", "name": "Ops Agent", "department": "operations"},
        ):
            with patch(
                "app.services.agent_capability_profile_service.get_agent_capability_profile_service"
            ) as mock_cap:
                mock_cap.return_value.build_profile.return_value = {
                    "capabilities": ["search"],
                    "connectedKnowledgeSources": [],
                    "freshnessStatus": "unknown",
                    "allowedConnectors": [],
                    "availableReadActions": [],
                    "availableWriteActions": [],
                    "approvalRequiredActions": [],
                    "memoryCount": 0,
                    "canRecommend": True,
                    "canExecuteWithApproval": False,
                }
                with patch.object(svc, "_compute_domain_health_entries", new=AsyncMock(return_value=[])):
                    with patch(
                        "app.services.outcome_learning_service.get_outcome_learning_service"
                    ) as mock_outcome:
                        mock_outcome.return_value.get_agent_success_rate = AsyncMock(
                            return_value={"status": "insufficient_data", "events_found": 0, "min_required": 5}
                        )
                        with patch.object(svc, "_safe_admin_call", new=AsyncMock(return_value={"segment_summaries": []})):
                            payload = await svc.get_agent_visibility("org-a", "agent-1")
    assert payload["status"] == "ok"
    assert payload["agent_id"] == "agent-1"
    assert payload["advisory_only"] is True


@pytest.mark.asyncio
async def test_visibility_executive_admin_route(admin_client):
    client, org_id = admin_client
    payload = {
        "org_id": org_id,
        "intelligence_score": 0.72,
        "score_label": "healthy",
        "score_weights": DEFAULT_SCORE_WEIGHTS,
        "advisory_only": True,
    }
    with patch(
        "app.services.intelligence_visibility_service.IntelligenceVisibilityService.get_executive_summary",
        new=AsyncMock(return_value=payload),
    ):
        response = await client.get("/api/intelligence/visibility/executive")
    assert response.status_code == 200
    body = response.json()
    assert body["intelligence_score"] == pytest.approx(0.72)
    assert body["score_weights"]["domain_health"] == 0.10
