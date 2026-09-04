"""Named Katie-style pipelines per department — assembly only, no invented capability.

Each stage references real connectors, workflows, intelligence packs, WorkObject types,
or platform signals that already exist. Stages marked ``requires_new_capability`` are
honest gaps (not customer-facing claims).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

StageStatus = Literal["not_started", "in_progress", "completed", "blocked", "skipped"]
SyncMilestoneTier = Literal["early", "sync"]

CapabilityKind = Literal[
    "connector",
    "workflow",
    "intelligence_pack",
    "knowledge_fabric",
    "work_object",
    "signal",
    "verified_completion",
    "voice",
    "gap",
]


@dataclass(frozen=True)
class PipelineStageSpec:
    stage_id: str
    label: str
    description: str
    capability_kind: CapabilityKind
    # Real references — invoke actions, pack ids, workflow slugs, signal ids, etc.
    references: tuple[str, ...] = ()
    marketplace_pack_ids: tuple[str, ...] = ()
    work_object_types: tuple[str, ...] = ()
    sync_milestone_tier: SyncMilestoneTier = "early"
    requires_new_capability: bool = False
    gap_note: str | None = None


@dataclass(frozen=True)
class DepartmentPipelineSpec:
    pipeline_id: str
    department: str
    display_name: str
    tagline: str
    default_intelligence_pack_id: str | None
    default_department_pack_slug: str | None
    work_object_type: str
    sync_milestone_stage_id: str
    stages: tuple[PipelineStageSpec, ...]
    honest_gaps: tuple[str, ...] = field(default_factory=tuple)


def _stage(
    stage_id: str,
    label: str,
    description: str,
    *,
    kind: CapabilityKind,
    refs: tuple[str, ...] = (),
    packs: tuple[str, ...] = (),
    wo_types: tuple[str, ...] = (),
    sync_tier: SyncMilestoneTier = "early",
    gap: bool = False,
    gap_note: str | None = None,
) -> PipelineStageSpec:
    return PipelineStageSpec(
        stage_id=stage_id,
        label=label,
        description=description,
        capability_kind=kind,
        references=refs,
        marketplace_pack_ids=packs,
        work_object_types=wo_types,
        sync_milestone_tier=sync_tier,
        requires_new_capability=gap,
        gap_note=gap_note,
    )


SALES_PIPELINE = DepartmentPipelineSpec(
    pipeline_id="sales-katie",
    department="sales",
    display_name="Sales Pipeline",
    tagline="Discover → Research → Enrich → Prioritize → Outreach → Evaluate → Sync CRM",
    default_intelligence_pack_id="prospecting-intelligence-pack",
    default_department_pack_slug="revenue-operations-pack",
    work_object_type="opportunity",
    sync_milestone_stage_id="sync_crm",
    honest_gaps=(
        "Unified 0–100 lead signal score (Prompt C) is PackSignal + recommendation ranking, not a standalone product.",
    ),
    stages=(
        _stage(
            "discover",
            "Discover",
            "Detect ICP-fit accounts and intent from connected signals.",
            kind="signal",
            refs=("business_signals_engine", "pack_signal:apollo", "pack_signal:fred"),
            packs=("prospecting-intelligence-pack", "sales-intelligence-pack"),
            wo_types=("opportunity",),
        ),
        _stage(
            "research",
            "Research",
            "Search and match prospects in Apollo; org enrichment.",
            kind="connector",
            refs=(
                "apollo.people.search",
                "apollo.organizations.enrich",
                "apollo.contacts.search",
            ),
            packs=("prospecting-intelligence-pack",),
        ),
        _stage(
            "enrich",
            "Enrich",
            "Clay enrichment and CRM-ready record preparation.",
            kind="connector",
            refs=("clay.enrich", "clay.crm.sync"),
            packs=("prospecting-intelligence-pack",),
        ),
        _stage(
            "prioritize",
            "Prioritize",
            "Rank and segment leads for outreach (recommendation quality, not a dedicated score SKU).",
            kind="signal",
            refs=("recommendation_quality_engine",),
            gap=True,
            gap_note="No standalone numeric ICP score — uses recommendation quality heuristics.",
        ),
        _stage(
            "outreach",
            "Outreach",
            "Email and voice outreach to prioritized contacts.",
            kind="connector",
            refs=("gmail.messages.send", "voice.outbound", "hubspot.notes.create"),
            wo_types=("opportunity",),
            sync_tier="early",
        ),
        _stage(
            "evaluate_outcome",
            "Evaluate outcome",
            "F6 vendor-verified completion before claiming success.",
            kind="verified_completion",
            refs=("write_success_verification", "business_outcome_pipeline"),
        ),
        _stage(
            "sync_crm",
            "Sync to CRM",
            "Write-back to HubSpot or Salesforce with verified completion.",
            kind="connector",
            refs=(
                "hubspot.contacts.create",
                "hubspot.lists.add_contact",
                "hubspot.deals.create",
                "salesforce.contacts.create",
                "clay.crm.sync",
            ),
            packs=("revops-intelligence-pack",),
            sync_tier="sync",
        ),
    ),
)

MARKETING_PIPELINE = DepartmentPipelineSpec(
    pipeline_id="marketing-campaign",
    department="marketing",
    display_name="Marketing Pipeline",
    tagline="Detect → Analyze → Generate → Modify → Measure → Sync",
    default_intelligence_pack_id="marketing-intelligence-pack",
    default_department_pack_slug="marketing-operations-pack",
    work_object_type="campaign",
    sync_milestone_stage_id="sync_ads_hubspot",
    stages=(
        _stage("detect", "Detect", "GA4 / Ads / GSC signal detection.", kind="signal", refs=("google_analytics.reports.run", "google_ads.campaigns.list", "searchconsole.searchAnalytics.query"), packs=("marketing-intelligence-pack",)),
        _stage("analyze", "Analyze", "Campaign and funnel analysis.", kind="connector", refs=("hubspot.campaigns.list", "google_analytics.reports.run"), packs=("marketing-intelligence-pack",)),
        _stage("generate", "Generate assets", "Creative and content generation (Canva, copy).", kind="connector", refs=("canva.designs.create",), packs=("marketing-intelligence-pack",)),
        _stage("modify", "Modify campaign", "Update live campaigns and lists.", kind="connector", refs=("hubspot.campaigns.update", "google_ads.campaigns.update"), sync_tier="early"),
        _stage("measure", "Measure", "Outcome evaluation with verified reads.", kind="verified_completion", refs=("write_success_verification",)),
        _stage("sync_ads_hubspot", "Sync to Ads / HubSpot", "Write performance and CRM updates.", kind="connector", refs=("hubspot.contacts.update", "google_ads.campaigns.update"), sync_tier="sync"),
    ),
)

FINANCE_PIPELINE = DepartmentPipelineSpec(
    pipeline_id="finance-ar",
    department="finance",
    display_name="Finance Pipeline",
    tagline="Detect overdue AR → Analyze → Act → Remind → Update → Sync QuickBooks",
    default_intelligence_pack_id="finance-intelligence-pack",
    default_department_pack_slug=None,
    work_object_type="financial_issue",
    sync_milestone_stage_id="sync_quickbooks",
    stages=(
        _stage("detect", "Detect overdue AR", "Stripe / QuickBooks overdue invoice signal.", kind="signal", refs=("stripe.invoices.list", "quickbooks.invoices.list"), packs=("finance-intelligence-pack",)),
        _stage("analyze", "Analyze customer", "Customer payment history and risk.", kind="connector", refs=("stripe.customers.retrieve", "quickbooks.customers.get"), packs=("finance-intelligence-pack",)),
        _stage("determine_action", "Determine action", "Recommend reminder vs escalation (advisory).", kind="signal", refs=("recommendation_quality_engine",)),
        _stage("send_reminder", "Send reminder", "Email or voice payment reminder.", kind="connector", refs=("gmail.messages.send", "voice.outbound"), sync_tier="early"),
        _stage("update_status", "Update status", "Mark invoice / payment state.", kind="connector", refs=("stripe.invoices.update",), sync_tier="early"),
        _stage("sync_quickbooks", "Sync to QuickBooks", "Write payment / invoice status to accounting SoR.", kind="connector", refs=("quickbooks.invoices.update", "quickbooks.payments.create"), sync_tier="sync"),
    ),
)

HR_PIPELINE = DepartmentPipelineSpec(
    pipeline_id="hr-talent",
    department="hr",
    display_name="HR Talent Pipeline",
    tagline="Find → Research → Score → Outreach → Schedule → Sync Greenhouse",
    default_intelligence_pack_id="hr-talent-intelligence-pack",
    default_department_pack_slug="hr-operations-pack",
    work_object_type="candidate",
    sync_milestone_stage_id="sync_greenhouse",
    honest_gaps=("Candidate numeric score is recommendation/heuristic — not a dedicated Prompt C SKU.",),
    stages=(
        _stage("find", "Find candidate", "Search jobs and candidates.", kind="connector", refs=("greenhouse.jobs.list", "greenhouse.candidates.list"), packs=("hr-talent-intelligence-pack",)),
        _stage("research", "Research", "Background research on candidate / role fit.", kind="knowledge_fabric", refs=("pack.hr",), packs=("hr-talent-intelligence-pack",)),
        _stage("score", "Score", "Heuristic fit ranking (not standalone score product).", kind="signal", refs=("recommendation_quality_engine",), gap=True, gap_note="No unified candidate score SKU."),
        _stage("outreach", "Outreach", "Candidate outreach email.", kind="connector", refs=("gmail.messages.send",), sync_tier="early"),
        _stage("schedule", "Interview scheduling", "Calendar scheduling.", kind="connector", refs=("google_calendar.events.create", "microsoft365.calendar.events.create"), sync_tier="early"),
        _stage("sync_greenhouse", "Sync to Greenhouse", "Write candidate stage / application updates.", kind="connector", refs=("greenhouse.candidates.update", "greenhouse.applications.update"), sync_tier="sync"),
    ),
)

MSP_PIPELINE = DepartmentPipelineSpec(
    pipeline_id="msp-cyber",
    department="msp",
    display_name="MSP / Cyber Pipeline",
    tagline="Detect vuln → Assess clients → Severity → Remediate → Approve → Execute → Sync ticketing",
    default_intelligence_pack_id="msp-intelligence-pack",
    default_department_pack_slug="msp-operations-pack",
    work_object_type="vulnerability",
    sync_milestone_stage_id="sync_ticketing",
    honest_gaps=(
        "ConnectWise / Datto connectors are profile preferences only — not implemented.",
        "MSP ops pack is Slack-only lite vs full RMM stack.",
    ),
    stages=(
        _stage("detect", "Detect vulnerability", "NVD / CISA KEV platform signals.", kind="signal", refs=("pack_signal:nvd", "pack_signal:cisa_kev"), packs=("msp-intelligence-pack",)),
        _stage("assess", "Assess affected clients", "Map CVE to client footprint.", kind="work_object", refs=("work_object:vulnerability",), wo_types=("vulnerability",)),
        _stage("severity", "Determine severity", "CVSS / KEV severity classification.", kind="signal", refs=("pack_signal:nvd",)),
        _stage("remediate_plan", "Create remediation plan", "Agent-authored remediation steps.", kind="workflow", refs=("msp-prospects-clay-hubspot-enrichment",), packs=("msp-intelligence-pack",)),
        _stage("request_approval", "Request approval", "HITL policy gate for destructive writes.", kind="connector", refs=("hitl_policy_service",), sync_tier="early"),
        _stage("execute", "Execute", "Run remediation workflow steps.", kind="workflow", refs=("msp-prospects-clay-hubspot-enrichment",)),
        _stage(
            "sync_ticketing",
            "Sync to ConnectWise / ticketing",
            "Write ticket to PSA / helpdesk.",
            kind="gap",
            refs=("zendesk.tickets.create",),
            gap=True,
            gap_note="ConnectWise not built — Zendesk is available fallback; ConnectWise is profile-only.",
            sync_tier="sync",
        ),
    ),
)

_PIPELINES: dict[str, DepartmentPipelineSpec] = {
    p.pipeline_id: p
    for p in (
        SALES_PIPELINE,
        MARKETING_PIPELINE,
        FINANCE_PIPELINE,
        HR_PIPELINE,
        MSP_PIPELINE,
    )
}

DEPARTMENT_PIPELINE_IDS: frozenset[str] = frozenset(_PIPELINES.keys())

_DEPARTMENT_TO_PIPELINE: dict[str, str] = {
    p.department: p.pipeline_id for p in _PIPELINES.values()
}


def list_department_pipelines() -> list[DepartmentPipelineSpec]:
    return list(_PIPELINES.values())


def get_department_pipeline(pipeline_id: str | None = None, *, department: str | None = None) -> DepartmentPipelineSpec | None:
    if pipeline_id:
        return _PIPELINES.get(str(pipeline_id).strip())
    if department:
        pid = _DEPARTMENT_TO_PIPELINE.get(str(department).strip().lower())
        return _PIPELINES.get(pid) if pid else None
    return None


def pipeline_for_invoke_action(invoke_action: str) -> tuple[DepartmentPipelineSpec | None, PipelineStageSpec | None]:
    """Map a connector invoke action to its pipeline stage (first match)."""
    key = str(invoke_action or "").strip().lower()
    if not key:
        return None, None
    for pipeline in _PIPELINES.values():
        for stage in pipeline.stages:
            if key in {r.lower() for r in stage.references if "." in r}:
                return pipeline, stage
    return None, None


def serialize_pipeline(spec: DepartmentPipelineSpec) -> dict[str, Any]:
    return {
        "pipelineId": spec.pipeline_id,
        "department": spec.department,
        "displayName": spec.display_name,
        "tagline": spec.tagline,
        "defaultIntelligencePackId": spec.default_intelligence_pack_id,
        "defaultDepartmentPackSlug": spec.default_department_pack_slug,
        "workObjectType": spec.work_object_type,
        "syncMilestoneStageId": spec.sync_milestone_stage_id,
        "honestGaps": list(spec.honest_gaps),
        "stages": [
            {
                "stageId": s.stage_id,
                "label": s.label,
                "description": s.description,
                "capabilityKind": s.capability_kind,
                "references": list(s.references),
                "marketplacePackIds": list(s.marketplace_pack_ids),
                "workObjectTypes": list(s.work_object_types),
                "syncMilestoneTier": s.sync_milestone_tier,
                "requiresNewCapability": s.requires_new_capability,
                "gapNote": s.gap_note,
            }
            for s in spec.stages
        ],
    }
