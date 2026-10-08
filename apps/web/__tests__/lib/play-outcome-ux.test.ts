import fs from "node:fs"
import path from "node:path"
import { describe, expect, it } from "vitest"

const read = (p: string) => fs.readFileSync(path.join(process.cwd(), p), "utf8")

describe("Play outcome UX", () => {
  it("labels dashboard impact as verified and rejects workflow-completion ROI", () => {
    const c = read("components/home/v3/play-outcomes.tsx")
    expect(c).toMatch(/Verified Play impact/)
    expect(c).toMatch(/Workflow completion is not counted as impact/)
  })

  it("separates pending results from verified impact", () => {
    const c = read("components/plays/play-results.tsx")
    expect(c).toMatch(/Not included in verified impact totals/)
    expect(c).toMatch(/PENDING|pending/i)
  })

  it("provides evidence drill-down", () => {
    const c = read("app/(app)/plays/[key]/results/[outcomeId]/page.tsx")
    expect(c).toMatch(/Source of record/)
    expect(c).toMatch(/Governance/)
    expect(c).toMatch(/Workflow run/)
  })
})
