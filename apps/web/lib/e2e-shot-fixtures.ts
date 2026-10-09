/**
 * Fixtures for the marketing/product screenshot harness (app/e2e/shots).
 *
 * These render the REAL product surfaces with illustrative data so marketing
 * assets can be refreshed without pointing a camera at a live customer
 * tenant. Per the standing rule in lib/demo-runtime-fallback.ts — never show
 * fabricated data as if it were real — every record here is deliberately
 * fictional ("Northwind Logistics"), and this harness is unreachable in
 * production.
 *
 * The story deliberately continues the browser-extension screenshots: an
 * operator approved a HubSpot contact create from a LinkedIn profile, and that
 * same write shows up here as a recorded outcome.
 */

import shotActionCatalog from "./e2e-shot-action-catalog.json"
import { MARKETPLACE_SHOT_FIXTURES } from "./e2e-shot-marketplace-fixtures"
import { homeReportsShotFixture } from "./e2e-shot-home-reports-fixture"

const DEMO_ORG_ID = "00000000-0000-0000-0000-000000000001"

/** Timestamps are rendered with toLocaleString(), so keep them fixed and recent-looking. */
const T = (minutesAgo: number) =>
  new Date(Date.UTC(2026, 2, 12, 16, 40) - minutesAgo * 60_000).toISOString()

/**
 * Anchored to the real clock, unlike T().
 *
 * Use this wherever the UI renders a *relative* distance rather than an
 * absolute date. The conversation sidebar computes `now - updated_at`, so a
 * T()-based value renders as however far the pinned instant happens to be from
 * today ("5 months ago") and makes a fresh capture look abandoned. This is
 * evaluated server-side as the fixtures are serialised into the harness
 * bootstrap, so it is always current at capture time.
 */
const AGO = (minutesAgo: number) =>
  new Date(Date.now() - minutesAgo * 60_000).toISOString()

const supabaseUser = {
  id: "8f14e45f-ceea-467a-9f4c-2d5b1f0a3c21",
  aud: "authenticated",
  role: "authenticated",
  email: "dana@northwind.io",
  email_confirmed_at: T(20000),
  phone: "",
  confirmed_at: T(20000),
  last_sign_in_at: T(120),
  app_metadata: { provider: "email", providers: ["email"] },
  user_metadata: { full_name: "Dana Whitfield" },
  identities: [],
  created_at: T(20000),
  updated_at: T(120),
  is_anonymous: false,
}

const businessOutcomes = [
  {
    id: "bo_01hq8s5f1a",
    orgId: DEMO_ORG_ID,
    runId: "run_01hq8s5f1a",
    kind: "failed_action",
    title: "hubspot.lists.create may have been applied before the connection failed",
    status: "failed",
    lifecycleState: "presented",
    lifecycleStatesReached: ["planned", "presented"],
    source: "browser_extension",
    createdAt: T(2),
    sections: {
      summary: "hubspot.lists.create may have been applied before the connection failed: [Errno 11] Resource temporarily unavailable",
      evidence: { links: [{ label: "HubSpot lists", href: "https://app.hubspot.com/contacts/1/lists", kind: "record" }], integration: "hubspot" },
      verification: {
        verified: false,
        confidence: "unverified",
        checkFailed: "module_a_terminal_status",
        nextActions: ["The list may already exist in HubSpot. Check for it before retrying so you do not create a duplicate."],
      },
      explanation: "You asked for a list of high-intent leads. The agent created the list, then the HubSpot connection dropped before the response came back.",
      timeline: [
        { index: 1, label: "Plan", status: "succeeded", summary: "Agent chose the action" },
        { index: 2, label: "Authorize", status: "succeeded", summary: "Connector signed in" },
        { index: 3, label: "Create list", status: "failed", summary: "Connection dropped mid call" },
      ],
      diff: { available: false, note: "No before-and-after was captured because the call did not return." },
      undo: { available: false, honestUnavailableReason: "Nothing was confirmed as created, so there is nothing to undo yet." },
      metadata: { actionArgs: { name: "High-intent leads" } },
    },
  },
  {
    id: "bo_01hq8s4m2k",
    orgId: DEMO_ORG_ID,
    runId: "run_01hq8s4m2k",
    kind: "crm_write",
    title: "Created HubSpot contact for Jane Doe",
    status: "succeeded",
    lifecycleState: "verified",
    lifecycleStatesReached: ["planned", "approved", "executed", "verified"],
    source: "browser_extension",
    createdAt: T(6),
    sections: {
      summary:
        "Jane Doe (CTO, Northwind Logistics) was not in HubSpot. Gravitre matched her in Apollo, then created the contact after you approved the write.",
      evidence: {
        links: [
          { label: "HubSpot contact", href: "https://app.hubspot.com/contacts/1/contact/40118", kind: "record" },
          { label: "Source profile", href: "https://www.linkedin.com/in/jane-doe-northwind", kind: "source" },
        ],
        entityType: "contact",
        entityId: "40118",
        integration: "hubspot",
      },
      verification: {
        verified: true,
        method: "read_after_write",
        detail: "Re-read hubspot.contacts.search by email and matched contact 40118.",
      },
      explanation:
        "Apollo returned a confident person match on jane.doe@northwind.io. HubSpot had no contact with that email, so the plan was a create rather than an update.",
      timeline: [
        { index: 1, label: "Read page", status: "succeeded", summary: "Extracted name, title, company, domain from LinkedIn profile." },
        { index: 2, label: "Apollo lookup", status: "succeeded", summary: "apollo.people.match — matched on email." },
        { index: 3, label: "HubSpot lookup", status: "succeeded", summary: "hubspot.contacts.search — no existing contact." },
        { index: 4, label: "Approval", status: "succeeded", summary: "Approved by Dana Whitfield.", agentName: "Human review" },
        { index: 5, label: "HubSpot write", status: "succeeded", summary: "hubspot.contact.create — created contact 40118." },
      ],
      approval: { status: "approved", required: 1, received: 1 },
      diff: { available: true, prior: null, note: "No prior record — this created a new contact." },
      undo: { available: true, compensatingAction: "hubspot.contact.archive" },
    },
  },
  {
    id: "bo_01hq8s3d9v",
    orgId: DEMO_ORG_ID,
    runId: "run_01hq8s3d9v",
    kind: "report",
    title: "Drafted Q1 business review for Northwind Logistics",
    status: "succeeded",
    lifecycleState: "executed",
    lifecycleStatesReached: ["planned", "executed"],
    source: "chat",
    createdAt: T(52),
    sections: {
      summary:
        "Pulled closed-won deals and open tickets for the account, then drafted a five-section review document.",
      evidence: {
        links: [{ label: "Draft document", href: "https://docs.google.com/document/d/1x9", kind: "deliverable" }],
        entityType: "document",
        entityId: "1x9",
        integration: "google_docs",
      },
      verification: { verified: false, method: "none", detail: "Draft is advisory — no system of record was changed." },
      explanation: "Read-only across HubSpot and Zendesk. Nothing was written back.",
      timeline: [
        { index: 1, label: "HubSpot deals", status: "succeeded", summary: "hubspot.deals.search — 7 closed-won." },
        { index: 2, label: "Zendesk tickets", status: "succeeded", summary: "zendesk.tickets.list — 3 open." },
        { index: 3, label: "Draft review", status: "succeeded", summary: "Generated document from retrieved records." },
      ],
      approval: { status: "not_required", required: 0, received: 0 },
      undo: { available: false, honestUnavailableReason: "Nothing was written to a system of record." },
    },
  },
  {
    id: "bo_01hq8s1a7p",
    orgId: DEMO_ORG_ID,
    runId: "run_01hq8s1a7p",
    kind: "crm_write",
    title: "Salesforce opportunity update blocked",
    status: "failed",
    lifecycleState: "blocked",
    lifecycleStatesReached: ["planned", "blocked"],
    source: "workflow",
    createdAt: T(96),
    sections: {
      summary:
        "The connected Salesforce user lacks edit access on Opportunity 0064x. Gravitre stopped before writing.",
      evidence: {
        links: [{ label: "Opportunity", href: "https://northwind.my.salesforce.com/0064x", kind: "record" }],
        entityType: "opportunity",
        entityId: "0064x",
        integration: "salesforce",
      },
      verification: { verified: false, method: "none", detail: "No write attempted." },
      explanation:
        "salesforce.opportunity.update returned INSUFFICIENT_ACCESS_OR_READONLY. Retrying will not help until the connected user is granted edit access.",
      timeline: [
        { index: 1, label: "Read opportunity", status: "succeeded", summary: "salesforce.opportunity.get — ok." },
        { index: 2, label: "Update opportunity", status: "failed", summary: "INSUFFICIENT_ACCESS_OR_READONLY" },
      ],
      approval: { status: "not_required", required: 0, received: 0 },
      undo: { available: false, honestUnavailableReason: "Nothing was written, so there is nothing to undo." },
    },
  },
]

/**
 * Shape must match normalizeAgent() in app/(app)/agents/page.tsx.
 *
 * Traps that cost real debugging time here:
 *  - `department` is validated against an exact allow-list (Marketing, Sales,
 *    Finance, Support, HR); anything else silently collapses to "Operations",
 *    so a plausible-looking "Revenue" would quietly mislabel every card.
 *  - `stats.successRate` renders as `{value}%`, so it must be a whole number.
 *    0.98 displays as "0.98%".
 *  - shouldShowSuccessRate() prints "No tasks yet" when status is "idle" AND
 *    successRate is 0, so an idle agent needs a non-zero rate to show a number.
 *  - `lastActionTime` passes through formatTaskTime(), which returns the string
 *    untouched when it is not Date-parseable. Relative copy like "4 min ago" is
 *    therefore stable; an ISO date would re-render as a drifting distance
 *    ("5 months ago") because these fixtures are pinned to a fixed instant.
 */
