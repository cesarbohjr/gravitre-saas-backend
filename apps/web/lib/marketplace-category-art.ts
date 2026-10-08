/**
 * Marketplace category art: maps a marketplace asset (title, slug, tags,
 * category, department, asset type) to one of the 15 objects-only market-*
 * illustrations. Per the illustration library rule, marketplace cards and the
 * template detail hero only ever use market-* art, never department scenes or
 * feature spots.
 *
 * Resolution order:
 *  1. Keyword rules over the asset's own words (title, slug, tags, category,
 *     use case), most specific first.
 *  2. The asset's department.
 *  3. The asset type.
 *  4. MARKET_ART_FALLBACK.
 */

export type MarketArtName =
  | "market-prospecting"
  | "market-compliance"
  | "market-security"
  | "market-finance"
  | "market-product"
  | "market-support"
  | "market-onboarding"
  | "market-pipeline"
  | "market-deals"
  | "market-campaigns"
  | "market-site-health"
  | "market-revenue"
  | "market-tickets"
  | "market-new-customers"
  | "market-leads"

export interface MarketArt {
  name: MarketArtName
  /** Category label shown on cards ("Pipeline", "Customer Tickets"). */
  label: string
  /** Alt text describing the objects in the scene. */
  alt: string
  src: string
}

const ART: Record<MarketArtName, { label: string; alt: string }> = {
  "market-prospecting": { label: "Prospecting", alt: "A magnifying glass over a grid of company cards with one target marked" },
  "market-compliance": { label: "Compliance", alt: "A clipboard checklist with every item ticked and a seal of approval" },
  "market-security": { label: "Security", alt: "A padlock in front of a shield" },
  "market-finance": { label: "Finance", alt: "A calculator beside stacks of coins and a receipt" },
  "market-product": { label: "Product", alt: "Stacked interface windows with a building block cube" },
  "market-support": { label: "Support", alt: "Two speech bubbles beside a life ring" },
  "market-onboarding": { label: "Onboarding", alt: "An open door with a welcome mat and three step markers leading in" },
  "market-pipeline": { label: "Pipeline", alt: "A stage board of deal cards moving along a pipe into a green win" },
  "market-deals": { label: "Deals", alt: "A signed contract with a pen and a price tag" },
  "market-campaigns": { label: "Campaigns", alt: "A megaphone sending out sound waves and a paper plane" },
  "market-site-health": { label: "Site Health", alt: "A browser window with a steady heartbeat line and a green check" },
  "market-revenue": { label: "Revenue", alt: "Rising bars with an upward arrow and coins" },
  "market-tickets": { label: "Customer Tickets", alt: "A stack of support tickets with a priority tag" },
  "market-new-customers": { label: "New Customers", alt: "A welcome badge with a star next to a gift box" },
  "market-leads": { label: "Leads", alt: "A magnet drawing in contact cards" },
}

export const MARKET_ART_NAMES = Object.keys(ART) as MarketArtName[]

/** Used when nothing about the asset points to a category. */
export const MARKET_ART_FALLBACK: MarketArtName = "market-product"

/**
 * Keyword rules, checked in order. Phrases are matched on word boundaries
 * against the normalised text (lowercase, `-`/`_`/punctuation as spaces).
 */
