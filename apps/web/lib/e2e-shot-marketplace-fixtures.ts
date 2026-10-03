/**
 * Marketplace fixtures for /e2e/shots.
 *
 * Slugs, titles, departments, and catalog prices come from
 * backend/app/marketplace/seed_catalog.py. This harness is unreachable in
 * production and uses the fictional Northwind org.
 */

const INSTALLED_AT = "2026-03-12T16:10:00.000Z"

type ChecklistItem = {
  connectorType: string
  label: string
  required: boolean
  connected: boolean
  connectPath: string
  ready: boolean
}

type PackChild = {
  id: string
  slug: string
  title: string
  assetType: string
  department?: string
}

function checklist(items: Array<Omit<ChecklistItem, "connectPath" | "ready">>): ChecklistItem[] {
  return items.map((item) => ({
    ...item,
    connectPath: `/connectors?connect=${encodeURIComponent(item.connectorType)}`,
    ready: item.connected,
  }))
}

function packItems(children: PackChild[]) {
  return children.map((child, index) => ({
    sortOrder: index,
    required: true,
    child,
  }))
}

function emptyReviews(assetId: string) {
  return {
    assetId,
    reviews: [],
    myReview: null,
    total: 0,
    limit: 20,
    offset: 0,
  }
}

function entitlement(args: { paid: boolean; entitled: boolean }) {
  return {
    requiresPayment: args.paid,
    hasEntitlement: args.entitled,
    pricingType: args.paid ? "one_time" : "free",
    priceCents: args.paid ? 0 : 0,
    currency: "usd",
  }
}

const marketingChecklist = checklist([
  { connectorType: "hubspot", label: "HubSpot", required: true, connected: true },
  { connectorType: "google_analytics", label: "Google Analytics", required: true, connected: false },
  { connectorType: "apollo", label: "Apollo", required: true, connected: false },
  { connectorType: "notion", label: "Notion", required: false, connected: false },
  { connectorType: "google_drive", label: "Google Drive", required: false, connected: false },
  { connectorType: "canva", label: "Canva", required: false, connected: false },
])

const revopsChecklist = checklist([
  { connectorType: "hubspot", label: "HubSpot", required: true, connected: true },
  { connectorType: "salesforce", label: "Salesforce", required: true, connected: true },
])

const mspChecklist = checklist([
  { connectorType: "slack", label: "Slack", required: true, connected: true },
])

const csChecklist = checklist([
  { connectorType: "hubspot", label: "HubSpot", required: true, connected: true },
])

const hrChecklist = checklist([
  { connectorType: "slack", label: "Slack", required: true, connected: true },
])

const supportChecklist = checklist([
  { connectorType: "zendesk", label: "Zendesk", required: true, connected: false },
])

const marketingPack = {
  id: "mkt_asset_marketing_ops",
  slug: "marketing-operations-pack",
  title: "Marketing Operations Pack",
  description: "Four-agent campaign chain: ICP → content → design → marketing ops, with brand RAG.",
  assetType: "department_pack",
  category: "department_pack",
  department: "Marketing",
  tags: ["marketing", "department-pack", "tier-2"],
  visibility: "public",
  orgId: null,
  status: "approved",
  pricingType: "paid",
  priceCents: 14900,
  canInstall: false,
  installed: false,
  connectorChecklist: marketingChecklist,
  connectorsReady: false,
  requiredConnectorsConnected: 1,
  requiredConnectorsTotal: 3,
  requiresPayment: true,
  hasEntitlement: false,
  installCount: 0,
  reviewCount: 0,
  featured: false,
  verified: true,
  publisherDisplayName: "Gravitre",
  packItems: packItems([
    { id: "mkt_child_icp", slug: "product-icp-strategist", title: "Product & ICP Strategist", assetType: "ai_agent", department: "Marketing" },
    { id: "mkt_child_writer", slug: "content-writer", title: "Content Writer", assetType: "ai_agent", department: "Marketing" },
    { id: "mkt_child_designer", slug: "marketing-designer", title: "Marketing Designer", assetType: "ai_agent", department: "Marketing" },
    { id: "mkt_child_ops", slug: "marketing-ops-coordinator", title: "Marketing Ops Coordinator", assetType: "ai_agent", department: "Marketing" },
    { id: "mkt_child_workflow", slug: "marketing-campaign-production", title: "Marketing campaign production chain", assetType: "workflow", department: "Marketing" },
    { id: "mkt_child_knowledge", slug: "marketing-operations-knowledge", title: "Brand Voice Guide", assetType: "knowledge_pack", department: "Marketing" },
  ]),
  blockers: [
    {
      connector: "google_analytics",
      reason: "Google Analytics is required before this pack can install.",
      action_url: "/connectors?connect=google_analytics",
    },
  ],
}

