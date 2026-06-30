"""STA-295: Marketing pack brand/positioning knowledge store audit."""
from __future__ import annotations

from app.marketplace.marketing_pack_brand_knowledge_gaps import (
    BRAND_KNOWLEDGE_CAPABILITIES,
    BRAND_VOICE_SEED_LABEL,
    audit_marketing_pack_brand_knowledge,
)


def test_audit_returns_sta295_structure():
    report = audit_marketing_pack_brand_knowledge()
    assert report["issue"] == "STA-295"
    assert report["v1StructuredBrandStoreRequired"] is False
    assert report["brandVoiceSeedLabel"] == BRAND_VOICE_SEED_LABEL
    assert len(report["capabilities"]) == len(BRAND_KNOWLEDGE_CAPABILITIES)


def test_unified_retrieval_and_department_rag_exist():
    report = audit_marketing_pack_brand_knowledge()
    by_key = {row["key"]: row for row in report["capabilities"]}
    assert by_key["unified_retrieval_service"]["liveState"] == "exists"
    assert by_key["department_scoped_rag_migration"]["liveState"] == "exists"
    assert by_key["agent_intelligence_retrieval_wiring"]["liveState"] == "exists"


def test_brand_voice_seed_is_partial_in_marketing_pack():
    report = audit_marketing_pack_brand_knowledge()
    by_key = {row["key"]: row for row in report["capabilities"]}
    assert by_key["pack_brand_voice_seed"]["liveState"] == "partial"
    assert by_key["marketing_knowledge_pack"]["liveState"] == "partial"


def test_structured_brand_store_not_required_for_v1():
    report = audit_marketing_pack_brand_knowledge()
    by_key = {row["key"]: row for row in report["capabilities"]}
    assert by_key["structured_brand_store"]["liveState"] == "missing"
    assert by_key["pack_scoped_brand_primitive"]["liveState"] == "missing"
    assert report["summary"]["v1Ready"] is True


def test_documented_states_match_live():
    report = audit_marketing_pack_brand_knowledge()
    assert all(row["stateMatchesDoc"] for row in report["capabilities"])
