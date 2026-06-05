/**
 * Connector catalog + vendor key mapping (Tier 1/2 shipped integrations).
 * Keep in sync with backend SUPPORTED_OAUTH_PROVIDERS and ALLOWED_CONNECTOR_VENDORS.
 */

/** OAuth providers with full backend start/callback routes (Tier 1 + Tier 2). */
export const SHIPPED_OAUTH_CONNECTOR_TYPES = [
  "HubSpot",
  "Salesforce",
  "QuickBooks",
  "Jira",
  "Confluence",
  "PagerDuty",
  "Notion",
  "Google Analytics",
  "Google Calendar",
  "Gmail",
  "Google Drive",
  "Google Docs",
  "Google Sheets",
] as const

export const OAUTH_CONNECTOR_TYPE_SET = new Set<string>(SHIPPED_OAUTH_CONNECTOR_TYPES)

export const OAUTH_VENDOR_KEYS = new Set([
  "hubspot",
  "salesforce",
  "quickbooks",
  "jira",
  "confluence",
  "pagerduty",
  "notion",
  "google_analytics",
  "google_calendar",
  "gmail",
  "google_drive",
  "google_docs",
  "google_sheets",
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
  pagerduty: "PagerDuty",
  jira: "Jira",
  confluence: "Confluence",
  notion: "Notion",
  microsoft365: "Microsoft 365",
  github: "GitHub",
  zendesk: "Zendesk",
  stripe: "Stripe",
}

/** Map UI label → backend vendor slug for OAuth/API routes. */
export function connectorVendorKey(type: string): string {
  const key = type.toLowerCase().replace(/\s+/g, "")
  if (key === "googlecalendar") return "google_calendar"
  if (key === "googleanalytics") return "google_analytics"
  if (key === "googledrive") return "google_drive"
  if (key === "googledocs") return "google_docs"
  if (key === "googlesheets") return "google_sheets"
  if (key === "awss3") return "aws_s3"
  return key
}

export function formatVendorLabel(vendor: string): string {
  const key = vendor.toLowerCase().replace(/\s+/g, "_")
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
