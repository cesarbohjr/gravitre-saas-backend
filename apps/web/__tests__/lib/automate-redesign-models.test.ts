import { describe, expect, it } from "vitest"
import type { PlayListItem } from "@/lib/api"
import {
  filterPlays,
  installationBody,
  ladder,
  nextGrant,
  readinessOf,
  shareOf,
  summarize,
  tierOf,
} from "@/components/plays/plays-board-model"
import {
  filterWorkflows,
  isFailing,
  normalizeWorkflows,
  sortWorkflows,
  summarizeFleet,
} from "@/components/workflows/workflow-fleet-model"
import {
  buildEntries,
  credentialFailures,
  hotspots,
  latestFailedPerWorkflow,
  monthGrid,
  successPercent,
  trimGrid,
} from "@/app/(app)/schedules/_components/month-model"
import { pageWindow, paginate } from "@/components/workspace/au-pages"
import type { ScheduledItem } from "@/lib/schedules"

function play(overrides: {
  key: string
  department?: string
  observe?: boolean
  recommend?: boolean
  act?: boolean
  connectorMissing?: boolean
  mode?: string
  status?: string
}): PlayListItem {
  return {
    play: {
      key: overrides.key,
      name: overrides.key.replace(/-/g, " "),
      version: "1",
      objective: `Objective for ${overrides.key}`,
      executable: false,
      executionAuthority: "canonical_workflow_runtime",
      department: overrides.department ?? "",
    },
    readiness: {
      play_key: overrides.key,
      dependency_status: "AVAILABLE",
      observe_ready: Boolean(overrides.observe),
      recommend_ready: Boolean(overrides.recommend),
      act_with_approval_ready: Boolean(overrides.act),
      act_within_policy_ready: false,
      blockers: overrides.connectorMissing ? ["connector group hubspot | salesforce: Connect required app"] : [],
      connector_groups: [
        {
          vendors: ["hubspot", "salesforce"],
          status: overrides.connectorMissing ? "MISSING" : "AVAILABLE",
          alternatives: { hubspot: overrides.connectorMissing ? "MISSING" : "AVAILABLE", salesforce: "MISSING" },
        },
      ],
    } as PlayListItem["readiness"],
    workflowBindings: [],
    workflowBindingCount: 0,
    installation: overrides.mode
      ? {
          id: `inst-${overrides.key}`,
          playKey: overrides.key,
          playVersion: "1",
          operatingMode: overrides.mode as never,
          status: overrides.status ?? "ready",
        }
      : null,
  }
}

