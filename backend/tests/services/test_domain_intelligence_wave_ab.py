"""Wave A+B — domain intelligence and domain-aware routing tests."""
from __future__ import annotations

import inspect
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.ml.base import ModelStatus
from app.ml.federated_learning import FederatedLearningCoordinator
from app.services.domain_intelligence_service import (
    DOMAIN_CONFIDENCE_THRESHOLD,
    DomainIntelligenceService,
    get_domain_intelligence_service,
)
from app.services.domain_routing_policy import (
    apply_agent_selection_policy,
    apply_model_selection_policy,
    apply_tool_selection_policy,
    build_routing_metadata,
    is_domain_routing_active,
)
from app.services.learning_strategy_keys import (
    build_route_strategy_key,
    domain_segment_active,
    parse_base_segment_key,
    parse_segment_key,
)
from app.services.intelligence_router import IntelligenceRouter


def _high_confidence_domain(**overrides: object) -> dict:
    base = {
        "industry_key": "saas",
        "industry": "SaaS",
        "department_key": "marketing",
        "department": "Marketing",
        "subdomain_key": "seo",
        "subdomain": "SEO",
        "confidence": 0.82,
        "routing_active": True,
        "source": "rules",
        "profile_id": "marketing",
    }
    base.update(overrides)
    return base


def _low_confidence_domain(**overrides: object) -> dict:
    base = {
        "industry_key": None,
        "department_key": None,
        "subdomain_key": None,
        "confidence": 0.2,
        "routing_active": False,
        "source": "rules",
    }
    base.update(overrides)
    return base


@pytest.mark.asyncio
async def test_domain_classification_marketing_seo():
    service = DomainIntelligenceService()
    with patch.object(service, "_load_org_domain_hints", AsyncMock(return_value={})):
        result = await service.classify(
            "org-1",
            "How do we improve organic traffic and SEO keyword rankings for our campaign?",
        )
    assert result["department_key"] == "marketing"
    assert result["subdomain_key"] == "seo"
    assert result["confidence"] >= DOMAIN_CONFIDENCE_THRESHOLD
    assert result["routing_active"] is True
    assert result["profile_id"] == "marketing"


@pytest.mark.asyncio
async def test_msp_classification():
    service = DomainIntelligenceService()
    with patch.object(service, "_load_org_domain_hints", AsyncMock(return_value={})):
        result = await service.classify(
            "org-1",
            "RMM alert: patch deployment failed on multiple endpoints in the NOC queue.",
        )
    assert result["industry_key"] == "msp" or result["department_key"] == "msp"
    assert result["confidence"] >= DOMAIN_CONFIDENCE_THRESHOLD
    assert result.get("profile_id") == "msp" or result.get("department_key") == "msp"


@pytest.mark.asyncio
async def test_org_profile_industry_fallback():
    service = DomainIntelligenceService()
    org_hints = {
        "industry": "saas",
        "industry_raw": "B2B SaaS",
        "department": "sales",
        "department_raw": "Sales",
        "profile_id": "sales",
    }
    with patch.object(service, "_load_org_domain_hints", AsyncMock(return_value=org_hints)):
        result = await service.classify("org-1", "Can you summarize our team update?")
    assert result["industry_key"] == "saas"
    assert result["department_key"] == "sales"
    assert result["source"] == "org_profile"
    assert result["confidence"] >= 0.65


@pytest.mark.asyncio
async def test_llm_fallback_when_rules_low_confidence():
    service = DomainIntelligenceService()
    llm_domain = {
        "industry": "healthcare",
        "department": "support",
        "subdomain": "technical_support",
        "business_objective": "improve_experience",
        "execution_type": "analysis",
        "confidence": 0.71,
        "source": "llm",
        "profile_id": None,
    }
    with patch.object(service, "_load_org_domain_hints", AsyncMock(return_value={})):
        with patch.object(service, "_classify_by_llm", AsyncMock(return_value=llm_domain)):
            result = await service.classify("org-1", "Need help with a nuanced operational question.")
    assert result["department_key"] == "support"
    assert result["confidence"] >= DOMAIN_CONFIDENCE_THRESHOLD
    assert result["source"] in {"llm", "rules"}


def test_segment_key_legacy_when_low_confidence():
    classification = {
        "intent": "question_answering",
        "department": "sales",
        "domain": _low_confidence_domain(),
    }
    assert domain_segment_active(classification) is False
    assert parse_base_segment_key(classification) == "sales:question_answering"
    assert parse_segment_key(classification) == "sales:question_answering"