const agents = [
  {
    id: "agt_lead_triage",
    name: "Inbound Lead Triage",
    role: "Revenue operations",
    department: "Sales",
    description:
      "Watches inbound form fills, enriches the company, and prepares the CRM write for review.",
    status: "active",
    model: "gpt-4o",
    avatarColor: "#2563eb",
    personality: {
      color: "blue",
      gradient: "from-blue-500 to-indigo-500",
      glow: "shadow-blue-500/30",
    },
    stats: {
      tasksToday: 34,
      successRate: 98,
      avgResponseTime: "1.8s",
      workflowsUsing: 2,
    },
    capabilities: ["Company enrichment", "Duplicate detection", "CRM staging"],
    permissions: ["hubspot", "apollo"],
    lastAction: "Prepared HubSpot contact create for Priya Raman",
    lastActionTime: "4 min ago",
    knowledgeDocCount: 6,
    connectedSystems: ["HubSpot", "Apollo"],
  },
  {
    id: "agt_deal_desk",
    name: "Deal Desk Sync",
    role: "Pipeline hygiene",
    department: "Sales",
    description:
      "Reconciles opportunity stages against meeting notes and support threads, then proposes stage changes.",
    status: "processing",
    model: "gpt-4o",
    avatarColor: "#7c3aed",
    personality: {
      color: "violet",
      gradient: "from-violet-500 to-purple-500",
      glow: "shadow-violet-500/30",
    },
    stats: {
      tasksToday: 12,
      successRate: 91,
      avgResponseTime: "3.4s",
      workflowsUsing: 1,
    },
    capabilities: ["Stage inference", "Close-date checks", "Note summarisation"],
    permissions: ["salesforce", "zendesk"],
    lastAction: "Proposed stage change on opportunity 0064x",
    lastActionTime: "38 min ago",
    knowledgeDocCount: 4,
    connectedSystems: ["Salesforce", "Zendesk"],
  },
  {
    id: "agt_support_escalation",
    name: "Support Escalation",
    role: "Customer support",
    department: "Support",
    description:
      "Triages inbound tickets, attaches account context, and escalates anything touching a paying account.",
    status: "active",
    model: "gpt-4o-mini",
    avatarColor: "#0d9488",
    personality: {
      color: "teal",
      gradient: "from-teal-500 to-emerald-500",
      glow: "shadow-teal-500/30",
    },
    stats: {
      tasksToday: 57,
      successRate: 96,
      avgResponseTime: "2.1s",
      workflowsUsing: 2,
    },
    capabilities: ["Ticket triage", "Account lookup", "Macro suggestion"],
    permissions: ["zendesk", "slack"],
    lastAction: "Escalated ticket 8841 to the on-call engineer",
    lastActionTime: "12 min ago",
    knowledgeDocCount: 11,
    connectedSystems: ["Zendesk", "Slack"],
    parentAgentId: "agt_lead_triage",
  },
  {
    id: "agt_invoice_recon",
    name: "Invoice Reconciliation",
    role: "Finance operations",
    department: "Finance",
    description:
      "Matches paid invoices against closed-won deals and flags the ones that disagree.",
    status: "idle",
    model: "gpt-4o-mini",
    avatarColor: "#c2410c",
    personality: {
      color: "orange",
      gradient: "from-orange-500 to-amber-500",
      glow: "shadow-orange-500/30",
    },
    stats: {
      // Non-zero on purpose: an idle agent with 0 here renders "No tasks yet"
      // instead of a success rate.
      tasksToday: 0,
      successRate: 99,
      avgResponseTime: "4.0s",
      workflowsUsing: 1,
    },
    capabilities: ["Invoice matching", "Variance flagging"],
    permissions: ["quickbooks", "hubspot"],
    lastAction: "Reconciled 18 invoices for February",
    lastActionTime: "yesterday",
    knowledgeDocCount: 3,
    connectedSystems: ["QuickBooks", "HubSpot"],
  },
  {
    id: "agt_market_research",
    name: "Market Research",
    role: "Account research",
    department: "Marketing",
    description: "Researches target accounts and summarises buying signals before outreach.",
    status: "active",
    model: "gpt-4o",
    stats: { tasksToday: 9, successRate: 95, avgResponseTime: "5.2s", workflowsUsing: 1 },
    capabilities: ["Account research", "Signal summaries"],
    permissions: ["google_search_console", "semrush"],
    lastAction: "Summarised buying signals for 6 target accounts",
    lastActionTime: "1 hr ago",
    knowledgeDocCount: 8,
    connectedSystems: ["Google Search Console", "SEMrush"],
  },
  {
    id: "agt_campaign_planner",
    name: "Campaign Planner",
    role: "Campaign planning",
    department: "Marketing",
    description: "Drafts nurture campaigns from segment changes and queues them for review.",
    status: "idle",
    model: "gpt-4o-mini",
    stats: { tasksToday: 0, successRate: 93, avgResponseTime: "3.9s", workflowsUsing: 1 },
    capabilities: ["Campaign drafts", "Segment checks"],
    permissions: ["mailchimp", "hubspot"],
    lastAction: "Drafted the March nurture sequence",
    lastActionTime: "3 hr ago",
    knowledgeDocCount: 5,
    connectedSystems: ["Mailchimp", "HubSpot"],
  },
  {
    id: "agt_access_review",
    name: "Access Review",
    role: "Security and compliance",
    department: "Operations",
    description: "Reviews connector scopes weekly and flags access that exceeds policy.",
    status: "active",
    model: "gpt-4o-mini",
    stats: { tasksToday: 4, successRate: 100, avgResponseTime: "2.6s", workflowsUsing: 1 },
    capabilities: ["Scope review", "Policy checks"],
    permissions: ["github", "slack"],
    lastAction: "Flagged 2 connector scopes above policy",
    lastActionTime: "2 hr ago",
    knowledgeDocCount: 2,
    connectedSystems: ["GitHub", "Slack"],
  },
]

/**
 * Shape must match normalizeWorkflow() in app/(app)/workflows/page.tsx.
 *
 * `successRate` and `lastRun` are STRINGS rendered verbatim into the table, so
 * they carry their own units — a bare number would print "98.2" with no percent
 * sign. `status` outside active|paused|draft|error silently becomes "draft".
 */
const workflows = [
  {
    id: "wf_lead_triage",
    name: "Inbound lead triage",
    description: "Enrich inbound form fills and stage the CRM contact for approval.",
    status: "active",
    environment: "production",
    lastRun: "4 min ago",
    successRate: "98.2%",
    runCount: 1284,
    isRunning: true,
  },
  {
    id: "wf_deal_desk",
    name: "Deal desk sync",
    description: "Reconcile opportunity stages against meeting notes and support threads.",
    status: "active",
    environment: "production",
    lastRun: "38 min ago",
    successRate: "94.7%",
    runCount: 412,
  },
  {
    id: "wf_support_routing",
    name: "Support escalation routing",
    description: "Attach account context to new tickets and page the on-call owner.",
    status: "active",
    environment: "production",
    lastRun: "12 min ago",
    successRate: "96.1%",
    runCount: 903,
  },
  {
    id: "wf_invoice_recon",
    name: "Invoice reconciliation",
    description: "Match paid invoices to closed-won deals and flag mismatches.",
    status: "paused",
    environment: "staging",
    lastRun: "yesterday",
    successRate: "99.0%",
    runCount: 156,
  },
  {
    id: "wf_churn_digest",
    name: "Churn risk digest",
    description: "Weekly summary of accounts with falling usage and open escalations.",
    status: "draft",
    environment: "staging",
    lastRun: "Never",
    successRate: "-",
    runCount: 0,
  },
]

/**
 * Keyed by request pathname. The harness serves these to the real client code
 * in place of a live backend.
 *
 * Matching is an exact `hasOwnProperty` check on the pathname, so nested routes
 * such as /api/workflows/stats need their own entry — they do NOT inherit from
 * /api/workflows. Anything under /api/ with no entry resolves to `{}`, which
 * renders as a silent empty state rather than an error, so a missing key looks
 * like a design problem instead of a fixture problem.
 */
// Multi-agent run review: one finished run with contributions and a merged
// recommendation, and one failed run with a connector error, so the list and
// the inspector show every state a reviewer needs to judge.
const swarmRenewalRisk = {
  id: "swr_renewal_risk",
  orgId: DEMO_ORG_ID,
  parentAgentId: "agt_deal_desk",
  objective: "Assess Q3 renewal risk for Northwind Logistics and recommend a save plan",
  status: "completed",
  decisionMethod: "majority_vote",
  councilSessionId: "cns_renewal_risk",
  finalRecommendation:
    "Offer a 12-month renewal at the current rate with a dedicated onboarding review in week 2. Usage dropped 31% after the March API change, but 4 of 5 open tickets are resolved and the champion is still active.",
  finalConfidence: 0.82,
  aggregateResult: { votes: { renew_with_review: 2, discount_10: 1 } },
  errorMessage: null,
  executionVerified: true,
  createdAt: AGO(48),
  updatedAt: AGO(41),
  completedAt: AGO(41),
  subtasks: [
    {
      id: "sst_rr_01",
      swarmRunId: "swr_renewal_risk",
      agentId: "agt_deal_desk",
      taskPrompt: "Review contract terms, pricing history and renewal date",
      scopedTools: [],
      sortOrder: 0,
      status: "completed",
      agentJobId: "job_rr_01",
      result: { recommendation: "renew_with_review", renewalDate: "2026-07-31", currentArr: 48000 },
      errorMessage: null,
      executionVerified: true,
      createdAt: AGO(48),
      completedAt: AGO(44),
    },
    {
      id: "sst_rr_02",
      swarmRunId: "swr_renewal_risk",
      agentId: "agt_support_escalation",
      taskPrompt: "Summarize open and recent support tickets",
      scopedTools: [],
      sortOrder: 1,
      status: "completed",
      agentJobId: "job_rr_02",
      result: { recommendation: "renew_with_review", openTickets: 1, resolvedLast30d: 4 },
      errorMessage: null,
      executionVerified: true,
      createdAt: AGO(48),
      completedAt: AGO(43),
    },
    {
      id: "sst_rr_03",
      swarmRunId: "swr_renewal_risk",
      agentId: "agt_lead_triage",
      taskPrompt: "Check product usage trend and champion engagement",
      scopedTools: [],
      sortOrder: 2,
      status: "completed",
      agentJobId: "job_rr_03",
      result: { recommendation: "discount_10", usageChange: -0.31, championActive: true },
      errorMessage: null,
      executionVerified: true,
      createdAt: AGO(48),
      completedAt: AGO(42),
    },
  ],
}

const swarmChurnAudit = {
  id: "swr_churn_audit",
  orgId: DEMO_ORG_ID,
  parentAgentId: "agt_support_escalation",
  objective: "Audit churned accounts from May for shared root causes",
  status: "failed",
  decisionMethod: "chair_decides",
  councilSessionId: null,
  finalRecommendation: null,
  finalConfidence: null,
  aggregateResult: {},
  errorMessage: "HubSpot connection expired before the account export finished. Reconnect HubSpot and run again.",
  executionVerified: true,
  createdAt: AGO(26 * 60),
  updatedAt: AGO(26 * 60 - 3),
  completedAt: AGO(26 * 60 - 3),
  subtasks: [
    {
      id: "sst_ca_01",
      swarmRunId: "swr_churn_audit",
      agentId: "agt_support_escalation",
      taskPrompt: "Group cancellation reasons from exit tickets",
      scopedTools: [],
      sortOrder: 0,
      status: "completed",
      agentJobId: "job_ca_01",
      result: { topReason: "onboarding_gap", accounts: 7 },
      errorMessage: null,
      executionVerified: true,
      createdAt: AGO(26 * 60),
      completedAt: AGO(26 * 60 - 2),
    },
    {
      id: "sst_ca_02",
      swarmRunId: "swr_churn_audit",
      agentId: "agt_lead_triage",
      taskPrompt: "Export churned account history from HubSpot",
      scopedTools: [],
      sortOrder: 1,
      status: "failed",
      agentJobId: "job_ca_02",
      result: null,
      errorMessage: "401 from HubSpot: token expired",
      executionVerified: true,
      createdAt: AGO(26 * 60),
      completedAt: AGO(26 * 60 - 3),
    },
  ],
}

