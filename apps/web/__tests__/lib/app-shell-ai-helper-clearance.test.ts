import { describe, expect, it } from "vitest"
import fs from "node:fs"
import path from "node:path"

const shell = fs.readFileSync(path.join(process.cwd(), "components/gravitre/app-shell.tsx"), "utf8")

describe("app shell AI helper clearance", () => {
  it("does not reserve a permanent full-width dock band", () => {
    expect(shell).not.toContain("data-gravitre-ai-dock=workspace")
    expect(shell).not.toContain("pb-[68px]")
    expect(shell).not.toContain("pb-[calc(116px+env(safe-area-inset-bottom))]")
  })

  it("keeps scroll-end clearance for ordinary pages", () => {
    expect(shell).toMatch(/pb-32 md:pb-24/)
  })
})
