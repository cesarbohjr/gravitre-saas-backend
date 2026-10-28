import { readFileSync } from "node:fs"
import { resolve } from "node:path"
import { describe, expect, it } from "vitest"

const src = readFileSync(resolve(__dirname, "../../components/gravitre/app-shell.tsx"), "utf8")

function block(name: string): string {
  const start = src.indexOf(`const ${name} =`)
  expect(start, `${name} is declared`).toBeGreaterThan(-1)
  return src.slice(start, src.indexOf("\n  const ", start + 1) === -1 ? undefined : src.indexOf("\n  const ", start + 1))
}

describe("AppShell chrome by route", () => {
  it("keeps the standard top bar (org + environment context) on Connectors", () => {
    expect(block("isImmersiveChat")).not.toContain("/connectors")
    expect(block("useCompactTopBar")).not.toContain("/connectors")
  })

  it("lets the Connectors hub scroll like any document page", () => {
    // The redesigned hub has no inner scroll region; locking the main column
    // left everything below the first screen unreachable, on phones most of all.
    expect(src).not.toContain("isFullHeightHub")
    expect(block("locksDocumentScroll")).not.toContain("/connectors")
  })
})