export const SHOT_FIXTURES: Record<string, unknown> = {
  // Intelligence › Data: public dataset providers and a search result page.
  "/api/training/external-datasets/providers": {
    providers: [
      { id: "huggingface", label: "Hugging Face", capabilities: ["search", "inspect"], auth: "optional_token", materialization: "explicit_only", notes: "" },
      { id: "kaggle", label: "Kaggle", capabilities: ["search", "inspect"], auth: "optional_token", materialization: "explicit_only", notes: "" },
    ],
    count: 2,
    mutation: false,
    materialization: "explicit_only",
  },
  "/api/training/external-datasets/search": {
    provider: "huggingface",
    query: "support",
    count: 3,
    mutation: false,
    datasets: [
      { provider: "huggingface", dataset_id: "bitext/customer-support-intents", name: "customer-support-intents", author: "bitext", description: "Customer support utterances labelled by intent.", tags: ["text-classification"], downloads: null, likes: null, private: false, gated: false, reference_url: "https://huggingface.co/datasets/bitext/customer-support-intents" },
      { provider: "huggingface", dataset_id: "example/support-tickets", name: "support-tickets", author: "example", description: "Service desk tickets with priority and category.", tags: ["tabular"], downloads: null, likes: null, private: false, gated: false, reference_url: "https://huggingface.co/datasets/example/support-tickets" },
      { provider: "huggingface", dataset_id: "example/crm-deal-outcomes", name: "crm-deal-outcomes", author: "example", description: "Deal stages with win and loss outcomes.", tags: ["tabular"], downloads: null, likes: null, private: false, gated: true, reference_url: "https://huggingface.co/datasets/example/crm-deal-outcomes" },
    ],
  },
  "/api/agent-swarm/swr_renewal_risk": swarmRenewalRisk,
  "/api/agent-swarm/swr_churn_audit": swarmChurnAudit,
  __supabaseUser: supabaseUser,
  __orgId: DEMO_ORG_ID,

  // Shape must match the `Connector` interface in app/(app)/connectors/page.tsx.
  // Requested as /api/connectors?org=…&live=1; the harness matches on pathname
  // only, so the query string is irrelevant here.
  "/api/connectors": {
    // Mirrors backend _connector_response_item: availability is the only
    // readiness signal; there are no usage/latency/request fields.
    connectors: [
      {
        id: "con_hubspot",
        name: "HubSpot",
        // `vendor` (NOT `type`) carries the vendor slug: normalizeConnector reads
        // `model.vendor ?? model.type` and shouldShowConnectedConnectorOnHub drops
        // any row whose slug is not a catalog vendor.
        vendor: "hubspot",
        status: "connected",
        environment: "production",
        lastSync: AGO(3),
        description: "Marketing, sales, and service",
        authType: "oauth",
        authStatus: "active",
        availability: {
          configured: true,
          authenticated: true,
          tokenValid: true,
          scopesValid: true,
          healthy: true,
          executable: true,
          lastCheckedAt: AGO(2),
          sourceOfTruth: "oauth_token_check",
        },
      },
      {
        id: "con_salesforce",
        name: "Salesforce",
        vendor: "salesforce",
        status: "error",
        environment: "production",
        lastSync: AGO(96),
        description: "CRM and sales automation",
        authType: "oauth",
        authStatus: "active",
        config: { instance_url: "northwind.my.salesforce.com" },
        availability: {
          configured: true,
          authenticated: true,
          tokenValid: true,
          scopesValid: false,
          healthy: true,
          executable: false,
          blockingReason: "missing_scope",
          recoveryAction: "Grant the connected user edit access on Opportunity, then re-run the blocked step.",
          lastCheckedAt: AGO(14),
          sourceOfTruth: "oauth_token_check",
        },
      },
      {
        id: "con_google_ads",
        name: "Google Ads",
        vendor: "google_ads",
        status: "error",
        environment: "production",
        lastSync: AGO(60 * 26),
        description: "Campaign performance reporting",
        authType: "oauth",
        authStatus: "auth_expired",
        availability: {
          configured: true,
          authenticated: true,
          tokenValid: false,
          scopesValid: true,
          healthy: false,
          executable: false,
          blockingReason: "token_expired",
          recoveryAction: "Reconnect Google Ads to restore reporting syncs.",
          lastCheckedAt: AGO(30),
          sourceOfTruth: "oauth_token_check",
        },
      },
      {
        id: "con_zendesk",
        name: "Zendesk",
        vendor: "zendesk",
        status: "connected",
        environment: "production",
        lastSync: AGO(12),
        description: "Support tickets and macros",
        authType: "oauth",
        authStatus: "active",
        config: { subdomain: "northwind" },
        availability: {
          configured: true,
          authenticated: true,
          tokenValid: true,
          scopesValid: true,
          healthy: true,
          executable: true,
          lastCheckedAt: AGO(11),
          sourceOfTruth: "oauth_token_check",
        },
      },
      {
        id: "con_slack",
        name: "Slack",
        vendor: "slack",
        status: "syncing",
        environment: "production",
        lastSync: AGO(1),
        description: "Notifications and approvals",
        authType: "oauth",
        authStatus: "active",
        availability: {
          configured: true,
          authenticated: true,
          tokenValid: true,
          scopesValid: true,
          healthy: true,
          executable: true,
          lastCheckedAt: AGO(1),
          sourceOfTruth: "oauth_token_check",
        },
      },
    ],
  },

  // Real action definitions exported from the backend catalog by
  // scripts/export-shot-action-catalog.py (static product data, not usage).
  "/api/connectors/catalog/actions": shotActionCatalog,

  // ensureSelectedOrg() resolves the active org from this list and calls
  // purgeStaleDemoOrgFromStorage(), which DELETES the seeded gravitre:selectedOrg
  // if its id is absent here. Without this the top bar falls back to its
  // hardcoded "Acme Corp" default.
  "/api/organizations": {
    organizations: [
      { id: DEMO_ORG_ID, name: "Northwind Logistics", slug: "northwind-logistics", role: "admin" },
    ],
  },

  // Shape must match the `Approval` interface in app/(app)/approvals/page.tsx;
  // normalizeApprovalsResponse drops any entry without an `id`.
  "/api/approvals": {
    approvals: [
      {
        id: "apr_01hq9d4k2m",
        title: "Create HubSpot contact for Priya Raman",
        description:
          "Inbound lead from the pricing page. Gravitre matched no existing contact and prepared a create with the enriched company record.",
        type: "workflow",
        environment: "production",
        requestedBy: "Inbound lead triage",
        requestedAt: T(4),
        priority: "high",
        status: "pending",
        aiRecommendation: {
          // Whole percent: the UI renders `{confidence}%` verbatim, so 0.94 would
          // display as "0.94% confidence".
          action: "approve",
          confidence: 94,
          reason: "No duplicate contact found. Company domain verified against the enriched record.",
        },
        slaDeadline: T(-56),
        slaMinutesRemaining: 56,
        slaBreached: false,
        context: {
          entity: "HubSpot contact",
          action: "hubspot.contacts.create",
          impact: "Creates one contact and associates it with Northwind Logistics.",
          runId: "run_01hq9d4k2m",
          risk_level: "medium",
        },
        steps: [
          { text: "Search HubSpot for an existing contact with this email", app: "hubspot", action: "hubspot.contacts.search", access: "read" },
          { text: "Enrich the company record from Apollo", app: "apollo", action: "apollo.organizations.enrich", access: "read" },
          { text: "Create the contact and associate it with Northwind Logistics", app: "hubspot", action: "hubspot.contacts.create", access: "write" },
        ],
      },
      {
        id: "apr_01hq9c8b1x",
        title: "Update Salesforce opportunity stage to Negotiation",
        description:
          "Zendesk thread confirms the procurement call is booked. Gravitre prepared the stage change on opportunity 0064x.",
        type: "workflow",
        environment: "production",
        requestedBy: "Deal desk sync",
        requestedAt: T(38),
        priority: "medium",
        status: "pending",
        aiRecommendation: {
          action: "review",
          confidence: 61,
          reason: "Close date is unchanged while the stage advances — worth a human check.",
        },
        slaDeadline: T(-182),
        slaMinutesRemaining: 182,
        slaBreached: false,
        context: {
          entity: "Salesforce opportunity 0064x",
          action: "salesforce.opportunity.update",
          impact: "Changes StageName on one opportunity.",
          runId: "run_01hq9c8b1x",
          risk_level: "medium",
        },
        steps: [
          { text: "Read the Zendesk thread for the booked procurement call", app: "zendesk", action: "zendesk.tickets.get", access: "read" },
          { text: "Move opportunity 0064x to Negotiation", app: "salesforce", action: "salesforce.opportunity.update", access: "write" },
        ],
      },
      {
        id: "apr_01hq9a2f7t",
        title: "Grant Zendesk write scope to the support workflow",
        description:
          "The macro-apply step needs ticket write access. Gravitre is holding until an admin approves the scope change.",
        type: "connector",
        environment: "production",
        requestedBy: "Dana Whitfield",
        requestedAt: T(126),
        priority: "low",
        status: "pending",
        aiRecommendation: {
          action: "review",
          confidence: 48,
          reason: "Scope expansion is permanent until revoked. Confirm the workflow still needs it.",
        },
        slaDeadline: null,
        slaMinutesRemaining: null,
        slaBreached: false,
        context: {
          entity: "Zendesk connector",
          action: "connector.scope.grant",
          risk_level: "high",
          impact: "Adds tickets:write for every workflow using this connector.",
        },
        steps: [
          { text: "Add tickets:write to the Zendesk connector", app: "zendesk", action: "connector.scope.grant", access: "write" },
          { text: "Apply the refund macro to the waiting tickets", app: "zendesk", action: "zendesk.macros.apply", access: "write" },
        ],
      },
    ],
  },

  "/api/billing/status": {
    canAccessApp: true,
    billingStatus: "active",
    requiresUpgrade: false,
    trialEndsAt: null,
    plan: "control",
  },
  // Billing overview for /settings/billing. Shape mirrors BillingOverview from
  // GET /api/billing. Capture-only; the shots layout 404s in production.
  //
  // Two fields are load-bearing and fail silently if omitted:
  //   - usage.voice_minutes_billing_visible gates the ENTIRE Voice Minutes card
  //     and the top-up / auto-top-up block behind showVoiceBilling.
  //   - usage.tier must be a real plan code, or planKnown goes false and the
  //     grid renders empty placeholders instead of the metric cards.
  "/api/billing": {
    billing_status: "active",
    subscription: {
      tier: "control",
      status: "active",
      // AGO, not T: T is pinned to a fixed anchor date, which would render this
      // renewal as already past. A negative offset here means 18 days ahead of
      // the real capture clock.
      current_period_end: AGO(-18 * 24 * 60),
      cancel_at_period_end: false,
    },
    usage: {
      tier: "control",
      totals: {
        workflow_runs: 1284,
        // The AI Credits card reads totals.ai_tokens; a key named ai_credits is
        // silently ignored and the card renders "0 / 5,000" at 0%.
        ai_tokens: 18_400,
        outputs: 742,
        research_lookups: 96,
        voice_minutes: 218,
        api_calls: 41_930,
      },
      weekly_totals: [140, 210, 265, 240, 190, 155, 84],
      workflow_runs_included: 2000,
      // ai_credits_included, not included_ai_credits — this one field inverts the
      // naming used by included_outputs / included_voice_minutes / etc., and the
      // wrong order silently falls back to the plan default limit.
      ai_credits_included: 25_000,
      included_outputs: 1000,
      included_research_lookups: 150,
      included_voice_minutes: 300,
      research_lookups_billing_visible: true,
      voice_minutes_billing_visible: true,
      voice_minute_overage_rate_usd: 0.12,
      output_overage_rate_usd: 0.4,
      overage_voice_minutes: 0,
      overage_outputs: 0,
      overage_research_lookups: 0,
    },
    invoices: [],
  },
  // Voice settings for the top-up + auto-top-up block. voice_enabled must not be
  // false or voiceOrgEnabled flips and the card captures its org-disabled state.
  "/api/settings/voice-access": {
    voice: {
      voice_enabled: true,
      voice_minutes_prepaid: 240,
      voice_auto_topup_enabled: true,
      voice_auto_topup_minutes: 60,
      voice_auto_topup_threshold_minutes: 15,
      voice_auto_topup_max_charge_cents: 3600,
    },
  },
  // AppShell gates the whole product on this: until welcome is completed or
  // skipped it replaces the route with /welcome, so an un-fixtured onboarding
  // response silently captures the onboarding flow instead of the surface.
  "/api/onboarding": {
    welcome_completed: true,
    skipped: true,
    completed_steps: ["welcome", "connect", "first_run"],
    current_step: null,
  },
  // The app calls /api/auth/me (not /api/me) — keep both so either path works.
  "/api/auth/me": {
    user: { id: supabaseUser.id, email: supabaseUser.email, name: "Dana Whitfield" },
    org: { id: DEMO_ORG_ID, name: "Northwind Logistics" },
    orgs: [{ id: DEMO_ORG_ID, name: "Northwind Logistics", role: "admin" }],
    billing: { can_access_app: true, billing_status: "active", plan: "control" },
  },
  "/api/me": {
    user: { id: supabaseUser.id, email: supabaseUser.email, name: "Dana Whitfield" },
    org: { id: DEMO_ORG_ID, name: "Northwind Logistics" },
    orgs: [{ id: DEMO_ORG_ID, name: "Northwind Logistics", role: "admin" }],
    billing: { can_access_app: true, billing_status: "active", plan: "control" },
  },
  "/api/orgs": {
    orgs: [{ id: DEMO_ORG_ID, name: "Northwind Logistics", role: "admin" }],
  },
  "/api/settings": {
    settings: { onboarding: { checklist_dismissed: true, skipped: true } },
  },
  "/api/business-outcomes": {
    businessOutcomes,
    count: businessOutcomes.length,
  },

  // Preset voice library. Shape mirrors the live /api/voice/library response
  // ({ voices: [...] }) so the assignment surface renders real preset cards
  // instead of its empty state during capture. Capture-only: this fixture is
  // never reachable in production because the shots layout 404s there.
  "/api/voice/library": {
    voices: [
      // voice_id is required by LibraryVoice and is what the card keys and
      // selection compare on — omitting it silently collapses every card onto
      // an undefined key.
      {
        voice_id: "shot-voice-atlas",
        key: "atlas",
        name: "Atlas",
        personality: { descriptor: "Steady and precise", tone: "Warm", energy: "Measured" },
        categories: ["Operations", "Support"],
        models: ["eleven_turbo_v2_5"],
        languages: ["en-US"],
      },
      {
        voice_id: "shot-voice-juno",
        key: "juno",
        name: "Juno",
        personality: { descriptor: "Bright and quick", tone: "Friendly", energy: "Upbeat" },
        categories: ["Sales"],
        models: ["eleven_turbo_v2_5"],
        languages: ["en-US", "en-GB"],
      },
      {
        voice_id: "shot-voice-cormac",
        key: "cormac",
        name: "Cormac",
        personality: { descriptor: "Low and deliberate", tone: "Authoritative", energy: "Calm" },
        categories: ["Finance", "Legal"],
        models: ["eleven_multilingual_v2"],
        languages: ["en-US"],
      },
      {
        voice_id: "shot-voice-sable",
        key: "sable",
        name: "Sable",
        personality: { descriptor: "Clear and neutral", tone: "Professional", energy: "Even" },
        categories: ["Operations"],
        models: ["eleven_turbo_v2_5"],
        languages: ["en-US"],
      },
    ],
  },

  "/api/agents": { agents },
  "/api/agents/agt_lead_triage": { agent: agents[0] },
  "/api/agents/agt_deal_desk": { agent: agents[1] },
  // FIXTURE: agent identity policy + capability profile (shape of GET /identity, /capabilities).
  "/api/agents/agt_lead_triage/identity": {
    identity: {
      agentId: "agt_lead_triage",
      trustLevel: "write_with_approval",
      allowedActionKinds: ["read", "write"],
      allowedToolPatterns: ["hubspot.contacts.*", "apollo.people.*"],
      maxActionsPerDay: 200,
      maxSpendUsdPerDay: null,
      approvalRuleOverrides: { "hubspot.contacts.delete": "always_deny" },
      updatedAt: "2026-09-21T15:00:00Z",
    },
    effective: {
      trustLevel: "write_with_approval",
      allowedActionKinds: ["read", "write"],
      allowedToolPatterns: ["hubspot.contacts.*", "apollo.people.*"],
    },
    usageToday: { actions: 34, tokens: 0, spendUsd: 0 },
  },
  "/api/agents/agt_lead_triage/capabilities": {
    allowedConnectors: ["hubspot", "apollo"],
    availableReadActions: ["hubspot.contacts.search", "apollo.people.enrich"],
    availableWriteActions: ["hubspot.contacts.create", "hubspot.contacts.update"],
    approvalRequiredActions: ["hubspot.contacts.create", "hubspot.contacts.update"],
  },

  // Agents 4.0 GRAPH — swarm parent→subtask edges (capture harness only).
  "/api/agent-swarm": {
    runs: [
      {
        id: "swr_revenue_enrich",
        orgId: DEMO_ORG_ID,
        parentAgentId: "agt_lead_triage",
        objective: "Enrich inbound lead and stage CRM write",
        status: "running",
        decisionMethod: "chair_decides",
        councilSessionId: null,
        finalRecommendation: null,
        finalConfidence: null,
        aggregateResult: {},
        errorMessage: null,
        createdAt: AGO(6),
        updatedAt: AGO(1),
        completedAt: null,
        subtasks: [
          {
            id: "sst_01",
            swarmRunId: "swr_revenue_enrich",
            agentId: "agt_deal_desk",
            taskPrompt: "Stage opportunity context",
            scopedTools: [],
            sortOrder: 0,
            status: "running",
            agentJobId: null,
            result: null,
            errorMessage: null,
            createdAt: AGO(5),
            completedAt: null,
          },
          {
            id: "sst_02",
            swarmRunId: "swr_revenue_enrich",
            agentId: "agt_support_escalation",
            taskPrompt: "Pull related tickets",
            scopedTools: [],
            sortOrder: 1,
            status: "queued",
            agentJobId: null,
            result: null,
            errorMessage: null,
            createdAt: AGO(5),
            completedAt: null,
          },
        ],
      },
      swarmRenewalRisk,
      swarmChurnAudit,
    ],
  },
  "/api/agent-swarm/swr_revenue_enrich": {
    id: "swr_revenue_enrich",
    orgId: DEMO_ORG_ID,
    parentAgentId: "agt_lead_triage",
    objective: "Enrich inbound lead and stage CRM write",
    status: "running",
    decisionMethod: "chair_decides",
    councilSessionId: null,
    finalRecommendation: null,
    finalConfidence: null,
    aggregateResult: {},
    errorMessage: null,
    createdAt: AGO(6),
    updatedAt: AGO(1),
    completedAt: null,
    subtasks: [
      {
        id: "sst_01",
        swarmRunId: "swr_revenue_enrich",
        agentId: "agt_deal_desk",
        taskPrompt: "Stage opportunity context",
        scopedTools: [],
        sortOrder: 0,
        status: "running",
        agentJobId: null,
        result: null,
        errorMessage: null,
        createdAt: AGO(5),
        completedAt: null,
      },
      {
        id: "sst_02",
        swarmRunId: "swr_revenue_enrich",
        agentId: "agt_support_escalation",
        taskPrompt: "Pull related tickets",
        scopedTools: [],
        sortOrder: 1,
        status: "queued",
        agentJobId: null,
        result: null,
        errorMessage: null,
        createdAt: AGO(5),
        completedAt: null,
      },
    ],
  },

  // Home dashboard (/home + /e2e/shots/home) — camelCase overview + AI OS fields
  // that normalizeMetricsOverview / normalizeAiOsStatus expect. Honest fixture
  // counts only; no invented product claims.
  // Screenshot-only inventory: mixed connection states, complete schema disclosure.
  "/api/sources": {
    sources: [
      { id: "src_hubspot", name: "HubSpot · hubspot", type: "hubspot", typeId: "hubspot", category: "warehouse", status: "error", environment: "production", lastSync: AGO(2), recordCount: 0, lastSyncError: "401 Unauthorized: refresh token expired", recentSyncs: [{ status: "error", records: null, createdAt: AGO(120) }, { status: "error", records: null, createdAt: AGO(60) }] },
      { id: "src_matrix", name: "Escalation Matrix", type: "manual", typeId: "manual", category: "warehouse", status: "error", environment: "production", lastSync: AGO(2), recordCount: 0, lastSyncError: "Could not parse row 1: missing header 'severity'", recentSyncs: [{ status: "error", records: null, createdAt: AGO(120) }, { status: "error", records: null, createdAt: AGO(60) }] },
      { id: "src_warehouse", name: "Northwind operations warehouse", type: "postgres", typeId: "postgresql", category: "sql", status: "connected", environment: "production", lastSync: AGO(12), tables: 16, recordCount: 12400, workflowsUsing: 3, operatorsUsing: 2, health: 98, topTables: ["accounts", "service_requests", "invoices", "contract_renewals", "workflow_events"], recentSyncs: [{ status: "success", records: 1200, createdAt: AGO(420) }, { status: "success", records: 1200, createdAt: AGO(360) }, { status: "success", records: 1200, createdAt: AGO(300) }, { status: "success", records: 1200, createdAt: AGO(240) }, { status: "success", records: 1200, createdAt: AGO(180) }, { status: "success", records: 1200, createdAt: AGO(120) }, { status: "success", records: 1200, createdAt: AGO(60) }] },
      { id: "src_ingesting", name: "Service event archive", type: "mongodb", category: "nosql", status: "syncing", environment: "staging", lastSync: AGO(3), tables: 4, recordCount: 1800, workflowsUsing: 1, operatorsUsing: 1, recentSyncs: [{ status: "success", records: 1200, createdAt: AGO(180) }, { status: "success", records: 1200, createdAt: AGO(120) }, { status: "success", records: 1200, createdAt: AGO(60) }] },
      { id: "src_attention", name: "Finance reporting warehouse", type: "snowflake", typeId: "snowflake", category: "warehouse", status: "error", environment: "production", lastSync: AGO(180), tables: 8, recordCount: 6400, workflowsUsing: 2, operatorsUsing: 1, description: "Connection requires review before the next ingestion.", recentSyncs: [{ status: "success", records: 1200, createdAt: AGO(360) }, { status: "success", records: 1200, createdAt: AGO(300) }, { status: "success", records: 1200, createdAt: AGO(240) }, { status: "success", records: 1200, createdAt: AGO(180) }, { status: "error", records: null, createdAt: AGO(120) }, { status: "error", records: null, createdAt: AGO(60) }] },
      { id: "src_macros", name: "Support Macros", type: "manual", typeId: "manual", category: "warehouse", status: "unknown", environment: "production", lastSync: AGO(60 * 24 * 88), recordCount: 0, recentSyncs: [] },
    ],
    ingestion: [
      { sourceId: "src_hubspot", kind: "sync", status: "error", createdAt: AGO(2) },
      { sourceId: "src_matrix", kind: "sync", status: "error", createdAt: AGO(2) },
      { sourceId: "src_ingesting", kind: "sync", status: "success", records: 1800, createdAt: AGO(3) },
      { sourceId: "src_warehouse", kind: "sync", status: "success", records: 12400, createdAt: AGO(12) },
      { sourceId: "src_attention", kind: "sync", status: "error", createdAt: AGO(180) },
      { sourceId: "src_macros", kind: "created", createdAt: AGO(60 * 24 * 88) },
    ],
  },
  // Source detail (/e2e/shots/source-detail/src_warehouse). Shapes follow
  // app/(app)/sources/[id]/page.tsx: `{ source }`, `{ tables }`, `{ history }`.
  "/api/sources/src_warehouse": {
    source: {
      id: "src_warehouse",
      name: "Northwind operations warehouse",
      type: "postgres",
      typeId: "postgres",
      status: "connected",
      environment: "production",
      description: "Operational system of record for accounts, service requests and invoicing.",
      lastSync: AGO(12),
      createdAt: AGO(60 * 24 * 41),
      recordCount: 12400,
      tables: 16,
      connectionHost: "warehouse.northwind.internal",
      connectionPort: 5432,
      connectionDatabase: "ops_prod",
      syncIntervalSeconds: 3600,
    },
  },
  "/api/sources/src_warehouse/schema": {
    tables: [
      { name: "accounts", schema: "public", columns: Array.from({ length: 14 }, (_, i) => ({ name: `c${i}`, type: "text" })) },
      { name: "service_requests", schema: "public", columns: Array.from({ length: 19 }, (_, i) => ({ name: `c${i}`, type: "text" })) },
      { name: "invoices", schema: "billing", columns: Array.from({ length: 11 }, (_, i) => ({ name: `c${i}`, type: "text" })) },
      { name: "contract_renewals", schema: "billing", columns: Array.from({ length: 9 }, (_, i) => ({ name: `c${i}`, type: "text" })) },
      { name: "workflow_events", schema: "ops", columns: Array.from({ length: 7 }, (_, i) => ({ name: `c${i}`, type: "text" })) },
    ],
  },
  "/api/sources/src_warehouse/sync-history": {
    history: [
      { id: "sh_3", status: "success", records: 12400, tables: 16, createdAt: AGO(12), trigger: "scheduled", durationMs: 41000 },
      { id: "sh_2", status: "failed", error: "Connection reset while reading billing.invoices", createdAt: AGO(72), trigger: "scheduled" },
      { id: "sh_1", status: "success", records: 12310, tables: 16, createdAt: AGO(132), trigger: "manual", durationMs: 38000 },
    ],
  },
  "/api/sources/src_warehouse/agent-assignments": {
    sourceName: "Northwind operations warehouse",
    assignedCount: 2,
    agents: [
      { agentId: "agt_lead_triage", agentName: "Lead triage", department: "Revenue", role: "Qualifies inbound leads", assigned: true, assignmentId: "asg_1" },
      { agentId: "agt_support_resolver", agentName: "Support resolver", department: "Support", role: "Resolves tier-1 tickets", assigned: true, assignmentId: "asg_2" },
      { agentId: "agt_renewals", agentName: "Renewals desk", department: "Finance", role: "Prepares renewal quotes", assigned: false, assignmentId: null },
    ],
  },
  // Connector detail (/e2e/shots/connector-detail/con_hubspot).
  "/api/connectors/con_hubspot": {
    connector: {
      id: "con_hubspot",
      name: "HubSpot",
      vendor: "hubspot",
      type: "hubspot",
      status: "connected",
      authStatus: "active",
      environment: "production",
      lastSync: AGO(3),
      createdAt: AGO(60 * 24 * 90),
      description: "Marketing, sales, and service",
      syncFrequency: "Every 15 minutes",
      config: { webhookUrl: "https://hooks.gravitre.app/hubspot/northwind" },
    },
  },
  "/api/metrics/runs": {
    runVolume: [
      { time: "08:00", completed: 42, failed: 2 }, { time: "09:00", completed: 58, failed: 1 },
      { time: "10:00", completed: 76, failed: 3 }, { time: "11:00", completed: 63, failed: 2 },
      { time: "12:00", completed: 89, failed: 1 }, { time: "13:00", completed: 72, failed: 2 },
    ],
    latencyDistribution: [{ time: "08:00", p50: 240, p95: 420, p99: 700 }, { time: "09:00", p50: 260, p95: 510, p99: 780 }, { time: "10:00", p50: 280, p95: 620, p99: 980 }, { time: "11:00", p50: 250, p95: 460, p99: 730 }],
    latencySpikeTime: "10:00",
  },
  "/api/metrics/insights": { insights: [] },
  "/api/metrics/home-reports": homeReportsShotFixture(),
  // FIXTURE: shape of GET /api/metrics/agent-roster (Agents roster Team / List / Work map).
  "/api/metrics/agent-roster": {
    generatedAt: AGO(1),
    days: Array.from({ length: 14 }, (_, i) => AGO((13 - i) * 1440)),
    agents: {
      agt_lead_triage: {
        tasksToday: 34, failedToday: 1, runningNow: 0, successRateToday: 97.1, successRate7d: 98,
        lastActiveAt: AGO(4), daily: [12, 18, 0, 22, 25, 19, 28, 30, 24, 0, 26, 31, 29, 34], blocked: null,
      },
      agt_deal_desk: {
        tasksToday: 6, failedToday: 0, runningNow: 1, successRateToday: 100, successRate7d: 94,
        lastActiveAt: AGO(2), daily: [3, 4, 2, 5, 6, 4, 3, 5, 7, 2, 4, 6, 5, 6], blocked: null,
      },
      agt_support_escalation: {
        tasksToday: 0, failedToday: 1, runningNow: 0, successRateToday: 0, successRate7d: 88,
        lastActiveAt: AGO(95), daily: [5, 4, 6, 3, 2, 4, 5, 6, 3, 2, 4, 3, 1, 0],
        blocked: { kind: "failed", reason: "Waiting on a Zendesk plan with API access", jobId: "job_shot_1", at: AGO(95) },
      },
      agt_market_research: {
        tasksToday: 3, failedToday: 0, runningNow: 0, successRateToday: 100, successRate7d: 100,
        lastActiveAt: AGO(40), daily: [0, 1, 0, 2, 1, 0, 3, 1, 2, 0, 1, 2, 1, 3], blocked: null,
      },
    },
    approvalGate: { agt_market_research: false },
    goals: [
      {
        id: "goal_pipeline", objective: "Recover $1.2M of stalled Q3 pipeline", status: "active",
        department: "Sales", priority: "high", connectedSystems: ["HubSpot", "Salesforce", "Slack"],
        agentIds: ["agt_lead_triage", "agt_deal_desk"],
      },
    ],
  },
  "/api/settings/home-reports-layout": { layout: null },
  "/api/settings/hitl-policies": { policies: [] },
  "/api/metrics/weekly-throughput": {
    target: 2400,
    days: ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"].map((day, index) => ({ day, records: [1800, 2200, 2600, 2100, 2800, 1500, 1200][index], target: 2400 })),
  },
  "/api/metrics/overview": {
    totalWorkflows: 12,
    activeWorkflows: 8,
    totalRuns: 2755,
    successRate: 96.8,
    avgDuration: 4200,
    avgLatency: 310,
    recordsProcessed: 18420,
    activeConnectors: 4,
    totalConnectors: 6,
    connectorHealthLatencyMs: 180,
    connectorHealthLatencyP95Ms: 420,
    changes: {
      totalRuns: 4.2,
      successRate: 0.6,
      recordsProcessed: 8.1,
      avgLatency: -3.4,
    },
    trends: {
      totalRuns: [210, 240, 255, 280, 300, 310, 320],
      successRate: [94, 95, 95.5, 96, 96.2, 96.5, 96.8],
      recordsProcessed: [1200, 1400, 1600, 1800, 2000, 2100, 2200],
      avgLatency: [340, 330, 325, 320, 315, 312, 310],
    },
  },
  "/api/admin/ai-os/status": {
    ml_models_live: 3,
    ml_models_planned: 2,
    memory_promotions_pending: 1,
    architecture_systems_live: 5,
    architecture_systems_planned: 1,
    intelligence_engine: { last_run: "2026-09-08T06:00:00.000Z" },
  },
  "/api/admin/intelligence/learning-progress": {
    queryRows: 42,
    queryRowsNeeded: 50,
    workflowRows: 28,
    workflowRowsNeeded: 30,
    hasAnySnapshot: true,
  },
  "/api/admin/intelligence/trust-summary": {
    avg_confidence: 0.86,
  },
  "/api/admin/intelligence/business-impact": {
    scopeNote: "Fixture scope for visual capture only.",
    businessImpactScore: 72,
    scoreLabel: "Stable",
    pendingReviewCount: 1,
    pendingBusinessSignals: 2,
    poorOutcomeAgents: 0,
    avgOutcomeWinRate: 0.81,
    revenueRiskItems: [
      {
        id: "risk_fixture_01",
        severity: "medium",
        title: "Connector retry backlog rising",
        summary: "HubSpot write retries climbed over the last 24h.",
        source: "fixture",
        suggestionType: "ops",
      },
    ],
    dimensions: { revenueRisk: 40, outcomeHealth: 78, operationalLoad: 55 },
  },
  "/api/admin/intelligence/predictive-ops": {
    summary: "No critical predictive alerts in the fixture window.",
  },
  "/api/admin/intelligence/learning/live-dashboard": {
    ready_model_count: 3,
  },
  "/api/admin/learning/status": {
    learning_velocity: "steady",
  },
  "/api/settings/dashboard-layout": {
    layout: null,
  },
  // useOrgAdmin reads this first; without it the settings shell hides the Admin tier.
  "/api/settings/lite-membership": { is_admin: true },
  "/api/lite/tasks": {
    tasks: [
      {
        id: "lt_invoice_chase",
        workflow_id: "wf_invoice_chase",
        workflow_name: "Chase overdue invoices",
        status: "processing",
        progress: 62,
        input_summary: "14 invoices over 30 days, Northwind EU",
        created_at: "2026-10-05T08:12:00Z",
      },
      {
        id: "lt_renewal_brief",
        workflow_id: "wf_renewal_brief",
        workflow_name: "Renewal brief for Q4 accounts",
        status: "completed",
        progress: 100,
        input_summary: "9 accounts renewing before Dec 31",
        created_at: "2026-10-04T15:40:00Z",
        completed_at: "2026-10-04T16:05:00Z",
      },
      {
        id: "lt_ticket_triage",
        workflow_id: "wf_ticket_triage",
        workflow_name: "Triage weekend support tickets",
        status: "pending",
        progress: 0,
        input_summary: "Zendesk queue, 38 open tickets",
        created_at: "2026-10-05T09:01:00Z",
      },
      {
        id: "lt_lead_enrich",
        workflow_id: "wf_lead_enrich",
        workflow_name: "Enrich inbound leads",
        status: "failed",
        progress: 40,
        input_summary: "HubSpot list: October webinar",
        created_at: "2026-10-03T11:20:00Z",
        error: "HubSpot token expired. Reconnect HubSpot to retry.",
      },
    ],
  },
  "/api/lite/workflows": {
    workflows: [
      {
        id: "wf_invoice_chase",
        name: "Chase overdue invoices",
        description: "Sends polite, escalating reminders and flags disputes for a person.",
        required_inputs: ["Customer list"],
      },
      {
        id: "wf_lead_enrich",
        name: "Enrich inbound leads",
        description: "Adds company, role and fit score to new leads.",
        required_inputs: ["HubSpot list"],
      },
      {
        id: "wf_weekly_report",
        name: "Weekly pipeline report",
        description: "Summarizes pipeline changes into a one-page brief.",
        required_inputs: [],
      },
    ],
  },
  "/api/lite/results": {
    summary: {
      period: "30d",
      tasks_completed: 42,
      success_rate: 92.86,
      avg_completion_time_hours: 1.6,
      by_workflow: [
        { workflow_name: "Chase overdue invoices", count: 18 },
        { workflow_name: "Enrich inbound leads", count: 15 },
        { workflow_name: "Weekly pipeline report", count: 9 },
      ],
    },
    recent: [
      {
        id: "lt_weekly_report",
        workflow_id: "wf_weekly_report",
        workflow_name: "Weekly pipeline report",
        status: "completed",
        progress: 100,
        input_summary: "Week of Sep 28",
        created_at: "2026-10-04T08:00:00Z",
      },
    ],
  },
  "/api/lite/deliverables": {
    deliverables: [
      {
        id: "dl_pipeline_brief",
        task_id: "lt_weekly_report",
        task_name: "Weekly pipeline report",
        name: "Pipeline brief - week of Sep 28.pdf",
        type: "pdf",
        size_bytes: 284_000,
        download_url: "/api/lite/deliverables/dl_pipeline_brief/download",
        created_at: "2026-10-04T08:12:00Z",
      },
      {
        id: "dl_invoice_log",
        task_id: "lt_invoice_chase",
        task_name: "Chase overdue invoices",
        name: "Reminder log.csv",
        type: "csv",
        size_bytes: 18_400,
        download_url: "/api/lite/deliverables/dl_invoice_log/download",
        created_at: "2026-10-03T16:40:00Z",
      },
    ],
  },
  "/api/settings/organization": {
    organization: {
      id: DEMO_ORG_ID,
      name: "Northwind Logistics",
      slug: "northwind-logistics",
      primaryDomain: "northwind.example",
      logoUrl: "",
    },
  },
  // Shape matches `User` in types/api.ts; TeamSettings keys rows on id.
  "/api/settings/team": {
    team: [
      { id: "usr_dana", email: "dana@northwind.example", full_name: "Dana Whitfield", role: "owner", job_title: "COO", department: "Operations" },
      { id: "usr_marcus", email: "marcus@northwind.example", full_name: "Marcus Oyelaran", role: "admin", job_title: "RevOps lead", department: "Revenue" },
      { id: "usr_priya", email: "priya@northwind.example", full_name: "Priya Raman", role: "member", job_title: "Account executive", department: "Sales" },
      { id: "usr_lena", email: "lena@northwind.example", full_name: "Lena Sato", role: "member", job_title: "Support manager", department: "Support" },
    ],
  },
  "/api/settings/agents-fleet": {
    prefs: null,
  },
  // Shapes match AuditListResponse / AuditSummary in types/api.ts.
  "/api/audit/summary": {
    byAction: { approve: 2, reject: 1, execute: 1, update: 1, invite: 1 },
    byUser: [
      { user_id: "usr_dana", user_name: "Dana Whitfield", count: 3 },
      { user_id: "usr_marcus", user_name: "Marcus Oyelaran", count: 2 },
    ],
    byEntityType: { approval: 3, workflow: 1, settings: 1, user: 1 },
  },
  "/api/audit": {
    total: 6,
    hasMore: false,
    logs: [
      { id: "aud_1", action: "approve", entity_type: "approval", entity_id: "apr_renewal", entity_name: "Acme renewal discount", user_id: "usr_dana", user_name: "Dana Whitfield", created_at: AGO(12), details: { description: "Approved a 12% renewal discount for Acme before it was written to HubSpot.", outcome: "approved", destination: "HubSpot" } },
      { id: "aud_2", action: "execute", entity_type: "workflow", entity_id: "wf_invoice", entity_name: "Overdue invoice follow-up", agent_id: "agt_collections", agent_name: "Collections agent", created_at: AGO(38), details: { description: "Sent 4 reminder emails for invoices over 30 days.", outcome: "completed" } },
      { id: "aud_3", action: "reject", entity_type: "approval", entity_id: "apr_bulk", entity_name: "Bulk contact deletion", user_id: "usr_marcus", user_name: "Marcus Oyelaran", created_at: AGO(95), details: { description: "Rejected deleting 212 contacts; the list included active customers.", outcome: "rejected" } },
      { id: "aud_4", action: "update", entity_type: "settings", entity_id: "set_sso", entity_name: "SSO enforcement", user_id: "usr_dana", user_name: "Dana Whitfield", created_at: AGO(240), details: { description: "Required SSO for all members.", outcome: "applied" } },
      { id: "aud_5", action: "approve", entity_type: "approval", entity_id: "apr_ticket", entity_name: "Escalate priority ticket", user_id: "usr_marcus", user_name: "Marcus Oyelaran", created_at: AGO(410), details: { description: "Approved escalating ticket #4821 to the on-call manager.", outcome: "approved" } },
      { id: "aud_6", action: "invite", entity_type: "user", entity_id: "usr_lena", entity_name: "Lena Sato", user_id: "usr_dana", user_name: "Dana Whitfield", created_at: AGO(1440), details: { description: "Invited Lena Sato as a member.", outcome: "sent" } },
    ],
  },

  // Requested as /api/workflows?org_id=… — the query string is ignored by the
  // pathname matcher, but the page still gates the request on an org being
  // resolved from /api/organizations above.
  "/api/goals": {
    goals: [
      {
        id: "goal_pipeline",
        objective: "Recover $1.2M of stalled Q3 pipeline",
        category: "revenue",
        priority: "high",
        department: "Sales",
        status: "active",
        connectedSystems: ["HubSpot", "Salesforce", "Slack"],
        successMetrics: { primary: "Stalled deals re-engaged within 14 days" },
        createdAt: T(60 * 24 * 6),
      },
      {
        id: "goal_churn",
        objective: "Cut first-90-day churn below 4%",
        category: "retention",
        priority: "high",
        department: "Customer Success",
        status: "active",
        connectedSystems: ["Zendesk", "Stripe"],
        successMetrics: { primary: "90-day logo churn" },
        createdAt: T(60 * 24 * 12),
      },
      {
        id: "goal_close",
        objective: "Close the books two days faster each month",
        category: "finance",
        priority: "medium",
        department: "Finance",
        status: "paused",
        connectedSystems: ["QuickBooks"],
        createdAt: T(60 * 24 * 20),
      },
      {
        id: "goal_onboard",
        objective: "Automate new-hire IT provisioning",
        category: "operations",
        priority: "low",
        department: "IT",
        status: "draft",
        createdAt: T(60 * 24 * 2),
      },
    ],
  },
  "/api/goals/goal_pipeline/progress": {
    goal: {
      id: "goal_pipeline",
      objective: "Recover $1.2M of stalled Q3 pipeline",
      status: "active",
      category: "revenue",
      department: "Sales",
    },
    completionPercentage: 58,
    milestoneStatus: [
      { id: "m1", title: "Identify deals with no activity in 21+ days", status: "completed" },
      { id: "m2", title: "Draft re-engagement sequences per deal stage", status: "completed" },
      { id: "m3", title: "Route high-value deals to account owners for approval", status: "in_progress" },
      { id: "m4", title: "Send approved outreach and log replies to Salesforce", status: "pending" },
      { id: "m5", title: "Measure recovered pipeline against the $1.2M target", status: "pending" },
    ],
  },
  "/api/plays": {
    count: 3,
    plays: [
      {
        play: {
          key: "pipeline_recovery",
          name: "Stalled pipeline recovery",
          objective: "Find deals that have gone quiet, draft the right follow-up, and route it to the owner for approval.",
          version: "1.3.0",
        },
        readiness: {
          dependency_status: "ready",
          observe_ready: true,
          recommend_ready: true,
          act_with_approval_ready: true,
          act_within_policy_ready: false,
          blockers: [],
          connector_groups: [{ ready: true }, { ready: true }],
        },
        workflowBindingCount: 3,
      },
      {
        play: {
          key: "churn_early_warning",
          name: "Churn early warning",
          objective: "Watch support and billing signals for at-risk accounts and recommend a save plan.",
          version: "0.9.2",
        },
        readiness: {
          observe_ready: true,
          recommend_ready: true,
          act_with_approval_ready: false,
          blockers: [],
          connector_groups: [{ ready: true }, { ready: true }, { ready: false }],
        },
        workflowBindingCount: 1,
      },
      {
        play: {
          key: "invoice_collections",
          name: "Invoice collections",
          objective: "Chase overdue invoices with polite, escalating reminders and flag disputes for a person.",
          version: "1.0.0",
        },
        readiness: {
          observe_ready: false,
          blockers: ["Connect an accounting connector such as QuickBooks or Xero"],
          connector_groups: [{ ready: false }],
        },
        workflowBindingCount: 0,
      },
    ],
  },
  "/api/plays/pipeline_recovery/readiness": {
    play: {
      key: "pipeline_recovery",
      name: "Stalled pipeline recovery",
      objective: "Find deals that have gone quiet, draft the right follow-up, and route it to the owner for approval.",
      version: "1.3.0",
    },
    readiness: {
      observe_ready: true,
      recommend_ready: true,
      act_with_approval_ready: true,
      act_within_policy_ready: false,
      blockers: [],
      connector_groups: [{ ready: true }, { ready: true }],
    },
    workflowBindings: [],
    workflowBindingCount: 3,
  },
  "/api/plays/pipeline_recovery/installation": {
    installation: {
      id: "inst_pipeline",
      goalId: "goal_pipeline",
      operatingMode: "ACT WITH APPROVAL",
      status: "ready",
    },
  },
  "/api/plays/pipeline_recovery/outcomes": {
    truthRule: "Verified success requires source-of-record evidence.",
    outcomes: [
      {
        id: "out_recovered",
        measurement_status: "measured",
        created_at: T(60 * 26),
        metadata: {
          verification_state: "VERIFIED SUCCESS",
          metric_key: "pipeline_recovered",
          delta_value: 184000,
          currency: "USD",
          verified: true,
        },
      },
      {
        id: "out_reply_rate",
        measurement_status: "pending",
        created_at: T(60 * 4),
        metadata: { verification_state: "INCONCLUSIVE", metric_key: "reply_rate" },
      },
    ],
  },
  "/api/plays/pipeline_recovery/outcomes/out_recovered/evidence": {
    playKey: "pipeline_recovery",
    evidence: {
      metric: {
        key: "pipeline_recovered",
        baseline: 0,
        result: 184000,
        delta: 184000,
        currency: "USD",
        measuredAt: T(60 * 26),
      },
      play: { key: "pipeline_recovery", runId: "prn_7f21c9", installationId: "inst_pipeline" },
      workflow: { id: "wf_reengage", runId: "run_reengage_1182" },
      governance: { approvalStatus: "approved", requiredApprovals: 1 },
      sourceRecords: [
        { system: "salesforce", record_type: "Opportunity", record_id: "0068c00001AbCdE" },
        { system: "salesforce", record_type: "Opportunity", record_id: "0068c00001FgHiJ" },
      ],
      verification: { state: "Verified success", method: "Source-of-record diff", verified: true, confidence: 0.94 },
    },
  },
  "/api/workflows": { workflows },
  "/api/ml/models": {
    models: [
      { id: "mdl_churn", name: "Churn risk scorer", description: "Flags accounts likely to churn in the next 60 days.", model_type: "classifier", status: "deployed", current_version: 3, deployed_version: 3, base_model: "gradient-boosted-trees", dataset_id: "ds_churn", created_at: "2026-03-02T15:00:00Z", updated_at: "2026-05-08T09:30:00Z" },
      { id: "mdl_lead_score", name: "Lead fit score", description: "Ranks inbound leads by fit with closed-won accounts.", model_type: "regressor", status: "deployed", current_version: 2, deployed_version: 1, created_at: "2026-04-11T12:00:00Z", updated_at: "2026-05-09T18:10:00Z" },
      { id: "mdl_ticket_route", name: "Ticket router", description: null, model_type: "classifier", status: "draft", current_version: 0, dataset_id: "ds_tickets", created_at: "2026-05-07T10:00:00Z" },
    ],
  },
  "/api/ml/models/mdl_churn": {
    id: "mdl_churn",
    name: "Churn risk scorer",
    description: "Flags accounts likely to churn in the next 60 days.",
    model_type: "classifier",
    task_type: "binary_classification",
    status: "deployed",
    current_version: 3,
    deployed_version: 3,
    base_model: "gradient-boosted-trees",
    created_at: "2026-03-02T15:00:00Z",
    updated_at: "2026-05-08T09:30:00Z",
    versions: [
      { version: 3, metrics: { accuracy: 0.91, f1: 0.87, auc: 0.94 }, artifact_size_bytes: 4820000, created_at: "2026-05-08T09:30:00Z" },
      { version: 2, metrics: { accuracy: 0.88, f1: 0.83, auc: 0.91 }, artifact_size_bytes: 4610000, created_at: "2026-04-15T14:00:00Z" },
      { version: 1, metrics: { accuracy: 0.84, f1: 0.79 }, artifact_size_bytes: 4100000, created_at: "2026-03-02T15:00:00Z" },
    ],
  },
  // Built-in catalog: SLA breach predictor runs on rules but has enough examples, so Models shows it as a suggestion.
  "/api/intelligence/models/catalog": {
    catalog: {
      sla_breach_predictor: { status: "HEURISTIC", use_cases: ["ticket_sla", "support_queue"] },
      revenue_forecaster: { status: "TRAINED", use_cases: ["pipeline_forecast"] },
      graph_neural_network: { status: "PLANNED", use_cases: [] },
    },
    orgTrainingStatus: {
      sla_breach_predictor: { runtime_status: "HEURISTIC" },
      revenue_forecaster: { runtime_status: "TRAINED" },
    },
    outcomeScores: { revenue_forecaster: 0.82 },
  },
  "/api/intelligence/training-readiness": {
    by_model: {
      sla_breach_predictor: { signals_available: 640, min_required: 500 },
      revenue_forecaster: { signals_available: 1200, min_required: 300, last_trained_at: "2026-05-02T08:00:00Z" },
    },
  },
  // Lead fit score's accuracy slipped between versions, so its card shows the needs-attention state.
  "/api/ml/models/mdl_lead_score": {
    id: "mdl_lead_score",
    name: "Lead fit score",
    description: "Ranks inbound leads by fit with closed-won accounts.",
    model_type: "regressor",
    status: "deployed",
    current_version: 2,
    deployed_version: 2,
    created_at: "2026-04-11T12:00:00Z",
    updated_at: "2026-05-09T18:10:00Z",
    versions: [
      { version: 2, metrics: { accuracy: 0.74 }, created_at: "2026-03-12T10:00:00Z" },
      { version: 1, metrics: { accuracy: 0.8 }, created_at: "2026-02-01T10:00:00Z" },
    ],
  },
  // Shape must match ScheduledItem in types/api.ts; one item per schedule phase.
  "/api/schedules": {
    items: [
      { kind: "workflow", id: "sch_lead_triage", title: "Inbound lead triage", subtitle: "Every 15 minutes", status: "running", cron: "*/15 * * * *", timezone: "America/Chicago", scheduleType: "recurring", workflowId: "wf_lead_triage", startedAt: T(2), lastRunAt: T(17), nextRunAt: T(-13), progress: 60 },
      { kind: "workflow", id: "sch_deal_desk", title: "Deal desk sync", subtitle: "Weekdays at 08:00", status: "enabled", cron: "0 8 * * 1-5", timezone: "America/New_York", scheduleType: "recurring", workflowId: "wf_deal_desk", lastRunAt: T(38), nextRunAt: T(-960) },
      { kind: "workflow", id: "sch_support_routing", title: "Support escalation routing", subtitle: "Hourly", status: "failed", cron: "0 * * * *", timezone: "UTC", scheduleType: "recurring", workflowId: "wf_support_routing", lastRunAt: T(44), nextRunAt: T(-16) },
      { kind: "workflow", id: "sch_invoice_recon", title: "Invoice reconciliation", subtitle: "Paused by operator", status: "disabled", cron: "30 6 * * *", timezone: "Europe/London", scheduleType: "recurring", workflowId: "wf_invoice_recon", lastRunAt: T(2880) },
      { kind: "workflow", id: "sch_churn_digest", title: "Churn risk digest", subtitle: "Once", status: "scheduled", timezone: "America/Chicago", scheduleType: "once", workflowId: "wf_churn_digest", runAt: T(-2880), nextRunAt: T(-2880) },
    ],
  },
  "/api/runs/run_support_4821": {
    run: {
      id: "run_support_4821",
      workflow_id: "wf_support_routing",
      workflow_name: "Support escalation routing",
      status: "failed",
      environment: "production",
      triggered_by: "Schedule · hourly",
      created_by: "dana.whitfield@northwind.example",
      started_at: T(44),
      completed_at: T(41),
      duration_ms: 192000,
      records_processed: 37,
      error: "Zendesk returned 429 Too Many Requests while assigning ticket #88213.",
    },
    steps: [
      { id: "stp_1", name: "Fetch open escalations", stepType: "source", status: "completed", orderIndex: 0, startedAt: T(44), completedAt: T(44), outputSnapshot: { tickets: 37 } },
      { id: "stp_2", name: "Classify severity", stepType: "agent", status: "completed", orderIndex: 1, startedAt: T(44), completedAt: T(43), outputSnapshot: { p1: 3, p2: 11, p3: 23 } },
      { id: "stp_3", name: "Approve P1 reassignment", stepType: "approval", status: "completed", orderIndex: 2, startedAt: T(43), completedAt: T(42), outputSnapshot: { decision: "approved", approver: "Dana Whitfield" } },
      { id: "stp_4", name: "Assign tickets in Zendesk", stepType: "connector", status: "failed", orderIndex: 3, startedAt: T(42), completedAt: T(41), errorMessage: "429 Too Many Requests — rate limit resets in 60s.", isRetryable: true, outputSnapshot: { assigned: 29, remaining: 8 } },
      { id: "stp_5", name: "Notify on-call channel", stepType: "task", status: "skipped", orderIndex: 4 },
    ],
  },
  // Capture-only agent jobs (AgentJob shape) spanning every execution phase.
  "/api/assignments": {
    jobs: [
      {
        jobId: "job_shot_enrich",
        kind: "agent_task",
        status: "running",
        sessionId: null,
        attempts: 1,
        error: null,
        createdAt: AGO(12),
        finishedAt: null,
        result: {
          agent_name: "Inbound lead triage",
          action_title: "Enrich this week's inbound leads and route them to owners",
          task: { description: "Enrich this week's inbound leads with firmographics and route each to the right owner in HubSpot." },
          tool_call_count: 7,
        },
      },
      {
        jobId: "job_shot_renewal",
        kind: "agent_task",
        status: "completed",
        sessionId: null,
        attempts: 1,
        error: null,
        createdAt: AGO(48),
        finishedAt: AGO(31),
        result: {
          agent_name: "Deal desk sync",
          action_title: "Send renewal reminders for Q4 contracts",
          task: { description: "Draft and send renewal reminders for contracts expiring in Q4." },
          requires_approval: true,
          human_input_prompt: "Send 12 renewal emails from the account owner's mailbox?",
          tool_call_count: 4,
        },
      },
      {
        jobId: "job_shot_digest",
        kind: "agent_task",
        status: "completed",
        sessionId: null,
        attempts: 1,
        error: null,
        createdAt: AGO(180),
        finishedAt: AGO(170),
        result: {
          agent_name: "Churn risk digest",
          task: { description: "{\"objective\":\"Summarize churn signals from Zendesk escalations\",\"window\":\"7d\"}" },
          tool_call_count: 3,
          rag_sources: [{}, {}, {}, {}],
          execution_verified: true,
          summary: "Six accounts show rising escalation volume this week; two are within 60 days of renewal.",
        },
      },
      {
        jobId: "job_shot_invoice",
        kind: "agent_task",
        status: "failed",
        sessionId: null,
        attempts: 2,
        error: "Salesforce connector token expired — reconnect to continue.",
        createdAt: AGO(95),
        finishedAt: AGO(90),
        result: {
          agent_name: "Invoice reconciliation",
          action_title: "Reconcile October invoices against Salesforce opportunities",
          task: { description: "Reconcile October invoices against closed-won Salesforce opportunities." },
        },
      },
      {
        jobId: "job_shot_queue",
        kind: "agent_task",
        status: "queued",
        sessionId: null,
        attempts: 0,
        error: null,
        createdAt: AGO(2),
        finishedAt: null,
        result: {
          agent_name: "Support escalation routing",
          action_title: "Triage overnight Zendesk escalations",
          task: { description: "Triage overnight Zendesk escalations and page the on-call owner for P1s." },
        },
      },
    ],
  },
  // Capture-only assignment detail: a delivered job whose search step hit a plan limit.
  "/api/agent-jobs/job_shot_blocked": {
    jobId: "job_shot_blocked",
    kind: "agent_task",
    status: "completed",
    sessionId: null,
    attempts: 1,
    error: null,
    createdAt: AGO(300),
    finishedAt: AGO(290),
    result: {
      agent_name: "Inbound lead triage",
      action_title: "Add Northwind's new logistics prospects to the Q4 target list",
      task: { description: "Find logistics companies that match the Q4 ICP and add them to the Q4 target list." },
      summary: "Company search needs a data provider plan with search API access. See app.apollo.io to upgrade.",
      confidence: 0.35,
      tool_call_count: 5,
      tools_available: 24,
      tool_calls: [
        { tool: "apollo.lists.list", result: { success: false, error: "Plan does not include API access" } },
        { tool: "apollo.organizations.search", result: { success: false, error: "Plan does not include search API access" } },
        { tool: "apollo.lists.list", result: { success: true } },
        { tool: "apollo.organizations.search", result: { success: true } },
        { tool: "apollo.organizations.search", result: { success: false, error: "Plan does not include search API access" } },
      ],
    },
  },
  // FIXTURE: execution-outcome ledger rollup (shape of GET ops-summary). Counts only.
  "/api/workflows/execution-outcomes/ops-summary": {
    window_hours: 24,
    totals: { pass: 58, fail: 6, cancel: 3, other: 0 },
    pass_rate: 0.866,
    by_source: [
      { source: "workflow", pass: 41, fail: 4, cancel: 2, pass_rate: 0.872 },
      { source: "chat", pass: 17, fail: 2, cancel: 1, pass_rate: 0.85 },
    ],
    by_connector: [
      { connector: "hubspot", pass: 31, fail: 2, cancel: 1, pass_rate: 0.912 },
      { connector: "salesforce", pass: 12, fail: 3, cancel: 0, pass_rate: 0.8 },
      { connector: "zendesk", pass: 9, fail: 0, cancel: 2, pass_rate: 0.818 },
      { connector: "slack", pass: 6, fail: 1, cancel: 0, pass_rate: 0.857 },
    ],
    event_count: 67,
  },
  "/api/workflows/stats": {
    overallSuccessRate: 96.8,
    totalRunsThisWeek: 2755,
  },

  // Activity → Failures tab. Spans all four severities so the collapsible
  // severity groups and the severity filter chips have something to group and
  // filter; an un-fixtured path returns {} and renders the empty state, which
  // would verify nothing.
  "/api/workflows/failure-predictions": {
    count: 5,
    alerts: [
      {
        id: "fpa_01",
        workflowId: "wf_lead_intake",
        stepId: "step_hubspot_upsert",
        connectorId: "con_hubspot",
        alertType: "connector_token_expiring",
        severity: "critical",
        title: "HubSpot token expires in 26 hours",
        message:
          "The HubSpot connector's refresh token expires before the next scheduled run of Lead intake → HubSpot. Re-authorize to avoid a failed write.",
        confidence: 0.94,
        status: "open",
        predictedAt: AGO(42),
      },
      {
        id: "fpa_02",
        workflowId: "wf_lead_intake",
        stepId: "step_apollo_enrich",
        connectorId: "con_apollo",
        alertType: "rate_limit_projection",
        severity: "high",
        title: "Apollo enrichment projected to hit rate limit",
        message:
          "Recent runs used 82% of the hourly Apollo quota. The next batch of 400 contacts is projected to exceed it mid-run.",
        confidence: 0.78,
        status: "open",
        predictedAt: AGO(96),
      },
      {
        id: "fpa_03",
        workflowId: "wf_weekly_digest",
        stepId: "step_send_summary",
        connectorId: "con_slack",
        alertType: "recent_failure_pattern",
        severity: "high",
        title: "Slack delivery failed twice this week",
        message:
          "Two of the last five Weekly digest runs failed posting to #revenue-ops. The channel may have been archived or the app removed.",
        confidence: 0.71,
        status: "open",
        predictedAt: AGO(180),
      },
      {
        id: "fpa_04",
        workflowId: "wf_invoice_sync",
        stepId: "step_quickbooks_match",
        connectorId: "con_quickbooks",
        alertType: "schema_drift",
        severity: "medium",
        title: "QuickBooks custom field renamed",
        message:
          "The field this step maps to (po_number) no longer appears in the connector schema. Runs will complete but leave the value empty.",
        confidence: 0.62,
        status: "open",
        predictedAt: AGO(420),
      },
      {
        id: "fpa_05",
        workflowId: "wf_weekly_digest",
        stepId: null,
        connectorId: null,
        alertType: "long_running_trend",
        severity: "low",
        title: "Runtime trending up 18% week over week",
        message:
          "Weekly digest is taking longer each run. Not failing yet, but worth reviewing before the dataset grows further.",
        confidence: 0.44,
        status: "open",
        predictedAt: AGO(600),
      },
    ],
  },

  // Drives the chat landing surface: buildOrgSearchChips() turns these counts
  // and names into the suggestion chips, so an empty payload here yields the
  // generic fallback chips instead of org-specific ones.
  "/api/assistant/org-context": {
    counts: { agents: agents.length, workflows: workflows.length, connectors: 4 },
    agents: agents.map((agent) => ({ id: agent.id, name: agent.name })),
    workflows: workflows.map((workflow) => ({ id: workflow.id, name: workflow.name })),
    connectors: [
      { id: "con_hubspot", name: "HubSpot", type: "hubspot" },
      { id: "con_salesforce", name: "Salesforce", type: "salesforce" },
      { id: "con_zendesk", name: "Zendesk", type: "zendesk" },
      { id: "con_slack", name: "Slack", type: "slack" },
    ],
  },
  // Drives the Gravitre AI history sidebar. `updated_at` uses AGO() because the
  // sidebar renders a relative distance from now.
  "/api/conversations": {
    conversations: [
      {
        id: "cv_lead_triage",
        title: "Why did the Salesforce write get blocked?",
        preview:
          "The connected user lacks edit access on Opportunity objects, so the run stopped before writing.",
        created_at: AGO(64),
        updated_at: AGO(12),
        message_count: 6,
      },
      {
        id: "cv_qbr",
        title: "Draft the Q1 review for Northwind",
        preview: "Pulled 7 closed-won deals and 3 open tickets, then drafted a five-section review.",
        created_at: AGO(180),
        updated_at: AGO(52),
        message_count: 9,
      },
      {
        id: "cv_connector_audit",
        title: "Which workflows write to HubSpot?",
        preview: "Four workflows hold hubspot write scope. Two of them stage an approval first.",
        created_at: AGO(1500),
        updated_at: AGO(1440),
        message_count: 4,
      },
    ],
  },
  "/api/conversations/cv_lead_triage/messages": {
    has_more: false,
    messages: [
      {
        id: "m1",
        conversation_id: "cv_lead_triage",
        role: "user",
        content: "Why did the Salesforce write in Lead Triage get blocked this morning?",
        created_at: AGO(64),
      },
      {
        id: "m2",
        conversation_id: "cv_lead_triage",
        role: "assistant",
        content:
          "The 08:12 run of **Lead Triage** stopped at step 4, *Update Opportunity*, before writing anything.\n\n- **Cause:** the connected Salesforce user `ops-integration@northwind.com` has read-only access on Opportunity.\n- **Impact:** 14 leads were scored but not routed. No records were changed.\n- **Since:** the permission set was edited yesterday at 17:40.\n\nI can draft a request to restore edit access, or re-run the 14 leads once access is back.",
        created_at: AGO(63),
      },
      {
        id: "m3",
        conversation_id: "cv_lead_triage",
        role: "user",
        content: "Draft the access request and queue the re-run for after it is approved.",
        created_at: AGO(20),
      },
      {
        id: "m4",
        conversation_id: "cv_lead_triage",
        role: "assistant",
        content:
          "Done. Two things are waiting on you:\n\n1. **Access request** to the Salesforce admin, restoring *Edit* on Opportunity for the integration user.\n2. **Re-run of 14 leads** in Lead Triage, held until the request is approved.\n\nNothing will write to Salesforce until you approve both.",
        created_at: AGO(12),
      },
    ],
  },
  "/api/assistant/business-signals": { signals: [], collected_at: AGO(5) },
  "/api/assistant/advisor-brief": {},

  "/api/search/history": {
    searches: [
      {
        id: "sh_01",
        query: "failed runs in production today",
        results_count: 3,
        created_at: T(18),
      },
      {
        id: "sh_02",
        query: "which workflows write to Salesforce",
        results_count: 2,
        created_at: T(64),
      },
      {
        id: "sh_03",
        query: "approvals waiting on me",
        results_count: 3,
        created_at: T(140),
      },
    ],
  },

  // Learning → Relationships graph workspace (/e2e/shots/relationships).
  // Fictional Northwind entities only — visual capture harness, not live tenant data.
  "/api/admin/intelligence/snapshot": {
    queryVolume: { totalLogged: 42, distinctNormalized: 38, failedSearchCount: 2 },
    recentFailedSearches: [],
    clusters: [],
    glossary: [
      { id: "term_northwind", term: "Northwind Logistics" },
      { id: "term_revops", term: "RevOps playbook" },
    ],
    knowledgeGaps: [],
    entityRelationships: [],
  },
  "/api/admin/intelligence/relationships": {
    orgId: DEMO_ORG_ID,
    relationships: [
      {
        id: "rel_fixture_01",
        source_entity_type: "glossary_term",
        source_entity_id: "term_northwind",
        source_label: "Northwind Logistics",
        relationship_type: "associated_with",
        target_entity_type: "department",
        target_entity_id: "dept_ops",
        target_label: "Operations",
        confidence: 0.82,
        evidence_count: 4,
        last_observed_at: T(120),
        created_at: T(2000),
      },
      {
        id: "rel_fixture_02",
        source_entity_type: "glossary_term",
        source_entity_id: "term_revops",
        source_label: "RevOps playbook",
        relationship_type: "used_by",
        target_entity_type: "agent",
        target_entity_id: "agent_lead_triage",
        target_label: "Lead triage agent",
        confidence: 0.71,
        evidence_count: 3,
        last_observed_at: T(240),
        created_at: T(1500),
      },
      {
        id: "rel_fixture_03",
        source_entity_type: "agent",
        source_entity_id: "agent_lead_triage",
        source_label: "Lead triage agent",
        relationship_type: "integrates_with",
        target_entity_type: "glossary_term",
        target_entity_id: "term_northwind",
        target_label: "Northwind Logistics",
        confidence: 0.88,
        evidence_count: 6,
        last_observed_at: T(60),
        created_at: T(800),
      },
    ],
  },
  "/api/admin/intelligence/knowledge-nodes/match": {
    orgId: DEMO_ORG_ID,
    query: "Northwind",
    matches: [
      {
        id: "kn_fixture_01",
        name: "Northwind Logistics",
        nodeType: "company",
        entityType: "company",
        matchScore: 80,
        source: "confirmed_knowledge",
      },
    ],
  },
  "/api/admin/intelligence/knowledge-nodes": {
    orgId: DEMO_ORG_ID,
    nodes: [
      {
        id: "kn_fixture_01",
        node_type: "company",
        name: "Northwind Logistics",
        created_at: T(5000),
      },
      {
        id: "kn_fixture_02",
        node_type: "employee",
        name: "Dana Whitfield",
        created_at: T(4800),
      },
    ],
    validNodeTypes: ["company", "employee", "customer", "vendor", "product"],
    primaryNodeTypes: ["company", "employee", "customer", "vendor", "product"],
  },
  "/api/admin/intelligence/knowledge-graph": {
    entity_count: 6,
    relationship_count: 3,
    max_traversal_hops: 3,
    avg_relationship_confidence: 0.8033,
    entity_types: ["agent", "department", "glossary_term"],
    relationship_types: ["associated_with", "integrates_with", "used_by"],
    scope_note: "Fixture scope for visual capture only.",
    advisory_only: true,
  },
  "/api/admin/intelligence/knowledge-graph/traverse": {
    startEntityType: "glossary_term",
    startEntityId: "term_northwind",
    maxHopsRequested: 2,
    maxHopsCap: 3,
    paths: [
      {
        entityType: "agent",
        entityId: "agent_lead_triage",
        hopDepth: 1,
        confidence: 0.71,
        relationshipType: "used_by",
        pathSummary: "glossary_term:term_northwind -[integrates_with]-> glossary_term:term_northwind",
      },
    ],
    scope_note: "Fixture scope for visual capture only.",
  },

  // Intelligence field (/e2e/shots/intelligence-field). Same fictional entities and
  // relationships as the fixtures above — no additional graph content.
  "/api/intelligence/page-context": {
    snapshot: {
      generatedAt: T(5),
      tenantId: DEMO_ORG_ID,
      timeWindowHours: 24,
      coreState: "active",
      agents: [
        {
          id: "agent_lead_triage",
          name: "Lead triage agent",
          department: "Operations",
          businessLabel: "Lead triage agent",
          configuredStatus: "active",
          executionStatus: "idle",
          isConfiguredActive: true,
          isCurrentlyRunning: false,
        },
      ],
      predictions: [],
      learnings: [],
      knowledgeEntityTypes: ["agent", "department", "glossary_term"],
      metrics: {
        knowledge: { knownEntities: 4, knownRelationships: 3 },
        learning: {},
        predictions: {},
        execution: {},
        outcomes: {},
      },
      qualityFlags: [],
      departments: [],
    },
    graph: {
      nodes: [
        { id: "core:gravitre", type: "core", businessLabel: "Gravitre" },
        { id: "dept:dept_ops", type: "domain", businessLabel: "Operations", status: "active" },
        { id: "agent:agent_lead_triage", type: "agent", businessLabel: "Lead triage agent", status: "active", metadata: { isConfiguredActive: true } },
        { id: "entity:term_northwind", type: "entity", businessLabel: "Northwind Logistics", metadata: { instance: true, entityType: "glossary_term" } },
        { id: "entity:term_revops", type: "entity", businessLabel: "RevOps playbook", metadata: { instance: true, entityType: "glossary_term" } },
      ],
      edges: [
        { id: "rel_fixture_01", type: "RELATED_TO", fromId: "entity:term_northwind", toId: "dept:dept_ops" },
        { id: "rel_fixture_02", type: "USED_BY", fromId: "entity:term_revops", toId: "agent:agent_lead_triage" },
        { id: "rel_fixture_03", type: "READ_FROM", fromId: "agent:agent_lead_triage", toId: "entity:term_northwind" },
      ],
    },
    activeLens: "knows",
    availableLenses: ["knows", "learns", "predicts", "acts", "improves"],
    metrics: {
      knowledge: { knownEntities: 4, knownRelationships: 3 },
      learning: {},
      predictions: {},
      execution: {},
      outcomes: {},
    },
    qualityFlags: [],
    suggestedQuestions: [],
  },

  // FIXTURE: agent ROI (shape of GET /api/enterprise/agent-roi). Impact and Reports.
  "/api/enterprise/agent-roi": (() => {
    const m = (value: number | null, provenance: string, unit: string | null = null) => ({ label: "", value, unit, provenance })
    const row = (agentId: string, agentName: string, tasks: number, cost: number, hours: number) => ({
      agentId,
      agentName,
      tasksCompleted: m(tasks, "operational"),
      actionsExecuted: m(tasks * 3, "operational"),
      agentCostUsd: m(cost, "measured", "usd"),
      modelCallCount: tasks * 6,
      estimatedHoursSaved: m(hours, "estimate", "hours"),
      estimatedLaborValueUsd: m(hours * 55, "estimate", "usd"),
      revenueInfluencedUsd: m(null, "not_configured", "usd"),
      roiMultiple: m(null, "insufficient_data"),
    })
    return {
      orgId: DEMO_ORG_ID,
      periodDays: 30,
      periodStart: T(43200),
      periodEnd: T(0),
      methodology: "Measured model cost and task counts; time saved is estimated from task type.",
      laborUsdPerHour: { value: 55, source: "org_settings", provenance: "org_settings" },
      orgTotals: {
        tasksCompleted: m(41, "operational"),
        actionsExecuted: m(123, "operational"),
        agentCostUsd: m(18.42, "measured", "usd"),
        estimatedHoursSaved: m(23.5, "estimate", "hours"),
        estimatedLaborValueUsd: m(1292.5, "estimate", "usd"),
        revenueInfluencedUsd: m(null, "not_configured", "usd"),
        roiMultiple: m(null, "insufficient_data"),
      },
      agents: [
        row("agt_lead_triage", agents[0].name, 29, 11.9, 16),
        row("agt_deal_desk", agents[1].name, 12, 5.8, 7.5),
        row("unassigned", "Unassigned", 0, 0.72, 0),
      ],
      honesty: {
        measuredFields: ["agentCostUsd"],
        operationalFields: ["tasksCompleted", "actionsExecuted"],
        estimateFields: ["estimatedHoursSaved", "estimatedLaborValueUsd"],
        notConfiguredUnlessEvidence: ["revenueInfluencedUsd", "roiMultiple"],
        moduleC: true,
        sta286: true,
      },
    }
  })(),
  // FIXTURE: memory promotion candidates (shape of GET /api/admin/memory-promotion/candidates).
  // The harness matches on path only, so every status filter gets this list.
  "/api/admin/memory-promotion/candidates": {
    items: [
      {
        id: "mpc_cold_chain",
        candidate_type: "pattern",
        content: "Refrigerated freight only ships from the Reno and Tacoma depots.",
        memory_category: "operations",
        status: "pending_approval",
        source_table: "agent_memories",
        frequency: 4,
        department_count: 2,
        metadata: { confidence: 0.86, term: "Depot" },
        updated_at: T(90),
        thresholdComparison: { frequency: 4, departmentCount: 2, autoPromoteMinOccurrences: 20, autoPromoteMinDepartments: 2, meetsAutoThreshold: false, canAutoPromote: false },
      },
      {
        id: "mpc_support_churn",
        candidate_type: "pattern",
        content: "Accounts whose ticket volume rises for three weeks renew less often.",
        memory_category: "customer_success",
        status: "pending_approval",
        source_table: "agent_memories",
        frequency: 3,
        department_count: 1,
        metadata: {},
        updated_at: T(240),
        thresholdComparison: { frequency: 3, departmentCount: 1, autoPromoteMinOccurrences: 20, autoPromoteMinDepartments: 2, meetsAutoThreshold: false, canAutoPromote: false },
      },
    ],
    total: 2,
    limit: 200,
    offset: 0,
  },
  // FIXTURE: training datasets (shape of GET /api/training/datasets).
  "/api/training/datasets": {
    datasets: [
      { id: "ds_churn", name: "churn-training", description: "Renewals and support history", type: "examples", status: "ready", record_count: 1840, created_by: supabaseUser.id, created_at: T(43000), updated_at: T(2000) },
      { id: "ds_tickets", name: "ticket-routing", description: "Labelled support tickets", type: "examples", status: "ready", record_count: 620, created_by: supabaseUser.id, created_at: T(30000), updated_at: T(9000) },
    ],
  },
  // FIXTURE: Agents > Instructions (shape of GET /api/training/instructions).
  "/api/training/instructions": {
    instructions: [
      { id: "ins_email", agent_id: null, name: "Confirm before emailing customers", content: "Agents may draft customer emails but never send one until a person approves it.", is_active: true, kind: "guardrail", department: null, created_at: T(9000), updated_at: T(120) },
      { id: "ins_floor", agent_id: null, name: "Protect pricing floors", content: "Never quote below the approved floor or promise a discount without sign off.", is_active: true, kind: "guardrail", department: "sales", created_at: T(8000), updated_at: T(600) },
      { id: "ins_cite", agent_id: null, name: "Cite your sources", content: "Every recommendation lists the records, reports or pages it relied on.", is_active: true, kind: "guidance", department: null, created_at: T(7000), updated_at: T(1400) },
      { id: "ins_tone", agent_id: null, name: "Escalation tone", content: "When a customer is upset, acknowledge the problem first, then offer one clear next step.", is_active: false, kind: "guidance", department: "customer_success", created_at: T(6000), updated_at: T(3000) },
    ],
  },
  ...MARKETPLACE_SHOT_FIXTURES,
}
