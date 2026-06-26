/**
 * Vendors Simple Icons brand logos locally so the app renders exact official
 * marks fully offline (no runtime CDN dependency).
 *
 * Generates the SVGs from the `simple-icons` npm package (offline). For each
 * vendor it writes a brand-color SVG and a white SVG. Brands that have been
 * delisted from Simple Icons for trademark reasons (Slack, Salesforce,
 * LinkedIn, Oracle, Amazon S3, Google/Microsoft, ...) are simply absent from
 * the package and get omitted from the manifest, so the app falls back to its
 * inline logos / initials.
 *
 * Run:  node scripts/fetch-brand-logos.mjs
 * Out:  public/brand-logos/<slug>.svg, <slug>-white.svg
 *       lib/brand-logos-manifest.json  ({ vendorKey: slug })
 */
import { mkdir, writeFile } from "node:fs/promises"
import { fileURLToPath } from "node:url"
import { dirname, join } from "node:path"
import * as simpleIcons from "simple-icons"

const __dirname = dirname(fileURLToPath(import.meta.url))
const webRoot = join(__dirname, "..")
const outDir = join(webRoot, "public", "brand-logos")
const manifestPath = join(webRoot, "lib", "brand-logos-manifest.json")

// vendorKey (as resolved by lib/connectors connectorVendorKey) -> Simple Icons slug.
// Where omitted, the slug equals the vendorKey with separators stripped.
const SLUG_OVERRIDES = {
  aws_s3: "amazons3",
  monday: "mondaydotcom",
  bigquery: "googlebigquery",
  google_analytics: "googleanalytics",
  google_calendar: "googlecalendar",
  google_drive: "googledrive",
  google_docs: "googledocs",
  google_sheets: "googlesheets",
  microsoft_teams: "microsoftteams",
  constant_contact: "constantcontact",
  openai: "openai",
  anthropic: "anthropic",
  xai: "xai",
  aws: "amazonaws",
  linear: "linear",
  pinecone: "pinecone",
  clickhouse: "clickhouse",
  cockroachdb: "cockroachdb",
  duckdb: "duckdb",
  weaviate: "weaviate",
  qdrant: "qdrant",
  meta: "meta",
}

// Full vendor universe (connector registry + marketing apps + data-source types).
const VENDOR_KEYS = [
  "adp", "airtable", "apollo", "asana", "aws_s3", "bamboohr", "canva", "figma",
  "clickup", "confluence", "constant_contact", "freshdesk", "github", "gmail",
  "google", "google_analytics", "google_calendar", "google_docs",
  "google_drive", "google_sheets", "gorgias", "greenhouse", "gusto",
  "hootsuite", "hubspot", "intercom", "jira", "linkedin", "mailchimp",
  "marketo", "microsoft365", "microsoft_teams", "mixpanel", "monday",
  "mongodb", "motion", "n8n", "netsuite", "notion", "odoo", "outlook",
  "pagerduty", "plaid", "postgresql", "quickbooks", "salesforce", "segment",
  "semrush", "sendgrid", "slack", "snowflake", "stackadapt", "stripe",
  "twilio", "workday", "xero", "zapier", "zendesk",
  "openai", "anthropic", "xai", "meta", "linear", "aws",
  // data-source types
  "mysql", "oracle", "bigquery", "redshift", "databricks", "elasticsearch",
  "redis", "mariadb", "supabase", "pinecone", "clickhouse", "cockroachdb",
  "duckdb", "weaviate", "qdrant",
]

// Build a slug -> icon lookup from the package (export names are mangled).
const bySlug = {}
for (const icon of Object.values(simpleIcons)) {
  if (icon && typeof icon === "object" && icon.slug && icon.path) {
    bySlug[icon.slug] = icon
  }
}

function slugFor(vendorKey) {
  return SLUG_OVERRIDES[vendorKey] ?? vendorKey.replace(/[_\s.]/g, "")
}

function svgFor(icon, fill) {
  return (
    `<svg role="img" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">` +
    `<path fill="${fill}" d="${icon.path}"/></svg>\n`
  )
}

async function main() {
  await mkdir(outDir, { recursive: true })
  const manifest = {}
  const skipped = []

  for (const vendorKey of VENDOR_KEYS) {
    const slug = slugFor(vendorKey)
    const icon = bySlug[slug]
    if (!icon) {
      skipped.push(`${vendorKey} (${slug})`)
      continue
    }
    await writeFile(join(outDir, `${slug}.svg`), svgFor(icon, `#${icon.hex}`), "utf8")
    await writeFile(join(outDir, `${slug}-white.svg`), svgFor(icon, "#ffffff"), "utf8")
    manifest[vendorKey] = slug
  }

  await writeFile(manifestPath, JSON.stringify(manifest, null, 2) + "\n", "utf8")
  console.log(`Vendored ${Object.keys(manifest).length}:`, Object.keys(manifest).join(", "))
  console.log(`\nSkipped ${skipped.length} (fall back to inline/initials):`, skipped.join(", "))
}

main().catch((err) => {
  console.error(err)
  process.exit(1)
})
