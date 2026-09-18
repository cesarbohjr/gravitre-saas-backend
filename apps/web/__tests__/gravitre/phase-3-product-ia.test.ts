import { readFileSync } from "node:fs"
import { resolve } from "node:path"
import { describe, expect, it } from "vitest"

import { DEFAULT_AGENTS_FLEET_PREFS, normalizeAgentsFleetPrefs } from "@/lib/agents-fleet-prefs"

const webRoot = resolve(__dirname, "../..")

describe("UX Reset Phase 3 — product IA flatten", () => {
  it("agents roster defaults to the operating team view", () => {
    expect(DEFAULT_AGENTS_FLEET_PREFS.view).toBe("team")
    expect(normalizeAgentsFleetPrefs({ version: 1, view: "list" }).view).toBe("team")
    expect(normalizeAgentsFleetPrefs({ version: 2, view: "list" }).view).toBe("list")
    const src = readFileSync(resolve(webRoot, "app/agents/page.tsx"), "utf8")
    expect(src).not.toMatch(/ConnectorsAtmosphere/)
    expect(src).not.toMatch(/NucleoAgent/)
    const identity = readFileSync(resolve(webRoot, "components/agents/fleet-v4/identity-tokens.ts"), "utf8")
    expect(identity).not.toMatch(/NucleoAgent/)
    expect(identity).not.toMatch(/NavSparkles/)
    expect(identity).not.toMatch(/NucleoIntelligence/)
    const team = readFileSync(resolve(webRoot, "components/agents/fleet-v4/team-view.tsx"), "utf8")
    expect(team).not.toMatch(/NodusGravitreHub/)
    expect(team).not.toMatch(/nodusGlow/)
    const inspector = readFileSync(
      resolve(webRoot, "components/agents/fleet-v4/agent-fleet-inspector.tsx"),
      "utf8",
    )
    expect(inspector).not.toMatch(/AgentIdentityAvatar/)
    const graph = readFileSync(resolve(webRoot, "components/agents/fleet-v4/graph-view.tsx"), "utf8")
    expect(graph).not.toMatch(/ConnectorsAtmosphere/)
    const tabs = readFileSync(resolve(webRoot, "components/agents/agents-hub-tabs.tsx"), "utf8")
    expect(tabs).not.toMatch(/from \"@\/components\/gravitre\/hub-tabs\"/)
    expect(tabs).toMatch(/aria-label="Agents hub"/)
  })

  it("connectors default to a compact list without atmosphere", () => {
    const src = readFileSync(resolve(webRoot, "app/connectors/page.tsx"), "utf8")
    expect(src).toMatch(/useState<"topology" \| "grid">\("grid"\)/)
    expect(src).toMatch(/variant="list"/)
    expect(src).toMatch(/data-gravitre-connector-row/)
    expect(src).not.toMatch(/ConnectorsAtmosphere/)
  })

  it("relationships map is not wrapped in a permanent evidence dashboard", () => {
    const src = readFileSync(resolve(webRoot, "app/intelligence/page.tsx"), "utf8")
    expect(src).toMatch(/Attention, learnings, and impact/)
    expect(src).toMatch(/<details className="mx-auto max-w-\[1600px\]/)
    expect(src).toMatch(/aria-label=\{group\.heading\}/)
    expect(src).not.toMatch(/hover:border-\[color:var\(--g-brand-border\)\]/)
    const workspace = readFileSync(
      resolve(webRoot, "components/intelligence/relationships/relationships-workspace.tsx"),
      "utf8",
    )
    expect(workspace).toMatch(/viewMode === "graph"/)
    expect(workspace).toMatch(/\{selection \?/)
    expect(workspace).not.toMatch(/RelationshipMetrics/)
    const toolbar = readFileSync(
      resolve(webRoot, "components/intelligence/relationships/relationship-toolbar.tsx"),
      "utf8",
    )
    expect(toolbar).toMatch(/Neighborhood/)
    expect(toolbar).toMatch(/>\s*Focus\s*</)
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

  it("settings preference chrome uses rows, not elevated cards", () => {
    const src = readFileSync(resolve(webRoot, "app/settings/page.tsx"), "utf8")
    expect(src).toMatch(/AI Operator/)
    const operatorIdx = src.indexOf("AI Operator")
    const operatorWindow = src.slice(Math.max(0, operatorIdx - 700), operatorIdx)
    expect(operatorWindow).toMatch(/border-b border-divide py-3/)
    expect(operatorWindow).not.toMatch(/shadow-\[var\(--np-shadow\)\]/)
    expect(src).toMatch(/Enable/)
  })
})
