import { readFileSync } from "node:fs"
import path from "node:path"
import { describe, expect, it } from "vitest"

const PANEL = path.resolve(
  __dirname,
  "../../components/gravitre/assistant/chat-execution-panel.tsx",
)
const CANVAS = path.resolve(__dirname, "../../components/gravitre/ai-work-canvas.tsx")

describe("canonical artifact presentation contract", () => {
  it("renders structured.rows from executionResult rather than a second artifact model", () => {
    const panel = readFileSync(PANEL, "utf8")
    const canvas = readFileSync(CANVAS, "utf8")
    expect(panel).toContain('data-testid="canonical-artifact-table"')
    expect(panel).toContain("export function canonicalArtifactRows")
    expect(panel).toContain("structured?.rows")
    expect(canvas).toContain("canonicalArtifactRows")
    expect(canvas).toContain("CanonicalArtifactTable")
    expect(canvas).toContain("executionResult?.structured?.kind")
    expect(canvas).not.toMatch(/useState\(\[\]\)\s*\/\/\s*artifacts/)
    expect(canvas).not.toContain("localArtifacts")
  })
})
