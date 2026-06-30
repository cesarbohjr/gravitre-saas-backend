export interface ProductionConnectorDoc {
  slug: string
  title: string
  authType: string
  summary: string
  setupSteps: string[]
  apiNotes?: string
}

export const productionConnectors: ProductionConnectorDoc[] = [
  {
    slug: "hubspot",
    title: "HubSpot",
    authType: "OAuth (platform app)",
    summary: "Sync CRM objects, run HubSpot actions in workflows and agents, and receive inbound webhooks.",
    setupSteps: [
      "Open **Connectors → HubSpot → Connect**.",
      "Sign in to HubSpot and authorize the requested scopes.",
      "Verify the connector shows **Connected**.",
      "Use HubSpot actions in workflows or grant tools to agents.",
    ],
    apiNotes: "OAuth callback: `/api/connectors/oauth/hubspot/callback` on your API host.",
  },
  {
    slug: "salesforce",
    title: "Salesforce",
    authType: "OAuth with PKCE",
    summary: "Query and update Salesforce records from workflows and agents.",
    setupSteps: [
      "Open **Connectors → Salesforce → Connect**.",
      "Complete OAuth in your Salesforce org.",
      "Confirm connected status before scheduling production workflows.",
    ],
  },
  {
    slug: "quickbooks",
    title: "QuickBooks",
    authType: "OAuth (Intuit)",
    summary: "Read financial objects and run QuickBooks actions when connected.",
    setupSteps: [
      "Connect via **Connectors → QuickBooks**.",
      "Select the correct QuickBooks company during OAuth.",
      "Test with a dry-run workflow before write actions.",
    ],
  },
  {
    slug: "jira",
    title: "Jira",
    authType: "OAuth (Atlassian)",
    summary: "Create and search Jira issues from automated workflows.",
    setupSteps: [
      "Connect **Jira** and pick your Atlassian cloud site.",
      "Grant the connector access to required projects.",
      "Add Jira steps in the workflow builder.",
    ],
  },
  {
    slug: "pagerduty",
    title: "PagerDuty",
    authType: "OAuth",
    summary: "Trigger and acknowledge incidents; integrate on-call workflows.",
    setupSteps: [
      "Connect **PagerDuty** from Connectors.",
      "Configure inbound webhooks in PagerDuty pointing to Gravitre if using event triggers.",
    ],
  },
  {
    slug: "github",
    title: "GitHub",
    authType: "OAuth or personal access token",
    summary: "Manage repos, issues, and PRs via GitHub tools in workflows and agents.",
    setupSteps: [
      "Choose OAuth or PAT when adding the connector.",
      "Scope tokens to minimum required repositories.",
    ],
  },
  {
    slug: "zendesk",
    title: "Zendesk",
    authType: "OAuth or API token",
    summary: "Search tickets and update support records from automations.",
    setupSteps: [
      "Provide subdomain plus OAuth or API token credentials.",
      "Test read actions before enabling ticket updates.",
    ],
  },
  {
    slug: "odoo",
    title: "Odoo",
    authType: "API key (JSON-RPC)",
    summary: "ERP read/write via Odoo API key authentication.",
    setupSteps: [
      "Generate an API key in Odoo user preferences.",
      "Enter Odoo URL, database, username, and key in Gravitre.",
    ],
  },
  {
    slug: "google-workspace",
    title: "Google Workspace",
    authType: "OAuth (shared Google app)",
    summary: "Covers Gmail, Calendar, Drive, Docs, Sheets, and Google Analytics when enabled.",
    setupSteps: [
      "Connect the Google app you need from **Connectors** (Gmail, Calendar, etc.).",
      "Grant Google account access in the OAuth consent screen.",
      "Pick GA4 property when connecting Google Analytics.",
    ],
  },
  {
    slug: "email",
    title: "Email (SMTP)",
    authType: "SMTP credentials",
    summary: "Send outbound email from workflows using your SMTP server.",
    setupSteps: [
      "Add **Email** connector with SMTP host, port, username, and password.",
      "Send a test message from a workflow dry-run.",
    ],
  },
]

export function getProductionConnector(slug: string) {
  return productionConnectors.find((c) => c.slug === slug) ?? null
}
