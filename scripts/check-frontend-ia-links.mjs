#!/usr/bin/env node
/**
 * Static link checker for Frontend IA consolidation.
 * Fails if primary admin nav still points at retired top-level destinations.
 */
import fs from "node:fs"
import path from "node:path"
import { fileURLToPath } from "node:url"

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..")
const web = path.join(root, "apps", "web")

const RETIRED_NAV_HREFS = [
  'href: "/runs"',
  'href: "/outcomes"',
  'href: "/metrics"',
  'href: "/multi-agent-run"',
  'href: "/training"',
  'href: "/workflows/failure-predictions"',
  'href: "/intelligence/agents"',
  'href: "/settings/enterprise"',
  'href: "/settings/federation"',
  'href: "/environments"',
  'href: "/marketplace/analytics/roi"',
]

const MUST_HAVE_NAV = [
  "APP_ROUTES.activity",
  "APP_ROUTES.intelligence",
  "APP_ROUTES.settings",
  "APP_ROUTES.agents",
]

const configPath = path.join(web, "components", "gravitre", "sidebar-nav-config.ts")
const config = fs.readFileSync(configPath, "utf8")

const adminBlockMatch = config.match(
  /export const ADMIN_SIDEBAR_NAV[\s\S]*?export const LITE_SIDEBAR_NAV/,
)
const adminBlock = adminBlockMatch ? adminBlockMatch[0] : config

const failures = []

for (const needle of RETIRED_NAV_HREFS) {
  if (adminBlock.includes(needle)) {
    failures.push(`ADMIN_SIDEBAR_NAV still contains retired nav ${needle}`)
  }
}

for (const needle of MUST_HAVE_NAV) {
  if (!adminBlock.includes(needle)) {
    failures.push(`ADMIN_SIDEBAR_NAV missing required ${needle}`)
  }
}

const itemCount = [...adminBlock.matchAll(/name:\s*"/g)].length
if (itemCount > 16 || itemCount < 12) {
  failures.push(`admin nav item count out of range: ${itemCount} (target ~14–16)`)
}

const out = {
  checked_at: new Date().toISOString(),
  sidebar_config: configPath,
  admin_named_items: itemCount,
  failures,
  verdict: failures.length === 0 ? "PASS" : "FAIL",
}

const outPath = path.join(root, "docs", "delivery", "frontend-ia-link-check.json")
fs.mkdirSync(path.dirname(outPath), { recursive: true })
fs.writeFileSync(outPath, JSON.stringify(out, null, 2))
console.log(JSON.stringify(out, null, 2))
process.exit(failures.length === 0 ? 0 : 1)
