/**
 * Connector catalog + vendor key mapping.
 * Single source of truth for Connectors UI, marketing pages, and wizards.
 * Keep oauthReady in sync with backend GENERIC_OAUTH_VENDORS + SUPPORTED_OAUTH_PROVIDERS.
 */

export type ConnectorAuthType = "oauth" | "apiKey" | "webhook"

/** How credentials are collected — orthogonal to UI authType label. */
export type ConnectorCredentialModel =
  | "oauth2"
  | "oauth2_custom"
  | "api_key"
  | "connection_string"
  | "iam"
  | "partner_oauth"
  | "plaid_link"
  | "platform_only"

export type ConnectorSetupComplexity = "low" | "medium" | "high" | "enterprise"

export interface CatalogConnectorEntry {
  type: string
  vendorKey: string
  description: string
  authType: ConnectorAuthType
  category: string
  credentialModel: ConnectorCredentialModel
  /** Backend agent tools implemented */
  shipped?: boolean
  /** OAuth start/callback routes implemented and verified for this vendor */
  oauthReady?: boolean
  /** OAuth is primary connect path; PAT/API token available as fallback (GitHub, Zendesk) */
  dualPatAuth?: boolean
  requiresSubdomain?: boolean
  requiresInstanceUrl?: boolean
  requiresPartnerApproval?: boolean
  setupComplexity?: ConnectorSetupComplexity
}

export const CONNECTOR_CATEGORY_META: Record<string, { color: string; label: string }> = {
  "CRM / Marketing": { color: "emerald", label: "CRM / Marketing" },
  "Sales / Prospecting": { color: "sky", label: "Sales / Prospecting" },
  "Payments / Finance": { color: "blue", label: "Payments / Finance" },
  Communication: { color: "violet", label: "Communication" },
  "DevOps / Incidents": { color: "rose", label: "DevOps / Incidents" },
  "Operations / Workflow": { color: "amber", label: "Operations / Workflow" },
  "Customer Support": { color: "pink", label: "Customer Support" },
  "HR / People": { color: "cyan", label: "HR / People" },
  "Storage / Dev / Infra": { color: "orange", label: "Storage / Dev / Infra" },
  "Learning / Creative": { color: "indigo", label: "Learning / Creative" },
}

/** Tier 1–3 + verified generic OAuth providers with working backend routes. */
export const SHIPPED_OAUTH_CONNECTOR_TYPES = [
  "HubSpot",
  "Salesforce",
  "QuickBooks",
  "NetSuite",
  "Workday",
  "Marketo",
  "Jira",
  "Confluence",
  "PagerDuty",
  "Notion",
  "Slack",
  "Google Analytics",
  "Google Calendar",
  "Gmail",
  "Google Drive",
  "Google Docs",
  "Google Sheets",
  "Mailchimp",
  "Constant Contact",
  "Xero",
  "Airtable",
  "Asana",
  "ClickUp",
  "Freshdesk",
  "Intercom",
  "Monday.com",
  "Microsoft 365",
  "GitHub",
  "Zendesk",
  "Canva",
  "Figma",
] as const

/** Generic OAuth providers that require PKCE (RFC 7636). Salesforce uses backend PKCE too. */
export const PKCE_OAUTH_VENDOR_KEYS = new Set(["airtable", "canva", "salesforce", "xero"])

export const OAUTH_CONNECTOR_TYPE_SET = new Set<string>(SHIPPED_OAUTH_CONNECTOR_TYPES)

/** Vendors with platform OAuth app + authorization-code callback routes. */
export const OAUTH_VENDOR_KEYS = new Set([
  "hubspot",
  "salesforce",
  "quickbooks",
  "netsuite",
  "workday",
  "marketo",
  "jira",
  "confluence",
  "pagerduty",
  "notion",
  "slack",
  "google_analytics",
  "google_calendar",
  "gmail",
  "google_drive",
  "google_docs",
  "google_sheets",
  "mailchimp",
  "constant_contact",
  "xero",
  "airtable",
  "asana",
  "clickup",
  "freshdesk",
  "intercom",
  "monday",
  "microsoft365",
  "zendesk",
  "github",
  "canva",
  "figma",
])