const KEYWORD_RULES: ReadonlyArray<readonly [MarketArtName, readonly string[]]> = [
  ["market-security", ["security", "access review", "vulnerability", "vulnerabilities", "threat", "phishing", "siem", "soc 2", "soc2", "identity", "password", "mfa"]],
  ["market-compliance", ["compliance", "audit", "audits", "policy", "policies", "gdpr", "hipaa", "sox", "regulatory", "governance", "legal", "contract review"]],
  ["market-new-customers", ["new customer", "new customers", "customer onboarding", "welcome", "activation", "signup", "sign up", "first value", "kickoff"]],
  ["market-onboarding", ["onboarding", "new hire", "new hires", "hiring", "recruiting", "recruitment", "talent", "employee", "hr"]],
  ["market-tickets", ["ticket", "tickets", "triage", "zendesk", "sla", "escalation", "escalations", "incident", "incidents", "helpdesk", "help desk", "backlog"]],
  ["market-prospecting", ["prospect", "prospects", "prospecting", "outbound", "scouting", "icp", "sdr", "target accounts", "account research", "competitor", "competitive"]],
  ["market-leads", ["lead", "leads", "enrichment", "enrich", "lead routing", "qualification", "inbound"]],
  ["market-deals", ["deal", "deals", "deal desk", "quote", "quotes", "proposal", "proposals", "contract", "contracts", "pricing approval", "closing"]],
  ["market-pipeline", ["pipeline", "forecast", "forecasting", "crm hygiene", "stage", "stages", "opportunity", "opportunities"]],
  ["market-site-health", ["site health", "website", "web", "seo", "uptime", "ai search", "geo", "brand radar", "platform health", "workflow health", "page speed"]],
  ["market-support", ["support", "customer success", "customer health", "health score", "renewal", "renewals", "retention", "churn", "qbr", "nps", "csat"]],
  ["market-campaigns", ["campaign", "campaigns", "marketing", "content", "attribution", "newsletter", "email marketing", "social", "brand", "launch"]],
  ["market-finance", ["finance", "financial", "invoice", "invoices", "accounting", "budget", "budgets", "variance", "cash", "cash flow", "expense", "expenses", "payroll", "cfo", "billing", "reconciliation", "month end close"]],
  ["market-revenue", ["revenue", "revops", "arr", "mrr", "bookings", "executive", "board", "kpi", "kpis", "growth"]],
  ["market-product", ["product", "feedback", "roadmap", "feature", "features", "release", "engineering"]],
]

const DEPARTMENT_ART: Record<string, MarketArtName> = {
  sales: "market-pipeline",
  marketing: "market-campaigns",
  finance: "market-finance",
  accounting: "market-finance",
  support: "market-support",
  "customer support": "market-support",
  "customer success": "market-support",
  cs: "market-support",
  "revenue operations": "market-revenue",
  revops: "market-revenue",
  executive: "market-revenue",
  product: "market-product",
  engineering: "market-product",
  security: "market-security",
  it: "market-security",
  legal: "market-compliance",
  compliance: "market-compliance",
  hr: "market-onboarding",
  "human resources": "market-onboarding",
  people: "market-onboarding",
  operations: "market-tickets",
  msp: "market-tickets",
  platform: "market-site-health",
}

const ASSET_TYPE_ART: Record<string, MarketArtName> = {
  knowledge_pack: "market-compliance",
  dataset_pack: "market-revenue",
  dashboard_pack: "market-revenue",
  connector_config: "market-product",
  capability_package: "market-product",
}

export function normaliseArtText(value: string | null | undefined): string {
  return ` ${String(value ?? "")
    .toLowerCase()
    .replace(/&/g, " and ")
    .replace(/[^a-z0-9]+/g, " ")
    .trim()} `
}

function hasPhrase(text: string, phrase: string): boolean {
  return text.includes(` ${phrase} `)
}

export interface MarketArtInput {
  title?: string | null
  slug?: string | null
  category?: string | null
  department?: string | null
  tags?: readonly string[] | null
  assetType?: string | null
  useCase?: string | null
}

export function marketArtFor(name: MarketArtName): MarketArt {
  const meta = ART[name]
  return { name, label: meta.label, alt: meta.alt, src: `/illustrations/${name}.svg` }
}

/** Resolve the market-* illustration name for a marketplace asset. */
export function resolveMarketArtName(asset: MarketArtInput): MarketArtName {
  // Own words first: title is the strongest signal, then tags/category/use case.
  const sources = [
    asset.title,
    asset.slug,
    ...(asset.tags ?? []),
    asset.category,
    asset.useCase,
  ]
  const text = sources.map(normaliseArtText).join(" ")
  for (const [name, phrases] of KEYWORD_RULES) {
    if (phrases.some((phrase) => hasPhrase(text, phrase))) return name
  }
  const department = normaliseArtText(asset.department).trim()
  if (department && DEPARTMENT_ART[department]) return DEPARTMENT_ART[department]
  const assetType = String(asset.assetType ?? "").toLowerCase()
  if (assetType && ASSET_TYPE_ART[assetType]) return ASSET_TYPE_ART[assetType]
  return MARKET_ART_FALLBACK
}

/** Resolve the full art record (name, label, alt, src) for a marketplace asset. */
export function resolveMarketArt(asset: MarketArtInput): MarketArt {
  return marketArtFor(resolveMarketArtName(asset))
}
