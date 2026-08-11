"""Unit tests — knowledge router + authority rerank."""
from __future__ import annotations

from app.knowledge_fabric.registry import list_platform_packs
from app.knowledge_fabric.retrieval import jurisdiction_allowed, rerank_with_authority
from app.knowledge_fabric.router import (
    classify_knowledge_query,
    recommended_pack_ids_for_department,
)


def test_router_scopes_employment_law_to_jurisdiction_and_legal():
    route = classify_knowledge_query(
        "What does California employment law say about overtime?",
        assigned_pack_ids=["pack.legal", "pack.cybersecurity"],
    )
    assert "legal" in route.departments
    assert "US-CA" in route.jurisdictions
    assert route.pack_ids == ["pack.legal"]


def test_router_respects_assigned_packs_only():
    route = classify_knowledge_query(
        "Explain NIST CSF Govern function",
        assigned_pack_ids=["pack.finance"],
    )
    # Cyber keyword would select cybersecurity, but assignment filters to finance only → finance retained
    assert "pack.finance" in route.pack_ids
    assert "pack.cybersecurity" not in route.pack_ids


def test_authority_rerank_beats_naive_semantic_similarity():
    candidates = [
        {
            "id": "blog",
            "semantic_score": 0.99,
            "authority_score": 0.35,
            "freshness_score": 0.4,
            "content": "random blog",
        },
        {
            "id": "nist",
            "semantic_score": 0.71,
            "authority_score": 0.97,
            "freshness_score": 0.95,
            "content": "NIST CSF",
        },
    ]
    ranked = rerank_with_authority(candidates)
    assert ranked[0]["id"] == "nist"
    assert ranked[0]["score"] > ranked[1]["score"]


def test_marketing_compliance_routes_marketing_and_legal():
    route = classify_knowledge_query(
        "What does the FTC CAN-SPAM rule require for email marketing?",
        assigned_pack_ids=["pack.marketing", "pack.legal", "pack.sales"],
    )
    assert "marketing" in route.departments
    assert "legal" in route.departments
    assert "pack.marketing" in route.pack_ids
    assert "pack.legal" in route.pack_ids


def test_router_canada_federal_separates_from_us_default():
    ca = classify_knowledge_query(
        "What does PIPEDA require under Justice Laws Canada?",
        assigned_pack_ids=["pack.legal"],
    )
    us = classify_knowledge_query(
        "What does U.S. federal employment law say about overtime?",
        assigned_pack_ids=["pack.legal"],
    )
    assert "CA-federal" in ca.jurisdictions
    assert "US-federal" not in ca.jurisdictions
    assert "CA-federal" not in us.jurisdictions
    assert "US-federal" in us.jurisdictions


def test_jurisdiction_filter_blocks_cross_border_chunks():
    assert jurisdiction_allowed("CA-federal", ["US-federal"]) is False
    assert jurisdiction_allowed("US-federal", ["CA-federal"]) is False
    assert jurisdiction_allowed("CA-federal", ["CA-federal"]) is True
    assert jurisdiction_allowed("US-federal", ["US-CA"]) is True
    assert jurisdiction_allowed(None, ["US-federal"]) is True


def test_department_pack_recommendations_use_server_correlation():
    sales = recommended_pack_ids_for_department("Sales")
    legal = recommended_pack_ids_for_department("Legal")
    assert "pack.sales" in sales
    assert "pack.marketing" in sales  # secondary_packs on sales sources
    assert "pack.legal" in legal
    assert "pack.sales" not in legal
    sales_packs = list_platform_packs(agent_department="Sales")
    all_packs = list_platform_packs()
    assert sales_packs[0]["recommended"] is True
    assert sales_packs[0]["pack_id"] in sales
    assert len(sales_packs) == len(all_packs)  # recommendation never hides packs


def test_gov_authority_outranks_academic_and_live_commercial():
    candidates = [
        {
            "id": "hubspot_live",
            "semantic_score": 0.95,
            "authority_score": 0.55,
            "freshness_score": 0.9,
            "content": "hubspot research",
        },
        {
            "id": "saylor",
            "semantic_score": 0.85,
            "authority_score": 0.84,
            "freshness_score": 0.8,
            "content": "saylor syllabus",
        },
        {
            "id": "ftc",
            "semantic_score": 0.80,
            "authority_score": 0.99,
            "freshness_score": 0.95,
            "content": "ftc can-spam",
        },
    ]
    ranked = rerank_with_authority(candidates)
    assert ranked[0]["id"] == "ftc"
    assert ranked[1]["id"] == "saylor"
    assert ranked[2]["id"] == "hubspot_live"
