"""CI lint — knowledge source schema standard (process twin of G.2/G.4)."""
from __future__ import annotations

import pytest

from app.knowledge_fabric.license_types import (
    LICENSE_TYPES,
    assert_ingest_allowed,
    license_implies_noncommercial,
)
from app.knowledge_fabric.registry import PLATFORM_KNOWLEDGE_SOURCES
from app.knowledge_fabric.sources.openstax import deliberate_nc_ingest_attempt


def test_every_source_has_required_metadata():
    required = (
        "source_id",
        "publisher",
        "url",
        "source_type",
        "department",
        "ingestion_method",
        "license_type",
        "refresh_frequency",
        "legal_review_status",
    )
    for spec in PLATFORM_KNOWLEDGE_SOURCES:
        for field in required:
            assert getattr(spec, field), f"{spec.source_id} missing {field}"
        assert spec.topics, f"{spec.source_id} topics empty"
        assert spec.license_type in LICENSE_TYPES
        assert 0.0 <= spec.authority_score <= 1.0
        assert 0.0 <= spec.quality_score <= 1.0
        spec.validate()


def test_type_d_cannot_be_permanent_ingest():
    for spec in PLATFORM_KNOWLEDGE_SOURCES:
        if spec.license_type == "D":
            assert spec.ingestion_method == "live_only"
            assert spec.crawl_allowed is False
            with pytest.raises(ValueError, match="must not be permanently ingested"):
                assert_ingest_allowed(
                    spec.license_type,
                    ingestion_method=spec.ingestion_method,
                    crawl_allowed=spec.crawl_allowed,
                    commercial_use_allowed=spec.commercial_use_allowed,
                )


def test_commercial_use_hard_gate_blocks_false_and_unconfirmed():
    with pytest.raises(ValueError, match="commercial_use_allowed"):
        assert_ingest_allowed("A", ingestion_method="bulk", crawl_allowed=True, commercial_use_allowed=False)
    with pytest.raises(ValueError, match="commercial_use_allowed"):
        assert_ingest_allowed("A", ingestion_method="bulk", crawl_allowed=True, commercial_use_allowed=None)


def test_openstax_nc_discrepancy_is_blocked():
    openstax = next(s for s in PLATFORM_KNOWLEDGE_SOURCES if s.source_id == "marketing.openstax.principles")
    assert openstax.commercial_use_allowed is False
    assert openstax.hold_reason
    assert openstax.legal_review_status == "blocked_nc"
    assert license_implies_noncommercial(openstax.license)
    result = deliberate_nc_ingest_attempt(
        {
            "license_type": "A",
            "ingestion_method": "bulk",
            "crawl_allowed": True,
            "commercial_use_allowed": False,
        }
    )
    assert result["rejected"] is True
    assert "commercial_use" in (result["error"] or "")


def test_hubspot_and_trends_are_live_only_type_d():
    hubspot = next(s for s in PLATFORM_KNOWLEDGE_SOURCES if "hubspot" in s.source_id)
    trends = next(s for s in PLATFORM_KNOWLEDGE_SOURCES if "google_trends" in s.source_id)
    for spec in (hubspot, trends):
        assert spec.license_type == "D"
        assert spec.ingestion_method == "live_only"
        assert spec.legal_review_status == "live_retrieval_only"


def test_sales_marketing_have_ingestible_open_sources():
    sm = [s for s in PLATFORM_KNOWLEDGE_SOURCES if s.department in {"sales", "marketing"}]
    assert sm
    ingestible = [s for s in sm if not s.hold_reason and s.license_type in {"A", "B"} and s.commercial_use_allowed]
    assert any(s.source_id.startswith("marketing.ftc") for s in ingestible)
    assert any(s.source_id.startswith("marketing.sba") for s in ingestible)
    assert any(s.source_id.startswith("sales.census") for s in ingestible)
    assert any(".saylor." in s.source_id for s in ingestible)


def test_nist_is_type_a():
    nist = [s for s in PLATFORM_KNOWLEDGE_SOURCES if s.source_id.startswith("cyber.nist")]
    assert nist
    for spec in nist:
        assert spec.license_type == "A"
        assert spec.commercial_use_allowed is True


def test_ae_not_duplicated_by_ingestion_policy_enum():
    """Ensure registry still keys off license_type A–E only (no parallel policy enum field)."""
    for spec in PLATFORM_KNOWLEDGE_SOURCES:
        assert not hasattr(spec, "ingestion_policy")
        assert spec.license_type in LICENSE_TYPES
