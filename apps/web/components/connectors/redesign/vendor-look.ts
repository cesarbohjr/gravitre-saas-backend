import { connectorVendorKey, formatVendorLabel, lookupConnectorCategory } from "@/lib/connectors"

/**
 * How a connector looks in the Connectors redesign: a two-letter mono tile in
 * the vendor's colours, and one of twelve category covers on the detail page.
 * Vendors the design names keep their exact colours; the rest take the ink of
 * their cover type so every tile still belongs to the palette.
 */

export type CoverType =
  | "crm"
  | "erp"
  | "accounting"
  | "email"
  | "chat"
  | "helpdesk"
  | "marketing"
  | "docs"
  | "projects"
  | "hr"
  | "data"
  | "custom"

export type CoverSpec = {
  type: CoverType
  label: string
  ink: string
  colors: [string, string, string, string]
  stroke: string
  /** Icon keys: the big mark, then the four companions. */
  icons: [IconKey, IconKey, IconKey, IconKey, IconKey]
}

export const COVER_ICONS = {
  card: "M3 5h18v14H3z M8.5 12a2.5 2.5 0 1 0 0-5a2.5 2.5 0 1 0 0 5z M5 17c0-2 1.6-3.5 3.5-3.5S12 15 12 17 M14 9h5 M14 12.5h5 M14 16h3",
  funnel: "M3 5h18l-7 8v6l-4 2v-8z",
  person: "M12 11a4 4 0 1 0 0-8a4 4 0 1 0 0 8z M4 21c0-4 3.6-7 8-7s8 3 8 7",
  mail: "M3 6h18v12H3z M3 7l9 6 9-6",
  trend: "M3 17l6-6 4 4 8-8 M15 7h6v6",
  box: "M12 3l8 4.5v9L12 21l-8-4.5v-9z M4 7.5l8 4.5 8-4.5 M12 12v9",
  gear: "M12 8a4 4 0 1 0 0 8a4 4 0 1 0 0-8z M12 2v3 M12 19v3 M2 12h3 M19 12h3 M4.9 4.9l2.1 2.1 M17 17l2.1 2.1 M4.9 19.1l2.1-2.1 M17 7l2.1-2.1",
  truck: "M3 7h11v9H3z M14 10h4l3 3v3h-7z M7 19a2 2 0 1 0 0-4a2 2 0 1 0 0 4z M17 19a2 2 0 1 0 0-4a2 2 0 1 0 0 4z",
  list: "M9 6h11 M9 12h11 M9 18h11 M4 6l1 1 2-2 M4 12l1 1 2-2 M4 18l1 1 2-2",
  clock: "M12 3a9 9 0 1 0 0 18a9 9 0 1 0 0-18z M12 7v5l3 2",
  calc: "M7 3h10a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2z M8 6h8v3.5H8z M8.5 13h1 M11.5 13h1 M14.5 13h1 M8.5 16.5h1 M11.5 16.5h1 M14.5 16.5h1",
  coins: "M4 7c0-1.7 3.6-3 8-3s8 1.3 8 3-3.6 3-8 3-8-1.3-8-3z M4 7v4c0 1.7 3.6 3 8 3s8-1.3 8-3V7 M4 11v4c0 1.7 3.6 3 8 3s8-1.3 8-3v-4",
  pct: "M19 5L5 19 M7 5a2 2 0 1 0 0 4a2 2 0 1 0 0-4z M17 15a2 2 0 1 0 0 4a2 2 0 1 0 0-4z",
  receipt: "M6 3h12v18l-3-2-3 2-3-2-3 2z M9 8h6 M9 12h6 M9 16h3",
  plane: "M3 11l18-8-8 18-2-8z M11 13l10-10",
  inbox: "M3 13l3-8h12l3 8v6H3z M3 13h5l1 2h6l1-2h5",
  at: "M16 12a4 4 0 1 1-4-4 M16 8v5a2 2 0 0 0 4 0v-1a8 8 0 1 0-3 6.3",
  chat2: "M4 4h12v9H8l-4 3z M10 16h6l4 3v-9h-2",
  hash: "M5 9h14 M5 15h14 M10 4l-2 16 M16 4l-2 16",
  bell: "M6 16V11a6 6 0 1 1 12 0v5l1.5 2h-15z M10 20a2 2 0 0 0 4 0",
  ticket: "M3 7h18v4a2 2 0 0 0 0 4v4H3v-4a2 2 0 0 0 0-4z M14 7v12",
  headset: "M4 14v-2a8 8 0 0 1 16 0v2 M4 14h3v5H4z M17 14h3v5h-3z",
  okc: "M12 3a9 9 0 1 0 0 18a9 9 0 1 0 0-18z M8 12l3 3 5-6",
  chat: "M4 5h16v11H9l-5 4z M8 9h8 M8 12h5",
  bars: "M5 20V10 M12 20V4 M19 20v-7",
  search: "M11 4a7 7 0 1 0 0 14a7 7 0 1 0 0-14z M20 20l-4-4",
  mega: "M3 10v4h3l7 4V6L6 10z M16 9a4 4 0 0 1 0 6 M18.5 6.5a7.5 7.5 0 0 1 0 11",
  spark: "M12 3l2 6 6 2-6 2-2 6-2-6-6-2 6-2z",
  doc: "M6 3h9l4 4v14H6z M14 3v5h5 M9 13h7 M9 17h5",
  book: "M4 5a2 2 0 0 1 2-2h12v16H6a2 2 0 0 0-2 2z M18 19v2H6",
  folder: "M3 6h6l2 2h10v11H3z",
  link: "M10 14a4 4 0 0 0 6 0l3-3a4 4 0 0 0-6-6l-1 1 M14 10a4 4 0 0 0-6 0l-3 3a4 4 0 0 0 6 6l1-1",
  kanban: "M3 4h18v16H3z M9 4v16 M15 4v16 M5 7h2 M11 7h2 M17 7h2",
  code: "M8 7l-5 5 5 5 M16 7l5 5-5 5 M14 4l-4 16",
  branch: "M6 3v12 M18 9a3 3 0 1 0 0-6a3 3 0 1 0 0 6z M6 21a3 3 0 1 0 0-6a3 3 0 1 0 0 6z M18 9a9 9 0 0 1-9 9",
  cal: "M4 5h16v15H4z M4 10h16 M9 3v4 M15 3v4",
  people: "M9 11a3 3 0 1 0 0-6a3 3 0 1 0 0 6z M3 20c0-3.3 2.7-6 6-6s6 2.7 6 6 M16 11a3 3 0 1 0 0-6 M21 20c0-3-2-5.5-5-6",
  badge: "M6 3h12v18H6z M9 3v3h6V3 M12 10a2 2 0 1 0 0 4a2 2 0 1 0 0-4z M9 18h6",
  heart: "M12 20s-7-4.4-7-10a4 4 0 0 1 7-2.6A4 4 0 0 1 19 10c0 5.6-7 10-7 10z",
  db: "M4 6c0-1.7 3.6-3 8-3s8 1.3 8 3-3.6 3-8 3-8-1.3-8-3z M4 6v12c0 1.7 3.6 3 8 3s8-1.3 8-3V6 M4 12c0 1.7 3.6 3 8 3s8-1.3 8-3",
  grid: "M3 4h18v16H3z M3 10h18 M3 15h18 M9 4v16",
  plug: "M8 3v5 M16 3v5 M6 8h12v3a6 6 0 0 1-12 0z M12 17v4",
  bolt: "M13 3L5 14h6l-1 7 8-11h-6z",
  term: "M3 5h18v14H3z M7 10l3 2-3 2 M12 15h5",
} as const

