"""CI lint — knowledge source schema standard (process twin of G.2/G.4)."""
from __future__ import annotations

from app.knowledge_fabric.license_types import LICENSE_TYPES
from app.knowledge_fabric.registry import PLATFORM_KNOWLEDGE_SOURCES


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


def test_sales_marketing_held_until_sourcing_decision():
    held = [s for s in PLATFORM_KNOWLEDGE_SOURCES if s.department in {"sales", "marketing"}]
    assert held
    for spec in held:
        assert spec.hold_reason, f"{spec.source_id} must stay on hold"
        assert spec.license_type == "C"


def test_nist_is_type_a():
    nist = [s for s in PLATFORM_KNOWLEDGE_SOURCES if s.source_id.startswith("cyber.nist")]
    assert nist
    for spec in nist:
        assert spec.license_type == "A"
