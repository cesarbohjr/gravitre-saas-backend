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
 * Shape must match normalizeAgent() in app/agents/page.tsx.
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
  },
  {
    id: "agt_deal_desk",
    name: "Deal Desk Sync",
    role: "Pipeline hygiene",
    department: "Sales",
    description:
      "Reconciles opportunity stages against meeting notes and support threads, then proposes stage changes.",
    status: "processing",
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
  },
  {
    id: "agt_support_escalation",
    name: "Support Escalation",
    role: "Customer support",
    department: "Support",
    description:
      "Triages inbound tickets, attaches account context, and escalates anything touching a paying account.",
    status: "active",
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
  },
  {
    id: "agt_invoice_recon",
    name: "Invoice Reconciliation",
    role: "Finance operations",
    department: "Finance",
    description:
      "Matches paid invoices against closed-won deals and flags the ones that disagree.",
    status: "idle",
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
  },
]

/**
 * Shape must match normalizeWorkflow() in app/workflows/page.tsx.
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
export const SHOT_FIXTURES: Record<string, unknown> = {
  __supabaseUser: supabaseUser,
  __orgId: DEMO_ORG_ID,

  // Shape must match the `Connector` interface in app/connectors/page.tsx.
  // Requested as /api/connectors?org=…&live=1; the harness matches on pathname
  // only, so the query string is irrelevant here.
  "/api/connectors": {
    connectors: [
      {
        id: "con_hubspot",
        name: "HubSpot",
        // `vendor` (NOT `type`) carries the vendor slug: normalizeConnector reads
        // `model.vendor ?? model.type` and shouldShowConnectedConnectorOnHub drops
        // any row whose slug is not a catalog vendor. A category like "crm" here
        // silently filters every connector out, rendering "0 connected".
        vendor: "hubspot",
        status: "connected",
        environment: "production",
        lastSync: T(3),
        health: 99,
        description: "Marketing, sales, and service",
        category: "CRM",
        authType: "oauth",
        authStatus: "active",
        requestsToday: 1284,
        latency: 210,
        dataFlowRate: "1.2k/day",
        usedByWorkflows: 4,
        triggeredByAgents: 2,
      },
      {
        id: "con_salesforce",
        name: "Salesforce",
        vendor: "salesforce",
        status: "error",
        environment: "production",
        lastSync: T(96),
        health: 42,
        description: "CRM and sales automation",
        category: "CRM",
        authType: "oauth",
        authStatus: "active",
        requestsToday: 318,
        latency: 540,
        // Omitting dataFlowRate renders a bare "0 MB/s" on the card.
        dataFlowRate: "320/day",
        blockingReason: "Connected user lacks edit access on Opportunity objects.",
        recoveryAction: "Grant the connected user edit access, then re-run the blocked step.",
        usedByWorkflows: 3,
        triggeredByAgents: 1,
      },
      {
        id: "con_zendesk",
        name: "Zendesk",
        vendor: "zendesk",
        status: "connected",
        environment: "production",
        lastSync: T(12),
        health: 97,
        description: "Support tickets and macros",
        category: "Support",
        authType: "oauth",
        authStatus: "active",
        requestsToday: 642,
        latency: 260,
        dataFlowRate: "640/day",
        usedByWorkflows: 2,
        triggeredByAgents: 1,
      },
      {
        id: "con_slack",
        name: "Slack",
        vendor: "slack",
        status: "syncing",
        environment: "production",
        lastSync: T(1),
        health: 95,
        description: "Notifications and approvals",
        category: "Productivity",
        authType: "oauth",
        authStatus: "active",
        requestsToday: 87,
        latency: 180,
        dataFlowRate: "90/day",
        usedByWorkflows: 5,
        // Must be > 0: the card renders the count with no "agents" label when
        // it is zero, leaving a stray bare "0" next to "5 workflows".
        triggeredByAgents: 2,
      },
    ],
  },

  // ensureSelectedOrg() resolves the active org from this list and calls
  // purgeStaleDemoOrgFromStorage(), which DELETES the seeded gravitre:selectedOrg
  // if its id is absent here. Without this the top bar falls back to its
  // hardcoded "Acme Corp" default.
  "/api/organizations": {
    organizations: [
      { id: DEMO_ORG_ID, name: "Northwind Logistics", slug: "northwind-logistics", role: "admin" },
    ],
  },

  // Shape must match the `Approval` interface in app/approvals/page.tsx;
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
        },
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
        },
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
          impact: "Adds tickets:write for every workflow using this connector.",
        },
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

  // Requested as /api/workflows?org_id=… — the query string is ignored by the
  // pathname matcher, but the page still gates the request on an org being
  // resolved from /api/organizations above.
  "/api/workflows": { workflows },
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
}