export type IconKey = keyof typeof COVER_ICONS

export const COVERS: Record<CoverType, CoverSpec> = {
  crm: { type: "crm", label: "CRM", ink: "#5B5BD6", colors: ["#E9E9F3", "#CACCE8", "#E4DDEF", "#D9E3EC"], stroke: "#C3C5E6", icons: ["card", "person", "funnel", "mail", "trend"] },
  erp: { type: "erp", label: "ERP", ink: "#8A5A06", colors: ["#F1ECE0", "#E6D6B6", "#E9E1CC", "#DDE2E3"], stroke: "#E3D3B2", icons: ["box", "gear", "truck", "clock", "list"] },
  accounting: { type: "accounting", label: "Accounting", ink: "#4E7350", colors: ["#E7ECE3", "#CFDCCB", "#EBDCC0", "#DCE3E8"], stroke: "#C8D6C4", icons: ["calc", "trend", "coins", "pct", "receipt"] },
  email: { type: "email", label: "Email", ink: "#6B3F8F", colors: ["#EDEAF2", "#D9D2E8", "#E8DFEA", "#DDE3EA"], stroke: "#D3CBE3", icons: ["mail", "plane", "inbox", "at", "clock"] },
  chat: { type: "chat", label: "Chat", ink: "#1F7A6E", colors: ["#E5EDE9", "#CBDDD4", "#D8E6E1", "#E9E2D2"], stroke: "#C6DAD3", icons: ["chat2", "hash", "bell", "at", "person"] },
  helpdesk: { type: "helpdesk", label: "Helpdesk", ink: "#4D6472", colors: ["#E8EBEE", "#D9DEE3", "#D6E2E4", "#E6E2D8"], stroke: "#CED6DC", icons: ["ticket", "headset", "clock", "okc", "chat"] },
  marketing: { type: "marketing", label: "Marketing and analytics", ink: "#A5563C", colors: ["#F1EAE0", "#EBDCC0", "#E9CDBF", "#E6E0D2"], stroke: "#E8D1C1", icons: ["bars", "search", "mega", "spark", "trend"] },
  docs: { type: "docs", label: "Docs and knowledge", ink: "#33342F", colors: ["#ECEBE6", "#DEDAD0", "#D9DEE3", "#E4E1D8"], stroke: "#D6D3CB", icons: ["doc", "book", "folder", "search", "link"] },
  projects: { type: "projects", label: "Projects and engineering", ink: "#2B59E0", colors: ["#E8ECF4", "#CFD9EC", "#DCE2F0", "#E6E2D8"], stroke: "#C7D2E8", icons: ["kanban", "code", "branch", "okc", "cal"] },
  hr: { type: "hr", label: "HR and people", ink: "#9C4668", colors: ["#F2E8E7", "#E8D2CF", "#EADCE3", "#E9E2D6"], stroke: "#E7CFD6", icons: ["people", "badge", "cal", "heart", "list"] },
  data: { type: "data", label: "Data and enrichment", ink: "#6B6A2E", colors: ["#EFEEE2", "#DEDCC2", "#E6E2CC", "#DCE3E3"], stroke: "#D8D4B4", icons: ["db", "spark", "funnel", "person", "grid"] },
  custom: { type: "custom", label: "Webhooks and custom", ink: "#0A6B47", colors: ["#E9EAE7", "#D5D8D3", "#DCE5DC", "#E4E1D8"], stroke: "#CDD1CB", icons: ["plug", "code", "bolt", "link", "term"] },
}

