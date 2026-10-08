// @vitest-environment jsdom
import React, { act, type ReactNode } from "react"
import { createRoot, type Root } from "react-dom/client"
import { beforeEach, afterEach, expect, it, vi } from "vitest"
import { NewAssignmentPageContent } from "@/components/assignments/assignment-create-workspace"
import { AgentCapabilitiesCard } from "@/components/gravitre/agent-capabilities-card"
import ModelDetailPage from "@/app/(app)/models/[id]/page"
import ModelProfilePage from "@/app/(app)/intelligence/models/[name]/page"
import { MemoryCard } from "@/components/agents/agent-memory-row"
const state = vi.hoisted(() => ({
  data: {} as Record<string, unknown>,
  errors: {} as Record<string, unknown>,
  submit: vi.fn(),
  push: vi.fn(),
  mutate: vi.fn(),
  deploy: vi.fn(),
  predict: vi.fn(),
}))
vi.mock("swr", () => ({
  default: (key: string | unknown[]) => {
    const name = Array.isArray(key) ? (key[0] as string) : key
    return {
      data: state.data[name],
      error: state.errors[name],
      isLoading: false,
      mutate: state.mutate,
    }
  },
}))
vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: state.push }),
  useSearchParams: () => new URLSearchParams(),
  useParams: () => ({ name: "test_model" }),
}))
vi.mock("@/lib/auth-context", () => ({
  useAuth: () => ({ user: { id: "owner" } }),
}))
vi.mock("@/hooks/use-async-job", () => ({
  useAsyncJob: () => ({ submitJob: state.submit, isWorking: false }),
}))
vi.mock("@/components/gravitre/app-shell", () => ({
  AppShell: ({ children }: { children: ReactNode }) => <main>{children}</main>,
}))
vi.mock("@/components/gravitre/agent-identity-avatar", () => ({
  AgentIdentityAvatar: () => null,
}))
vi.mock("@/components/gravitre/nodus-product", () => ({
  GravitrePageHeader: ({
    title,
    actions,
  }: {
    title: ReactNode
    actions: ReactNode
  }) => (
    <header>
      <h1>{title}</h1>
      {actions}
    </header>
  ),
  GravitreMetric: ({ label, value }: { label: string; value: ReactNode }) => (
    <div>
      {label}: {value}
    </div>
  ),
}))
vi.mock("@/lib/api", () => ({
  agentsApi: {},
  connectorsApi: {},
  marketplaceApi: {},
  intelligenceApi: {},
  mlAdminApi: {},
  mlModelsApi: { deploy: state.deploy, predict: state.predict },
}))
vi.mock("@/components/gravitre/model-detail-insights", () => ({
  ModelDetailInsights: (props: {
    connectionsReported?: boolean
    inferenceJson: string
    onInferenceJsonChange: (value: string) => void
    onRunInference: () => void
    predictError: string | null
  }) => (
    <div>
      <span>
        {props.connectionsReported
          ? "Connections reported"
          : "Connection evidence not reported"}
      </span>
      <textarea
        value={props.inferenceJson}
        onChange={(event) => props.onInferenceJsonChange(event.target.value)}
      />
      <button onClick={props.onRunInference}>Run inference</button>
      {props.predictError && <p role="alert">{props.predictError}</p>}
    </div>
  ),
}))
vi.mock("sonner", () => ({ toast: { success: vi.fn(), error: vi.fn() } }))
;(
  globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }
).IS_REACT_ACT_ENVIRONMENT = true
let root: Root, container: HTMLDivElement
beforeEach(() => {
  vi.clearAllMocks()
  state.errors = {}
  state.data = {
    "assignment-agents": {
      agents: [{ id: "agent", name: "Research", role: "Analyst" }],
    },
    "assignment-installs": { installs: [] },
    "assignment-connectors": {
      connectors: [
        { id: "connected", name: "Real CRM", status: "connected" },
        { id: "unknown", name: "Unknown CRM", status: "unknown" },
      ],
    },
  }
  state.submit.mockResolvedValue({ jobId: "created-job", status: "queued" })
  container = document.createElement("div")
  document.body.append(container)
  root = createRoot(container)
})
afterEach(() => {
  act(() => root.unmount())
  container.remove()
})
const click = (text: string) =>
  act(() =>
    [...container.querySelectorAll<HTMLButtonElement>("button")]
      .find((b) => b.textContent?.trim() === text)!
      .click(),
  )
const input = (value: string) =>
  act(() => {
    const el = container.querySelector("textarea")!
    Object.getOwnPropertyDescriptor(
      HTMLTextAreaElement.prototype,
      "value",
    )!.set!.call(el, value)
    el.dispatchEvent(new Event("input", { bubbles: true }))
  })
const check = (text: string) =>
  act(() =>
    [...container.querySelectorAll("label")]
      .find((el) => el.textContent?.includes(text))!
      .querySelector<HTMLInputElement>("input")!
      .click(),
  )
