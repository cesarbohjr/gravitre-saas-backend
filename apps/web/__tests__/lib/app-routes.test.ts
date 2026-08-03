import { describe, expect, it } from "vitest"
import { APP_ROUTES, LEGACY_APP_ROUTES } from "@/lib/app-routes"
import {
  ADMIN_SIDEBAR_NAV,
  countAdminSidebarItems,
  isSidebarItemActive,
} from "@/components/gravitre/sidebar-nav-config"

describe("APP_ROUTES", () => {
  it("uses /search as canonical universal search", () => {
    expect(APP_ROUTES.universalSearch).toBe("/search")
  })

  it("uses /ai as canonical workspace surface", () => {
    expect(APP_ROUTES.gravitreAi).toBe("/ai")
    expect(APP_ROUTES.gravitreAiChat).toBe("/ai?mode=chat")
  })

  it("uses /activity as the app-wide BusinessOutcome surface", () => {
    expect(APP_ROUTES.activity).toBe("/activity")
    expect(APP_ROUTES.outcomes).toBe("/activity")
  })

  it("keeps /runs as the run detail base path", () => {
    expect(APP_ROUTES.runs).toBe("/runs")
  })

  it("does not expose legacy paths in canonical routes", () => {
    const canonicalValues = Object.values(APP_ROUTES)
    expect(canonicalValues).not.toContain("/operator")
    expect(canonicalValues).not.toContain("/assistant")
    expect(canonicalValues).not.toContain("/tasks")
    expect(canonicalValues).not.toContain("/systems")
  })
})

describe("LEGACY_APP_ROUTES", () => {
  it("retains redirect-only legacy paths", () => {
    expect(LEGACY_APP_ROUTES.operator).toBe("/operator")
    expect(LEGACY_APP_ROUTES.assistant).toBe("/assistant")
    expect(LEGACY_APP_ROUTES.tasks).toBe("/tasks")
    expect(LEGACY_APP_ROUTES.systems).toBe("/systems")
  })
})

describe("ADMIN_SIDEBAR_NAV IA consolidation", () => {
  it("targets about 14 primary items including Getting Started", () => {
    const count = countAdminSidebarItems(true)
    expect(count).toBeLessThanOrEqual(16)
    expect(count).toBeGreaterThanOrEqual(12)
  })

  it("exposes Activity and Intelligence hubs", () => {
    const hrefs = ADMIN_SIDEBAR_NAV.flatMap((g) => g.items.map((i) => i.href))
    expect(hrefs).toContain("/activity")
    expect(hrefs).toContain("/intelligence")
    expect(hrefs).not.toContain("/runs")
    expect(hrefs).not.toContain("/metrics")
    expect(hrefs).not.toContain("/multi-agent-run")
  })

  it("marks related destinations active under hub parents", () => {
    expect(isSidebarItemActive("/runs/abc", "/activity")).toBe(true)
    expect(isSidebarItemActive("/multi-agent-run", "/agents")).toBe(true)
    expect(isSidebarItemActive("/metrics", "/intelligence")).toBe(true)
    expect(isSidebarItemActive("/settings/enterprise", "/settings")).toBe(true)
  })
})