describe("Plays board model", () => {
  const plays = [
    play({ key: "stalled-deals", department: "sales", observe: true, recommend: true, act: true, mode: "RECOMMEND" }),
    play({ key: "renewal-risk", department: "customer_success", observe: true, recommend: true }),
    play({ key: "invoice-chaser", department: "finance", connectorMissing: true }),
    play({ key: "webinar", department: "marketing", observe: true, recommend: true, act: true, mode: "ACT WITH APPROVAL" }),
    play({ key: "paused-one", department: "sales", observe: true, recommend: true, mode: "OBSERVE", status: "paused" }),
  ]

  it("reads the tier from what the org switched on, never from what it could do", () => {
    expect(tierOf(plays[0])).toBe("recommend")
    expect(tierOf(plays[1])).toBe("off")
    expect(tierOf(plays[3])).toBe("act")
    // A paused set-up is not running.
    expect(tierOf(plays[4])).toBe("off")
  })

  it("separates connector gaps from other setup", () => {
    expect(readinessOf(plays[0])).toBe("ready")
    expect(readinessOf(plays[2])).toBe("connector")
    const signalOnly = play({ key: "signals" })
    expect(readinessOf(signalOnly)).toBe("setup")
  })

  it("summarizes the hero counts", () => {
    const summary = summarize(plays)
    expect(summary.total).toBe(5)
    expect(summary.observeReady).toBe(4)
    expect(summary.readyToTurnOn).toBe(2)
    expect(summary.needsConnector).toBe(1)
    expect(summary.tiers).toEqual({ off: 3, observe: 0, recommend: 1, act: 1 })
  })

  it("only offers the next authority when readiness has earned it", () => {
    expect(nextGrant(plays[0])?.mode).toBe("ACT WITH APPROVAL")
    expect(nextGrant(plays[1])?.mode).toBe("OBSERVE")
    expect(nextGrant(plays[2])).toBeNull()
    expect(nextGrant(plays[3])).toBeNull()
    const recommendNoWrite = play({ key: "rec", observe: true, recommend: true, mode: "RECOMMEND" })
    expect(nextGrant(recommendNoWrite)).toBeNull()
  })

  it("marks the ladder rungs as current, earned or locked", () => {
    expect(ladder(plays[0]).map((r) => r.state)).toEqual(["earned", "current", "earned"])
    expect(ladder(plays[2]).map((r) => r.state)).toEqual(["locked", "locked", "locked"])
  })

  it("filters by department, readiness, tier and text", () => {
    const base = { query: "", department: "all", readiness: "all" as const, tier: "all" as const }
    expect(filterPlays(plays, { ...base, department: "sales" }).map((p) => p.play.key)).toEqual(["stalled-deals", "paused-one"])
    expect(filterPlays(plays, { ...base, readiness: "connector" }).map((p) => p.play.key)).toEqual(["invoice-chaser"])
    expect(filterPlays(plays, { ...base, tier: "act" }).map((p) => p.play.key)).toEqual(["webinar"])
    expect(filterPlays(plays, { ...base, query: "hubspot" })).toHaveLength(5)
    expect(filterPlays(plays, { ...base, query: "invoice" }).map((p) => p.play.key)).toEqual(["invoice-chaser"])
  })

  it("never rounds a real share down to zero", () => {
    expect(shareOf(0, 47)).toBe(0)
    expect(shareOf(1, 200)).toBe(1)
    expect(shareOf(28, 47)).toBe(60)
  })

  it("switches a play on when granting authority", () => {
    expect(installationBody(plays[4], "RECOMMEND", plays[4].installation)).toEqual({
      playVersion: "1",
      operatingMode: "RECOMMEND",
      goalId: null,
      status: "ready",
    })
  })
})

describe("Workflow fleet model", () => {
  const workflows = normalizeWorkflows({
    workflows: [
      { id: "a", name: "SEO digest", status: "active", runCount: 24, successRate: 100, lastRun: "2026-10-13T08:00:00Z", lastRunStatus: "completed", recentRuns: [{ status: "completed" }], departments: ["Marketing"], nodes: [{ name: "Trigger" }, { data: { label: "Post to Slack" } }] },
      { id: "b", name: "CVE lookup", status: "active", runCount: 37, successRate: 78, lastRun: "2026-10-13T09:00:00Z", lastRunStatus: "failed", isRunning: false, departments: ["Security"] },
      { id: "c", name: "Uptime watch", status: "active", runCount: 288, successRate: 99, lastRun: "2026-10-12T09:00:00Z", isRunning: true },
      { id: "d", name: "Old flow", status: "inactive", runCount: 0, successRate: 0 },
      { id: "e", name: "Draft flow", status: "draft" },
    ],
  })

  it("normalizes rows and steps", () => {
    expect(workflows[0].steps).toEqual(["Trigger", "Post to Slack"])
    expect(workflows[3].status).toBe("paused")
    // No runs means no success rate, not 0%.
    expect(workflows[3].successRate).toBeNull()
  })

  it("counts failing from the latest run and running from live runs", () => {
    expect(isFailing(workflows[1])).toBe(true)
    expect(summarizeFleet(workflows)).toEqual({ all: 5, active: 3, paused: 1, failing: 1, draft: 1, running: 1 })
  })

  it("filters and sorts", () => {
    expect(filterWorkflows(workflows, { query: "", segment: "failing", department: "all" }).map((w) => w.id)).toEqual(["b"])
    expect(filterWorkflows(workflows, { query: "", segment: "all", department: "Marketing" }).map((w) => w.id)).toEqual(["a"])
    expect(filterWorkflows(workflows, { query: "slack", segment: "all", department: "all" }).map((w) => w.id)).toEqual(["a"])
    expect(sortWorkflows(workflows, "recent").map((w) => w.id).slice(0, 3)).toEqual(["c", "b", "a"])
    expect(sortWorkflows(workflows, "runs")[0].id).toBe("c")
  })
})