function createToReview() {
  act(() => root.render(<NewAssignmentPageContent />))
  input("Research our audience and prepare a report")
  click("Continue")
  check("Real CRM")
  click("Continue")
  check("Reports")
  click("Continue")
  check("Keep in assignment")
  click("Continue")
}
it("uses real connections and disables unknown connection status", () => {
  act(() => root.render(<NewAssignmentPageContent />))
  input("Research this audience")
  click("Continue")
  expect(
    [...container.querySelectorAll("label")]
      .find((el) => el.textContent?.includes("Unknown CRM"))!
      .querySelector<HTMLInputElement>("input")?.disabled,
  ).toBe(true)
  expect(container.textContent).not.toContain("Salesforce")
})
it("rejects whitespace-only briefs", () => {
  act(() => root.render(<NewAssignmentPageContent />))
  input("             ")
  expect(
    [...container.querySelectorAll<HTMLButtonElement>("button")].find(
      (b) => b.textContent === "Continue",
    )?.disabled,
  ).toBe(true)
})
it("inserts useful brief starters", () => {
  act(() => root.render(<NewAssignmentPageContent />))
  click("Report starter")
  expect(container.querySelector("textarea")?.value).toContain(
    "cite the sources",
  )
})
it("submits the existing context and opens the returned job immediately", async () => {
  createToReview()
  await act(async () => click("Run task"))
  expect(state.submit).toHaveBeenCalledWith(
    "Research our audience and prepare a report",
    {
      agentId: "agent",
      context: {
        priority: "normal",
        useTrainingKnowledge: true,
        requireApproval: true,
        dataSources: ["Real CRM"],
        outputs: ["Reports"],
        destinations: ["Keep in assignment"],
      },
    },
  )
  expect(state.push).toHaveBeenCalledWith("/assignments/created-job")
})
it("preserves the review after submission failure", async () => {
  state.submit.mockRejectedValue(new Error("Permission denied"))
  createToReview()
  await act(async () => click("Run task"))
  expect(container.querySelector('[role="alert"]')?.textContent).toContain(
    "Permission denied",
  )
  expect(container.textContent).toContain("Research our audience")
  expect(state.push).not.toHaveBeenCalled()
})
it("prevents duplicate pending submissions", async () => {
  let finish!: (job: { jobId: string }) => void
  state.submit.mockImplementation(
    () =>
      new Promise((resolve) => {
        finish = resolve
      }),
  )
  createToReview()
  click("Run task")
  click("Run task")
  expect(state.submit).toHaveBeenCalledTimes(1)
  await act(async () => finish({ jobId: "created-job" }))
})
it("offers retry without claiming a failed agent fetch is empty", () => {
  state.data["assignment-agents"] = undefined
  state.errors["assignment-agents"] = new Error("Offline")
  act(() => root.render(<NewAssignmentPageContent />))
  expect(container.textContent).toContain("Could not load agents")
  expect(container.textContent).not.toContain("No agents available")
  click("Try again")
  expect(state.mutate).toHaveBeenCalledOnce()
})
it("does not classify write permissions as reads and preserves zero memory count", () => {
  act(() =>
    root.render(
      <AgentCapabilitiesCard
        permissions={["Create CRM record"]}
        memoryCount={0}
      />,
    ),
  )
  const heading = [...container.querySelectorAll("div")].find(
    (el) => el.textContent?.trim() === "Can read / analyze",
  )!
  expect(heading.parentElement?.textContent).not.toContain("Create CRM record")
  expect(container.textContent).toContain("0 stored memories")
})
it("identifies absent built-in models", () => {
  state.data["intelligence/models/catalog"] = {
    catalog: {},
    orgTrainingStatus: {},
  }
  act(() => root.render(<ModelProfilePage />))
  expect(container.textContent).toContain("Model not found")
})
it("does not fabricate model readiness", () => {
  state.data["intelligence/models/catalog"] = {
    catalog: { test_model: { status: "READY" } },
  }
  act(() => root.render(<ModelProfilePage />))
  expect(container.textContent).toContain("Readiness: Not reported")
  expect(container.textContent).toContain("Signals: Not reported")
  expect(container.querySelector('[role="progressbar"]')).toBeNull()
})
it("shows memory actions without hover and separates zero confidence from unknown usage", () => {
  act(() =>
    root.render(
      <MemoryCard
        memory={{
          id: "memory",
          content: "Remember this",
          category: "fact",
          source: "Not reported",
          confidence: 0,
          usageCount: null,
          createdAt: "Not reported",
          editable: true,
        }}
        onEdit={vi.fn()}
        onDelete={vi.fn()}
      />,
    ),
  )
  expect(container.textContent).toContain("Reported confidence: 0%")
  expect(container.textContent).toContain("UsageNot reported")
  expect(container.querySelector('[class*="opacity-0"]')).toBeNull()
  expect(
    [...container.querySelectorAll("button")].map((b) => b.textContent),
  ).toEqual(["Edit", "Delete"])
})

const modelParams = Object.assign(Promise.resolve({ id: "model" }), {
  status: "fulfilled",
  value: { id: "model" },
})
function renderModel() {
  state.data["ml-model"] = {
    id: "model",
    name: "Test model",
    modelType: "classification",
    status: "ready",
    currentVersion: 1,
  }
  act(() => root.render(<ModelDetailPage params={modelParams} />))
}
it("does not announce success when deployment returns ok false", async () => {
  state.deploy.mockResolvedValue({ ok: false })
  renderModel()
  await act(async () => click("Deploy"))
  const { toast } = await import("sonner")
  expect(toast.success).not.toHaveBeenCalled()
  expect(state.mutate).not.toHaveBeenCalled()
})
it("rejects arrays containing non-object inference inputs before calling the API", async () => {
  renderModel()
  input("[null, 42]")
  await act(async () => click("Run inference"))
  expect(state.predict).not.toHaveBeenCalled()
  expect(container.querySelector('[role="alert"]')?.textContent).toContain(
    "non-empty JSON array of input objects",
  )
})
it("retains a model when its cached data cannot refresh", () => {
  state.errors["ml-model"] = new Error("Offline")
  renderModel()
  expect(container.textContent).toContain("Could not refresh model")
  expect(container.textContent).toContain("Test model")
  expect(container.textContent).toContain("Run inference")
})

it("does not treat missing connection evidence as an empty connection inventory", () => {
  renderModel()
  expect(container.textContent).toContain("Connection evidence not reported")
})
