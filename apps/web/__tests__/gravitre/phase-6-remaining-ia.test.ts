import { readFileSync } from "node:fs"
import { resolve } from "node:path"
import { describe, expect, it } from "vitest"

const webRoot = resolve(__dirname, "../..")

describe("UX Reset Phase 6 — remaining hub IA flatten", () => {
  it("workflows default to a table, not a card grid", () => {
    const src = readFileSync(resolve(webRoot, "app/workflows/page.tsx"), "utf8")
    expect(src).toMatch(/useState<"grid" \| "table">\("table"\)/)
    expect(src).toMatch(/Totals/)
    expect(src).not.toMatch(/workflow\{runningCount > 1/)
    expect(src).not.toMatch(/isMobile \? "grid"/)
  })

  it("activity is a list, not a KPI dashboard wrap", () => {
    const src = readFileSync(resolve(webRoot, "app/activity/page.tsx"), "utf8")
    expect(src).not.toMatch(/label="Selected"/)
    expect(src).not.toMatch(/hint="Inspector focus"/)
    expect(src).toMatch(/AskGravitreSummonButton/)
  })

  it("marketplace type filters are text, not chips, and metrics are closed", () => {
    const src = readFileSync(resolve(webRoot, "app/marketplace/assets/page.tsx"), "utf8")
    expect(src).toMatch(/Catalog/)
    expect(src).not.toMatch(/FilterChip/)
    expect(src).toMatch(/TYPE_FILTERS\.map/)
    expect(src).toMatch(/data-review-surface="marketplace-discovery"/)
    expect(src).toMatch(/data-review-surface="marketplace-ops"/)
    expect(src).toMatch(/More about this pack/)
    expect(src).not.toMatch(/2xl:grid-cols-4/)
  })

  it("connector and workflow detail pages are sections, not card stacks", () => {
    const connector = readFileSync(resolve(webRoot, "app/connectors/[id]/page.tsx"), "utf8")
    const workflow = readFileSync(resolve(webRoot, "app/workflows/[id]/page.tsx"), "utf8")
    expect(connector).not.toMatch(/from \"@\/components\/ui\/card\"/)
    expect(connector).toMatch(/Usage metrics and activity logs are not recorded/)
    expect(workflow).not.toMatch(/from \"@\/components\/ui\/card\"/)
    expect(workflow).toMatch(/Run now/)
    expect(workflow).toMatch(/Edit in builder/)
  })

  it("agent profile uses text sections, not a pill tab strip", () => {
    const src = readFileSync(resolve(webRoot, "app/agents/[id]/page.tsx"), "utf8")
    expect(src).toMatch(/aria-label="Agent profile"/)
    expect(src).toMatch(/role="tablist"/)
    expect(src).toMatch(/OPERATIONAL_METHODOLOGY_SHORT/)
    // Hard-coded / duplicated numbers must not come back as profile metrics.
    expect(src).not.toMatch(/Needs Approval|Decisions Today|Skill overview|confidence<\/p>/)
    expect(src).not.toMatch(/rounded-\[var\(--np-radius-lg\)\] border border-divide bg-\[color:var\(--g-surface-2\)\] p-1/)
  })

  it("intelligence hub and training are text, not pill/card-first", () => {
    const hub = readFileSync(
      resolve(webRoot, "components/intelligence/intelligence-hub-tabs.tsx"),
      "utf8",
    )
    expect(hub).toMatch(/aria-label="Intelligence hub"/)
    expect(hub).not.toMatch(/<HubTabs/)
    expect(hub).toMatch(/TYPE\.meta/)

    const overview = readFileSync(
      resolve(webRoot, "components/gravitre/training-overview.tsx"),
      "utf8",
    )
    expect(overview).not.toMatch(/rounded-2xl/)
    expect(overview).not.toMatch(/bg-gradient-to-br/)

    const training = readFileSync(resolve(webRoot, "app/training/page.tsx"), "utf8")
    expect(training).toMatch(/aria-label="Training sections"/)
    expect(training).toMatch(/AskGravitreSummonButton/)
    expect(training).not.toMatch(/TabsList/)
    expect(training).not.toMatch(/IntelligenceHubTabs/)
    expect(training).not.toMatch(/rounded-2xl border border-border\/70 bg-card\/80/)

    const loop = readFileSync(
      resolve(webRoot, "components/gravitre/learning-surfaces-callout.tsx"),
      "utf8",
    )
    expect(loop).toMatch(/aria-label="Learning loop navigation"/)
    expect(loop).not.toMatch(/bg-gradient-to-br/)
    expect(loop).not.toMatch(/rounded-2xl/)
  })
})
