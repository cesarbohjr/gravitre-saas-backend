import { readFileSync } from "node:fs"
import { resolve } from "node:path"
import { describe, expect, it } from "vitest"

const webRoot = resolve(__dirname, "../..")
const read = (path: string) => readFileSync(resolve(webRoot, path), "utf8")

describe("3.0 Plus final composition", () => {
  it("operating lanes size to content instead of the viewport", () => {
    const src = read("components/home/operating-flow.tsx")
    expect(src).toMatch(/data-flow-height="content"/)
    expect(src).not.toMatch(/100dvh-400px/)
    expect(src).not.toMatch(/h-\[420px\]/)
    expect(src).toMatch(/md:max-h-\[360px\] xl:max-h-\[440px\]/)
  })

  it("outcome flow sits directly under the KPI strip, before secondary widgets", () => {
    const src = read("components/home/home-dashboard.tsx")
    const sankey = src.indexOf("<OutcomeFlowSankey />")
    const grid = src.indexOf("{/* Desktop / tablet grid */}")
    expect(sankey).toBeGreaterThan(src.indexOf("</motion.dl>"))
    expect(sankey).toBeLessThan(grid)
  })

  it("outcome flow shows counts and backend pass rate only", () => {
    const src = read("components/home/outcome-flow-sankey.tsx")
    expect(src).toMatch(/counts, not value/)
    expect(src).toMatch(/row\.pass_rate != null/)
    expect(src).not.toMatch(/style:\s*["']currency["']|\bUSD\b|\bROI\b|savings/)
  })

  it("agent overview is a main field plus a knowledge rail", () => {
    const src = read("app/agents/[id]/page.tsx")
    expect(src).toMatch(/data-agent-main-field=""/)
    expect(src).toMatch(/data-agent-rail=""/)
    expect(src).toMatch(/<AgentAutonomyPanel agentId=\{agent\.id\} \/>/)
    expect(src).toMatch(/<AgentStrengthProfile/)
    expect(src).toMatch(/layout="rail"/)
    expect(src).toMatch(/variant="ruled"/)
    expect(src).not.toMatch(/Radar/)
  })

  it("connectors inspector column shows the operating summary when nothing is selected", () => {
    const src = read("app/connectors/page.tsx")
    expect(src).toMatch(/\) : \(\s*<ConnectorOperatingSummary/)
    expect(src).toMatch(/className="hidden xl:flex"/)
  })

  it("onboarding does not auto-complete connect without an active connector", () => {
    const src = read("components/gravitre/onboarding-checklist.tsx")
    expect(src).toMatch(/routeMatch\.stepKey === "connect" && !hasActiveConnector/)
    expect(src).toMatch(/\.catch\(\(\) => undefined\)/)
  })

  it("settings preference routes are called with auth headers", () => {
    for (const path of ["lib/agents-fleet-prefs.ts", "lib/dashboard/layout-storage.ts"]) {
      const src = read(path)
      expect(src).not.toMatch(/\bfetch\("\/api\/settings\//)
      expect(src).toMatch(/apiFetch\("\/api\/settings\//)
    }
  })

  it("marketplace saves requests stay within the backend limit (le=100)", () => {
    const src = read("components/marketplace/asset-save-button.tsx")
    expect(src).toMatch(/listSaves\(\{ limit: 100 \}\)/)
  })

  it("top bar org label is hydration-stable", () => {
    const src = read("components/gravitre/top-bar.tsx")
    expect(src).not.toMatch(/useState\(\(\) => getSelectedOrgFromStorage\(\)/)
    expect(src).toMatch(/useState\("Organization"\)/)
  })
})
