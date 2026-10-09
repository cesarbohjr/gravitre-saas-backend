/**
 * Builds the authoritative provider logo registry (fully offline).
 *
 * Source order per provider:
 *   1. Official multicolour asset already in the repo, when the brand's mark is
 *      multicolour and Simple Icons only ships a single-colour glyph
 *      (Google, Gmail, Slack, Microsoft, Drive, Calendar, Figma, Canva, ...).
 *   2. Simple Icons (brand-colour + white variants written to public/brand-logos).
 *   3. Official asset already in the repo (theSVG, stored byte-for-byte) for
 *      brands delisted from Simple Icons (Salesforce, LinkedIn, Pipedrive, ...).
 *   4. Neutral category fallback — rendered as a Lucide glyph, never initials
 *      and never a drawn approximation of the brand.
 *
 * Contrast treatment is computed here from the brand hex so components never
 * guess per brand:
 *   - dark theme: brand colour when it reads on Carbon surfaces, otherwise the
 *     white variant of the same official glyph;
 *   - light theme: a small ink plate only when the brand colour is too pale
 *     to read on white (e.g. Mailchimp yellow).
 *
 * Run:  node scripts/build-provider-registry.mjs
 * Out:  public/brand-logos/<slug>.svg, <slug>-white.svg
 *       lib/provider-registry.generated.json
 */
import { mkdir, writeFile, access } from "node:fs/promises"
import { fileURLToPath } from "node:url"
import { dirname, join } from "node:path"
import * as simpleIcons from "simple-icons"

const __dirname = dirname(fileURLToPath(import.meta.url))
const webRoot = join(__dirname, "..")
const brandDir = join(webRoot, "public", "brand-logos")
const outPath = join(webRoot, "lib", "provider-registry.generated.json")

const DARK_SURFACE = "#111315"
const LIGHT_SURFACE = "#FFFFFF"
const MIN_DARK_CONTRAST = 2.5
const MIN_LIGHT_CONTRAST = 1.6

/**
 * id: canonical provider id (matches lib/connectors vendorKey where one exists).
 * si: Simple Icons slug to try. asset: official repo asset (public path).
 * preferAsset: the official mark is multicolour; use the asset over the mono glyph.
 *   Only for assets that are the bare mark — never ones that bake in a tile or plate.
 * darkPlate: the official asset has dark ink that disappears on Carbon surfaces.
 */