/** OAuth + optional PAT/API-token fallback at connect time. */
export const DUAL_AUTH_VENDOR_KEYS = new Set(["github", "zendesk"])

/** Per-connector API key / token / secret (not platform OAuth). */
export const APIKEY_VENDOR_KEYS = new Set([
  "segment",
  "linkedin",
  "stripe",
  "mixpanel",
  "semrush",
  "stackadapt",
  "apollo",
  "sendgrid",
  "twilio",
  "n8n",
  "motion",
  "github",
  "zendesk",
  "bamboohr",
  "greenhouse",
  "odoo",
  "absorb_lms",
  "gorgias",
  "snowflake",
  "adp",
])

/** Database connection string collected per connector. */
export const DATABASE_VENDOR_KEYS = new Set(["postgresql", "mongodb"])

/** Cloud IAM / access-key style credentials per connector. */
export const IAM_VENDOR_KEYS = new Set(["aws_s3"])

/** Partner program / sales approval required before self-serve connect. */
export const PARTNER_GATED_CONNECTOR_KEYS = new Set([
  "adp",
  "gusto",
  "hootsuite",
  "zapier",
])

/** Partner-gated or requires non-standard integration (not generic OAuth callback). */
export const PARTNER_OR_CUSTOM_VENDOR_KEYS = new Set([
  "adp",
  "plaid",
  "workday",
  "marketo",
  "netsuite",
  "hootsuite",
  "gusto",
  "zapier",
])

const VENDOR_LABELS: Record<string, string> = {
  salesforce: "Salesforce",
  hubspot: "HubSpot",
  google_analytics: "Google Analytics",
  google_calendar: "Google Calendar",
  google_drive: "Google Drive",
  google_docs: "Google Docs",
  google_sheets: "Google Sheets",
  quickbooks: "QuickBooks",
  netsuite: "NetSuite",
  workday: "Workday",
  marketo: "Marketo",
  segment: "Segment",
  linkedin: "LinkedIn",
  pagerduty: "PagerDuty",
  jira: "Jira",
  confluence: "Confluence",
  notion: "Notion",
  microsoft365: "Microsoft 365",
  microsoft_teams: "Microsoft Teams",
  github: "GitHub",
  zendesk: "Zendesk",
  stripe: "Stripe",
  aws_s3: "AWS S3",
  mixpanel: "Mixpanel",
  zapier: "Zapier",
  sendgrid: "SendGrid",
  constant_contact: "Constant Contact",
  hootsuite: "Hootsuite",
  n8n: "n8n",
  semrush: "SEMrush",
  stackadapt: "StackAdapt",
  greenhouse: "Greenhouse",
  absorb_lms: "Absorb LMS",
  apollo: "Apollo",
  odoo: "Odoo",
  canva: "Canva",
  figma: "Figma",
  motion: "Motion",
}

