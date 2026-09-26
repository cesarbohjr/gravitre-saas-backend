import { readFileSync } from "node:fs"
import { resolve } from "node:path"
import { describe, expect, it } from "vitest"

const src = readFileSync(resolve(__dirname, "../../app/workflows/[id]/builder/page.tsx"), "utf8")

describe("Workflow Builder Meson panel default", () => {
  it("opens by default only on md+ viewports when no preference is stored", () => {
    expect(src).toMatch(/if \(stored !== null\) return stored !== "0"\s+return window\.matchMedia\("\(min-width: 768px\)"\)\.matches/)
  })

  it("does not auto-open (or persist) when the saved graph loads — only on later additions", () => {
    const effect = src.slice(src.indexOf("const graphSeededRef"), src.indexOf("}, [nodes.length, isLoadingGraph])"))
    expect(effect).toContain("if (!graphSeededRef.current)")
    expect(effect.indexOf("return")).toBeLessThan(effect.indexOf("setMesonPanelOpen(true)"))
  })
})
