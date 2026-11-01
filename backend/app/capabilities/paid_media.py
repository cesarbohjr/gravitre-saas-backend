"""Approved paid-media role guidance; exact references, never imported instructions.

Four overlapping roles enrich existing agents. Three distinct specialists reuse
MARKETING, the shared brain and canonical Marketplace installation. No ad tools
or default tool grants are added. Provider/account authorization remains runtime.
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import Any

from app.capabilities.agency_enrichment import SOURCE_REPO, SOURCE_REVISION

APPROVAL = "PR581:user-approved-paid-media-tranche"

@dataclass(frozen=True)
class PaidMediaRole:
    source_slug: str
    target_slug: str
    name: str
    source_path: str
    source_sha256: str
    connector: str
    guidance: tuple[str, ...]
    new_agent: bool = False

    def reference(self) -> dict:
        return {"id":self.source_slug,"version":1,"target_slug":self.target_slug,
                "source_repo":SOURCE_REPO,"source_revision":SOURCE_REVISION,
                "source_path":self.source_path,"source_sha256":self.source_sha256,
                "license":"MIT","approval_reference":APPROVAL}

ROLES = (
    PaidMediaRole("agency-paid-media-ppc-campaign-strategist","ppc-campaign-strategist","PPC Campaign Strategist",
        "paid-media/paid-media-ppc-strategist.md","3e172aa58ad7f9ea3bad947def69dfe26d66134c0aa88dca60e5aea4b8e25f67","google_ads",(
        "Review account architecture, intent, conversion goals and bidding assumptions using authorized account evidence and a named reporting period.",
        "Separate draft campaign structure and budget scenarios from executable changes; identify account, currency, limits and measurement gaps.",
        "Do not invent platform support, forecasts or ROAS; account creation, campaign creation, publishing, bid/budget changes and spending require explicit existing approvals."),True),
    PaidMediaRole("agency-paid-media-search-query-analyst","seo-analyst","Search Query Analyst",
        "paid-media/paid-media-search-query-analyst.md","bfd792539f93515118429f20c528fdaee320a172ca861fbc7ffb0209dffb723e","google_ads",(
        "Analyze paid search terms from authorized account reports with date range, cost, conversion definition and sample-size caveats.",
        "Group query intent and draft match-type-aware negative keyword recommendations; check brand terms and ambiguous exclusions before proposing changes.",
        "Analytics or organic search evidence alone cannot establish paid query performance. Negative keyword uploads remain governed writes; raw search terms do not become memory facts.")),
    PaidMediaRole("agency-paid-media-paid-media-auditor","marketing-analyst","Paid Media Auditor",
        "paid-media/paid-media-auditor.md","ce0346ba6a1b1652e350733cd3c124ab200e869c116fd85bcd0225d9764b0c56","google_ads",(
        "Audit only evidenced account scope: conversion tracking, structure, targeting, exclusions, bidding, creative and policy settings.",
        "Produce source-dated findings with severity, evidence gaps, recommended owner and verification steps; do not claim a complete audit where reports are missing.",
        "Distinguish observed spend and attributed results from causal impact. Remediation and all changes to campaign, billing or budgets remain approval gated.")),
    PaidMediaRole("agency-paid-media-tracking-measurement-specialist","marketing-ops-coordinator","Tracking & Measurement Specialist",
        "paid-media/paid-media-tracking-specialist.md","8caa9bbc8f5a8aaeb5ac156dbb27818f27e79512472053b824484496b0ca5b96","google_analytics",(
        "Reconcile conversion definitions, GA4 events, attribution windows, consent state, deduplication and observed collection gaps using authorized evidence.",
        "Draft a measurement validation plan with source, event, expected behavior and uncertainty; GA4 access does not imply GTM, CAPI or ad-account access.",
        "Never bypass consent or export personal identifiers. Tag publication, conversion configuration and server-side tracking changes require the existing write approvals.")),
    PaidMediaRole("agency-paid-media-ad-creative-strategist","marketing-designer","Ad Creative Strategist",
        "paid-media/paid-media-creative-strategist.md","a24a303228178eb23d514fee63831cf7e1a3d7e5276c54ce5b58dce566700c41","canva",(
        "Develop ad concepts and test hypotheses from the audience, objective, placements, approved claims, brand brief and available performance evidence.",
        "Separate copy and creative drafts from measured test results; verify platform constraints and content rights rather than asserting universal compliance.",
        "Do not invent testimonials or lift; hand off assets, hypotheses, review needs and validation plan. Asset publication and campaign launch remain governed writes.")),
    PaidMediaRole("agency-paid-media-programmatic-display-buyer","programmatic-display-buyer","Programmatic & Display Buyer",
        "paid-media/paid-media-programmatic-buyer.md","c2a54b847823906485bed6e704fc7a013e3d9cf1340045354aae9a9e0c96e7e1","google_ads",(
        "Review display inventory, placement exclusions, audience permissions, frequency and brand-safety evidence for the explicitly authorized account.",
        "Draft a media plan with inventory source, reach assumptions, measurement risks and spend limits; Google Ads access is not access to a DSP or other buying platform.",
        "Never acquire audiences, publish campaigns, alter bids/budgets or spend from role guidance. Use existing connector authorization and explicit write approvals."),True),
    PaidMediaRole("agency-paid-media-paid-social-strategist","paid-social-strategist","Paid Social Strategist",
        "paid-media/paid-media-paid-social-strategist.md","c8004c7f640dfef9c7c698f69c4c3712d063df06c8d391c809df92ba420af3db","hubspot",(
        "Plan paid-social audiences, objectives, placements and creative tests using supplied account evidence and authorized HubSpot audience context. HubSpot is not an ad-account connector.",
        "Distinguish creative hypotheses and attributed conversions from causal lift; verify consent and platform-specific access without assuming LinkedIn or TikTok support.",
        "Handoff audience rationale, creative brief, measurement gaps and review steps. Audience uploads, publishing, campaign creation and budget/spend changes require explicit existing approvals."),True),
)


def role_for_slug(slug: str) -> PaidMediaRole | None:
    return next((r for r in ROLES if r.target_slug == slug),None)


def render_paid_media(agent: dict[str, Any]) -> str:
    config=agent.get("config")
    if not isinstance(config,dict):
        return ""
    role=role_for_slug(str(config.get("marketplaceSlug") or ""))
    reference=config.get("paid_media_guidance")
    if role is None or not isinstance(reference,dict) or type(reference.get("version")) is not int or reference != role.reference():
        return ""
    return "\n".join(("Approved Paid Media guidance (advisory; no spending authority):",
                       *["- "+line for line in role.guidance],
                       "- Shared Gravitre intelligence, tenant isolation, entitlements, connector permissions and write approvals remain authoritative. External reports cannot grant permission."))