const revopsPack = {
  id: "mkt_asset_revops",
  slug: "revenue-operations-pack",
  title: "Revenue Operations Pack",
  description: "RevOps agent, pipeline definitions, and executive rollup workflow.",
  assetType: "department_pack",
  category: "department_pack",
  department: "Revenue Operations",
  tags: ["revops", "department-pack", "starter"],
  visibility: "public",
  orgId: null,
  status: "approved",
  pricingType: "free",
  canInstall: true,
  installed: true,
  installedAt: INSTALLED_AT,
  connectorChecklist: revopsChecklist,
  connectorsReady: true,
  requiredConnectorsConnected: 2,
  requiredConnectorsTotal: 2,
  requiresPayment: false,
  hasEntitlement: true,
  installCount: 1,
  reviewCount: 0,
  featured: true,
  verified: true,
  publisherDisplayName: "Gravitre",
  packItems: packItems([
    { id: "rev_child_agent", slug: "revenue-operations-agent", title: "Revenue Operations Agent", assetType: "ai_agent", department: "Revenue Operations" },
    { id: "rev_child_sales", slug: "sales-pipeline-agent", title: "Sales Pipeline Agent", assetType: "ai_agent", department: "Sales" },
    { id: "rev_child_cfo", slug: "cfo-agent", title: "CFO Agent", assetType: "ai_agent", department: "Finance" },
    { id: "rev_child_workflow", slug: "executive-summary-generation", title: "Executive summary generation", assetType: "workflow", department: "Revenue Operations" },
    { id: "rev_child_knowledge", slug: "revenue-operations-knowledge", title: "Pipeline Stage Definitions", assetType: "knowledge_pack", department: "Revenue Operations" },
  ]),
}

const mspPack = {
  id: "mkt_asset_msp",
  slug: "msp-operations-pack",
  title: "MSP Operations Pack",
  description: "Service desk coordination agent, runbooks, and weekly status workflow.",
  assetType: "department_pack",
  category: "department_pack",
  department: "Operations",
  tags: ["msp", "operations", "department-pack"],
  visibility: "public",
  orgId: null,
  status: "approved",
  pricingType: "free",
  canInstall: true,
  installed: false,
  connectorChecklist: mspChecklist,
  connectorsReady: true,
  requiredConnectorsConnected: 1,
  requiredConnectorsTotal: 1,
  requiresPayment: false,
  hasEntitlement: true,
  installCount: 0,
  reviewCount: 0,
  featured: false,
  verified: true,
  publisherDisplayName: "Gravitre",
  packItems: packItems([
    { id: "msp_child_knowledge", slug: "msp-operations-knowledge", title: "Service Runbooks", assetType: "knowledge_pack", department: "Operations" },
    { id: "msp_child_workflow", slug: "weekly-team-status-report", title: "Weekly team status report", assetType: "workflow", department: "Operations" },
  ]),
}

