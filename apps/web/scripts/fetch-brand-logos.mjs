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
const extRoot = join(webRoot, "..", "extension")
const outDir = join(webRoot, "public", "brand-logos")
const manifestPath = join(webRoot, "lib", "brand-logos-manifest.json")

// ---------------------------------------------------------------------------
// Vendor logos (full-colour official marks, from theSVG.org)
// ---------------------------------------------------------------------------
// Simple Icons ships single-path monochrome glyphs, and several of the vendors
// the browser extension actually detects (Slack, Salesforce, LinkedIn, Outlook,
// Microsoft) are absent from it entirely because those companies asked to be
// delisted. Mixing "monochrome where available, initials where not" is what the
// extension shipped before, and it reads as unfinished.
//
// So the extension's connector icons come from ONE source instead: theSVG's
// official full-colour marks. Same provenance for every vendor means one
// consistent scheme across the popup, side panel and overlay.
//
// Marks are stored byte-for-byte as published — never recoloured, cropped or
// composed — and are used nominatively to identify a real integration.
// Trademarks remain the property of their respective owners; review each
// brand's usage guidelines before shipping commercially.
const THESVG_CDN = "https://cdn.jsdelivr.net/gh/glincker/thesvg@main/public/icons"

// vendorKey -> theSVG slug. Only vendors the extension can surface, to keep the
// shipped extension bundle small.
const VENDOR_LOGOS = {
  hubspot: "hubspot",
  apollo: "apollodotio",
  salesforce: "salesforce",
  slack: "slack",
  linkedin: "linkedin",
  gmail: "gmail",
  outlook: "microsoft-outlook",
  google: "google",
  microsoft365: "microsoft",
  notion: "notion",
  pipedrive: "pipedrive",
  zendesk: "zendesk",
  intercom: "intercom",
  stripe: "stripe",
  jira: "jira",
  asana: "asana",
  github: "github",
}

// Emitted to both apps so the two surfaces can never drift apart.
//
// The web app serves them statically from /public. The extension instead keeps
// them under src/assets so they get INLINED into the bundle: the overlay is a
// content script running on somebody else's page, where a root-relative path
// would resolve against the host site, and an extension:// asset URL would need
// web_accessible_resources and could still be blocked by the host page's own
// CSP. Inlining sidesteps all three problems.
const VENDOR_OUT_DIRS = [
  join(webRoot, "public", "vendor-logos"),
  join(extRoot, "src", "assets", "vendor-logos"),
]

const VENDOR_MANIFESTS = [
  join(webRoot, "lib", "vendor-logos-manifest.json"),
  join(extRoot, "src", "lib", "vendor-logos-manifest.json"),
]

async function fetchVendorLogos() {
  for (const dir of VENDOR_OUT_DIRS) await mkdir(dir, { recursive: true })

  const manifest = {}
  const failed = []

  for (const [vendorKey, slug] of Object.entries(VENDOR_LOGOS)) {
    const url = `${THESVG_CDN}/${slug}/default.svg`
    try {
      const res = await fetch(url)
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      const svg = await res.text()
      // Guard against a CDN error page being written out as a logo.
      if (!svg.trimStart().startsWith("<svg") || svg.length < 80) {
        throw new Error("not an SVG")
      }
      for (const dir of VENDOR_OUT_DIRS) {
        await writeFile(join(dir, `${vendorKey}.svg`), svg, "utf8")
      }
      manifest[vendorKey] = `${vendorKey}.svg`
    } catch (err) {
      failed.push(`${vendorKey} (${slug}): ${err.message}`)
    }
  }

  for (const path of VENDOR_MANIFESTS) {
    await writeFile(path, JSON.stringify(manifest, null, 2) + "\n", "utf8")
  }

  console.log(`\nVendor logos ${Object.keys(manifest).length}/${Object.keys(VENDOR_LOGOS).length}:`, Object.keys(manifest).join(", "))
  if (failed.length) console.error(`Vendor logo failures:\n  ${failed.join("\n  ")}`)
  return failed.length === 0
}

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
  google_search_console: "googlesearchconsole",
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
  "google_drive", "google_sheets", "google_search_console", "gorgias", "greenhouse", "gusto",
  "hootsuite", "hubspot", "intercom", "jira", "linkedin", "mailchimp",
  "marketo", "microsoft365", "microsoft_teams", "mixpanel", "monday",
  "mongodb", "motion", "n8n", "netsuite", "notion", "odoo", "outlook",
  "pagerduty", "plaid", "pipedrive", "postgresql", "quickbooks", "salesforce", "segment",
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

  // A half-written vendor set would silently ship blank icons, so fail loudly.
  const ok = await fetchVendorLogos()
  if (!ok) process.exit(1)
}

main().catch((err) => {
  console.error(err)
  process.exit(1)
})