const COVER_BY_VENDOR: Record<string, CoverType> = {
  hubspot: "crm", salesforce: "crm", pipedrive: "crm", zoho: "crm", zohocrm: "crm", attio: "crm", close: "crm", dynamics: "crm",
  netsuite: "erp", odoo: "erp", sap: "erp", shopify: "erp", acumatica: "erp",
  quickbooks: "accounting", xero: "accounting", stripe: "accounting", plaid: "accounting", ramp: "accounting", brex: "accounting", bill: "accounting", freshbooks: "accounting",
  gmail: "email", outlook: "email", smartlead: "email", mailchimp: "email", sendgrid: "email", instantly: "email", constant_contact: "email", klaviyo: "email",
  slack: "chat", microsoft_teams: "chat", discord: "chat", twilio: "chat",
  zendesk: "helpdesk", freshservice: "helpdesk", freshdesk: "helpdesk", intercom: "helpdesk", servicenow: "helpdesk", helpscout: "helpdesk", pagerduty: "helpdesk",
  google_analytics: "marketing", google_search_console: "marketing", google_ads: "marketing", marketo: "marketing", meta_ads: "marketing", linkedin_ads: "marketing", semrush: "marketing", ahrefs: "marketing",
  notion: "docs", confluence: "docs", google_drive: "docs", google_docs: "docs", google_sheets: "docs", dropbox: "docs", box: "docs", sharepoint: "docs", microsoft365: "docs",
  jira: "projects", asana: "projects", github: "projects", gitlab: "projects", linear: "projects", monday: "projects", trello: "projects", clickup: "projects", google_calendar: "projects",
  workday: "hr", bamboohr: "hr", greenhouse: "hr", gusto: "hr", rippling: "hr", lever: "hr", absorb_lms: "hr",
  apollo: "data", clay: "data", peopledatalabs: "data", snowflake: "data", bigquery: "data", aws_s3: "data", zoominfo: "data", clearbit: "data",
  webhook: "custom", custom: "custom", rest: "custom", api: "custom",
}

