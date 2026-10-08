import { readFileSync } from "node:fs"
import { resolve } from "node:path"
import { describe, expect, it } from "vitest"
import { DEFAULT_DASHBOARD_VIEW, parseDashboardView } from "@/lib/dashboard/view-preference"
import { rankSystemOutcomes, SYSTEM_OUTCOMES_PREVIEW } from "@/components/home/system-outcomes"

const read = (path: string) => readFileSync(resolve(__dirname, "../..", path), "utf8")

describe("dashboard views", () => {
  it("defaults to AI Native and only honours an explicit Reports choice", () => {
    expect(DEFAULT_DASHBOARD_VIEW).toBe("ai")
    expect(parseDashboardView(null)).toBe("ai")
    expect(parseDashboardView("garbage")).toBe("ai")
    expect(parseDashboardView("reports")).toBe("reports")
  })

  it("renders the Reports board only in the Reports view and the AI Native briefing otherwise", () => {
    const src = read("components/home/home-dashboard.tsx")
    expect(src).toMatch(/data-dashboard-view-toggle/)
    expect(src).toMatch(/const showReports = view === "reports"/)
    const reports = src.indexOf("<ReportsView")
    const ai = src.indexOf("<AiNativeView")
    expect(reports).toBeGreaterThan(-1)
    expect(ai).toBeGreaterThan(reports)
    // Reports data loads only while the Reports view is open.
    expect(src).toMatch(/useHomeReportsData\(enabled && showReports/)
  })
})

describe("rankSystemOutcomes", () => {
  const row = (connector: string, pass: number, fail = 0, cancel = 0) => ({ connector, pass, fail, cancel, pass_rate: null })

  it("keeps failing systems in the preview ahead of busier healthy ones", () => {
    const ranked = rankSystemOutcomes([row("a", 50), row("b", 40), row("c", 30), row("d", 1, 1)])
    expect(ranked.slice(0, SYSTEM_OUTCOMES_PREVIEW).map((r) => r.connector)).toEqual(["d", "a", "b"])
  })

  it("drops systems with no executions", () => {
    expect(rankSystemOutcomes([row("a", 0), row("", 3)])).toEqual([])
    expect(rankSystemOutcomes(undefined)).toEqual([])
  })
})
