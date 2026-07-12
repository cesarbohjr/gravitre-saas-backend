import { readFileSync } from "node:fs"
import path from "node:path"
import { describe, expect, it } from "vitest"

const COMPONENT = path.resolve(
  __dirname,
  "../../components/intelligence/heuristic-suggestion-cards.tsx",
)

describe("HeuristicSuggestionCards contract (STA-314)", () => {
  it("has navigation only — no execute/apply/install handlers or buttons", () => {
    const source = readFileSync(COMPONENT, "utf8")
    expect(source).toContain('data-testid="heuristic-suggestion-cards"')
    expect(source).toContain("advisoryOnly")
    expect(source).toContain("Open")
    expect(source).toContain("href={card.href}")
    // Hard ban: no write/execute surface from the card.
    expect(source).not.toMatch(/\b(onExecute|handleExecute|executePlan|invoke_tool)\b/)
    expect(source).not.toMatch(/>\s*(Execute|Apply|Install|Run|Schedule)\s*</)
    expect(source).not.toContain("intelligenceApi.execute")
    expect(source).not.toContain("/execute")
  })
})
