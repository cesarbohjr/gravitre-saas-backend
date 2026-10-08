// @vitest-environment jsdom
import React, { act } from "react"
import { createRoot, type Root } from "react-dom/client"
import { afterEach, describe, expect, it, vi } from "vitest"

vi.mock("next/navigation", () => ({ useRouter: () => ({ push: vi.fn() }) }))
vi.mock("sonner", () => ({ toast: { success: vi.fn(), error: vi.fn() } }))
vi.mock("@/lib/api", () => ({ agentsApi: { update: vi.fn(), stop: vi.fn() } }))

import { RosterTeamView, TEAM_BAND_LIMIT } from "@/components/agents/roster/roster-team-view"
import { LIST_PAGE_SIZE, RosterListView, pageItems } from "@/components/agents/roster/roster-list-view"
import { ROSTER_DEPARTMENTS, toRosterAgent, yesterdayBestAgent, type RosterStatsPayload } from "@/lib/agents-roster"

;(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true

let root: Root | null = null
let host: HTMLDivElement | null = null
function render(ui: React.ReactElement): HTMLDivElement {
  host = document.createElement("div")
  document.body.appendChild(host)
  root = createRoot(host)
  act(() => root!.render(ui))
  return host
}
afterEach(() => {
  act(() => root?.unmount())
  host?.remove()
  root = null
  host = null
})
const band = (el: HTMLElement, id: string) => el.querySelector<HTMLElement>(`section[aria-labelledby="dept-${id}"]`)!
const linksNamed = (el: HTMLElement, re: RegExp) => [...el.querySelectorAll("a")].filter((a) => re.test(a.textContent ?? ""))
const buttonNamed = (el: HTMLElement, label: string) =>
  [...el.querySelectorAll("button")].find((b) => b.getAttribute("aria-label") === label || b.textContent?.trim() === label)!
const rowChecks = (el: HTMLElement, prefix: string) =>
  [...el.querySelectorAll("input[type=checkbox]")].filter((c) => c.getAttribute("aria-label")?.startsWith(`Select ${prefix} Agent`))
const click = (b: HTMLElement) => act(() => b.click())

function fleet(dept: string, n: number, prefix: string) {
  return Array.from({ length: n }, (_, i) => ({
    id: `${prefix}${i}`,
    name: `${prefix.toUpperCase()} Agent ${String(i).padStart(2, "0")}`,
    role: "Analyst",
    department: dept,
    description: "Does real work.",
    permissions: ["hubspot"],
  }))
}

const empty = (daily: number[] = []) => ({
  tasksToday: 0, failedToday: 0, runningNow: 0, successRateToday: null, successRate7d: 90,
  lastActiveAt: null, daily, blocked: null,
})

describe("agents team view limits", () => {
  const raw = [...fleet("Sales", 6, "s"), ...fleet("Security", 1, "sec"), ...fleet("General", 1, "g")]
  const agents = raw.map((r) => toRosterAgent(r, undefined))

  it("shows four agents per department and links the rest to the filtered list", () => {
    const el = render(<RosterTeamView agents={agents} statsAvailable={false} days={0} />)
    const sales = band(el, "sales")
    expect(sales.querySelectorAll("article")).toHaveLength(TEAM_BAND_LIMIT)
    expect(sales.textContent).toContain("Showing 4 of 6 Sales agents")
    const links = linksNamed(sales, /View all 6 in list view/)
    expect(links).toHaveLength(1)
    expect(links[0].getAttribute("href")).toBe("/agents?view=list&dept=sales")
  })

  it("gives Security and General their own bands with the v2 department art", () => {
    const container = render(<RosterTeamView agents={agents} statsAvailable={false} days={0} />)
    for (const id of ["security", "general"]) {
      expect(band(container, id)).toBeTruthy()
      expect(linksNamed(band(container, id), /View all/)).toHaveLength(0)
    }
    const srcs = [...container.querySelectorAll(".rs-band-art img")].map((img) => img.getAttribute("src"))
    expect(srcs).toEqual(
      expect.arrayContaining(["/illustrations/roster-sales.svg", "/illustrations/roster-security.svg", "/illustrations/roster-general.svg"]),
    )
    expect(ROSTER_DEPARTMENTS.every((d) => d.illustration)).toBe(true)
  })

  it("replaces the old empty standout with the warming up card", () => {
    const el = render(<RosterTeamView agents={agents} statsAvailable={false} days={0} />)
    expect(el.textContent).not.toContain("No finished tasks yet today")
    expect(el.textContent).toContain("Your team is warming up")
    expect(linksNamed(el, /^Give a task$/)[0].getAttribute("href")).toContain("s0")
    // No stats means no yesterday to show, so the button stays hidden.
    expect(buttonNamed(el, "See yesterday's best")).toBeUndefined()
  })

  it("shows yesterday's busiest agent on request", () => {
    const stats: RosterStatsPayload = {
      generatedAt: "", days: [], approvalGate: {}, goals: [],
      agents: { s0: empty([0, 3, 2, 0]), s1: empty([0, 1, 4, 0]) },
    }
    const withStats = raw.map((r) => toRosterAgent(r, stats))
    expect(yesterdayBestAgent(withStats)?.agent.id).toBe("s1")
    expect(yesterdayBestAgent(withStats)?.tasks).toBe(4)
    const el = render(<RosterTeamView agents={withStats} statsAvailable days={4} />)
    click(buttonNamed(el, "See yesterday's best"))
    expect(el.textContent).toContain("Yesterday's best")
    expect(el.textContent).toContain("S Agent 01")
    expect(el.textContent).toContain("tasks finished yesterday")
    click(buttonNamed(el, "Back to today"))
    expect(el.textContent).toContain("Your team is warming up")
  })
})

describe("agents list view pagination", () => {
  const agents = fleet("Sales", 23, "s").map((r) => toRosterAgent(r, undefined))
  const noop = async () => undefined

  it("shows ten per page with numbered pages and View all", () => {
    const el = render(<RosterListView agents={agents} statsAvailable={false} onChanged={noop} />)
    expect(rowChecks(el, "S")).toHaveLength(LIST_PAGE_SIZE)
    expect(el.textContent).toContain("Showing 1 to 10 of 23 agents")
    expect(el.textContent).toContain("Page 1 of 3, 10 per page")
    click(buttonNamed(el, "Next"))
    expect(el.textContent).toContain("Showing 11 to 20 of 23 agents")
    click(buttonNamed(el, "Page 3"))
    expect(rowChecks(el, "S")).toHaveLength(3)
    click(buttonNamed(el, "View all 23"))
    expect(rowChecks(el, "S")).toHaveLength(23)
    expect(el.textContent).toContain("Showing every agent on one page")
    click(buttonNamed(el, "Show 10 per page"))
    expect(rowChecks(el, "S")).toHaveLength(LIST_PAGE_SIZE)
  })

  it("opens filtered to the department a team band linked to", () => {
    const mixed = [...agents, ...fleet("Security", 2, "sec").map((r) => toRosterAgent(r, undefined))]
    const el = render(<RosterListView agents={mixed} statsAvailable={false} initialDept="security" onChanged={noop} />)
    expect(rowChecks(el, "SEC")).toHaveLength(2)
    expect(rowChecks(el, "S")).toHaveLength(0)
    expect(el.querySelector("#rs-list-heading")?.textContent).toBe("Security agents")
    expect(linksNamed(el, /Back to team view/)[0].getAttribute("href")).toBe("/agents?view=team")
  })

  it("windows long page lists", () => {
    expect(pageItems(1, 3)).toEqual([1, 2, 3])
    expect(pageItems(6, 12)).toEqual([1, "gap", 5, 6, 7, "gap", 12])
  })
})