const csPack = {
  id: "mkt_asset_cs",
  slug: "customer-success-pack",
  title: "Customer Success Pack",
  description: "CS agent, health rubric RAG, and account monitoring workflow.",
  assetType: "department_pack",
  category: "department_pack",
  department: "Customer Success",
  tags: ["customer-success", "department-pack"],
  visibility: "public",
  orgId: null,
  status: "approved",
  pricingType: "free",
  canInstall: true,
  installed: false,
  connectorChecklist: csChecklist,
  connectorsReady: true,
  requiredConnectorsConnected: 1,
  requiredConnectorsTotal: 1,
  requiresPayment: false,
  hasEntitlement: true,
  installCount: 0,
  reviewCount: 0,
  featured: false,
  verified: true,
  publisherDisplayName: "Gravitre",
  packItems: packItems([
    { id: "cs_child_agent", slug: "customer-success-agent", title: "Customer Success Agent", assetType: "ai_agent", department: "Customer Success" },
    { id: "cs_child_workflow", slug: "customer-health-monitoring", title: "Customer health monitoring", assetType: "workflow", department: "Customer Success" },
    { id: "cs_child_knowledge", slug: "customer-success-knowledge", title: "Customer Health Rubric", assetType: "knowledge_pack", department: "Customer Success" },
  ]),
}

const hrPack = {
  id: "mkt_asset_hr",
  slug: "hr-operations-pack",
  title: "HR Operations Pack",
  description: "HR policy RAG and onboarding checklist workflow.",
  assetType: "department_pack",
  category: "department_pack",
  department: "HR",
  tags: ["hr", "department-pack"],
  visibility: "public",
  orgId: null,
  status: "approved",
  pricingType: "free",
  canInstall: true,
  installed: false,
  connectorChecklist: hrChecklist,
  connectorsReady: true,
  requiredConnectorsConnected: 1,
  requiredConnectorsTotal: 1,
  requiresPayment: false,
  hasEntitlement: true,
  installCount: 0,
  reviewCount: 0,
  featured: false,
  verified: true,
  publisherDisplayName: "Gravitre",
  packItems: packItems([
    { id: "hr_child_knowledge", slug: "hr-operations-knowledge", title: "Policy Handbook", assetType: "knowledge_pack", department: "HR" },
  ]),
}

const supportPack = {
  id: "mkt_asset_support",
  slug: "support-operations-pack",
  title: "Support Operations Pack",
  description: "Zendesk ticket triage agent, support knowledge pack, and optional SLA escalation workflow.",
  assetType: "department_pack",
  category: "department_pack",
  department: "Support",
  tags: ["support", "zendesk", "department-pack", "tier-1", "starter"],
  visibility: "public",
  orgId: null,
  status: "approved",
  pricingType: "paid",
  priceCents: 4900,
  canInstall: false,
  installed: false,
  connectorChecklist: supportChecklist,
  connectorsReady: false,
  requiredConnectorsConnected: 0,
  requiredConnectorsTotal: 1,
  requiresPayment: true,
  hasEntitlement: false,
  installCount: 0,
  reviewCount: 0,
  featured: false,
  verified: true,
  publisherDisplayName: "Gravitre",
  packItems: packItems([
    { id: "sup_child_agent", slug: "ticket-triage", title: "Ticket Triage Agent", assetType: "ai_agent", department: "Support" },
    { id: "sup_child_workflow", slug: "zendesk-ticket-triage", title: "Zendesk ticket triage", assetType: "workflow", department: "Support" },
    { id: "sup_child_knowledge", slug: "support-operations-knowledge", title: "Help Center Knowledge", assetType: "knowledge_pack", department: "Support" },
    { id: "sup_child_sla", slug: "sla-breach-escalation", title: "SLA breach escalation", assetType: "workflow", department: "Support" },
  ]),
  blockers: [
    {
      connector: "zendesk",
      reason: "Zendesk is required before this pack can install.",
      action_url: "/connectors?connect=zendesk",
    },
  ],
  installVariables: [
    {
      key: "TICKET_ID",
      label: "Zendesk ticket ID",
      required: true,
      description: "Ticket to look up for triage (install/run parameter for $TICKET_ID).",
    },
  ],
}

const departmentPacks = [marketingPack, mspPack, revopsPack, csPack, hrPack, supportPack]

