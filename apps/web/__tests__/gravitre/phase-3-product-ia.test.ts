import { readFileSync } from "node:fs"
import { resolve } from "node:path"
import { describe, expect, it } from "vitest"

import { DEFAULT_AGENTS_FLEET_PREFS } from "@/lib/agents-fleet-prefs"

const webRoot = resolve(__dirname, "../..")

describe("UX Reset Phase 3 — product IA flatten", () => {
  it("agents roster defaults to list, not team cards", () => {
    expect(DEFAULT_AGENTS_FLEET_PREFS.view).toBe("list")
    const src = readFileSync(resolve(webRoot, "app/agents/page.tsx"), "utf8")
    expect(src).not.toMatch(/ConnectorsAtmosphere/)
    const tabs = readFileSync(resolve(webRoot, "components/agents/agents-hub-tabs.tsx"), "utf8")
    expect(tabs).not.toMatch(/from \"@\/components\/gravitre\/hub-tabs\"/)
    expect(tabs).toMatch(/aria-label="Agents hub"/)
  })

  it("connectors default to a compact list without atmosphere", () => {
    const src = readFileSync(resolve(webRoot, "app/connectors/page.tsx"), "utf8")
    expect(src).toMatch(/useState<"topology" \| "grid">\("grid"\)/)
    expect(src).toMatch(/md:flex md:flex-col md:gap-2/)
    expect(src).not.toMatch(/ConnectorsAtmosphere/)
  })

  it("relationships map is not wrapped in a permanent evidence dashboard", () => {
    const src = readFileSync(resolve(webRoot, "app/intelligence/page.tsx"), "utf8")
    expect(src).toMatch(/Attention, learnings, and impact/)
    expect(src).toMatch(/<details className="mx-auto max-w-\[1600px\]/)
  })

  it("performance shows attribution before collapsed metrics", () => {
    const src = readFileSync(
      resolve(webRoot, "components/intelligence/pages/performance-stage.tsx"),
      "utf8",
    )
    const flow = src.indexOf("OutcomeAttributionFlow")
    const metrics = src.indexOf("Totals for the selected view")
    expect(flow).toBeGreaterThan(0)
    expect(metrics).toBeGreaterThan(flow)
  })
})