const CATALOG_ENTRIES: CatalogConnectorEntry[] = [
  // CRM / Marketing
  { type: "Salesforce", vendorKey: "salesforce", description: "CRM and sales automation", authType: "oauth", credentialModel: "oauth2", category: "CRM / Marketing", shipped: true },
  { type: "HubSpot", vendorKey: "hubspot", description: "Marketing, sales, and service", authType: "oauth", credentialModel: "oauth2", category: "CRM / Marketing", shipped: true },
  { type: "Google Analytics", vendorKey: "google_analytics", description: "GA4 campaign and conversion analytics", authType: "oauth", credentialModel: "oauth2", category: "CRM / Marketing", shipped: true },
  { type: "Marketo", vendorKey: "marketo", description: "Enterprise marketing automation", authType: "oauth", credentialModel: "oauth2_custom", category: "CRM / Marketing", shipped: true },
  { type: "Segment", vendorKey: "segment", description: "Customer data platform", authType: "apiKey", credentialModel: "api_key", category: "CRM / Marketing", shipped: true },
  { type: "Mailchimp", vendorKey: "mailchimp", description: "Email marketing campaigns", authType: "oauth", credentialModel: "oauth2", category: "CRM / Marketing", oauthReady: true },
  { type: "Mixpanel", vendorKey: "mixpanel", description: "Product analytics", authType: "apiKey", credentialModel: "api_key", category: "CRM / Marketing" },
  { type: "Constant Contact", vendorKey: "constant_contact", description: "Email and marketing automation", authType: "oauth", credentialModel: "oauth2", category: "CRM / Marketing", oauthReady: true },
  { type: "Hootsuite", vendorKey: "hootsuite", description: "Social media management", authType: "oauth", credentialModel: "partner_oauth", category: "CRM / Marketing", requiresPartnerApproval: true, setupComplexity: "enterprise" },
  { type: "SEMrush", vendorKey: "semrush", description: "SEO and marketing intelligence", authType: "apiKey", credentialModel: "api_key", category: "CRM / Marketing" },
  { type: "StackAdapt", vendorKey: "stackadapt", description: "Programmatic advertising", authType: "apiKey", credentialModel: "api_key", category: "CRM / Marketing" },
  // Sales / Prospecting
  { type: "LinkedIn", vendorKey: "linkedin", description: "Prospect enrichment for Sales Agent", authType: "apiKey", credentialModel: "api_key", category: "Sales / Prospecting", shipped: true },
  { type: "Apollo", vendorKey: "apollo", description: "Sales intelligence and outreach", authType: "apiKey", credentialModel: "api_key", category: "Sales / Prospecting", shipped: true },
  // Payments / Finance
  { type: "Stripe", vendorKey: "stripe", description: "Payment processing", authType: "apiKey", credentialModel: "api_key", category: "Payments / Finance", shipped: true },
  { type: "QuickBooks", vendorKey: "quickbooks", description: "Accounting software", authType: "oauth", credentialModel: "oauth2", category: "Payments / Finance", shipped: true },
  { type: "NetSuite", vendorKey: "netsuite", description: "Enterprise ERP", authType: "oauth", credentialModel: "oauth2_custom", category: "Payments / Finance", shipped: true },
  { type: "Xero", vendorKey: "xero", description: "Cloud accounting", authType: "oauth", credentialModel: "oauth2_custom", category: "Payments / Finance", oauthReady: true, shipped: true },
  { type: "Plaid", vendorKey: "plaid", description: "Financial data via Plaid Link (not OAuth callback)", authType: "apiKey", credentialModel: "plaid_link", category: "Payments / Finance", setupComplexity: "high" },
  // Communication
  { type: "Slack", vendorKey: "slack", description: "Team messaging", authType: "oauth", credentialModel: "oauth2", category: "Communication", shipped: true, oauthReady: true },
  { type: "Microsoft Teams", vendorKey: "microsoft_teams", description: "Collaboration hub", authType: "oauth", credentialModel: "oauth2_custom", category: "Communication" },
  { type: "Microsoft 365", vendorKey: "microsoft365", description: "Outlook, Teams, SharePoint, and Microsoft Graph", authType: "oauth", credentialModel: "oauth2_custom", category: "Communication", oauthReady: true, shipped: true },
  { type: "Gmail", vendorKey: "gmail", description: "Email integration", authType: "oauth", credentialModel: "oauth2", category: "Communication", shipped: true },
  { type: "Google Calendar", vendorKey: "google_calendar", description: "Calendar availability and events", authType: "oauth", credentialModel: "oauth2", category: "Communication", shipped: true },
  { type: "Outlook", vendorKey: "outlook", description: "Microsoft email", authType: "oauth", credentialModel: "oauth2_custom", category: "Communication" },
  { type: "Twilio", vendorKey: "twilio", description: "SMS and voice API", authType: "apiKey", credentialModel: "api_key", category: "Communication" },
  { type: "SendGrid", vendorKey: "sendgrid", description: "Transactional email API", authType: "apiKey", credentialModel: "api_key", category: "Communication" },
  { type: "Email", vendorKey: "email", description: "SMTP / send email from workflows", authType: "webhook", credentialModel: "api_key", category: "Communication", shipped: true },
  // DevOps / Incidents
  { type: "PagerDuty", vendorKey: "pagerduty", description: "Incident management and on-call", authType: "oauth", credentialModel: "oauth2", category: "DevOps / Incidents", shipped: true },
  { type: "GitHub", vendorKey: "github", description: "Code repository and pull requests", authType: "oauth", credentialModel: "oauth2", category: "DevOps / Incidents", shipped: true, oauthReady: true, dualPatAuth: true },
  // Operations / Workflow
  { type: "Notion", vendorKey: "notion", description: "All-in-one workspace", authType: "oauth", credentialModel: "oauth2", category: "Operations / Workflow", shipped: true },
  { type: "Confluence", vendorKey: "confluence", description: "Team documentation wiki", authType: "oauth", credentialModel: "oauth2", category: "Operations / Workflow", shipped: true },
  { type: "Jira", vendorKey: "jira", description: "Issue tracking and DevOps", authType: "oauth", credentialModel: "oauth2", category: "Operations / Workflow", shipped: true },
  { type: "Airtable", vendorKey: "airtable", description: "Database spreadsheets", authType: "oauth", credentialModel: "oauth2_custom", category: "Operations / Workflow", oauthReady: true },
  { type: "Asana", vendorKey: "asana", description: "Project management", authType: "oauth", credentialModel: "oauth2", category: "Operations / Workflow", oauthReady: true },
  { type: "Monday.com", vendorKey: "monday", description: "Work OS", authType: "oauth", credentialModel: "oauth2", category: "Operations / Workflow", oauthReady: true },
  { type: "ClickUp", vendorKey: "clickup", description: "Productivity platform", authType: "oauth", credentialModel: "oauth2", category: "Operations / Workflow", oauthReady: true },
  { type: "Zapier", vendorKey: "zapier", description: "Automation between apps", authType: "oauth", credentialModel: "partner_oauth", category: "Operations / Workflow", requiresPartnerApproval: true, setupComplexity: "high" },
  { type: "n8n", vendorKey: "n8n", description: "Workflow automation", authType: "apiKey", credentialModel: "api_key", category: "Operations / Workflow" },
  { type: "Motion", vendorKey: "motion", description: "AI calendar and task planning", authType: "apiKey", credentialModel: "api_key", category: "Operations / Workflow" },
  { type: "Odoo", vendorKey: "odoo", description: "ERP and business apps", authType: "apiKey", credentialModel: "api_key", category: "Operations / Workflow", requiresInstanceUrl: true, shipped: true },
  // Customer Support
  { type: "Zendesk", vendorKey: "zendesk", description: "Customer service", authType: "apiKey", credentialModel: "api_key", category: "Customer Support", shipped: true, oauthReady: true, requiresSubdomain: true, dualPatAuth: true },
  { type: "Intercom", vendorKey: "intercom", description: "Customer messaging", authType: "oauth", credentialModel: "oauth2", category: "Customer Support", oauthReady: true },
  { type: "Freshdesk", vendorKey: "freshdesk", description: "Help desk software", authType: "oauth", credentialModel: "oauth2_custom", category: "Customer Support", oauthReady: true, requiresSubdomain: true },
  { type: "Gorgias", vendorKey: "gorgias", description: "E-commerce helpdesk", authType: "apiKey", credentialModel: "api_key", category: "Customer Support", requiresSubdomain: true },
  // HR / People
  { type: "Workday", vendorKey: "workday", description: "HR management", authType: "oauth", credentialModel: "oauth2_custom", category: "HR / People", shipped: true },
  { type: "BambooHR", vendorKey: "bamboohr", description: "HR software", authType: "apiKey", credentialModel: "api_key", category: "HR / People", requiresSubdomain: true, shipped: true },
  { type: "Greenhouse", vendorKey: "greenhouse", description: "Recruiting and applicant tracking", authType: "apiKey", credentialModel: "api_key", category: "HR / People", shipped: true },
  { type: "Gusto", vendorKey: "gusto", description: "Payroll and benefits", authType: "oauth", credentialModel: "partner_oauth", category: "HR / People", requiresPartnerApproval: true, setupComplexity: "enterprise" },
  { type: "ADP", vendorKey: "adp", description: "HR and payroll", authType: "apiKey", credentialModel: "partner_oauth", category: "HR / People", requiresPartnerApproval: true, setupComplexity: "enterprise" },
  // Storage / Dev / Infra
  { type: "AWS S3", vendorKey: "aws_s3", description: "Cloud object storage", authType: "apiKey", credentialModel: "iam", category: "Storage / Dev / Infra" },
  { type: "PostgreSQL", vendorKey: "postgresql", description: "SQL database", authType: "apiKey", credentialModel: "connection_string", category: "Storage / Dev / Infra", shipped: true },
  { type: "MongoDB", vendorKey: "mongodb", description: "NoSQL database (Atlas)", authType: "apiKey", credentialModel: "connection_string", category: "Storage / Dev / Infra" },
  { type: "Snowflake", vendorKey: "snowflake", description: "Data warehouse (account, role, warehouse, database, schema)", authType: "apiKey", credentialModel: "oauth2_custom", category: "Storage / Dev / Infra", requiresSubdomain: true, setupComplexity: "high" },
  { type: "Google Drive", vendorKey: "google_drive", description: "File storage", authType: "oauth", credentialModel: "oauth2", category: "Storage / Dev / Infra", shipped: true },
  { type: "Google Docs", vendorKey: "google_docs", description: "Documents", authType: "oauth", credentialModel: "oauth2", category: "Storage / Dev / Infra", shipped: true },
  { type: "Google Sheets", vendorKey: "google_sheets", description: "Spreadsheets", authType: "oauth", credentialModel: "oauth2", category: "Storage / Dev / Infra", shipped: true },
  // Learning / Creative
  { type: "Absorb LMS", vendorKey: "absorb_lms", description: "Learning management system", authType: "apiKey", credentialModel: "api_key", category: "Learning / Creative" },
  { type: "Canva", vendorKey: "canva", description: "Design and brand assets", authType: "oauth", credentialModel: "oauth2_custom", category: "Learning / Creative", shipped: true, oauthReady: true, setupComplexity: "high" },
  { type: "Figma", vendorKey: "figma", description: "Product design and prototyping", authType: "oauth", credentialModel: "oauth2", category: "Learning / Creative", shipped: true, oauthReady: true, setupComplexity: "medium" },
]

