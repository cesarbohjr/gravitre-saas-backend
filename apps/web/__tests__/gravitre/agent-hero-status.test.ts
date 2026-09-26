import { readFileSync } from "node:fs"
import { resolve } from "node:path"
import { describe, expect, it } from "vitest"

const page = readFileSync(resolve(__dirname, "../../app/agents/[id]/page.tsx"), "utf8")

describe("agent detail identity hero", () => {
  it("shows status once, through the anchored chip, not also as an avatar dot", () => {
    const hero = page.slice(page.indexOf("function AgentIdentityHero"), page.indexOf("function AgentIdentityHero") + 2000)
    expect(hero).toContain("status.label")
    expect(hero).not.toContain("showStatusDot")
  })
})
