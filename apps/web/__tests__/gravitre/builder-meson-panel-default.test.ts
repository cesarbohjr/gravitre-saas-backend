import { readFileSync } from "node:fs"
import { resolve } from "node:path"
import { describe, expect, it } from "vitest"

const src = readFileSync(resolve(__dirname, "../../app/workflows/[id]/builder/page.tsx"), "utf8")

describe("Workflow Builder inspector modes", () => {
  it("defaults the right inspector to Configure; Meson is a mode, not a permanent column", () => {
    expect(src).toMatch(/useState<InspectorMode>\("configure"\)/)
    expect(src).toContain("const mesonPanelOpen = inspectorMode === \"meson\"")
    expect(src).not.toContain("gravitre:mesonPanelOpen")
  })

  it("does not switch to Meson when the saved graph loads; later additions only flag it", () => {
    const effect = src.slice(src.indexOf("const graphSeededRef"), src.indexOf("}, [nodes.length, isLoadingGraph, inspectorMode])"))
    expect(effect).toContain("if (!graphSeededRef.current)")
    expect(effect.indexOf("return")).toBeLessThan(effect.indexOf("setMesonAttention(true)"))
    expect(effect).not.toContain('setInspectorMode("meson")')
  })

  it("selecting a node returns to Configure and a live run opens Run / Trace", () => {
    expect(src).toMatch(/if \(selectedNodeId\) setInspectorMode\("configure"\)/)
    expect(src).toMatch(/if \(executionStatus === "running"\) setInspectorMode\("trace"\)/)
  })
})
