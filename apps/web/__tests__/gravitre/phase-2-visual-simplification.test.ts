import { readFileSync } from "node:fs"
import { resolve } from "node:path"
import { describe, expect, it } from "vitest"

const webRoot = resolve(__dirname, "../..")

describe("UX Reset Phase 2 — visual simplification", () => {
  it("empty landing is identity + composer + text suggestions, not a mode dashboard", () => {
    const src = readFileSync(resolve(webRoot, "app/ai/_components/ai-landing.tsx"), "utf8")
    expect(src).toMatch(/What do you want to get done/)
    expect(src).not.toMatch(/One surface, three modes/)
    expect(src).not.toMatch(/AI_MODES\.map/)
    expect(src).toMatch(/data-gravitre-ai-landing/)
  })

  it("Ask Gravitre entry is not a nested product card", () => {
    const src = readFileSync(
      resolve(webRoot, "components/intelligence/ask-gravitre-composer.tsx"),
      "utf8",
    )
    expect(src).not.toMatch(/shadow-\[var\(--np-shadow\)\]/)
    expect(src).toMatch(/summonWorkspace/)
  })

  it("expanded/fullscreen default with history and context rails collapsed", () => {
    const src = readFileSync(resolve(webRoot, "app/ai/_components/ai-workspace.tsx"), "utf8")
    expect(src).toMatch(/useState\(true\)/)
    expect(src).toMatch(/GravitreAIContextIndicator/)
    expect(src).toMatch(/const closeToHelper = minimizeToHelper/)
  })

  it("header Ask Gravitre exists on Activity, Agents, Workflows, Connectors, Performance, Approvals", () => {
    const pages = [
      "app/activity/page.tsx",
      "app/agents/page.tsx",
      "app/workflows/page.tsx",
      "app/connectors/page.tsx",
      "app/intelligence/performance/page.tsx",
      "app/approvals/page.tsx",
    ]
    for (const rel of pages) {
      const src = readFileSync(resolve(webRoot, rel), "utf8")
      expect(src, rel).toMatch(/AskGravitreSummonButton/)
    }
  })
})