describe("Schedules month model", () => {
  const now = new Date(2026, 9, 13, 10, 0)
  const from = new Date(2026, 8, 28)
  const to = new Date(2026, 10, 1, 23, 59)
  const run = (id: string, workflowId: string, status: ScheduledItem["status"], day: number, extra: Partial<ScheduledItem> = {}): ScheduledItem => ({
    id,
    kind: "task",
    title: `Run · ${workflowId}`,
    workflowName: workflowId === "wf-lead" ? "Lead enrichment" : "CVE lookup",
    status,
    workflowId,
    startedAt: new Date(2026, 9, day, 2, 0).toISOString(),
    ...extra,
  })
  const items: ScheduledItem[] = [
    run("r1", "wf-lead", "failed", 2, { error: "HubSpot token expired" }),
    run("r2", "wf-lead", "failed", 9),
    run("r3", "wf-cve", "failed", 13, { error: "Rate limited" }),
    run("r4", "wf-cve", "completed", 13),
    run("r5", "wf-cve", "running", 13),
    {
      id: "s1",
      kind: "workflow",
      title: "Weekly digest",
      status: "enabled",
      occurrences: [new Date(2026, 9, 6, 9).toISOString(), new Date(2026, 9, 20, 9).toISOString()],
    },
  ]
  const entries = buildEntries(items, from, to, now)

  it("shows past schedule fires as their runs, and only future fires as scheduled", () => {
    const scheduled = entries.filter((e) => e.state === "scheduled")
    expect(scheduled).toHaveLength(1)
    expect(scheduled[0].date.getDate()).toBe(20)
    expect(entries.find((e) => e.occurrence.item.id === "r1")?.name).toBe("Lead enrichment")
  })

  it("ranks hotspots and counts credential failures literally", () => {
    expect(hotspots(entries)).toEqual([
      { name: "Lead enrichment", count: 2 },
      { name: "CVE lookup", count: 1 },
    ])
    expect(credentialFailures(entries)).toBe(1)
  })

  it("retries each workflow once, from its latest failure", () => {
    const targets = latestFailedPerWorkflow(entries)
    expect(targets.map((t) => t.occurrence.item.id).sort()).toEqual(["r2", "r3"])
  })

  it("reports day success over finished runs only", () => {
    const day13 = entries.filter((e) => e.date.getDate() === 13 && e.date.getMonth() === 9)
    expect(successPercent(day13)).toBe(50)
    expect(successPercent([])).toBeNull()
  })

  it("lays the month out Monday first", () => {
    const grid = trimGrid(monthGrid(new Date(2026, 9, 1)), new Date(2026, 9, 1))
    expect(grid[0].getDay()).toBe(1)
    expect(grid[0].getDate()).toBe(28)
    expect(grid).toHaveLength(35)
  })
})

describe("Pager", () => {
  it("windows long page lists", () => {
    expect(pageWindow(1, 5)).toEqual([1, 2, 3, 4, 5])
    expect(pageWindow(6, 12)).toEqual([1, null, 5, 6, 7, null, 12])
  })

  it("clamps a page past the end", () => {
    const result = paginate(Array.from({ length: 23 }, (_, i) => i), 9, 10)
    expect(result.page).toBe(3)
    expect(result.rows).toEqual([20, 21, 22])
    expect([result.from, result.to]).toEqual([21, 23])
  })
})