function pipelineView(args: {
  pipelineId: string
  department: string
  displayName: string
  tagline: string
  connectAndGoReady: boolean
  stages: Array<{ stageId: string; label: string; status: string; detail?: string }>
  honestGaps?: string[]
}) {
  return {
    pipeline: {
      pipelineId: args.pipelineId,
      department: args.department,
      displayName: args.displayName,
      tagline: args.tagline,
      connectAndGoReady: args.connectAndGoReady,
      syncBackPolicy: {
        syncTiming: "immediate",
        deferMilestoneStageId: null,
        defaultDeferMilestoneStageId: "sync_crm",
      },
      stageStatuses: args.stages,
      honestGaps: args.honestGaps ?? [],
    },
  }
}

export const MARKETPLACE_SHOT_FIXTURES: Record<string, unknown> = {
  "/api/settings/lite-membership": { is_admin: true },
  "/api/marketplace/assets": {
    assets: departmentPacks,
    total: departmentPacks.length,
    limit: 100,
    offset: 0,
  },
  "/api/marketplace/categories": {
    categories: [{ key: "department_pack", count: 6 }],
    departments: [
      { key: "Marketing", count: 1 },
      { key: "Operations", count: 1 },
      { key: "Revenue Operations", count: 1 },
      { key: "Customer Success", count: 1 },
      { key: "HR", count: 1 },
      { key: "Support", count: 1 },
    ],
    assetTypes: [{ key: "department_pack", count: 6 }],
    totalAssets: 6,
  },
  "/api/marketplace/federated-connectors": { assets: [], total: 0 },
  "/api/marketplace/saves": { saves: [], total: 0, limit: 100, offset: 0 },
  "/api/marketplace/installs": {
    installs: [
      {
        id: "inst_revops_northwind",
        assetId: revopsPack.id,
        status: "active",
        installedEntityType: "department_pack",
        installedEntityId: revopsPack.id,
        installedAt: INSTALLED_AT,
        deepLinks: [
          { label: "Revenue Operations Agent", entityType: "agent", entityId: "agt_revops", path: "/agents/agt_revops" },
          { label: "Executive summary generation", entityType: "workflow", entityId: "wf_exec_summary", path: "/workflows/wf_exec_summary" },
        ],
        asset: {
          id: revopsPack.id,
          slug: revopsPack.slug,
          title: revopsPack.title,
          assetType: revopsPack.assetType,
          category: revopsPack.category,
          department: revopsPack.department,
        },
      },
    ],
    total: 1,
    limit: 100,
    offset: 0,
  },
  "/api/marketplace/assets/marketing-operations-pack": { asset: marketingPack },
  "/api/marketplace/assets/revenue-operations-pack": { asset: revopsPack },
  "/api/marketplace/assets/msp-operations-pack": { asset: mspPack },
  "/api/marketplace/assets/customer-success-pack": { asset: csPack },
  "/api/marketplace/assets/hr-operations-pack": { asset: hrPack },
  "/api/marketplace/assets/support-operations-pack": { asset: supportPack },
  "/api/marketplace/assets/marketing-operations-pack/entitlement": {
    ...entitlement({ paid: true, entitled: false }),
    priceCents: 14900,
  },
  "/api/marketplace/assets/revenue-operations-pack/entitlement": entitlement({ paid: false, entitled: true }),
  "/api/marketplace/assets/msp-operations-pack/entitlement": entitlement({ paid: false, entitled: true }),
  "/api/marketplace/assets/customer-success-pack/entitlement": entitlement({ paid: false, entitled: true }),
  "/api/marketplace/assets/hr-operations-pack/entitlement": entitlement({ paid: false, entitled: true }),
  "/api/marketplace/assets/support-operations-pack/entitlement": {
    ...entitlement({ paid: true, entitled: false }),
    priceCents: 4900,
  },
  "/api/marketplace/assets/marketing-operations-pack/install-check": {
    canInstall: false,
    blockers: marketingPack.blockers,
    connectorChecklist: marketingChecklist,
    connectorsReady: false,
    requiredConnectorsConnected: 1,
    requiredConnectorsTotal: 3,
    requiresPayment: true,
    hasEntitlement: false,
    pricingType: "paid",
    priceCents: 14900,
    currency: "usd",
  },
  "/api/marketplace/assets/revenue-operations-pack/install-check": {
    canInstall: true,
    blockers: [],
    connectorChecklist: revopsChecklist,
    connectorsReady: true,
    requiredConnectorsConnected: 2,
    requiredConnectorsTotal: 2,
    requiresPayment: false,
    hasEntitlement: true,
    pricingType: "free",
    priceCents: 0,
    currency: "usd",
  },
  "/api/marketplace/assets/msp-operations-pack/install-check": {
    canInstall: true,
    blockers: [],
    connectorChecklist: mspChecklist,
    connectorsReady: true,
    requiredConnectorsConnected: 1,
    requiredConnectorsTotal: 1,
    requiresPayment: false,
    hasEntitlement: true,
    pricingType: "free",
    priceCents: 0,
    currency: "usd",
  },
  "/api/marketplace/assets/customer-success-pack/install-check": {
    canInstall: true,
    blockers: [],
    connectorChecklist: csChecklist,
    connectorsReady: true,
    requiredConnectorsConnected: 1,
    requiredConnectorsTotal: 1,
    requiresPayment: false,
    hasEntitlement: true,
    pricingType: "free",
    priceCents: 0,
    currency: "usd",
  },
  "/api/marketplace/assets/hr-operations-pack/install-check": {
    canInstall: true,
    blockers: [],
    connectorChecklist: hrChecklist,
    connectorsReady: true,
    requiredConnectorsConnected: 1,
    requiredConnectorsTotal: 1,
    requiresPayment: false,
    hasEntitlement: true,
    pricingType: "free",
    priceCents: 0,
    currency: "usd",
  },
  "/api/marketplace/assets/support-operations-pack/install-check": {
    canInstall: false,
    blockers: supportPack.blockers,
    connectorChecklist: supportChecklist,
    connectorsReady: false,
    requiredConnectorsConnected: 0,
    requiredConnectorsTotal: 1,
    requiresPayment: true,
    hasEntitlement: false,
    pricingType: "paid",
    priceCents: 4900,
    currency: "usd",
  },
  "/api/marketplace/assets/marketing-operations-pack/reviews": emptyReviews(marketingPack.id),
  "/api/marketplace/assets/revenue-operations-pack/reviews": emptyReviews(revopsPack.id),
  "/api/marketplace/assets/msp-operations-pack/reviews": emptyReviews(mspPack.id),
  "/api/marketplace/assets/customer-success-pack/reviews": emptyReviews(csPack.id),
  "/api/marketplace/assets/hr-operations-pack/reviews": emptyReviews(hrPack.id),
  "/api/marketplace/assets/support-operations-pack/reviews": emptyReviews(supportPack.id),
  "/api/department-pipelines": {
    pipelines: [
      { pipelineId: "sales-katie", department: "sales", displayName: "Sales Pipeline" },
      { pipelineId: "marketing-campaign", department: "marketing", displayName: "Marketing Pipeline" },
      { pipelineId: "finance-ar", department: "finance", displayName: "Finance Pipeline" },
      { pipelineId: "hr-talent", department: "hr", displayName: "HR Talent Pipeline" },
      { pipelineId: "msp-cyber", department: "msp", displayName: "MSP / Cyber Pipeline" },
    ],
  },
  "/api/department-pipelines/by-department/marketing": pipelineView({
    pipelineId: "marketing-campaign",
    department: "marketing",
    displayName: "Marketing Pipeline",
    tagline: "Detect → Analyze → Generate → Modify → Measure → Sync",
    connectAndGoReady: false,
    stages: [
      { stageId: "detect", label: "Detect", status: "completed", detail: "GA4 / Ads / GSC signal detection." },
      { stageId: "analyze", label: "Analyze", status: "in_progress", detail: "Campaign and funnel analysis." },
      { stageId: "generate", label: "Generate assets", status: "not_started" },
      { stageId: "modify", label: "Modify campaign", status: "not_started" },
      { stageId: "measure", label: "Measure", status: "not_started" },
      { stageId: "sync_ads_hubspot", label: "Sync to Ads / HubSpot", status: "not_started" },
    ],
  }),
  "/api/department-pipelines/by-department/sales": pipelineView({
    pipelineId: "sales-katie",
    department: "sales",
    displayName: "Sales Pipeline",
    tagline: "Discover → Research → Enrich → Prioritize → Outreach → Evaluate → Sync CRM",
    connectAndGoReady: true,
    stages: [
      { stageId: "discover", label: "Discover", status: "completed" },
      { stageId: "research", label: "Research", status: "completed" },
      { stageId: "enrich", label: "Enrich", status: "in_progress" },
      { stageId: "prioritize", label: "Prioritize", status: "not_started" },
      { stageId: "outreach", label: "Outreach", status: "not_started" },
      { stageId: "evaluate_outcome", label: "Evaluate outcome", status: "not_started" },
      { stageId: "sync_crm", label: "Sync to CRM", status: "not_started" },
    ],
  }),
  "/api/department-pipelines/by-department/hr": pipelineView({
    pipelineId: "hr-talent",
    department: "hr",
    displayName: "HR Talent Pipeline",
    tagline: "Find → Research → Score → Outreach → Schedule → Sync Greenhouse",
    connectAndGoReady: false,
    stages: [
      { stageId: "find", label: "Find candidate", status: "not_started" },
      { stageId: "research", label: "Research", status: "not_started" },
      { stageId: "score", label: "Score", status: "not_started" },
      { stageId: "outreach", label: "Outreach", status: "not_started" },
      { stageId: "schedule", label: "Interview scheduling", status: "not_started" },
      { stageId: "sync_greenhouse", label: "Sync to Greenhouse", status: "not_started" },
    ],
    honestGaps: ["Live HRIS / ATS connectors stay governance-gated."],
  }),
  "/api/department-pipelines/by-department/msp": pipelineView({
    pipelineId: "msp-cyber",
    department: "msp",
    displayName: "MSP / Cyber Pipeline",
    tagline: "Detect vuln → Assess clients → Severity → Remediate → Approve → Execute → Sync ticketing",
    connectAndGoReady: false,
    stages: [
      { stageId: "detect", label: "Detect vulnerability", status: "completed" },
      { stageId: "assess", label: "Assess affected clients", status: "not_started" },
      { stageId: "severity", label: "Determine severity", status: "not_started" },
      { stageId: "remediate_plan", label: "Create remediation plan", status: "not_started" },
      { stageId: "request_approval", label: "Request approval", status: "not_started" },
      { stageId: "execute", label: "Execute", status: "not_started" },
      { stageId: "sync_ticketing", label: "Sync to PSA / ticketing", status: "not_started" },
    ],
  }),
  "/api/department-pipelines/by-department/finance": pipelineView({
    pipelineId: "finance-ar",
    department: "finance",
    displayName: "Finance Pipeline",
    tagline: "Detect overdue AR → Analyze → Act → Remind → Update → Sync QuickBooks",
    connectAndGoReady: false,
    stages: [
      { stageId: "detect", label: "Detect overdue AR", status: "not_started" },
      { stageId: "analyze", label: "Analyze customer", status: "not_started" },
      { stageId: "determine_action", label: "Determine action", status: "not_started" },
      { stageId: "send_reminder", label: "Send reminder", status: "not_started" },
      { stageId: "update_status", label: "Update status", status: "not_started" },
      { stageId: "sync_quickbooks", label: "Sync to QuickBooks", status: "not_started" },
    ],
    honestGaps: ["No default department pack. Finance live connectors stay governance-gated."],
  }),
}