export const CONNECTOR_CATALOG: CatalogConnectorEntry[] = CATALOG_ENTRIES

export const CONNECTOR_CATEGORIES = Object.fromEntries(
  Object.keys(CONNECTOR_CATEGORY_META).map((category) => [
    category,
    {
      color: CONNECTOR_CATEGORY_META[category].color,
      connectors: CONNECTOR_CATALOG.filter((c) => c.category === category).map(
        ({
          type,
          description,
          authType,
          vendorKey,
          shipped,
          oauthReady,
          requiresSubdomain,
          requiresInstanceUrl,
          requiresPartnerApproval,
          setupComplexity,
        }) => ({
          type,
          description,
          authType,
          vendorKey,
          shipped,
          oauthReady,
          requiresSubdomain,
          requiresInstanceUrl,
          requiresPartnerApproval,
          setupComplexity,
        })
      ),
    },
  ])
) as Record<
  string,
  {
    color: string
    connectors: Array<{
      type: string
      description: string
      authType: ConnectorAuthType
      vendorKey: string
      shipped?: boolean
      oauthReady?: boolean
      requiresSubdomain?: boolean
      requiresInstanceUrl?: boolean
    }>
  }
>

export const MARKETING_INTEGRATION_APPS = [
  "Salesforce",
  "HubSpot",
  "Slack",
  "Stripe",
  "QuickBooks",
  "NetSuite",
  "Workday",
  "Marketo",
  "Segment",
  "LinkedIn",
  "Apollo",
  "Google Analytics",
  "Gmail",
  "Notion",
  "Confluence",
  "Jira",
  "PagerDuty",
  "Zendesk",
  "GitHub",
  "PostgreSQL",
  "Snowflake",
  "Microsoft 365",
  "Twilio",
  "Zapier",
  "SendGrid",
  "Mailchimp",
  "Asana",
  "Airtable",
  "Xero",
  "Canva",
  "Figma",
] as const

