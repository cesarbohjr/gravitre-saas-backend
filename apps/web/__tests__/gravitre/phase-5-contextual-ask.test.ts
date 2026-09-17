import { readFileSync } from "node:fs"
import { resolve } from "node:path"
import { describe, expect, it } from "vitest"

const webRoot = resolve(__dirname, "../..")

describe("UX Reset Phase 5 — contextual Ask Gravitre", () => {
  it("provider exposes setSelectedEntity without requiring a summon", () => {
    const src = readFileSync(
      resolve(webRoot, "components/gravitre/ai-workspace-provider.tsx"),
      "utf8",
    )
    expect(src).toMatch(/export function usePublishGravitreAISelection/)
    expect(src).toMatch(/setSelectedEntity: \(selected: GravitreAISelectedEntity \| null\)/)
  })

  it("remaining primary surfaces summon the same workspace", () => {
    const pages = [
      "components/home/home-dashboard.tsx",
      "app/marketplace/assets/page.tsx",
      "app/agents/[id]/page.tsx",
      "app/workflows/[id]/page.tsx",
      "app/connectors/[id]/page.tsx",
    ]
    for (const rel of pages) {
      const src = readFileSync(resolve(webRoot, rel), "utf8")
      expect(src, rel).toMatch(/AskGravitreSummonButton/)
    }
  })

  it("product lists publish the selected object into pageContext", () => {
    const files = [
      "app/agents/page.tsx",
      "app/activity/page.tsx",
      "app/approvals/page.tsx",
      "app/connectors/page.tsx",
      "app/intelligence/page.tsx",
      "components/intelligence/pages/performance-stage.tsx",
    ]
    for (const rel of files) {
      const src = readFileSync(resolve(webRoot, rel), "utf8")
      expect(src, rel).toMatch(/usePublishGravitreAISelection/)
    }
  })
})
