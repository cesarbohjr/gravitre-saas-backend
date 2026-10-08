// @vitest-environment jsdom
import React, { act, Suspense } from "react"
import { createRoot, type Root } from "react-dom/client"
import { afterEach, beforeEach, expect, it, vi } from "vitest"
import NewWorkflowPage from "@/app/(app)/workflows/new/builder/page"
import WorkflowDetailPage from "@/app/(app)/workflows/[id]/page"
import CapabilitiesPage from "@/app/(app)/marketplace/capabilities/page"
import { WorkflowIntelligenceDrawer } from "@/components/workflows/intelligence-drawer"
import { ConnectorOpsCard } from "@/app/(app)/admin/intelligence/_components/connector-ops-card"
import { ScoreBar } from "@/app/(app)/admin/intelligence/_components/shared"
import {
  formatSimulationDuration,
  simulationDuration,
  totalSimulationDuration,
} from "@/lib/workflow-evidence"
const state = vi.hoisted(() => ({
  entries: {} as Record<string, { data?: unknown; error?: Error; isLoading?: boolean }>,
  mutate: vi.fn(),
  execute: vi.fn(),
  update: vi.fn(),
  push: vi.fn(),
  create: vi.fn(),
  replace: vi.fn(),
  patchServer: vi.fn(),
  patchTool: vi.fn(),
}))
vi.mock("swr", () => ({
  default: (key: string | string[] | null) => ({
    ...(key ? state.entries[typeof key === "string" ? key : JSON.stringify(key)] : {}),
    mutate: state.mutate,
  }),
}))
vi.mock("@/lib/api", () => ({
  workflowsApi: {
    create: state.create,
    get: vi.fn(),
    getBuilder: vi.fn(),
    update: state.update,
    execute: state.execute,
  },
  runsApi: { list: vi.fn() },
  intelligenceApi: { connectorWrites: vi.fn() },
  portableCapabilitiesApi: {},
  mcpAdminApi: { patchServer: state.patchServer, patchTool: state.patchTool },
}))
vi.mock("@/lib/auth-context", () => ({ useAuth: () => ({ user: { id: "owner" } }) }))
vi.mock("@/lib/use-org-admin", () => ({ useOrgAdmin: () => ({ isAdmin: true, isLoading: false }) }))
vi.mock("next/navigation", () => ({
  useSearchParams: () => new URLSearchParams("sourceId=source-1&sourceType=crm"),
  usePathname: () => "/workflows",
  useRouter: () => ({ push: state.push, replace: state.replace }),
}))
vi.mock("@/components/gravitre/app-shell", () => ({
  AppShell: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
}))
vi.mock("@/components/gravitre/ai-workspace-provider", () => ({
  usePublishGravitreAISelection: () => undefined,
}))
vi.mock("@/components/intelligence/ask-gravitre-summon-button", () => ({
  AskGravitreSummonButton: () => null,
}))
vi.mock("@/components/workflows/workflow-pre-run-panel", () => ({
  WorkflowPreRunPanel: () => null,
}))
vi.mock("@/components/ui/dialog", () => {
  const Box = ({ children }: { children: React.ReactNode }) => <div>{children}</div>
  return {
    Dialog: ({ open, children }: { open: boolean; children: React.ReactNode }) =>
      open ? <div role="dialog">{children}</div> : null,
    DialogContent: Box,
    DialogHeader: Box,
    DialogTitle: Box,
    DialogDescription: Box,
    DialogFooter: Box,
  }
})
vi.mock("@/components/ui/sheet", () => {
  const Box = ({ children }: { children: React.ReactNode }) => <div>{children}</div>
  return {
    Sheet: ({ open, children }: { open: boolean; children: React.ReactNode }) =>
      open ? <div>{children}</div> : null,
    SheetContent: Box,
    SheetTitle: Box,
    SheetDescription: Box,
  }
})
;(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true
let host: HTMLDivElement
let root: Root
beforeEach(() => {
  vi.clearAllMocks()
  state.entries = {}
  state.mutate.mockResolvedValue(undefined)
  host = document.createElement("div")
  document.body.append(host)
  root = createRoot(host)
})
afterEach(() => {
  act(() => root.unmount())
  host.remove()
})
async function render(element: React.ReactNode) {
  await act(async () => {
    root.render(element)
  })
}
async function click(label: string) {
  const button = Array.from(
    (host.querySelector('[role="dialog"]') ?? host).querySelectorAll("button"),
  ).find((el) => el.textContent?.trim() === label)
  expect(button, label).toBeTruthy()
  await act(async () => button!.click())
}
async function workflow() {
  state.entries['["workflow-detail","wf"]'] = {
    data: { id: "wf", name: "Invoice follow-up", status: "active" },
  }
  state.entries['["workflow-builder","wf"]'] = {
    data: { nodes: [{ id: "a", name: "Send invoice", node_type: "task" }] },
  }
  state.entries['["workflow-active-run","wf"]'] = { data: { runs: [] } }
  state.entries['["workflow-latest-run","wf"]'] = { data: { runs: [] } }
  const params = Promise.resolve({ id: "wf" })
  await params
  await render(
    <Suspense>
      <WorkflowDetailPage params={params} />
    </Suspense>,
  )
}
it("keeps zero timing and rejects absent, invalid or reversed timestamps", () => {
  expect(
    formatSimulationDuration(
      simulationDuration({
        started_at: "2026-10-04T00:00:00Z",
        completed_at: "2026-10-04T00:00:00Z",
      }),
    ),
  ).toBe("0ms")
  for (const step of [
    {},
    { started_at: "bad", completed_at: "bad" },
    { started_at: "2026-10-05", completed_at: "2026-10-04" },
  ])
    expect(simulationDuration(step)).toBeNull()
  expect(totalSimulationDuration([{ predictedMs: 0 }, { predictedMs: null }])).toBeNull()
})
it("does not claim success for an omitted dry-run status", async () => {
  await render(
    <WorkflowIntelligenceDrawer
      open
      onClose={vi.fn()}
      workflowId="wf"
      isPersisted
      nodes={[]}
      initialTab="dryrun"
      prefetchedDryRun={{ steps: [{ id: "a" }], errors: [] } as never}
    />,
  )
  expect(host.textContent).toContain("Not reported")
  expect(host.textContent).not.toContain("Validation passed")
})
it("shows a successful dry run only when explicitly reported", async () => {
  await render(
    <WorkflowIntelligenceDrawer
      open
      onClose={vi.fn()}
      workflowId="wf"
      isPersisted
      nodes={[]}
      initialTab="dryrun"
      prefetchedDryRun={
        { status: "completed", steps: [{ id: "a", status: "completed" }], errors: [] } as never
      }
    />,
  )
  expect(host.textContent).toContain("Validation passed")
})
it("keeps an execution request open if no durable run ID is returned", async () => {
  await workflow()
  state.execute.mockResolvedValue({ status: "running" })
  await click("Run now")
  expect(state.execute).not.toHaveBeenCalled()
  await click("Run in production")
  expect(host.querySelector('[role="alert"]')?.textContent).toContain("no run ID")
  expect(state.push).not.toHaveBeenCalled()
})
it("opens the returned run even if refresh fails after execution", async () => {
  await workflow()
  state.execute.mockResolvedValue({ run_id: "durable", status: "pending_approval" })
  state.mutate.mockRejectedValue(new Error("refresh failed"))
  await click("Run now")
  await click("Run in production")
  expect(state.push).toHaveBeenCalledWith("/runs/durable")
  expect(host.querySelector('[role="dialog"]')).toBeNull()
})
it("blocks production when active execution checks fail", async () => {
  await workflow()
  state.entries['["workflow-active-run","wf"]'] = { error: new Error("offline") }
  await render(
    <Suspense>
      <WorkflowDetailPage params={Promise.resolve({ id: "wf" })} />
    </Suspense>,
  )
  const run = Array.from(
    (host.querySelector('[role="dialog"]') ?? host).querySelectorAll("button"),
  ).find((el) => el.textContent?.trim() === "Run now")
  expect(run?.disabled).toBe(true)
  expect(host.textContent).toContain("Active execution check unavailable")
})
it("keeps the MCP approval dialog open when the API returns disabled", async () => {
  state.entries["portable-capability-mcp-servers"] = {
    data: {
      servers: [
        { id: "mcp", server_name: "CRM", source_capability_package_id: "pkg", enabled: false },
      ],
    },
  }
  state.entries["portable-capability-mcp-tools"] = {
    data: { tools: [{ id: "tool", server_id: "mcp", tool_name: "Read", enabled: false }] },
  }
  await render(<CapabilitiesPage />)
  await click("Approve server")
  expect(state.patchServer).not.toHaveBeenCalled()
  state.patchServer.mockResolvedValue({ server: { enabled: false } })
  await click("Approve server")
  expect(state.patchServer).toHaveBeenCalledWith("mcp", true)
  expect(host.querySelector('[role="alert"]')?.textContent).toContain("did not confirm")
})
it("does not label missing connector evidence healthy", async () => {
  await render(<ConnectorOpsCard />)
  expect(host.textContent).not.toContain("Healthy")
  expect(host.textContent).toContain("Not reported")
})
it("preserves cached connector evidence and offers retry on refresh errors", async () => {
  state.entries["admin/intelligence/connector-writes"] = {
    data: {
      rows: [{ vendor: "CRM", action: "read", requested: 0, completed: 0, failed: 0 }],
      hasSpike: false,
    },
    error: new Error("offline"),
  }
  await render(<ConnectorOpsCard />)
  expect(host.textContent).toContain("CRM")
  await click("Try again")
  expect(state.mutate).toHaveBeenCalled()
})
it("renders an unknown score without a fabricated zero progressbar", async () => {
  await render(<ScoreBar label="Grounding" score={null} />)
  expect(host.textContent).toContain("Not reported")
  expect(host.querySelector('[role="progressbar"]')).toBeNull()
  await render(<ScoreBar label="Grounding" score={0} />)
  expect(host.querySelector('[role="progressbar"]')?.getAttribute("aria-valuenow")).toBe("0")
})

async function enterName(value: string) {
  const input = host.querySelector<HTMLInputElement>("#workflow-name")!
  await act(async () => {
    Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, "value")!.set!.call(input, value)
    input.dispatchEvent(new Event("input", { bubbles: true }))
  })
}
it("creates a persisted workflow and forwards source handoff parameters", async () => {
  await render(<NewWorkflowPage />)
  await enterName("  Invoice follow-up  ")
  state.create.mockResolvedValue({ id: "12345678-1234-4234-8234-123456789012" })
  await click("Create & open builder")
  expect(state.create).toHaveBeenCalledWith({
    name: "Invoice follow-up",
    goal: undefined,
    description: undefined,
  })
  expect(state.replace).toHaveBeenCalledWith(
    "/workflows/12345678-1234-4234-8234-123456789012/builder?sourceId=source-1&sourceType=crm",
  )
})
it("retains the creation draft when the API fails", async () => {
  await render(<NewWorkflowPage />)
  await enterName("Invoice follow-up")
  state.create.mockRejectedValue(new Error("offline"))
  await click("Create & open builder")
  expect(host.querySelector<HTMLInputElement>("#workflow-name")?.value).toBe("Invoice follow-up")
  expect(host.querySelector('[role="alert"]')?.textContent).toContain("offline")
  expect(state.replace).not.toHaveBeenCalled()
})
it("prevents duplicate creation and reuses the saved ID if opening the builder fails", async () => {
  let finish!: (value: unknown) => void
  state.create.mockImplementation(
    () =>
      new Promise((resolve) => {
        finish = resolve
      }),
  )
  await render(<NewWorkflowPage />)
  await enterName("Invoice follow-up")
  await act(async () => {
    const form = host.querySelector("form")!
    form.dispatchEvent(new Event("submit", { bubbles: true, cancelable: true }))
    form.dispatchEvent(new Event("submit", { bubbles: true, cancelable: true }))
  })
  expect(state.create).toHaveBeenCalledTimes(1)
  state.replace.mockImplementationOnce(() => {
    throw new Error("navigation blocked")
  })
  await act(async () => finish({ id: "12345678-1234-4234-8234-123456789012" }))
  await click("Open saved builder")
  expect(state.create).toHaveBeenCalledTimes(1)
  expect(state.replace).toHaveBeenCalledTimes(2)
})