const COVER_BY_CATEGORY: Record<string, CoverType> = {
  "CRM / Marketing": "crm",
  "Sales / Prospecting": "data",
  "Payments / Finance": "accounting",
  Communication: "chat",
  "DevOps / Incidents": "projects",
  "Operations / Workflow": "projects",
  "Customer Support": "helpdesk",
  "HR / People": "hr",
  "Storage / Dev / Infra": "custom",
  "Learning / Creative": "docs",
  "Analytics / Data": "marketing",
}

/** Exact tile colours for the vendors the design draws. */
const VENDOR_TILES: Record<string, { mono: string; bg: string; fg: string }> = {
  hubspot: { mono: "HS", bg: "#FBE3D6", fg: "#A5563C" },
  zendesk: { mono: "ZD", bg: "#E5EDE9", fg: "#1F7A6E" },
  xero: { mono: "XE", bg: "#E3EEF8", fg: "#22608F" },
  quickbooks: { mono: "QB", bg: "#DDF3E8", fg: "#0A6B47" },
  gmail: { mono: "GM", bg: "#F8E4E6", fg: "#A3333D" },
  slack: { mono: "SL", bg: "#EEE6F5", fg: "#6B3F8F" },
  google_search_console: { mono: "SC", bg: "#EEF2FF", fg: "#2B59E0" },
  google_analytics: { mono: "GA", bg: "#FBF1DC", fg: "#8A5A06" },
  notion: { mono: "NO", bg: "#EFEFEA", fg: "#141513" },
  jira: { mono: "JI", bg: "#E3EAF8", fg: "#2B59E0" },
  apollo: { mono: "AP", bg: "#FBF1DC", fg: "#8A5A06" },
  clay: { mono: "CL", bg: "#F2E8E7", fg: "#9C4668" },
}

export function coverTypeFor(vendor: string, category?: string): CoverType {
  const key = connectorVendorKey(vendor || "")
  if (COVER_BY_VENDOR[key]) return COVER_BY_VENDOR[key]
  const cat = category || lookupConnectorCategory(vendor || "")
  return COVER_BY_CATEGORY[cat] ?? "custom"
}

export function coverFor(vendor: string, category?: string): CoverSpec {
  return COVERS[coverTypeFor(vendor, category)]
}

/** Two letters for the tile: initials of a two-word name, else the first two letters. */
export function vendorMono(name: string): string {
  const words = name.replace(/[^A-Za-z0-9 ]+/g, " ").trim().split(/\s+/).filter(Boolean)
  if (words.length === 0) return "··"
  if (words.length === 1) return words[0].slice(0, 2).toUpperCase()
  return (words[0][0] + words[1][0]).toUpperCase()
}

export type VendorLook = { key: string; label: string; mono: string; bg: string; fg: string; cover: CoverSpec }

export function vendorLook(vendor: string, category?: string): VendorLook {
  const key = connectorVendorKey(vendor || "")
  const label = formatVendorLabel(vendor || key || "Connector")
  const cover = coverFor(vendor, category)
  const exact = VENDOR_TILES[key]
  if (exact) return { key, label, cover, ...exact }
  return { key, label, cover, mono: vendorMono(label), bg: cover.colors[1], fg: cover.ink }
}
