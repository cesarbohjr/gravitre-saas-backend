// @vitest-environment jsdom
import React, { act } from "react"
import { createRoot, type Root } from "react-dom/client"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"
import type { AgentRoiSummary, CostAttributionSummary, KnowledgeSyncOverview } from "@/lib/settings-api/enterprise"

const mocks = vi.hoisted(() => ({
  byKey: {} as Record<string, unknown>,
  trigger: vi.fn(),
  updateInputs: vi.fn(),
}))

vi.mock("swr", () => ({
  default: (key: unknown) => {
    const k = String(key)
    const match = Object.keys(mocks.byKey).find((prefix) => k.startsWith(prefix))
    return { data: match ? mocks.byKey[match] : undefined, error: undefined, isLoading: false, mutate: vi.fn() }
  },
}))
vi.mock("@/lib/api", () => ({
  knowledgeSyncApi: { listSyncJobs: vi.fn(), triggerConnectorSync: mocks.trigger },
  enterpriseApi: {},
}))
vi.mock("@/lib/settings-api/enterprise", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/lib/settings-api/enterprise")>()
  return { ...actual, enterpriseInsightsApi: { ...actual.enterpriseInsightsApi, updateAgentRoiInputs: mocks.updateInputs } }
})
vi.mock("next/link", () => ({
  default: ({ href, children, ...rest }: { href: string; children: React.ReactNode }) => (
    <a href={href} {...rest}>
      {children}
    </a>
  ),
}))
vi.mock("sonner", () => ({ toast: { success: vi.fn(), error: vi.fn(), message: vi.fn() } }))
;(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true

import { EnterpriseKnowledgeSync } from "@/components/settings/enterprise-knowledge-sync"
import { EnterpriseRoi } from "@/components/settings/enterprise-roi"
import { EnterpriseCost } from "@/components/settings/enterprise-cost"

let root: Root
let host: HTMLDivElement

beforeEach(() => {
  host = document.createElement("div")
  document.body.appendChild(host)
  root = createRoot(host)
  mocks.byKey = {}
})
afterEach(() => {
  act(() => root.unmount())
  host.remove()
})

function render(node: React.ReactNode) {
  act(() => root.render(<div className="gv-set">{node}</div>))
}

const days = Array.from({ length: 14 }, (_, i) => ({ date: `2026-10-${String(i + 6).padStart(2, "0")}`, documents: i === 3 ? 0 : 5 }))

const overview = (patch: Partial<KnowledgeSyncOverview> = {}): KnowledgeSyncOverview => ({
  ingestionDisabled: false,
  heldReason: null,
  sourcesSyncing: 1,
  sourceCount: 1,
  documentsIndexed: 12,
  lastSyncAt: null,
  failedJobs: 0,
  days,
  totalDocuments: 65,
  windowDays: 14,
  sources: [
    {
      connectorId: "c1",
      name: "Notion workspace",
      type: "notion",
      connectorStatus: "active",
      status: "failed",
      syncConfigured: true,
      schedule: "Daily",
      docs14d: 65,
      lastSyncAt: null,
      lastJobStatus: "failed",
      lastError: "token expired",
      heldReason: null,
    },
  ],
  ...patch,
})

describe("Enterprise knowledge sync", () => {
  it("shows real sources and lets admins retry", () => {
    mocks.byKey["/api/enterprise/insights/knowledge-sync"] = overview()
    render(<EnterpriseKnowledgeSync isAdmin />)
    expect(host.textContent).toContain("Notion workspace")
    expect(host.textContent).toContain("token expired")
    const retry = Array.from(host.querySelectorAll("button")).find((b) => b.textContent === "Retry")
    expect(retry?.disabled).toBe(false)
    expect(host.querySelectorAll(".ent-bars span.zero")).toHaveLength(1)
  })

  it("disables every sync control when ingestion is turned off", () => {
    mocks.byKey["/api/enterprise/insights/knowledge-sync"] = overview({ ingestionDisabled: true })
    render(<EnterpriseKnowledgeSync isAdmin />)
    expect(host.textContent).toContain("Ingestion is turned off")
    const retry = Array.from(host.querySelectorAll("button")).find((b) => b.textContent === "Retry")
    const all = Array.from(host.querySelectorAll("button")).find((b) => b.textContent?.includes("Sync all now"))
    expect(retry?.disabled).toBe(true)
    expect(all?.disabled).toBe(true)
  })
})

const roi = (patch: Partial<AgentRoiSummary> = {}): AgentRoiSummary => ({
  periodDays: 30,
  periodStart: "2026-09-19T00:00:00Z",
  periodEnd: "2026-10-19T00:00:00Z",
  laborUsdPerHour: null,
  agents: [
    { agentId: "a1", name: "Router agent", department: "Sales", tasks: 4, minutesPerTask: null, costUsd: 0.2, laborValueUsd: null, returnMultiple: null },
  ],
  rows: [],
  hiddenWithoutEstimate: 1,
  totals: { agentCostUsd: null, laborValueUsd: null, netValueUsd: null, returnMultiple: null },
  truncated: false,
  ...patch,
})

describe("Enterprise agent ROI", () => {
  it("asks for the hourly rate instead of assuming one", () => {
    mocks.byKey["/api/enterprise/insights/agent-roi"] = roi()
    render(<EnterpriseRoi isAdmin />)
    expect(host.textContent).toContain("Set your hourly rate")
    expect(host.textContent).not.toContain("$45")
    const rate = host.querySelector<HTMLInputElement>('input[aria-label="Hourly labor rate"]')
    expect(rate?.value).toBe("")
    expect(host.textContent).toContain("Minutes per task")
  })

  it("shows totals and per agent rows once inputs exist, and is read only for non-admins", () => {
    const row = { agentId: "a1", name: "Router agent", department: "Sales", tasks: 4, minutesPerTask: 15, costUsd: 0.5, laborValueUsd: 60, returnMultiple: 120 }
    mocks.byKey["/api/enterprise/insights/agent-roi"] = roi({
      laborUsdPerHour: 60,
      agents: [row],
      rows: [row],
      hiddenWithoutEstimate: 0,
      totals: { agentCostUsd: 0.5, laborValueUsd: 60, netValueUsd: 59.5, returnMultiple: 120 },
    })
    render(<EnterpriseRoi isAdmin={false} />)
    expect(host.textContent).toContain("$60.00")
    expect(host.textContent).toContain("120×")
    expect(host.textContent).toContain("4 tasks · 15 min each")
    expect(host.querySelector<HTMLInputElement>('input[aria-label="Hourly labor rate"]')?.disabled).toBe(true)
    expect(Array.from(host.querySelectorAll("button")).some((b) => b.textContent === "Save estimates")).toBe(false)
  })
})

describe("Enterprise cost attribution", () => {
  it("renders None yet with no measured spend", () => {
    const empty: CostAttributionSummary = {
      periodStart: "2026-10-01T00:00:00Z",
      periodEnd: "2026-10-19T00:00:00Z",
      source: null,
      totalCostUsd: 0,
      agentCount: 0,
      byAgent: [],
      byDepartment: [],
      truncated: false,
    }
    mocks.byKey["/api/enterprise/insights/cost"] = empty
    render(<EnterpriseCost />)
    expect(host.textContent).toContain("None yet")
    expect(host.querySelector('[aria-label="Group by"] [aria-pressed="true"]')?.textContent).toBe("By department")
  })
})
