import { readFileSync } from "node:fs"
import { resolve } from "node:path"
import { describe, expect, it } from "vitest"

const page = readFileSync(resolve(__dirname, "../../app/workflows/[id]/builder/page.tsx"), "utf8")

describe("Workflow Builder header", () => {
  it("keeps toolbar button names for assistive tech while icon-only below lg, so the workflow name has room on tablet", () => {
    for (const label of ["Settings", "Meson", "Intelligence", "Preview", "Last run"]) {
      expect(page).toContain(`<span className="sr-only lg:not-sr-only">${label}</span>`)
    }
    expect(page).not.toMatch(/<span className="hidden sm:inline">(Settings|Meson|Intelligence|Preview|Last run)<\/span>/)
  })
})
