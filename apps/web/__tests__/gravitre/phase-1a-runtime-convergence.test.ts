import { readFileSync } from "node:fs"
import { resolve } from "node:path"
import { describe, expect, it } from "vitest"

const webRoot = resolve(__dirname, "../..")

function source(rel: string): string {
  return readFileSync(resolve(webRoot, rel), "utf8")
}

describe("Phase 1A — no duplicate chat runtimes in entry surfaces", () => {
  it("AskGravitreComposer does not import or call useChat", () => {
    const src = source("components/intelligence/ask-gravitre-composer.tsx")
    expect(src).not.toMatch(/from ["']@ai-sdk\/react["']/)
    expect(src).not.toMatch(/\buseChat\b/)
    expect(src).toMatch(/summonWorkspace/)
  })

  it("agent chat route does not import or call useChat", () => {
    const src = source("app/agents/[id]/chat/page.tsx")
    expect(src).not.toMatch(/from ["']@ai-sdk\/react["']/)
    expect(src).not.toMatch(/\buseChat\b/)
    expect(src).toMatch(/agentScope/)
    expect(src).toMatch(/summonWorkspace/)
  })

  it("legacy /assistant page redirects to canonical /ai chat", () => {
    const src = source("app/assistant/page.tsx")
    expect(src).toMatch(/redirect\(APP_ROUTES\.gravitreAiChat\)/)
  })

  it("proxy rewrites /assistant before session so Playwright can follow /ai", () => {
    const src = source("proxy.ts")
    expect(src).toMatch(/pathname === "\/assistant"/)
    expect(src).toMatch(/APP_ROUTES\.gravitreAi/)
  })

  it("float kill-switch is XOR: host unmounts when flag is false", () => {
    const host = source("components/gravitre/ai-workspace-host.tsx")
    expect(host).toMatch(/if \(!GRAVITRE_AI_FLOAT_ENABLED \|\| !armed\) return null/)
    const page = source("app/ai/page.tsx")
    expect(page).toMatch(/GRAVITRE_AI_FLOAT_ENABLED \?/)
    expect(page).toMatch(/AiWorkspace/)
  })
})
