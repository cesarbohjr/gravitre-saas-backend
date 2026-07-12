import { readFileSync } from "node:fs"
import path from "node:path"
import { describe, expect, it } from "vitest"

const COMPONENT = path.resolve(
  __dirname,
  "../../components/intelligence/heuristic-suggestion-cards.tsx",
)
const API = path.resolve(__dirname, "../../lib/api.ts")

describe("HeuristicSuggestionCards contract (STA-314)", () => {
  it("has navigation + dismiss only — no execute/apply/install handlers or buttons", () => {
    const source = readFileSync(COMPONENT, "utf8")
    expect(source).toContain('data-testid="heuristic-suggestion-cards"')
    expect(source).toContain("advisoryOnly")
    expect(source).toContain("Open")
    expect(source).toContain("href={card.href}")
    expect(source).toContain('data-testid="heuristic-card-dismiss"')
    expect(source).toContain("dismissHeuristicRecommendation")
    // Hard ban: no write/execute surface from the card.
    expect(source).not.toMatch(/\b(onExecute|handleExecute|executePlan|invoke_tool)\b/)
    expect(source).not.toMatch(/>\s*(Execute|Apply|Install|Run|Schedule)\s*</)
    expect(source).not.toContain("intelligenceApi.execute")
    expect(source).not.toContain("/execute")
  })

  it("api client exposes GET + dismiss — never an execute helper for heuristics", () => {
    const source = readFileSync(API, "utf8")
    expect(source).toContain("/api/intelligence/recommendations/heuristics")
    expect(source).toContain("dismissHeuristicRecommendation")
    expect(source).toContain("/dismiss")
    const heuristicsBlockStart = source.indexOf("heuristicRecommendations:")
    const heuristicsBlockEnd = source.indexOf("modelCatalog:", heuristicsBlockStart)
    const block = source.slice(heuristicsBlockStart, heuristicsBlockEnd)
    expect(block).not.toMatch(/execute|invoke_tool|execute_plan/i)
  })
})
