import { readFileSync } from "node:fs"
import { resolve } from "node:path"
import { describe, expect, it } from "vitest"

const webRoot = resolve(__dirname, "../..")

describe("UX Reset Phase 7 — progressive disclosure in the workspace", () => {
  it("sources sit behind a details control, not an always-open block", () => {
    const src = readFileSync(
      resolve(webRoot, "components/gravitre/assistant/assistant-source-links.tsx"),
      "utf8",
    )
    expect(src).toMatch(/<details/)
    expect(src).toMatch(/Sources/)
    expect(src).not.toMatch(/Sources checked/)
  })

  it("research cascade is collapsed until opened", () => {
    const src = readFileSync(
      resolve(webRoot, "components/gravitre/assistant/research-cascade-panel.tsx"),
      "utf8",
    )
    expect(src).toMatch(/<details/)
    expect(src).not.toMatch(/rounded-xl border border-border\/60 bg-card\/50/)
  })

  it("artifacts and execution steps are disclosed, not card-first", () => {
    const src = readFileSync(
      resolve(webRoot, "components/gravitre/assistant/chat-execution-panel.tsx"),
      "utf8",
    )
    expect(src).toMatch(/Artifacts \(/)
    expect(src).toMatch(/Execution \(/)
    expect(src).not.toMatch(/uppercase tracking-wide text-muted-foreground">Artifacts/)
  })

  it("tool execution stays collapsed unless running", () => {
    const src = readFileSync(
      resolve(webRoot, "components/gravitre/agent-ui/tool-execution-group.tsx"),
      "utf8",
    )
    expect(src).toMatch(/open \|\| running/)
    expect(src).not.toMatch(/if \(invocations\.length === 1\)/)
  })

  it("models and studio use text sections, not pill strips", () => {
    const models = readFileSync(resolve(webRoot, "app/models/page.tsx"), "utf8")
    expect(models).toMatch(/aria-label="Models catalog"/)
    expect(models).toMatch(/AskGravitreSummonButton/)
    expect(models).not.toMatch(/TabsList/)

    const studio = readFileSync(
      resolve(webRoot, "components/intelligence/pages/model-studio-stage.tsx"),
      "utf8",
    )
    expect(studio).toMatch(/aria-label="Model Studio action"/)
    expect(studio).not.toMatch(/SegmentedControl/)
  })
})
