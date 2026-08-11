"""Unit tests — knowledge router + authority rerank."""
from __future__ import annotations

from app.knowledge_fabric.retrieval import rerank_with_authority
from app.knowledge_fabric.router import classify_knowledge_query


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
