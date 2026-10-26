import { readFileSync } from "node:fs"
import { resolve } from "node:path"
import { describe, expect, it } from "vitest"

const page = readFileSync(resolve(__dirname, "../../app/(app)/agents/[id]/page.tsx"), "utf8")
const header = readFileSync(resolve(__dirname, "../../components/agents/agent-detail-header.tsx"), "utf8")

describe("agent detail identity header", () => {
  it("renders the shared identity header with the department cover", () => {
    expect(page).toMatch(/<AgentDetailHeader/)
    expect(header).toMatch(/<DepartmentCover/)
  })

  it("names the status once, in the chip; the avatar dot is decorative", () => {
    expect(header.match(/\{status\.label\}/g) ?? []).toHaveLength(1)
    expect(header).toMatch(/aria-hidden\s+className=\{cn\("absolute bottom-2 right-2/)
  })
})
