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

  it("renders the KPI board only in the Reports view, and Customize switches to it", () => {
    const src = read("components/home/home-dashboard.tsx")
    expect(src).toMatch(/<DashboardViewToggle/)
    expect(src).toMatch(/const showReports = view === "reports" \|\| editMode/)
    expect(src).toMatch(/onClick=\{startCustomize\}/)
    const reports = src.indexOf('data-dashboard-view="reports"')
    expect(src.indexOf("{/* Desktop / tablet grid */}")).toBeGreaterThan(reports)
    expect(src.indexOf("<OperatingFlow")).toBeLessThan(reports)
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