const CATEGORY_BY_VENDOR = new Map(
  CONNECTOR_CATALOG.map((entry) => [entry.vendorKey, entry.category] as const),
)

/** Resolve catalog category for a connected instance (API rows omit category). */
export function lookupConnectorCategory(vendor: string): string {
  const key = connectorVendorKey(vendor)
  return CATEGORY_BY_VENDOR.get(key) ?? ""
}

export function connectorVendorKey(type: string): string {
  const key = type.toLowerCase().replace(/\s+/g, "").replace(/\./g, "")
  if (key === "googlecalendar") return "google_calendar"
  if (key === "googleanalytics") return "google_analytics"
  if (key === "googledrive") return "google_drive"
  if (key === "googledocs") return "google_docs"
  if (key === "googlesheets") return "google_sheets"
  if (key === "awss3") return "aws_s3"
  if (key === "microsoftteams") return "microsoft_teams"
  if (key === "microsoft365") return "microsoft365"
  if (key === "mondaycom") return "monday"
  if (key === "constantcontact") return "constant_contact"
  if (key === "absorblms") return "absorb_lms"
  if (key === "apolloio" || key === "apolloai") return "apollo"
  return key
}

export function formatVendorLabel(vendor: string): string {
  const key = vendor.toLowerCase().replace(/\s+/g, "_").replace(/-/g, "_")
  if (VENDOR_LABELS[key]) return VENDOR_LABELS[key]
  return vendor
    .replace(/_/g, " ")
    .replace(/\b\w/g, (char) => char.toUpperCase())
}