def test_segment_key_includes_industry_department_subdomain_task():
    classification = {
        "intent": "data_analysis",
        "department": "marketing",
        "domain": _high_confidence_domain(),
    }
    assert domain_segment_active(classification) is True
    assert parse_base_segment_key(classification) == "saas:marketing:seo:data_analysis"
    assert (
        parse_segment_key(
            {
                **classification,
                "query_cluster_id": "cluster-1",
            }
        )
        == "cluster:cluster-1:saas:marketing:seo:data_analysis"
    )


def test_route_strategy_key_includes_domain_suffix():
    classification = {"intent": "question_answering", "domain": _high_confidence_domain()}
    key = build_route_strategy_key(
        {"primary_model": "llm", "llm_tier": "standard"},
        classification,
        {},
    )
    assert key.endswith(":saas:marketing:seo")


def test_domain_aware_model_routing_low_risk_profile():
    classification = {"domain": _high_confidence_domain(department_key="finance", profile_id="finance")}
    selection = apply_model_selection_policy({"llm_tier": "fast", "primary_model": "llm"}, classification)
    assert selection["llm_tier"] == "standard"
    assert selection.get("domain_routing_applied") is True


def test_domain_aware_agent_routing_connector_preferences():
    classification = {"domain": _high_confidence_domain()}
    agent_selection = apply_agent_selection_policy(
        {"persona": {"preferred_connectors": ["slack"]}, "persona_key": "DEFAULT"},
        classification,
    )
    preferred = agent_selection["persona"]["preferred_connectors"]
    assert "hubspot" in preferred
    assert agent_selection.get("domain_routing_applied") is True


def test_domain_aware_tool_routing_orders_preferred_connectors():
    classification = {"domain": _high_confidence_domain()}
    tools = apply_tool_selection_policy(
        {
            "read_tools": [
                {"function": {"name": "zendesk_search"}, "name": "zendesk_search"},
                {"function": {"name": "hubspot_search"}, "name": "hubspot_search"},
            ],
            "write_tools": [],
        },
        classification,
        {"preferred_connectors": ["hubspot"]},
    )
    first = tools["read_tools"][0]["function"]["name"]
    assert first.startswith("hubspot")


def test_build_routing_metadata():
    classification = {"domain": _high_confidence_domain()}
    meta = build_routing_metadata(classification)
    assert meta["domain_routing_active"] is True
    assert meta["segment_key_format"] == "domain_v2"
    assert meta["profile_id"] == "marketing"


def test_routing_inactive_when_low_confidence():
    classification = {"domain": _low_confidence_domain()}
    assert is_domain_routing_active(classification) is False
    selection = apply_model_selection_policy({"llm_tier": "fast"}, classification)
    assert selection.get("domain_routing_applied") is not True


@pytest.mark.asyncio
async def test_outcome_logging_includes_domain_metadata():
    from app.services.outcome_learning_service import OutcomeLearningService

    service = OutcomeLearningService()
    captured: dict = {}

    async def fake_insert(payload: dict) -> None:
        captured.update(payload)

    with patch.object(service, "_insert_event", fake_insert):
        await service.record_recommendation_outcome(
            "org-1",
            "rec-1",
            "recommendation_created",
            department="marketing",
            task_type="question_answering",
            domain_context=_high_confidence_domain(),
            strategy_key="route:test",
        )
    assert captured["department"] == "marketing"
    assert captured["metadata"]["domain"]["subdomain"] == "seo"
    assert captured["metadata"]["strategy_key"] == "route:test"


def test_intelligence_router_remains_single_hot_path_orchestrator():
    source = inspect.getsource(IntelligenceRouter.route)
    assert "understand" in source
    assert "DynamicDomainRouter" not in source
    assert "DomainIntelligenceService" not in source
    assert source.count("await self._model_selector.select") >= 1


def test_no_dynamic_domain_router_module_as_orchestrator():
    import app.services.domain_routing_policy as policy

    assert not hasattr(policy, "route")
    assert callable(policy.apply_model_selection_policy)


@pytest.mark.asyncio
async def test_federated_learning_remains_disabled():
    coordinator = FederatedLearningCoordinator()
    assert coordinator.catalog_status == ModelStatus.DISABLED
    result = await coordinator.predict_structured(org_id="org-1")
    assert result["status"] == "disabled"


def test_get_domain_intelligence_service_singleton():
    a = get_domain_intelligence_service()
    b = get_domain_intelligence_service()
    assert a is b
