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
    const home = readFileSync(resolve(webRoot, "components/home/home-dashboard.tsx"), "utf8")
    // Master prompt §5: no duplicate page composer — contextual prompts summon the canonical workspace.
    expect(home).not.toMatch(/<OperatingAskLine/)
    const operatingFlow = readFileSync(resolve(webRoot, "components/home/operating-flow.tsx"), "utf8")
    expect(operatingFlow).toMatch(/useGravitreAIWorkspace/)
    expect(operatingFlow).toMatch(/data-ask-prompt/)
    const pages = [
      "app/marketplace/assets/page.tsx",
      "app/agents/[id]/page.tsx",
      "app/workflows/[id]/page.tsx",
      "app/connectors/[id]/page.tsx",
      "components/training/training-workbench.tsx",
      "app/models/page.tsx",
      "app/intelligence/model-studio/page.tsx",
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
      "app/marketplace/assets/page.tsx",
    ]
    for (const rel of files) {
      const src = readFileSync(resolve(webRoot, rel), "utf8")
      expect(src, rel).toMatch(/usePublishGravitreAISelection/)
    }
  })
})