export function isOAuthConnectorType(type: string): boolean {
  return OAUTH_CONNECTOR_TYPE_SET.has(type)
}

export function isOAuthVendorKey(vendorKey: string): boolean {
  return OAUTH_VENDOR_KEYS.has(vendorKey)
}

export function isPartnerGatedConnector(
  entry: Pick<CatalogConnectorEntry, "vendorKey" | "requiresPartnerApproval">
): boolean {
  if (entry.requiresPartnerApproval === true) return true
  return PARTNER_GATED_CONNECTOR_KEYS.has(entry.vendorKey)
}

export function isShippedConnector(
  entry: Pick<
    CatalogConnectorEntry,
    "vendorKey" | "shipped" | "oauthReady" | "requiresPartnerApproval"
  >
): boolean {
  if (isPartnerGatedConnector(entry)) return false
  return entry.shipped === true || entry.oauthReady === true
}

export function supportsDualPatAuth(
  entry: Pick<CatalogConnectorEntry, "vendorKey" | "dualPatAuth">
): boolean {
  return entry.dualPatAuth === true || DUAL_AUTH_VENDOR_KEYS.has(entry.vendorKey)
}

export function isOAuthConnectable(
  entry: Pick<
    CatalogConnectorEntry,
    "authType" | "shipped" | "oauthReady" | "vendorKey" | "requiresPartnerApproval" | "dualPatAuth"
  >
): boolean {
  if (isPartnerGatedConnector(entry)) return false
  if (entry.authType === "oauth" && (entry.shipped === true || entry.oauthReady === true)) {
    return true
  }
  return supportsDualPatAuth(entry) && entry.oauthReady === true && entry.shipped === true
}

/** Self-serve connectors (shipped or OAuth-ready, not partner-gated). */
export function listAvailableConnectors(): CatalogConnectorEntry[] {
  return CONNECTOR_CATALOG.filter((entry) => isShippedConnector(entry))
}

export const AVAILABLE_CONNECTORS = listAvailableConnectors().map((entry) => ({
  ...entry,
  category: entry.category,
}))
