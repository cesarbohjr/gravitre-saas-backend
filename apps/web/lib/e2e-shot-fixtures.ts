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
 * Keyed by request pathname. The harness serves these to the real client code
 * in place of a live backend.
 */
export const SHOT_FIXTURES: Record<string, unknown> = {
  __supabaseUser: supabaseUser,
  __orgId: DEMO_ORG_ID,

  "/api/billing/status": {
    canAccessApp: true,
    billingStatus: "active",
    requiresUpgrade: false,
    trialEndsAt: null,
    plan: "control",
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
}
