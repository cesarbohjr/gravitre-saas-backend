import { existsSync } from "node:fs"
import { join } from "node:path"
import { describe, expect, it } from "vitest"
import { PROVIDER_REGISTRY, hasProviderMark, resolveProvider } from "@/lib/provider-registry"
import { suggestRoleIcon } from "@/components/agents/fleet-v4/identity-tokens"
import { getCategoryIcon } from "@/lib/marketplace-category-icons"
import { DECISION_GEOMETRY, nodeAnchor } from "@/components/workflows/builder-node-chrome"

describe("provider registry", () => {
  it("resolves canonical ids, display names and aliases to one entry", () => {
    expect(resolveProvider("hubspot")?.id).toBe("hubspot")
    expect(resolveProvider("HubSpot")?.id).toBe("hubspot")
    expect(resolveProvider("google-drive")?.id).toBe("google_drive")
  })

  it("never ships a mark for fallback providers", () => {
    for (const entry of Object.values(PROVIDER_REGISTRY)) {
      if (entry.source === "fallback") expect(entry.src).toBeFalsy()
      else {
        expect(existsSync(join(process.cwd(), "public", entry.src!))).toBe(true)
        if (entry.srcDark) expect(existsSync(join(process.cwd(), "public", entry.srcDark))).toBe(true)
      }
    }
    expect(hasProviderMark("openai")).toBe(false)
    expect(hasProviderMark("not-a-real-vendor")).toBe(false)
  })
})

describe("agent role inference", () => {
  it.each([
    ["Pipeline Enrichment", "sales"],
    ["RevOps Analyst", "revops"],
    ["Churn Watch", "customer_success"],
    ["Competitive Intelligence", "research"],
    ["Access Review", "security"],
    ["Product Analytics", "analytics"],
    ["Mystery", "general"],
  ])("%s → %s", (name, role) => {
    expect(suggestRoleIcon("", name)).toBe(role)
  })
})

describe("marketplace asset glyphs", () => {
  it("uses role glyphs for agents and kind glyphs for workflows and knowledge", () => {
    expect(getCategoryIcon("workflow").label).toBe("Workflow")
    expect(getCategoryIcon("knowledge_pack").label).toBe("Knowledge")
    expect(getCategoryIcon("department_pack", "customer_success").label).toBe("Customer Success")
    expect(getCategoryIcon("department_pack", "unknown dept").label).toBe("Department pack")
  })
})

describe("decision anchors", () => {
  it("meet the diamond tips, centred in the node column", () => {
    const size = { w: DECISION_GEOMETRY.columnWidth, h: DECISION_GEOMETRY.square }
    const half = (DECISION_GEOMETRY.square / 2) * Math.SQRT2
    const top = nodeAnchor("decision", { x: 0, y: 0 }, size, "top")
    const right = nodeAnchor("decision", { x: 0, y: 0 }, size, "right")
    expect(top.x).toBe(DECISION_GEOMETRY.columnWidth / 2)
    expect(top.y).toBeCloseTo(DECISION_GEOMETRY.square / 2 - half)
    expect(right.x).toBeCloseTo(DECISION_GEOMETRY.columnWidth / 2 + half)
  })

  it("meet rectangle border midpoints for rect nodes", () => {
    expect(nodeAnchor("agent", { x: 10, y: 20 }, { w: 224, h: 80 }, "left")).toEqual({ x: 10, y: 60 })
    expect(nodeAnchor("agent", { x: 10, y: 20 }, { w: 224, h: 80 }, "bottom")).toEqual({ x: 122, y: 100 })
  })
})
