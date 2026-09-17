import { readFileSync } from "node:fs"
import { resolve } from "node:path"
import { describe, expect, it } from "vitest"

/**
 * Phase 1B selected-entity trace (frontend contract).
 * Backend ResearchScope is an enum of retrieval breadth — not an entity id.
 */
const RESEARCH_SCOPE_ENUM = [
  "internal_only",
  "intelligence_packs",
  "internet_research",
  "everything",
] as const

describe("selected entity must not be smuggled through research_scope", () => {
  it("entity coordinates are not valid ResearchScope values", () => {
    const smuggled = "/intelligence:entity:acme:Acme Corporation"
    expect(RESEARCH_SCOPE_ENUM.includes(smuggled as (typeof RESEARCH_SCOPE_ENUM)[number])).toBe(
      false,
    )
  })

  it("canonical chat transport body sends workspace_focus and not selected entity on research_scope", () => {
    const src = readFileSync(resolve(__dirname, "../../app/ai/_components/ai-workspace.tsx"), "utf8")
    const start = src.indexOf("body: () => {")
    const end = src.indexOf("useChat({")
    const bodyFn = src.slice(start, end)
    expect(bodyFn).toMatch(/workspace_focus/)
    expect(bodyFn).toMatch(/agent_id/)
    expect(bodyFn).toMatch(/research_scope: researchScopeRef/)
    expect(bodyFn).not.toMatch(/research_scope: .*selected/)
  })
})
