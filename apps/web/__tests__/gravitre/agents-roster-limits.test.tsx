// @vitest-environment jsdom
import React, { act } from "react"
import { createRoot, type Root } from "react-dom/client"
import { afterEach, describe, expect, it, vi } from "vitest"

const push = vi.hoisted(() => vi.fn())
vi.mock("next/navigation", () => ({ useRouter: () => ({ push }) }))
vi.mock("sonner", () => ({ toast: { success: vi.fn(), error: vi.fn() } }))
vi.mock("@/lib/api", () => ({ agentsApi: { update: vi.fn(), stop: vi.fn() } }))

import { RosterTeamView } from "@/components/agents/roster/roster-team-view"
import { LIST_PAGE_SIZE, RosterListView, pageItems } from "@/components/agents/roster/roster-list-view"
import { toRosterAgent, yesterdayBestAgent, type RosterStatsPayload } from "@/lib/agents-roster"

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

describe("agents team view", () => {
  const raw = [...fleet("Sales", 6, "s"), ...fleet("Security", 1, "sec"), ...fleet("General", 1, "g")]
  const agents = raw.map((r) => toRosterAgent(r, undefined))
  const cards = (el: HTMLElement) => [...el.querySelectorAll("article.tm-card")]
  const setInput = (input: HTMLInputElement, value: string) =>
    act(() => {
      Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, "value")!.set!.call(input, value)
      input.dispatchEvent(new Event("input", { bubbles: true }))
    })

  it("shows every agent and filters by department chip and search", () => {
    const el = render(<RosterTeamView agents={agents} statsAvailable={false} />)
    expect(el.querySelector("h1")?.textContent).toBe("8 agents, ready when you are.")
    expect(cards(el)).toHaveLength(8)
    click(buttonNamed(el, "Security 1"))
    expect(cards(el)).toHaveLength(1)
    expect(buttonNamed(el, "Security 1").getAttribute("aria-pressed")).toBe("true")
    click(buttonNamed(el, "All 8"))
    setInput(el.querySelector<HTMLInputElement>('input[aria-label="Find an agent"]')!, "agent 03")
    expect(cards(el).map((c) => c.querySelector(".nm")?.textContent)).toEqual(["S Agent 03"])
  })

  it("links each card to a task, a chat and the agent", () => {
    const el = render(<RosterTeamView agents={agents} statsAvailable={false} />)
    const card = cards(el)[0]
    const href = (label: string) => card.querySelector(`a[aria-label="${label}"]`)?.getAttribute("href")
    expect(href("Give S Agent 00 a task")).toBe("/assignments/new?agent=s0")
    expect(href("Chat with S Agent 00")).toBe("/agents/s0/chat")
    expect(card.querySelector("a.nm")?.getAttribute("href")).toBe("/agents/s0")
  })

  it("offers the Marketplace for departments with no agent", () => {
    const el = render(<RosterTeamView agents={agents} statsAvailable={false} />)
    const hire = el.querySelector<HTMLElement>("article.tm-hire")!
    expect(hire.textContent).toContain("5 departments have no agent yet")
    click(buttonNamed(el, "Finance 0"))
    const one = el.querySelector<HTMLElement>("article.tm-hire")!
    expect(one.textContent).toContain("Finance has no agent yet")
    expect(linksNamed(one, /Browse agents/)[0].getAttribute("href")).toBe("/marketplace/assets?type=ai_agent&department=finance")
  })

  it("shows the warming up standout until someone finishes a task", () => {
    const el = render(<RosterTeamView agents={agents} statsAvailable={false} />)
    expect(el.textContent).toContain("Your team is warming up")
    const standout = el.querySelector<HTMLElement>(".tm-standout")!
    expect(linksNamed(standout, /^Give a task$/)[0].getAttribute("href")).toContain("s0")
    const stats: RosterStatsPayload = {
      generatedAt: "", days: [], approvalGate: {}, goals: [],
      agents: { s1: { ...empty([0, 4]), tasksToday: 4, successRateToday: 100 } },
    }
    const busy = render(<RosterTeamView agents={raw.map((r) => toRosterAgent(r, stats))} statsAvailable />)
    expect(busy.querySelector(".tm-standout")?.textContent).toContain("S Agent 01")
    expect(busy.querySelector(".tm-standout")?.textContent).toContain("4 tasks done today")
  })

  it("counts pending approvals and stuck agents under Needs you", () => {
    const el = render(<RosterTeamView agents={agents} statsAvailable={false} pendingApprovals={2} />)
    const needs = [...el.querySelectorAll<HTMLElement>(".tm-stat")].find((s) => s.textContent?.includes("Needs you"))!
    expect(needs.tagName).toBe("A")
    expect(needs.getAttribute("href")).toBe("/approvals")
    expect(needs.textContent).toContain("2 approvals")
  })

  it("shows the running task and the autonomy level from the roster", () => {
    const stats: RosterStatsPayload = {
      generatedAt: "", days: [], approvalGate: {}, goals: [], autonomy: { s0: "read_only" },
      agents: { s0: { ...empty(), runningNow: 1, currentTask: "Drafting a quote for Acme" } },
    }
    const el = render(<RosterTeamView agents={raw.map((r) => toRosterAgent(r, stats))} statsAvailable />)
    const first = cards(el)[0]
    expect(first.textContent).toContain("Now: Drafting a quote for Acme")
    expect(first.textContent).toContain("Working")
    expect(first.querySelector('[role="img"]')?.getAttribute("aria-label")).toBe("Autonomy 1 of 3: Suggests only")
    // Agents without an identity record fail closed to asking first.
    expect(cards(el)[1].textContent).toContain("Asks before acting")
  })

  it("hands a job to the best matching agent through the assignment flow", () => {
    push.mockClear()
    const mixed = [
      ...agents,
      toRosterAgent({ id: "fin", name: "Invoice Chaser", department: "Finance", description: "Follows up on overdue invoices.", permissions: ["quickbooks"] }, undefined),
    ]
    const el = render(<RosterTeamView agents={mixed} statsAvailable={false} />)
    click(buttonNamed(el, "Chase invoices over 30 days"))
    const input = el.querySelector<HTMLInputElement>(".tm-job input")!
    expect(input.value).toBe("Chase invoices over 30 days")
    act(() => el.querySelector("form")!.dispatchEvent(new Event("submit", { bubbles: true, cancelable: true })))
    expect(push).toHaveBeenCalledWith("/assignments/new?agent=fin&task=Chase+invoices+over+30+days")
  })

  it("keeps the yesterday helper for the roster model", () => {
    const stats: RosterStatsPayload = {
      generatedAt: "", days: [], approvalGate: {}, goals: [],
      agents: { s0: empty([0, 3, 2, 0]), s1: empty([0, 1, 4, 0]) },
    }
    const withStats = raw.map((r) => toRosterAgent(r, stats))
    expect(yesterdayBestAgent(withStats)?.agent.id).toBe("s1")
    expect(yesterdayBestAgent(withStats)?.tasks).toBe(4)
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
