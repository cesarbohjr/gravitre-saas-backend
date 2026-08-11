"""Canonical platform knowledge source registry — CI-linted metadata.

A–E license_type remains the sole classification scheme. Extra fields
(license, license_url, derivatives_allowed, third_party_content_present,
legal_review_status) add granularity on the same knowledge_sources rows.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.knowledge_fabric.license_types import (
    assert_ingest_allowed,
    validate_legal_review_status,
    validate_license_type,
)


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
    # Extended A–E granularity (same table — not a parallel schema)
    license: str | None = None
    license_url: str | None = None
    derivatives_allowed: bool | None = None
    third_party_content_present: bool = False
    legal_review_status: str = "unreviewed"
    secondary_packs: tuple[str, ...] = ()
    # Wave 2 licensing / retrieval / freshness
    licence_verified: bool = False
    license_verified_at: str | None = None
    retrieval_semantic: bool = True
    retrieval_keyword: bool = True
    citation_required: bool = True
    refresh_days: int | None = None
    effective_date_sensitive: bool = False

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
            "license": self.license,
            "license_url": self.license_url,
            "derivatives_allowed": self.derivatives_allowed,
            "third_party_content_present": self.third_party_content_present,
            "legal_review_status": self.legal_review_status,
            "licence_verified": self.licence_verified,
            "license_verified_at": self.license_verified_at,
            "retrieval_semantic": self.retrieval_semantic,
            "retrieval_keyword": self.retrieval_keyword,
            "citation_required": self.citation_required,
            "refresh_days": self.refresh_days,
            "effective_date_sensitive": self.effective_date_sensitive,
            "metadata": {
                "pack_id": self.pack_id,
                "pack_label": self.pack_label,
                "license_notes": self.license_notes,
                "hold_reason": self.hold_reason,
                "secondary_packs": list(self.secondary_packs),
            },
        }

    def validate(self) -> None:
        validate_license_type(self.license_type)
        validate_legal_review_status(self.legal_review_status)
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
            if self.legal_review_status not in {"live_retrieval_only", "verified_live"}:
                raise ValueError(f"{self.source_id}: type D needs live_retrieval_only review status")
            return
        assert_ingest_allowed(
            self.license_type,
            ingestion_method=self.ingestion_method,
            crawl_allowed=self.crawl_allowed,
            commercial_use_allowed=self.commercial_use_allowed,
            licence_verified=self.licence_verified,
        )


def _base_legal_finance_cyber_hr() -> tuple[KnowledgeSourceSpec, ...]:
    return (
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
            license="CourtListener-API",
            license_url="https://www.courtlistener.com/api/rest-info/",
            derivatives_allowed=None,
            legal_review_status="pending_credentials",
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
            license="US-Gov-Work",
            license_url="https://www.archives.gov/founding-docs/constitution-transcript",
            derivatives_allowed=True,
            legal_review_status="verified_live",
            licence_verified=True,
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
            license="OpenLaws-API",
            license_url="https://www.openlaws.com/",
            legal_review_status="pending_credentials",
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
            license="SEC-EDGAR-API",
            license_url="https://www.sec.gov/edgar/sec-api-documentation",
            derivatives_allowed=True,
            legal_review_status="verified_live",
            licence_verified=True,
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
            license="US-Gov-Work",
            license_url="https://www.nist.gov/open",
            derivatives_allowed=True,
            legal_review_status="verified_live",
            licence_verified=True,
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
            license="US-Gov-Work",
            license_url="https://www.nist.gov/open",
            derivatives_allowed=True,
            legal_review_status="verified_live",
            licence_verified=True,
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
            license="DOL-API",
            license_url="https://developer.dol.gov/",
            derivatives_allowed=True,
            legal_review_status="verified_live",
            licence_verified=True,
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
            license="ONET-API",
            license_url="https://www.onetcenter.org/dataAuth.html",
            legal_review_status="pending_credentials",
            license_notes="O*NET Web Services — requires registered credentials; hold until ONET_API_KEY set.",
            hold_reason="ONET credentials not provisioned — registry only until API access confirmed.",
        ),
    )


def _sales_marketing_sources() -> tuple[KnowledgeSourceSpec, ...]:
    saylor_common = dict(
        publisher="Saylor Academy",
        source_type="open_course",
        industry=None,
        jurisdictions=(),
        ingestion_method="bulk",
        license_type="A",
        commercial_use_allowed=True,
        attribution_required=True,
        crawl_allowed=True,
        refresh_frequency="version_change",
        authority_score=0.84,
        quality_score=0.82,
        license="CC-BY-3.0",
        license_url="https://learn.saylor.org/course/view.php?id=1250",
        derivatives_allowed=True,
        third_party_content_present=True,
        legal_review_status="filtered_provenance",
        licence_verified=True,
        refresh_days=90,
        license_notes=(
            "Live footer: Saylor-authored content CC BY 3.0; third-party materials keep "
            "their own licenses — ingest only provenance-filtered Saylor-authored pages "
            "(guest-accessible syllabi/intros). UNIT READINGS BLOCKED until further "
            "clarification (Cesar 2026-08-11): no authenticated-enrollment provenance "
            "pass / deeper ingest without explicit reopen. Resource allowlist: "
            "CC-BY-3.0/4.0, CC-BY-SA-3.0/4.0; block NC/ARR/UNKNOWN."
        ),
    )
    saylor_specs = (
        KnowledgeSourceSpec(
            source_id="marketing.saylor.bus203",
            url="https://learn.saylor.org/course/view.php?id=1250",
            department="marketing",
            topics=("marketing_strategy", "segmentation", "promotion", "pricing", "consumer_behavior"),
            pack_id="pack.marketing",
            pack_label="Marketing Pack",
            secondary_packs=("pack.sales",),
            **saylor_common,
        ),
        KnowledgeSourceSpec(
            source_id="sales.saylor.bus633",
            url="https://learn.saylor.org/course/view.php?id=881",
            department="sales",
            topics=("personal_selling", "sales_management", "pipeline"),
            pack_id="pack.sales",
            pack_label="Sales Pack",
            secondary_packs=("pack.marketing",),
            **saylor_common,
        ),
        KnowledgeSourceSpec(
            source_id="marketing.saylor.bus630",
            url="https://learn.saylor.org/course/view.php?id=789",
            department="marketing",
            topics=("consumer_behavior", "customer_value"),
            pack_id="pack.marketing",
            pack_label="Marketing Pack",
            **saylor_common,
        ),
        KnowledgeSourceSpec(
            source_id="marketing.saylor.bus631",
            url="https://learn.saylor.org/course/view.php?id=878",
            department="marketing",
            topics=("brand_management", "positioning", "promotion"),
            pack_id="pack.marketing",
            pack_label="Marketing Pack",
            **saylor_common,
        ),
        KnowledgeSourceSpec(
            source_id="marketing.saylor.bus632",
            url="https://learn.saylor.org/course/view.php?id=1266",
            department="marketing",
            topics=("digital_marketing", "advertising"),
            pack_id="pack.marketing",
            pack_label="Marketing Pack",
            **saylor_common,
        ),
        KnowledgeSourceSpec(
            source_id="marketing.saylor.bus634",
            url="https://learn.saylor.org/course/view.php?id=1278",
            department="marketing",
            topics=("market_research", "marketing_strategy"),
            pack_id="pack.marketing",
            pack_label="Marketing Pack",
            **saylor_common,
        ),
        KnowledgeSourceSpec(
            source_id="marketing.saylor.bus502",
            url="https://learn.saylor.org/course/view.php?id=669",
            department="marketing",
            topics=("marketing_strategy", "targeting", "positioning"),
            pack_id="pack.marketing",
            pack_label="Marketing Pack",
            **saylor_common,
        ),
        KnowledgeSourceSpec(
            source_id="marketing.saylor.bus615",
            url="https://learn.saylor.org/course/view.php?id=796",
            department="marketing",
            topics=("international_marketing", "marketing_strategy"),
            pack_id="pack.marketing",
            pack_label="Marketing Pack",
            **saylor_common,
        ),
    )
    return (
        KnowledgeSourceSpec(
            source_id="marketing.openstax.principles",
            publisher="OpenStax / Rice University",
            url="https://openstax.org/books/principles-marketing/pages/preface",
            source_type="open_textbook",
            department="marketing",
            industry=None,
            topics=(
                "marketing_strategy",
                "customer_value",
                "segmentation",
                "targeting",
                "positioning",
                "consumer_behavior",
                "market_research",
                "product_strategy",
                "pricing",
                "distribution",
                "promotion",
                "advertising",
                "public_relations",
                "digital_marketing",
                "personal_selling",
                "sales_promotions",
                "marketing_metrics",
                "ethics",
            ),
            jurisdictions=(),
            ingestion_method="bulk",
            license_type="C",
            commercial_use_allowed=False,
            attribution_required=True,
            crawl_allowed=False,
            refresh_frequency="manual",
            authority_score=0.88,
            quality_score=0.9,
            pack_id="pack.marketing",
            pack_label="Marketing Pack",
            license="CC-BY-NC-SA-4.0",
            license_url="https://openstax.org/books/principles-marketing/pages/preface",
            derivatives_allowed=True,
            third_party_content_present=False,
            legal_review_status="blocked_nc",
            secondary_packs=("pack.sales",),
            license_notes=(
                "LIVE DISCREPANCY 2026-08-11: preface + chapter pages state "
                "CC BY-NC-SA 4.0 (NonCommercial), not CC BY 4.0. Shared-corpus ingest HALTED. "
                "BLOCKED until further clarification (Cesar 2026-08-11) — no OpenStax "
                "commercial reuse / alternate-title ingest without explicit reopen."
            ),
            hold_reason=(
                "blocked until further clarification (Cesar 2026-08-11): CC BY-NC-SA 4.0 "
                "live-verified; commercial_use false; do not ingest."
            ),
        ),
        *saylor_specs,
        KnowledgeSourceSpec(
            source_id="marketing.ftc.business_guidance",
            publisher="U.S. Federal Trade Commission",
            url="https://www.ftc.gov/business-guidance",
            source_type="government_work",
            department="marketing",
            industry=None,
            topics=(
                "can_spam",
                "endorsements",
                "influencers",
                "native_advertising",
                "deceptive_advertising",
                "advertising",
                "compliance",
                "ethics",
            ),
            jurisdictions=("US", "US-federal"),
            ingestion_method="bulk",
            license_type="A",
            commercial_use_allowed=True,
            attribution_required=True,
            crawl_allowed=True,
            refresh_frequency="weekly",
            authority_score=0.99,
            quality_score=0.95,
            pack_id="pack.marketing",
            pack_label="Marketing Pack",
            license="US-Gov-Work",
            license_url="https://www.ftc.gov/policy-notices/website-policy",
            derivatives_allowed=True,
            third_party_content_present=False,
            legal_review_status="verified_live",
            licence_verified=True,
            secondary_packs=("pack.legal",),
            license_notes=(
                "Live-verified: FTC website policy — U.S. government work / public domain "
                "(17 U.S.C. § 105). REFRESHABLE regulatory guidance. Cross-links Legal pack."
            ),
        ),
        KnowledgeSourceSpec(
            source_id="marketing.sba.guidance",
            publisher="U.S. Small Business Administration",
            url="https://www.sba.gov/business-guide/plan-your-business/market-research-competitive-analysis",
            source_type="government_work",
            department="marketing",
            industry=None,
            topics=(
                "market_research",
                "competitive_analysis",
                "marketing_strategy",
                "customer_acquisition",
                "customer_retention",
                "sales_planning",
            ),
            jurisdictions=("US", "US-federal"),
            ingestion_method="bulk",
            license_type="A",
            commercial_use_allowed=True,
            attribution_required=True,
            crawl_allowed=True,
            refresh_frequency="weekly",
            authority_score=0.90,
            quality_score=0.88,
            pack_id="pack.marketing",
            pack_label="Marketing Pack",
            license="US-Gov-Work",
            license_url="https://www.sba.gov/about-sba/open-government/about-sbagov-website/privacy-policy",
            derivatives_allowed=True,
            third_party_content_present=False,
            legal_review_status="verified_live",
            licence_verified=True,
            secondary_packs=("pack.sales",),
            license_notes=(
                "Live-verified: SBA.gov government information is public domain; "
                "exclude any third-party copyrighted embeds."
            ),
        ),
        KnowledgeSourceSpec(
            source_id="sales.census.api",
            publisher="U.S. Census Bureau",
            url="https://www.census.gov/data/developers/about/terms-of-service.html",
            source_type="api",
            department="sales",
            industry=None,
            topics=(
                "geography",
                "industry",
                "establishments",
                "employment",
                "population",
                "income",
                "business_formation",
                "trade",
            ),
            jurisdictions=("US", "US-federal"),
            ingestion_method="api",
            license_type="B",
            commercial_use_allowed=True,
            attribution_required=True,
            crawl_allowed=False,
            refresh_frequency="weekly",
            authority_score=0.99,
            quality_score=0.95,
            pack_id="pack.sales",
            pack_label="Sales Pack",
            license="Census-Data-API",
            license_url="https://www.census.gov/data/developers/about/terms-of-service.html",
            derivatives_allowed=True,
            third_party_content_present=False,
            legal_review_status="verified_live",
            licence_verified=True,
            secondary_packs=("pack.marketing",),
            license_notes=(
                "Live-verified Census API ToS: permitted to develop services that get Census "
                "data; attribution notice required; API key for most datasets. Structured "
                "intelligence — not narrative scrape."
            ),
        ),
        KnowledgeSourceSpec(
            source_id="marketing.google_trends.live",
            publisher="Google Trends",
            url="https://trends.google.com/trends/",
            source_type="live_signal",
            department="marketing",
            industry=None,
            topics=(
                "topic_interest",
                "keyword_interest",
                "geo_interest",
                "historical_interest",
                "trend_comparison",
            ),
            jurisdictions=(),
            ingestion_method="live_only",
            license_type="D",
            commercial_use_allowed=False,
            attribution_required=True,
            crawl_allowed=False,
            refresh_frequency="realtime",
            authority_score=0.75,
            quality_score=0.7,
            pack_id="pack.marketing",
            pack_label="Marketing Pack",
            license="Google-Trends-Terms",
            license_url="https://policies.google.com/terms",
            derivatives_allowed=False,
            third_party_content_present=False,
            legal_review_status="live_retrieval_only",
            secondary_packs=("pack.sales",),
            license_notes=(
                "Live signal only. Official Trends API alpha credential not configured "
                "(2026-08-11) — use live-research connector fallback; never permanent ingest."
            ),
        ),
        KnowledgeSourceSpec(
            source_id="marketing.hubspot.research_live",
            publisher="HubSpot",
            url="https://www.hubspot.com/state-of-marketing",
            source_type="commercial_research",
            department="marketing",
            industry=None,
            topics=("marketing_research", "benchmarks"),
            jurisdictions=(),
            ingestion_method="live_only",
            license_type="D",
            commercial_use_allowed=False,
            attribution_required=True,
            crawl_allowed=False,
            refresh_frequency="realtime",
            authority_score=0.55,
            quality_score=0.6,
            pack_id="pack.marketing",
            pack_label="Marketing Pack",
            license="HubSpot-Site-Terms",
            license_url="https://legal.hubspot.com/terms-of-service",
            derivatives_allowed=False,
            third_party_content_present=False,
            legal_review_status="live_retrieval_only",
            license_notes=(
                "LIVE_RETRIEVAL_ONLY — do not permanently ingest HubSpot commercial research "
                "into platform_shared (type D caution)."
            ),
        ),
    )


def _wave2_expansion_sources() -> tuple[KnowledgeSourceSpec, ...]:
    """Genuinely new Wave 2 KF sources (Phase 0 deduped). licence_verified set after live check."""
    us_gov = dict(
        license_type="A",
        commercial_use_allowed=True,
        attribution_required=True,
        crawl_allowed=True,
        license="US-Gov-Work",
        license_url="https://www.usa.gov/government-works",
        derivatives_allowed=True,
        legal_review_status="verified_live",
        licence_verified=True,
        retrieval_semantic=True,
        retrieval_keyword=True,
        citation_required=True,
        refresh_days=30,
    )
    ca_ogl = dict(
        license_type="A",
        commercial_use_allowed=True,
        attribution_required=True,
        crawl_allowed=True,
        license="Canada-OGL",
        license_url="https://open.canada.ca/en/open-government-licence-canada",
        derivatives_allowed=True,
        legal_review_status="verified_live",
        licence_verified=True,
        retrieval_semantic=True,
        retrieval_keyword=True,
        citation_required=True,
        refresh_days=30,
        effective_date_sensitive=True,
    )
    return (
        KnowledgeSourceSpec(
            source_id="hr.dol.employment_law_guide",
            publisher="U.S. Department of Labor / Wage and Hour Division",
            url="https://www.dol.gov/agencies/whd/employment-law-guide",
            source_type="government_work",
            department="hr",
            industry=None,
            topics=("employment_law", "wage_hour", "flsa", "fmla", "dol_guide"),
            jurisdictions=("US", "US-federal"),
            ingestion_method="bulk",
            refresh_frequency="monthly",
            authority_score=0.96,
            quality_score=0.9,
            pack_id="pack.hr",
            pack_label="HR Pack",
            license_notes=(
                "U.S. government work (17 U.S.C. § 105) — live-confirmed before ingest. "
                "Expands beyond hr.dol.developer FLSA/FMLA snippets."
            ),
            **us_gov,
        ),
        KnowledgeSourceSpec(
            source_id="hr.eeoc.employer_guidance",
            publisher="U.S. Equal Employment Opportunity Commission",
            url="https://www.eeoc.gov/employers",
            source_type="government_work",
            department="hr",
            industry=None,
            topics=("eeoc", "employment_discrimination", "title_vii", "employer_guidance"),
            jurisdictions=("US", "US-federal"),
            ingestion_method="bulk",
            refresh_frequency="monthly",
            authority_score=0.97,
            quality_score=0.9,
            pack_id="pack.hr",
            pack_label="HR Pack",
            license_notes="U.S. government work — EEOC employer guidance + guidance library.",
            **us_gov,
        ),
        KnowledgeSourceSpec(
            source_id="legal.ca.justice_laws",
            publisher="Department of Justice Canada / Justice Laws Website",
            url="https://laws-lois.justice.gc.ca/eng/",
            source_type="government_work",
            department="legal",
            industry=None,
            topics=("statutes", "regulations", "pipeda", "competition_act", "canada_federal"),
            jurisdictions=("CA", "CA-federal"),
            ingestion_method="bulk",
            refresh_frequency="monthly",
            authority_score=0.98,
            quality_score=0.94,
            pack_id="pack.legal",
            pack_label="Legal Pack",
            license_notes=(
                "Canada Open Government Licence — commercial use with attribution; "
                "chunks carry jurisdiction/act/current_to_date metadata. New jurisdiction — "
                "router-tested US vs CA separation required."
            ),
            **ca_ogl,
        ),
        KnowledgeSourceSpec(
            source_id="cyber.nist.ai_rmf",
            publisher="National Institute of Standards and Technology",
            url="https://doi.org/10.6028/NIST.AI.100-1",
            source_type="government_work",
            department="cybersecurity",
            industry="msp",
            topics=("ai_rmf", "govern", "map", "measure", "manage", "ai_risk"),
            jurisdictions=("US",),
            ingestion_method="bulk",
            refresh_frequency="version_change",
            authority_score=0.97,
            quality_score=0.94,
            pack_id="pack.cybersecurity",
            pack_label="Cybersecurity / MSP Pack",
            license_notes="NIST AI RMF 1.0 — U.S. government work; attribute NIST.",
            **{**us_gov, "license_url": "https://www.nist.gov/open", "refresh_days": 90},
        ),
        KnowledgeSourceSpec(
            source_id="cyber.nist.genai_profile",
            publisher="National Institute of Standards and Technology",
            url="https://doi.org/10.6028/NIST.AI.600-1",
            source_type="government_work",
            department="cybersecurity",
            industry="msp",
            topics=("genai", "ai_rmf", "content_integrity", "ai_risk"),
            jurisdictions=("US",),
            ingestion_method="bulk",
            refresh_frequency="version_change",
            authority_score=0.96,
            quality_score=0.93,
            pack_id="pack.cybersecurity",
            pack_label="Cybersecurity / MSP Pack",
            license_notes="NIST AI 600-1 Generative AI Profile — U.S. government work.",
            **{**us_gov, "license_url": "https://www.nist.gov/open", "refresh_days": 90},
        ),
        KnowledgeSourceSpec(
            source_id="cyber.nist.zero_trust",
            publisher="National Institute of Standards and Technology",
            url="https://doi.org/10.6028/NIST.SP.800-207",
            source_type="government_work",
            department="cybersecurity",
            industry="msp",
            topics=("zero_trust", "zta", "sp800-207", "access_control"),
            jurisdictions=("US",),
            ingestion_method="bulk",
            refresh_frequency="version_change",
            authority_score=0.96,
            quality_score=0.93,
            pack_id="pack.cybersecurity",
            pack_label="Cybersecurity / MSP Pack",
            license_notes="NIST SP 800-207 Zero Trust Architecture — U.S. government work.",
            **{**us_gov, "license_url": "https://www.nist.gov/open", "refresh_days": 90},
        ),
        KnowledgeSourceSpec(
            source_id="cyber.cisa.advisories",
            publisher="Cybersecurity and Infrastructure Security Agency",
            url="https://www.cisa.gov/news-events/cybersecurity-advisories",
            source_type="government_work",
            department="cybersecurity",
            industry="msp",
            topics=("cisa", "advisories", "cyber_threats", "msp", "ransomware"),
            jurisdictions=("US", "US-federal"),
            ingestion_method="bulk",
            refresh_frequency="weekly",
            authority_score=0.95,
            quality_score=0.9,
            pack_id="pack.cybersecurity",
            pack_label="Cybersecurity / MSP Pack",
            license_notes="CISA advisories / MSP guidance / StopRansomware — U.S. government work.",
            **{**us_gov, "refresh_days": 7},
        ),
        KnowledgeSourceSpec(
            source_id="marketing.ca.competition_bureau",
            publisher="Competition Bureau Canada",
            url="https://competition-bureau.canada.ca/en/deceptive-marketing-practices",
            source_type="government_work",
            department="marketing",
            industry=None,
            topics=(
                "deceptive_marketing",
                "influencer_marketing",
                "competition_bureau",
                "advertising",
                "canada",
            ),
            jurisdictions=("CA", "CA-federal"),
            ingestion_method="bulk",
            refresh_frequency="monthly",
            authority_score=0.96,
            quality_score=0.9,
            pack_id="pack.marketing",
            pack_label="Marketing Pack",
            secondary_packs=("pack.legal",),
            license_notes=(
                "Canada Open Government Licence — Competition Bureau deceptive + influencer "
                "marketing guidance. Cross-pack with Legal."
            ),
            **ca_ogl,
        ),
    )


PLATFORM_KNOWLEDGE_SOURCES: tuple[KnowledgeSourceSpec, ...] = (
    *_base_legal_finance_cyber_hr(),
    *_sales_marketing_sources(),
    *_wave2_expansion_sources(),
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
                "legal_review_status": spec.legal_review_status,
                "commercial_use_allowed": spec.commercial_use_allowed,
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
        if spec.license_type in {"A", "B"} and spec.commercial_use_allowed:
            out.append(spec)
    return out
