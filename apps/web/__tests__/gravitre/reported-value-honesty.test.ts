import { readFileSync } from "node:fs"
import { resolve } from "node:path"
import { describe, expect, it } from "vitest"

const webRoot = resolve(__dirname, "../..")
const read = (relative: string) => readFileSync(resolve(webRoot, relative), "utf8")

describe("reported values stay reported", () => {
  it("metrics overview does not invent zeros for omitted payloads", () => {
    const src = read("app/metrics/page.tsx")
    expect(src).toMatch(/function parseReportedNumber/)
    expect(src).toMatch(/function normalizeOverview\(payload: unknown\): MetricsOverview \| null/)
    expect(src).toMatch(/if \(!payload \|\| typeof payload !== "object"\) return null/)
    expect(src).toMatch(/Not reported/)
    expect(src).toMatch(/WorkSectionErrorCard/)
    expect(src).not.toMatch(/const empty: MetricsOverview = \{[\s\S]*totalRuns: 0/)
  })

  it("environments do not invent health, resource counts, or timestamps", () => {
    const src = read("app/environments/page.tsx")
    expect(src).toMatch(/health: parseReportedCount/)
    expect(src).toMatch(/Not reported/)
    expect(src).not.toMatch(/health: 100/)
    expect(src).not.toMatch(/createdAt: "Recently created"/)
    expect(src).not.toMatch(/lastActivity: "Just now"/)
  })

  it("play evidence does not treat missing approvals as zero", () => {
    const src = read("app/plays/[key]/results/[outcomeId]/page.tsx")
    expect(src).toMatch(/Required approvals/)
    expect(src).toMatch(/Not reported/)
    expect(src).not.toMatch(/requiredApprovals \?\? 0/)
  })
})
