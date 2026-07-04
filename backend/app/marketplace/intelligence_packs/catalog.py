"""Marketplace intelligence packs — installable domain knowledge assignments."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class IntelligencePackAssignment:
    source_type: str
    source_id: str
    label: str
    department: str
    subdomain: str | None = None
    confidence_weight: float = 1.0
    reference_summary: str = ""
    external_url: str | None = None


@dataclass(frozen=True)
class IntelligencePackSpec:
    pack_id: str
    name: str
    department: str
    default_subdomain: str | None
    description: str
    marketplace_tags: list[str] = field(default_factory=list)
    tier: str = "starter"
    assignments: list[IntelligencePackAssignment] = field(default_factory=list)


def list_intelligence_pack_specs() -> list[IntelligencePackSpec]:
    return [
        IntelligencePackSpec(
            pack_id="marketing-intelligence-pack",
            name="Marketing Intelligence Pack",
            department="marketing",
            default_subdomain="content_marketing",
            description="Brand, campaign, HubSpot, GA4, and creative knowledge assignments.",
            marketplace_tags=["marketing", "starter", "intelligence-pack"],
            assignments=[
                IntelligencePackAssignment("google_drive_folder", "brand-guidelines", "Brand Guidelines", "marketing", "brand_marketing", reference_summary="Brand voice, visual standards, and messaging guardrails."),
                IntelligencePackAssignment("google_drive_folder", "campaign-playbooks", "Campaign Playbooks", "marketing", "content_marketing", reference_summary="Approved campaign templates and launch checklists."),
                IntelligencePackAssignment("hubspot_view", "marketing-campaigns", "HubSpot Campaigns", "marketing", "demand_generation"),
                IntelligencePackAssignment("google_analytics", "ga4-property", "GA4 Property", "marketing", "analytics"),
                IntelligencePackAssignment("canva", "brand-assets", "Canva Brand Assets", "marketing", "brand_marketing"),
            ],
        ),
        IntelligencePackSpec(
            pack_id="sales-intelligence-pack",
            name="Sales Intelligence Pack",
            department="sales",
            default_subdomain="pipeline_management",
            description="CRM, forecast reports, playbooks, and pipeline review knowledge.",
            marketplace_tags=["sales", "starter", "intelligence-pack"],
            assignments=[
                IntelligencePackAssignment("hubspot_view", "sales-pipeline", "CRM Pipeline", "sales", "pipeline_management"),
                IntelligencePackAssignment("google_drive_folder", "forecast-reports", "Forecast Reports", "sales", "forecasting"),
                IntelligencePackAssignment("knowledge_pack", "sales-playbooks", "Sales Playbooks", "sales", "enterprise_sales"),
                IntelligencePackAssignment("notion_page", "pipeline-reviews", "Pipeline Reviews", "sales", "pipeline_management"),
            ],
        ),
        IntelligencePackSpec(
            pack_id="support-intelligence-pack",
            name="Support Intelligence Pack",
            department="support",
            default_subdomain="technical_support",
            description="Zendesk views, KB, product docs, and escalation playbooks.",
            marketplace_tags=["support", "starter", "intelligence-pack"],
            assignments=[
                IntelligencePackAssignment("zendesk_view", "support-queue", "Zendesk Views", "support", "technical_support"),
                IntelligencePackAssignment("knowledge_pack", "support-kb", "Knowledge Base", "support", "technical_support"),
                IntelligencePackAssignment("confluence_space", "product-docs", "Product Docs", "support", "customer_success"),
                IntelligencePackAssignment("google_drive_folder", "escalation-playbooks", "Escalation Playbooks", "support", "escalations"),
            ],
        ),
        IntelligencePackSpec(
            pack_id="msp-intelligence-pack",
            name="MSP Intelligence Pack",
            department="msp",
            default_subdomain="rmm",
            description="PSA, RMM policies, vendor docs, and client knowledge base assignments.",
            marketplace_tags=["msp", "starter", "intelligence-pack"],
            assignments=[
                IntelligencePackAssignment("connectwise", "psa-tickets", "PSA Tickets", "msp", "helpdesk"),
                IntelligencePackAssignment("knowledge_pack", "rmm-policies", "RMM Policies", "msp", "rmm"),
                IntelligencePackAssignment("google_drive_folder", "vendor-documentation", "Vendor Documentation", "msp", "security_operations"),
                IntelligencePackAssignment("sharepoint_site", "client-kb", "Client Knowledge Base", "msp", "helpdesk"),
            ],
        ),
    ]


def get_intelligence_pack_spec(pack_id: str) -> IntelligencePackSpec | None:
    for spec in list_intelligence_pack_specs():
        if spec.pack_id == pack_id:
            return spec
    return None


def intelligence_pack_to_marketplace_asset(spec: IntelligencePackSpec) -> dict[str, Any]:
    return {
        "slug": spec.pack_id,
        "title": spec.name,
        "description": spec.description,
        "asset_type": "intelligence_pack",
        "category": "intelligence_pack",
        "department": spec.department,
        "tier": spec.tier,
        "tags": spec.marketplace_tags,
        "config": {
            "department": spec.department,
            "default_subdomain": spec.default_subdomain,
            "assignments": [
                {
                    "source_type": row.source_type,
                    "source_id": row.source_id,
                    "label": row.label,
                    "department": row.department,
                    "subdomain": row.subdomain,
                    "confidence_weight": row.confidence_weight,
                    "reference_summary": row.reference_summary,
                    "external_url": row.external_url,
                }
                for row in spec.assignments
            ],
        },
    }
