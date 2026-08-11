"""Canonical platform knowledge source registry — CI-linted metadata."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.knowledge_fabric.license_types import assert_ingest_allowed, validate_license_type


@dataclass(frozen=True)
class KnowledgeSourceSpec:
    source_id: str
    publisher: str
    url: str
    source_type: str
    department: str
    industry: str | None
    topics: tuple[str, ...]
    jurisdictions: tuple[str, ...]
    ingestion_method: str
    license_type: str
    commercial_use_allowed: bool
    attribution_required: bool
    crawl_allowed: bool
    refresh_frequency: str
    authority_score: float
    quality_score: float
    pack_id: str
    pack_label: str
    license_notes: str = ""
    hold_reason: str | None = None

    def to_row(self) -> dict[str, Any]:
        return {
            "source_id": self.source_id,
            "publisher": self.publisher,
            "url": self.url,
            "source_type": self.source_type,
            "department": self.department,
            "industry": self.industry,
            "topics": list(self.topics),
            "jurisdictions": list(self.jurisdictions),
            "ingestion_method": self.ingestion_method,
            "license_type": self.license_type,
            "commercial_use_allowed": self.commercial_use_allowed,
            "attribution_required": self.attribution_required,
            "crawl_allowed": self.crawl_allowed,
            "refresh_frequency": self.refresh_frequency,
            "authority_score": self.authority_score,
            "quality_score": self.quality_score,
            "namespace": "platform_shared",
            "status": "paused" if self.hold_reason else "active",
            "metadata": {
                "pack_id": self.pack_id,
                "pack_label": self.pack_label,
                "license_notes": self.license_notes,
                "hold_reason": self.hold_reason,
            },
        }

    def validate(self) -> None:
        validate_license_type(self.license_type)
        if not self.source_id or not self.publisher or not self.url:
            raise ValueError(f"{self.source_id}: missing identity fields")
        if not self.topics:
            raise ValueError(f"{self.source_id}: topics required")
        if not (0.0 <= self.authority_score <= 1.0 and 0.0 <= self.quality_score <= 1.0):
            raise ValueError(f"{self.source_id}: scores out of range")
        if self.hold_reason:
            return
        if self.license_type == "D":
            if self.ingestion_method != "live_only" or self.crawl_allowed:
                raise ValueError(f"{self.source_id}: type D must be live_only / no crawl")
            return
        assert_ingest_allowed(
            self.license_type,
            ingestion_method=self.ingestion_method,
            crawl_allowed=self.crawl_allowed,
        )


PLATFORM_KNOWLEDGE_SOURCES: tuple[KnowledgeSourceSpec, ...] = (
    KnowledgeSourceSpec(
        source_id="legal.courtlistener.opinions",
        publisher="Free Law Project / CourtListener",
        url="https://www.courtlistener.com/api/rest/v4/",
        source_type="api",
        department="legal",
        industry=None,
        topics=("case_law", "opinions", "federal_courts"),
        jurisdictions=("US", "US-federal"),
        ingestion_method="api",
        license_type="B",
        commercial_use_allowed=True,
        attribution_required=True,
        crawl_allowed=False,
        refresh_frequency="realtime",
        authority_score=0.92,
        quality_score=0.9,
        pack_id="pack.legal",
        pack_label="Legal Pack",
        license_notes="CourtListener REST API — use per Free Law Project API terms; attribution required.",
        hold_reason="COURTLISTENER_API_TOKEN not provisioned (REST v4 returns 401 without token).",
    ),
    KnowledgeSourceSpec(
        source_id="legal.us.constitution",
        publisher="U.S. National Archives / U.S. Government",
        url="https://www.archives.gov/founding-docs/constitution-transcript",
        source_type="government_work",
        department="legal",
        industry=None,
        topics=("constitution", "federal_law", "founding_documents"),
        jurisdictions=("US", "US-federal"),
        ingestion_method="bulk",
        license_type="A",
        commercial_use_allowed=True,
        attribution_required=True,
        crawl_allowed=True,
        refresh_frequency="version_change",
        authority_score=0.99,
        quality_score=0.95,
        pack_id="pack.legal",
        pack_label="Legal Pack",
        license_notes="U.S. government work / public domain founding document text.",
    ),
    KnowledgeSourceSpec(
        source_id="legal.openlaws.statutes",
        publisher="OpenLaws",
        url="https://www.openlaws.com/",
        source_type="api",
        department="legal",
        industry=None,
        topics=("statutes", "regulations", "state_law"),
        jurisdictions=("US",),
        ingestion_method="api",
        license_type="B",
        commercial_use_allowed=True,
        attribution_required=True,
        crawl_allowed=False,
        refresh_frequency="version_change",
        authority_score=0.9,
        quality_score=0.88,
        pack_id="pack.legal",
        pack_label="Legal Pack",
        license_notes="API-licensed; requires confirmed OpenLaws credentials before ingest.",
        hold_reason="OPENLAWS_API_KEY not provisioned — registry only until credentials confirmed.",
    ),
    KnowledgeSourceSpec(
        source_id="finance.sec.edgar",
        publisher="U.S. Securities and Exchange Commission",
        url="https://www.sec.gov/edgar/sec-api-documentation",
        source_type="api",
        department="finance",
        industry=None,
        topics=("filings", "xbrl", "corporate_disclosure"),
        jurisdictions=("US", "US-federal"),
        ingestion_method="api",
        license_type="B",
        commercial_use_allowed=True,
        attribution_required=True,
        crawl_allowed=False,
        refresh_frequency="realtime",
        authority_score=0.95,
        quality_score=0.92,
        pack_id="pack.finance",
        pack_label="Finance Pack",
        license_notes="SEC EDGAR APIs — fair access policy; identify User-Agent; no bulk abuse.",
    ),
    KnowledgeSourceSpec(
        source_id="cyber.nist.csf2",
        publisher="National Institute of Standards and Technology",
        url="https://doi.org/10.6028/NIST.CSWP.29",
        source_type="government_work",
        department="cybersecurity",
        industry="msp",
        topics=("csf2", "govern", "identify", "protect", "detect", "respond", "recover"),
        jurisdictions=("US",),
        ingestion_method="bulk",
        license_type="A",
        commercial_use_allowed=True,
        attribution_required=True,
        crawl_allowed=True,
        refresh_frequency="version_change",
        authority_score=0.97,
        quality_score=0.95,
        pack_id="pack.cybersecurity",
        pack_label="Cybersecurity / MSP Pack",
        license_notes=(
            "U.S. government work — not subject to U.S. copyright (17 U.S.C. § 105). "
            "Credit NIST; foreign rights may differ (nist.gov/copyrights-disclaimers)."
        ),
    ),
    KnowledgeSourceSpec(
        source_id="cyber.nist.sp800-53",
        publisher="National Institute of Standards and Technology",
        url="https://csrc.nist.gov/pubs/sp/800/53/r5/upd1/final",
        source_type="government_work",
        department="cybersecurity",
        industry="msp",
        topics=("sp800-53", "controls", "security_privacy"),
        jurisdictions=("US",),
        ingestion_method="bulk",
        license_type="A",
        commercial_use_allowed=True,
        attribution_required=True,
        crawl_allowed=True,
        refresh_frequency="version_change",
        authority_score=0.96,
        quality_score=0.94,
        pack_id="pack.cybersecurity",
        pack_label="Cybersecurity / MSP Pack",
        license_notes="NIST SP — U.S. government work; attribute NIST.",
    ),
    KnowledgeSourceSpec(
        source_id="hr.dol.developer",
        publisher="U.S. Department of Labor",
        url="https://developer.dol.gov/",
        source_type="api",
        department="hr",
        industry=None,
        topics=("labor", "employment", "wage_hour"),
        jurisdictions=("US", "US-federal"),
        ingestion_method="api",
        license_type="B",
        commercial_use_allowed=True,
        attribution_required=True,
        crawl_allowed=False,
        refresh_frequency="daily",
        authority_score=0.9,
        quality_score=0.85,
        pack_id="pack.hr",
        pack_label="HR Pack",
        license_notes="DOL developer APIs — use per DOL API terms.",
    ),
    KnowledgeSourceSpec(
        source_id="hr.onet.occupations",
        publisher="O*NET Resource Center / U.S. Department of Labor",
        url="https://services.onetcenter.org/",
        source_type="api",
        department="hr",
        industry=None,
        topics=("occupations", "skills", "job_taxonomy"),
        jurisdictions=("US",),
        ingestion_method="api",
        license_type="B",
        commercial_use_allowed=True,
        attribution_required=True,
        crawl_allowed=False,
        refresh_frequency="version_change",
        authority_score=0.88,
        quality_score=0.9,
        pack_id="pack.hr",
        pack_label="HR Pack",
        license_notes="O*NET Web Services — requires registered credentials; hold until ONET_API_KEY set.",
        hold_reason="ONET credentials not provisioned — registry only until API access confirmed.",
    ),
    KnowledgeSourceSpec(
        source_id="sales.content.hold",
        publisher="Gravitre (pending sourcing decision)",
        url="https://gravitre.ai/",
        source_type="pending",
        department="sales",
        industry=None,
        topics=("sales_enablement",),
        jurisdictions=(),
        ingestion_method="manual_authored",
        license_type="C",
        commercial_use_allowed=False,
        attribution_required=True,
        crawl_allowed=False,
        refresh_frequency="manual",
        authority_score=0.5,
        quality_score=0.5,
        pack_id="pack.sales",
        pack_label="Sales Pack",
        license_notes="No equivalent government API. Requires Cesar choice: commercial license (C) or Gravitre-authored.",
        hold_reason="Awaiting explicit Sales/Marketing content sourcing decision — do not ingest blogs.",
    ),
    KnowledgeSourceSpec(
        source_id="marketing.content.hold",
        publisher="Gravitre (pending sourcing decision)",
        url="https://gravitre.ai/",
        source_type="pending",
        department="marketing",
        industry=None,
        topics=("marketing_ops",),
        jurisdictions=(),
        ingestion_method="manual_authored",
        license_type="C",
        commercial_use_allowed=False,
        attribution_required=True,
        crawl_allowed=False,
        refresh_frequency="manual",
        authority_score=0.5,
        quality_score=0.5,
        pack_id="pack.marketing",
        pack_label="Marketing Pack",
        license_notes="No equivalent government API. Requires Cesar choice: commercial license (C) or Gravitre-authored.",
        hold_reason="Awaiting explicit Sales/Marketing content sourcing decision — do not ingest blogs.",
    ),
)


def list_platform_packs() -> list[dict[str, Any]]:
    packs: dict[str, dict[str, Any]] = {}
    for spec in PLATFORM_KNOWLEDGE_SOURCES:
        entry = packs.setdefault(
            spec.pack_id,
            {
                "pack_id": spec.pack_id,
                "label": spec.pack_label,
                "department": spec.department,
                "sources": [],
                "ingestible": False,
                "hold": False,
            },
        )
        entry["sources"].append(
            {
                "source_id": spec.source_id,
                "license_type": spec.license_type,
                "hold_reason": spec.hold_reason,
                "authority_score": spec.authority_score,
            }
        )
        if spec.hold_reason:
            entry["hold"] = True
        elif spec.license_type in {"A", "B"}:
            entry["ingestible"] = True
    return list(packs.values())


def get_spec(source_id: str) -> KnowledgeSourceSpec | None:
    for spec in PLATFORM_KNOWLEDGE_SOURCES:
        if spec.source_id == source_id:
            return spec
    return None


def ingestible_specs() -> list[KnowledgeSourceSpec]:
    out: list[KnowledgeSourceSpec] = []
    for spec in PLATFORM_KNOWLEDGE_SOURCES:
        if spec.hold_reason:
            continue
        if spec.license_type in {"A", "B"}:
            out.append(spec)
    return out