const PROVIDERS = [
  // CRM / Marketing
  { id: "salesforce", name: "Salesforce", category: "crm", asset: "/vendor-logos/salesforce.svg" },
  { id: "hubspot", name: "HubSpot", category: "crm", si: "hubspot" },
  { id: "pipedrive", name: "Pipedrive", category: "crm", asset: "/vendor-logos/pipedrive.svg" },
  { id: "google_analytics", name: "Google Analytics", category: "analytics", si: "googleanalytics", asset: "/connector-logos/google_analytics.svg", preferAsset: true },
  { id: "google_ads", name: "Google Ads", category: "marketing", si: "googleads", asset: "/connector-logos/google_ads.svg" },
  { id: "google_search_console", name: "Google Search Console", category: "analytics", si: "googlesearchconsole" },
  { id: "marketo", name: "Marketo", category: "marketing", asset: "/vendor-logos/marketo.svg", preferAsset: true },
  { id: "segment", name: "Segment", category: "analytics", asset: "/vendor-logos/segment.svg", preferAsset: true },
  { id: "mailchimp", name: "Mailchimp", category: "marketing", si: "mailchimp" },
  { id: "mixpanel", name: "Mixpanel", category: "analytics", si: "mixpanel" },
  { id: "constant_contact", name: "Constant Contact", category: "marketing", asset: "/vendor-logos/constant_contact.svg", preferAsset: true },
  { id: "hootsuite", name: "Hootsuite", category: "marketing", si: "hootsuite" },
  { id: "semrush", name: "Semrush", category: "analytics", si: "semrush" },
  { id: "ahrefs", name: "Ahrefs", category: "analytics", asset: "/connector-logos/ahrefs.svg" },
  { id: "finseo", name: "Finseo", category: "analytics" },
  { id: "ai_visibility_ui", name: "AI Visibility UI", category: "analytics" },
  { id: "stackadapt", name: "StackAdapt", category: "marketing" },
  // Sales / Prospecting
  { id: "linkedin", name: "LinkedIn", category: "sales", asset: "/vendor-logos/linkedin.svg" },
  { id: "apollo", name: "Apollo.io", category: "sales", asset: "/connector-logos/apollo.svg", aliases: ["apolloio", "apolloai"] },
  { id: "clay", name: "Clay", category: "sales", asset: "/connector-logos/clay.svg", aliases: ["claycom"] },
  { id: "zoominfo", name: "ZoomInfo", category: "sales", asset: "/vendor-logos/zoominfo.svg", preferAsset: true },
  { id: "pdl", name: "People Data Labs", category: "sales", aliases: ["peopledatalabs"], asset: "/vendor-logos/pdl.svg", preferAsset: true },
  { id: "linkedin_sales_navigator", name: "LinkedIn Sales Navigator", category: "sales", asset: "/vendor-logos/linkedin.svg" },
  // Knowledge bases (Gravitre-managed public data)
  { id: "fred", name: "FRED", category: "knowledge" },
  { id: "sec_edgar", name: "SEC EDGAR", category: "knowledge" },
  { id: "world_bank", name: "World Bank", category: "knowledge", asset: "/vendor-logos/world_bank.svg", preferAsset: true },
  { id: "oecd", name: "OECD", category: "knowledge" },
  { id: "opencorporates", name: "OpenCorporates", category: "knowledge" },
  { id: "nvd", name: "NVD", category: "knowledge" },
  { id: "cisa_kev", name: "CISA KEV", category: "knowledge" },
  // Payments / Finance
  { id: "stripe", name: "Stripe", category: "finance", si: "stripe" },
  { id: "paypal", name: "PayPal", category: "finance", si: "paypal" },
  { id: "quickbooks", name: "QuickBooks", category: "finance", si: "quickbooks" },
  { id: "netsuite", name: "NetSuite", category: "finance", asset: "/vendor-logos/netsuite.svg", preferAsset: true },
  { id: "xero", name: "Xero", category: "finance", si: "xero" },
  { id: "plaid", name: "Plaid", category: "finance", asset: "/vendor-logos/plaid.svg", preferAsset: true, darkPlate: true },
  { id: "shopify", name: "Shopify", category: "commerce", si: "shopify" },
  // Communication
  { id: "slack", name: "Slack", category: "communication", asset: "/vendor-logos/slack.svg" },
  { id: "microsoft_teams", name: "Microsoft Teams", category: "communication", si: "microsoftteams", aliases: ["teams"], asset: "/vendor-logos/microsoft_teams.svg", preferAsset: true },
  { id: "microsoft365", name: "Microsoft 365", category: "communication", asset: "/vendor-logos/microsoft365.svg", aliases: ["microsoft_365"] },
  { id: "microsoft", name: "Microsoft", category: "communication", asset: "/vendor-logos/microsoft365.svg", aliases: ["azure_sql", "azure_blob", "synapse", "mssql"] },
  { id: "gmail", name: "Gmail", category: "email", si: "gmail", asset: "/vendor-logos/gmail.svg", preferAsset: true },
  { id: "google_calendar", name: "Google Calendar", category: "communication", si: "googlecalendar", asset: "/connector-logos/google_calendar.svg" },
  { id: "outlook", name: "Outlook", category: "email", asset: "/vendor-logos/outlook.svg" },
  { id: "twilio", name: "Twilio", category: "communication", si: "twilio", asset: "/vendor-logos/twilio.svg", preferAsset: true },
  { id: "sendgrid", name: "SendGrid", category: "email", si: "sendgrid", asset: "/vendor-logos/sendgrid.svg", preferAsset: true },
  { id: "email", name: "Email (SMTP)", category: "email" },
  { id: "brevo", name: "Brevo", category: "email", si: "brevo" },
  { id: "vapi", name: "Vapi", category: "communication", asset: "/vendor-logos/vapi.svg" },
  // DevOps / Incidents
  { id: "gitlab", name: "GitLab", category: "devops", si: "gitlab" },
  { id: "okta", name: "Okta", category: "devops", si: "okta" },
  { id: "connectwise", name: "ConnectWise", category: "devops", asset: "/vendor-logos/connectwise.svg" },
  { id: "pagerduty", name: "PagerDuty", category: "devops", si: "pagerduty" },
  { id: "github", name: "GitHub", category: "devops", si: "github" },
  // Operations / Workflow
  { id: "notion", name: "Notion", category: "productivity", si: "notion" },
  { id: "confluence", name: "Confluence", category: "productivity", si: "confluence" },
  { id: "jira", name: "Jira", category: "productivity", si: "jira" },
  { id: "airtable", name: "Airtable", category: "productivity", si: "airtable" },
  { id: "asana", name: "Asana", category: "productivity", si: "asana" },
  { id: "monday", name: "monday.com", category: "productivity", si: "mondaydotcom", aliases: ["mondaycom"], asset: "/vendor-logos/monday.svg", preferAsset: true },
  { id: "clickup", name: "ClickUp", category: "productivity", si: "clickup" },
  { id: "linear", name: "Linear", category: "productivity", si: "linear" },
  { id: "zapier", name: "Zapier", category: "automation", si: "zapier" },
  { id: "n8n", name: "n8n", category: "automation", si: "n8n" },
  { id: "motion", name: "Motion", category: "productivity" },
  { id: "odoo", name: "Odoo", category: "productivity", si: "odoo" },
  // Customer Support
  { id: "zendesk", name: "Zendesk", category: "support", si: "zendesk" },
  { id: "intercom", name: "Intercom", category: "support", si: "intercom" },
  { id: "freshdesk", name: "Freshdesk", category: "support", si: "freshdesk", asset: "/vendor-logos/freshdesk.svg", preferAsset: true },
  { id: "freshservice", name: "Freshservice", category: "support", asset: "/vendor-logos/freshservice.svg", preferAsset: true },
  { id: "gorgias", name: "Gorgias", category: "support", asset: "/vendor-logos/gorgias.svg", preferAsset: true },
  // HR / People
  { id: "workday", name: "Workday", category: "hr", si: "workday", asset: "/vendor-logos/workday.svg", preferAsset: true },
  { id: "bamboohr", name: "BambooHR", category: "hr", si: "bamboohr", asset: "/vendor-logos/bamboohr.svg", preferAsset: true },
  { id: "greenhouse", name: "Greenhouse", category: "hr", si: "greenhouse" },
  { id: "gusto", name: "Gusto", category: "hr", si: "gusto" },
  { id: "adp", name: "ADP", category: "hr", si: "adp" },
  // Storage / Data / Infra
  { id: "aws_s3", name: "Amazon S3", category: "storage", si: "amazons3", asset: "/vendor-logos/aws_s3.svg", preferAsset: true },
  { id: "aws", name: "AWS", category: "storage", si: "amazonwebservices", aliases: ["amazon", "rds", "kinesis", "dynamodb"], asset: "/vendor-logos/aws.svg", preferAsset: true },
  { id: "postgresql", name: "PostgreSQL", category: "data", si: "postgresql", aliases: ["postgres"] },
  { id: "mongodb", name: "MongoDB", category: "data", si: "mongodb" },
  { id: "snowflake", name: "Snowflake", category: "data", si: "snowflake" },
  { id: "mysql", name: "MySQL", category: "data", si: "mysql" },
  { id: "oracle", name: "Oracle", category: "data", si: "oracle", asset: "/vendor-logos/oracle.svg", preferAsset: true },
  { id: "bigquery", name: "BigQuery", category: "data", si: "googlebigquery" },
  { id: "redshift", name: "Amazon Redshift", category: "data", si: "amazonredshift", asset: "/vendor-logos/redshift.svg", preferAsset: true },
  { id: "databricks", name: "Databricks", category: "data", si: "databricks" },
  { id: "elasticsearch", name: "Elasticsearch", category: "data", si: "elasticsearch" },
  { id: "redis", name: "Redis", category: "data", si: "redis" },
  { id: "mariadb", name: "MariaDB", category: "data", si: "mariadb" },
  { id: "supabase", name: "Supabase", category: "data", si: "supabase", aliases: ["supabase_db"] },
  { id: "pinecone", name: "Pinecone", category: "data", si: "pinecone" },
  { id: "clickhouse", name: "ClickHouse", category: "data", si: "clickhouse" },
  { id: "cockroachdb", name: "CockroachDB", category: "data", si: "cockroachlabs" },
  { id: "duckdb", name: "DuckDB", category: "data", si: "duckdb" },
  { id: "weaviate", name: "Weaviate", category: "data", si: "weaviate" },
  { id: "qdrant", name: "Qdrant", category: "data", si: "qdrant" },
  { id: "neon", name: "Neon", category: "data", si: "neon" },
  { id: "planetscale", name: "PlanetScale", category: "data", si: "planetscale" },
  { id: "google_drive", name: "Google Drive", category: "storage", si: "googledrive", asset: "/connector-logos/google_drive.svg", preferAsset: true },
  { id: "google_docs", name: "Google Docs", category: "storage", si: "googledocs" },
  { id: "google_sheets", name: "Google Sheets", category: "storage", si: "googlesheets" },
  { id: "google", name: "Google", category: "storage", si: "google", asset: "/vendor-logos/google.svg", preferAsset: true, aliases: ["cloud_sql", "firestore", "gcs", "pubsub", "google_cloud"] },
  { id: "clio", name: "Clio", category: "productivity", asset: "/vendor-logos/clio.svg" },
  // Learning / Creative
  { id: "absorb_lms", name: "Absorb LMS", category: "learning", asset: "/vendor-logos/absorb_lms.svg", preferAsset: true },
  { id: "canva", name: "Canva", category: "design", asset: "/connector-logos/canva.svg" },
  { id: "figma", name: "Figma", category: "design", si: "figma", asset: "/connector-logos/figma.svg" },
  // Catalog vendors added with official marks (vendor assets via Nango/Airbyte connector libraries, or Simple Icons)
  { id: "servicenow", name: "ServiceNow", category: "support", asset: "/vendor-logos/servicenow.svg" },
  { id: "connectsecure", name: "ConnectSecure", category: "devops", asset: "/vendor-logos/connectsecure.svg" },
  { id: "sage_intacct", name: "Sage Intacct", category: "finance", si: "sage" },
  { id: "front", name: "Front", category: "support", asset: "/vendor-logos/front.svg" },
  { id: "gong", name: "Gong", category: "sales", asset: "/vendor-logos/gong.svg" },
  { id: "highlevel", name: "HighLevel", category: "crm", asset: "/vendor-logos/highlevel.svg" },
  { id: "instantly", name: "Instantly", category: "sales", asset: "/vendor-logos/instantly.svg" },
  { id: "attio", name: "Attio", category: "crm", asset: "/vendor-logos/attio.svg" },
  { id: "close", name: "Close", category: "crm", asset: "/vendor-logos/close.svg" },
  { id: "ashby", name: "Ashby", category: "hr", asset: "/vendor-logos/ashby.svg" },
  { id: "hibob", name: "HiBob", category: "hr", si: "hibob" },
  { id: "ukg_pro", name: "UKG Pro", category: "hr", asset: "/vendor-logos/ukg_pro.svg", darkPlate: true },
  { id: "box", name: "Box", category: "storage", si: "box" },
  { id: "dropbox", name: "Dropbox", category: "storage", si: "dropbox" },
  { id: "zoom", name: "Zoom", category: "communication", si: "zoom" },
  { id: "discord", name: "Discord", category: "communication", si: "discord" },
  { id: "sap_s4hana_cloud", name: "SAP S/4HANA Cloud", category: "finance", si: "sap" },
  { id: "sharepoint_online", name: "SharePoint Online", category: "storage", asset: "/vendor-logos/sharepoint_online.svg" },
  { id: "kustomer", name: "Kustomer", category: "support", asset: "/vendor-logos/kustomer.svg" },
  { id: "helpscout", name: "Help Scout", category: "support", si: "helpscout" },
  { id: "copper", name: "Copper", category: "crm", asset: "/vendor-logos/copper.svg" },
  { id: "zoho_crm", name: "Zoho CRM", category: "crm", si: "zoho" },
  { id: "lever", name: "Lever", category: "hr", asset: "/vendor-logos/lever.svg" },
  { id: "deel", name: "Deel", category: "hr", asset: "/vendor-logos/deel.svg", darkPlate: true },
  { id: "rippling", name: "Rippling", category: "hr", asset: "/vendor-logos/rippling.svg" },
  { id: "personio", name: "Personio", category: "hr", si: "personio" },
  { id: "ramp", name: "Ramp", category: "finance", asset: "/vendor-logos/ramp.svg" },
  { id: "brex", name: "Brex", category: "finance", si: "brex" },
  { id: "chargebee", name: "Chargebee", category: "finance", asset: "/vendor-logos/chargebee.svg" },
  { id: "docusign", name: "DocuSign", category: "productivity", asset: "/vendor-logos/docusign.svg" },
  { id: "dropbox_sign", name: "Dropbox Sign", category: "productivity", asset: "/vendor-logos/dropbox_sign.svg" },
  { id: "pax8", name: "Pax8", category: "devops", asset: "/vendor-logos/pax8.svg" },
  { id: "autotask", name: "Autotask PSA", category: "devops", asset: "/vendor-logos/autotask.svg" },
  { id: "huntress", name: "Huntress", category: "devops", asset: "/vendor-logos/huntress.svg" },
  { id: "sentinelone", name: "SentinelOne", category: "devops", asset: "/vendor-logos/sentinelone.svg" },
  { id: "crowdstrike", name: "CrowdStrike", category: "devops", asset: "/vendor-logos/crowdstrike.svg" },
  { id: "jumpcloud", name: "JumpCloud", category: "devops", asset: "/vendor-logos/jumpcloud.svg" },
  { id: "duo", name: "Duo", category: "devops", asset: "/vendor-logos/duo.svg" },
  { id: "onepassword", name: "1Password", category: "devops", si: "1password" },
  { id: "microsoft_intune", name: "Microsoft Intune", category: "devops", asset: "/vendor-logos/microsoft_intune.svg" },
  { id: "jamf_pro", name: "Jamf Pro", category: "devops", asset: "/vendor-logos/jamf_pro.svg" },
  { id: "braintree", name: "Braintree", category: "finance", si: "braintree" },
  { id: "recurly", name: "Recurly", category: "finance", asset: "/vendor-logos/recurly.svg" },
  // Model providers
  { id: "openai", name: "OpenAI", category: "ai", si: "openai", asset: "/vendor-logos/openai.svg", preferAsset: true },
  { id: "anthropic", name: "Anthropic", category: "ai", si: "anthropic", aliases: ["claude"] },
  { id: "xai", name: "xAI", category: "ai", si: "xai", asset: "/vendor-logos/xai.svg", preferAsset: true },
  { id: "meta", name: "Meta", category: "ai", si: "meta", aliases: ["meta_marketing", "meta_ads", "facebook_ads"] },
  { id: "mistral", name: "Mistral AI", category: "ai", si: "mistralai" },
  { id: "huggingface", name: "Hugging Face", category: "ai", si: "huggingface" },
]

