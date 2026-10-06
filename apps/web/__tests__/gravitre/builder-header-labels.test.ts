import { readFileSync } from "node:fs"
import { resolve } from "node:path"
import { describe, expect, it } from "vitest"

const page = readFileSync(resolve(__dirname, "../../app/workflows/[id]/builder/page.tsx"), "utf8")

describe("Workflow Builder header", () => {
  it("splits identity (name, environment, status, version) from the workflow toolbar", () => {
    expect(page).toContain('data-review-surface="workflow-identity"')
    expect(page).toContain('data-review-surface="workflow-toolbar"')
    expect(page).toMatch(/role="toolbar"\s+aria-label="Workflow tools"/)
  })

  it("orders the toolbar Editor, Runs, Preview, Trace, Intelligence, Meson, Settings", () => {
    const toolbar = page.slice(page.indexOf('data-review-surface="workflow-toolbar"'))
    const order = ['key: "editor"', 'key: "runs"', 'key: "preview"', 'key: "trace"', 'key: "intelligence"', 'key: "meson"', 'key: "settings"']
    const positions = order.map((key) => toolbar.indexOf(key))
    expect(positions.every((p) => p >= 0)).toBe(true)
    expect([...positions].sort((a, b) => a - b)).toEqual(positions)
  })

  it("keeps toolbar names for assistive tech while icon-only below md", () => {
    expect(page).toContain('<span className="sr-only md:not-sr-only">{tool.label}</span>')
    expect(page).not.toMatch(/<span className="hidden sm:inline">(Settings|Meson|Intelligence|Preview|Last run)<\/span>/)
  })
})
