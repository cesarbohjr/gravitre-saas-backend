import { readFileSync } from "node:fs"
import { resolve } from "node:path"
import { describe, expect, it } from "vitest"

const src = readFileSync(resolve(__dirname, "../../app/(app)/workflows/[id]/builder/page.tsx"), "utf8")

describe("Workflow Builder inspector modes", () => {
  it("defaults the right inspector to Configure; Meson is a mode, not a permanent column", () => {
    expect(src).toMatch(/useState<InspectorMode>\("configure"\)/)
    expect(src).toContain("const mesonPanelOpen = inspectorOpen && inspectorMode === \"meson\"")
    expect(src).not.toContain("gravitre:mesonPanelOpen")
  })

  it("does not switch to Meson when the saved graph loads; later additions only flag it", () => {
    const effect = src.slice(src.indexOf("const graphSeededRef"), src.indexOf("}, [nodes.length, isLoadingGraph, inspectorMode])"))
    expect(effect).toContain("if (!graphSeededRef.current)")
    expect(effect.indexOf("return")).toBeLessThan(effect.indexOf("setMesonAttention(true)"))
    expect(effect).not.toContain('setInspectorMode("meson")')
  })

  it("selecting a node opens Configure and a live run opens Run / Trace", () => {
    expect(src).toMatch(/if \(selectedNodeId\) \{\s*setInspectorMode\("configure"\)\s*setInspectorOpen\(true\)/)
    expect(src).toMatch(/if \(executionStatus === "running"\) \{\s*setInspectorMode\("trace"\)\s*setInspectorOpen\(true\)/)
  })

  it("keeps the inspector closed until something is selected, with an X and click-outside to close", () => {
    expect(src).toContain("const [inspectorOpen, setInspectorOpen] = useState(false)")
    expect(src).toMatch(/\{inspectorOpen \? \(\s*<BuilderInspector/)
    expect(src).toContain("onClose={closeInspector}")
    const click = src.slice(src.indexOf("const handleCanvasClick"), src.indexOf("}, [closeInspector])", src.indexOf("const handleCanvasClick")))
    expect(click).toContain("closeInspector()")
  })

  it("pans the canvas by dragging empty space and keeps the second rail canvas-only", () => {
    expect(src).toContain("onMouseDown={handleCanvasPanStart}")
    expect(src).toContain("el.scrollLeft = pan.left - dx")
    expect(src).toContain("<BuilderCanvasRail")
    expect(src).not.toContain("<BuilderNav")
  })
})