const bySlug = {}
for (const icon of Object.values(simpleIcons)) {
  if (icon && typeof icon === "object" && icon.slug && icon.path) bySlug[icon.slug] = icon
}

function luminance(hex) {
  const n = hex.replace("#", "")
  const [r, g, b] = [0, 2, 4].map((i) => {
    const c = parseInt(n.slice(i, i + 2), 16) / 255
    return c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4
  })
  return 0.2126 * r + 0.7152 * g + 0.0722 * b
}

function contrast(a, b) {
  const [hi, lo] = [luminance(a), luminance(b)].sort((x, y) => y - x)
  return (hi + 0.05) / (lo + 0.05)
}

function svgFor(icon, fill) {
  return `<svg role="img" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg"><path fill="${fill}" d="${icon.path}"/></svg>\n`
}

async function exists(publicPath) {
  try {
    await access(join(webRoot, "public", publicPath))
    return true
  } catch {
    return false
  }
}

async function main() {
  await mkdir(brandDir, { recursive: true })
  const providers = {}
  const report = []

  for (const p of PROVIDERS) {
    const icon = p.si ? bySlug[p.si] : undefined
    const hasAsset = p.asset ? await exists(p.asset) : false
    const base = { id: p.id, name: p.name, category: p.category, aliases: p.aliases ?? [] }

    let entry
    if (hasAsset && (p.preferAsset || !icon)) {
      entry = {
        ...base,
        source: "official-asset",
        src: p.asset,
        ...(icon ? { hex: `#${icon.hex}`, simpleIcon: p.si } : {}),
        darkPlate: Boolean(p.darkPlate),
        lightPlate: false,
      }
    } else if (icon) {
      const hex = `#${icon.hex}`
      await writeFile(join(brandDir, `${icon.slug}.svg`), svgFor(icon, hex), "utf8")
      await writeFile(join(brandDir, `${icon.slug}-white.svg`), svgFor(icon, "#ffffff"), "utf8")
      const darkReadable = contrast(hex, DARK_SURFACE) >= MIN_DARK_CONTRAST
      entry = {
        ...base,
        source: "simple-icons",
        simpleIcon: icon.slug,
        hex,
        src: `/brand-logos/${icon.slug}.svg`,
        srcDark: darkReadable ? `/brand-logos/${icon.slug}.svg` : `/brand-logos/${icon.slug}-white.svg`,
        darkPlate: false,
        lightPlate: contrast(hex, LIGHT_SURFACE) < MIN_LIGHT_CONTRAST,
      }
    } else {
      entry = { ...base, source: "fallback", darkPlate: false, lightPlate: false }
    }
    providers[p.id] = entry
    report.push(`${p.id.padEnd(26)} ${entry.source.padEnd(15)} ${p.si && !icon ? `(si:${p.si} missing)` : ""}`)
  }

  await writeFile(outPath, JSON.stringify({ providers }, null, 2) + "\n", "utf8")
  console.log(report.join("\n"))
  const counts = Object.values(providers).reduce((acc, e) => ((acc[e.source] = (acc[e.source] ?? 0) + 1), acc), {})
  console.log("\n", counts)
}

main().catch((err) => {
  console.error(err)
  process.exit(1)
})
