// @vitest-environment jsdom
import React, { act } from "react"
import { createRoot, type Root } from "react-dom/client"
import { beforeEach, afterEach, expect, it, vi } from "vitest"
import TrainingPage from "@/app/training/page"
import { StartSwarmDialog } from "@/components/agent-swarm/start-swarm-dialog"
import { SwarmRunDetailPanel } from "@/components/agent-swarm/swarm-run-detail-panel"
import {
  parseTrainingExamples,
  reportedTrainingProgress,
} from "@/lib/training-journey"
const state = vi.hoisted(() => ({
  entries: {} as Record<
    string,
    { data?: unknown; error?: Error; isLoading?: boolean }
  >,
  mutate: vi.fn(),
  createDataset: vi.fn(),
  uploadRecords: vi.fn(),
  createInstruction: vi.fn(),
  assign: vi.fn(),
  deleteDataset: vi.fn(),
  start: vi.fn(),
  cancel: vi.fn(),
  aggregate: vi.fn(),
  org: vi.fn(),
}))
vi.mock("@/components/gravitre/ai-workspace-provider", () => ({ usePublishGravitreAISelection: vi.fn() }))
vi.mock("swr", () => ({
  default: (key: string | null) => ({
    ...(key ? state.entries[key] : {}),
    mutate: state.mutate,
  }),
}))
vi.mock("@/lib/api", () => ({
  trainingApi: {
    createDataset: state.createDataset,
    uploadRecords: state.uploadRecords,
    createInstruction: state.createInstruction,
    assignAgentFineTunedModel: state.assign,
    deleteDataset: state.deleteDataset,
  },
  agentsApi: {},
  marketplaceApi: {},
  agentSwarmApi: {
    start: state.start,
    cancel: state.cancel,
    aggregate: state.aggregate,
  },
}))
vi.mock("@/lib/org-context", () => ({ ensureSelectedOrg: state.org }))
const user = { id: "user" }
vi.mock("@/lib/auth-context", () => ({ useAuth: () => ({ user }) }))
vi.mock("next/navigation", () => ({
  usePathname: () => "/training",
  useSearchParams: () => new URLSearchParams(),
}))
vi.mock("sonner", () => ({
  toast: { success: vi.fn(), error: vi.fn(), message: vi.fn() },
}))
vi.mock("@/components/gravitre/app-shell", () => ({
  AppShell: ({ children }: { children: React.ReactNode }) => (
    <div>{children}</div>
  ),
}))
vi.mock("@/components/agents/agents-hub-tabs", () => ({
  AgentsHubTabs: () => null,
}))
vi.mock("@/components/gravitre/learning-surfaces-callout", () => ({
  LearningSurfacesCallout: () => null,
}))
vi.mock("@/components/intelligence/ask-gravitre-summon-button", () => ({
  AskGravitreSummonButton: () => null,
}))
vi.mock("@/components/gravitre/data-freshness", () => ({
  DataFreshness: () => null,
}))
vi.mock("@/components/gravitre/agent-ui/subagent-tool-group", () => ({
  SubagentToolGroup: ({ children }: { children: React.ReactNode }) => (
    <div>{children}</div>
  ),
}))
vi.mock("@/components/ui/dialog", () => {
  const Box = ({ children }: { children: React.ReactNode }) => (
    <div>{children}</div>
  )
  return {
    Dialog: ({
      open,
      children,
      onOpenChange,
    }: {
      open: boolean
      children: React.ReactNode
      onOpenChange: (open: boolean) => void
    }) =>
      open ? (
        <div>
          {children}
          <button onClick={() => onOpenChange(false)}>Dismiss</button>
        </div>
      ) : null,
    DialogContent: Box,
    DialogHeader: Box,
    DialogFooter: Box,
    DialogTitle: Box,
    DialogDescription: Box,
  }
})
vi.mock("framer-motion", () => ({
  useReducedMotion: () => true,
  AnimatePresence: ({ children }: { children: React.ReactNode }) => (
    <>{children}</>
  ),
  motion: Object.fromEntries(
    ["div", "section", "span"].map((tag) => [
      tag,
      ({
        children,
        initial: _i,
        animate: _a,
        exit: _e,
        layout: _l,
        transition: _t,
        ...props
      }: Record<string, unknown>) =>
        React.createElement(tag, props, children as React.ReactNode),
    ]),
  ),
}))
;(
  globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }
).IS_REACT_ACT_ENVIRONMENT = true
let root: Root, container: HTMLDivElement
const run = {
  id: "run",
  status: "running",
  objective: "Compare options",
  decisionMethod: "majority_vote",
  finalRecommendation: "Evidence to retain",
  finalConfidence: 0,
  executionVerified: false,
  subtasks: [
    {
      id: "sub",
      agentId: "agent",
      status: "completed",
      taskPrompt: "Research",
      result: { summary: "Reported finding" },
    },
  ],
}
beforeEach(() => {
  vi.clearAllMocks()
  state.org.mockResolvedValue("org")
  state.mutate.mockResolvedValue(undefined)
  state.entries = {
    "training/datasets": {
      data: {
        datasets: [
          {
            id: "dataset",
            name: "Examples",
            type: "examples",
            record_count: 2,
            status: "ready",
          },
        ],
      },
    },
    "training/jobs": { data: { jobs: [] } },
    "training/instructions": { data: { instructions: [] } },
    "training/workflow-agents": {
      data: {
        agents: [{ id: "agent", name: "Research", trainedModelId: "model" }],
      },
    },
    "training/fine-tuned-models": {
      data: { models: [{ id: "model", name: "Tuned", status: "ready" }] },
    },
    "agent-swarm/start/agents": {
      data: {
        agents: [
          { id: "parent", name: "Coordinator", status: "active" },
          { id: "worker", name: "Researcher", status: "active" },
        ],
      },
    },
    "agent-swarm/start/installs": { data: { installs: [] } },
    "agent-swarm/run": { data: run },
  }
  container = document.createElement("div")
  document.body.append(container)
  root = createRoot(container)
})
afterEach(() => {
  act(() => root.unmount())
  container.remove()
})
const render = async (el: React.ReactNode) => {
  await act(async () => root.render(el))
}
const button = (text: string) =>
  [...container.querySelectorAll<HTMLButtonElement>("button")].find(
    (b) => b.textContent?.trim() === text,
  )!
const click = async (text: string) => {
  await act(async () => button(text).click())
}
const set = async (label: string, value: string) => {
  const el = (container.querySelector(`[aria-label="${label}"]`) ??
    [...container.querySelectorAll<HTMLLabelElement>("label")].find(
      (l) => l.textContent === label,
    )?.control) as HTMLInputElement
  const prototype =
    el.tagName === "SELECT"
      ? HTMLSelectElement.prototype
      : el.tagName === "TEXTAREA"
        ? HTMLTextAreaElement.prototype
        : HTMLInputElement.prototype
  await act(async () => {
    Object.getOwnPropertyDescriptor(prototype, "value")!.set!.call(el, value)
    el.dispatchEvent(
      new Event(el.tagName === "SELECT" ? "change" : "input", {
        bubbles: true,
      }),
    )
  })
}
function deferred<T>() {
  let resolve!: (v: T) => void, reject!: (e: Error) => void
  const promise = new Promise<T>((a, b) => {
    resolve = a
    reject = b
  })
  return { promise, resolve, reject }
}
it("reports malformed bulk line numbers without silently dropping material", () => {
  expect(
    parseTrainingExamples("question => answer\n\ninvalid\nother\tresponse"),
  ).toEqual({
    records: [
      { input: "question", expected_output: "answer" },
      { input: "other", expected_output: "response" },
    ],
    invalidLines: [3],
  })
})
it("keeps genuine zero progress and rejects missing or invalid progress", () => {
  expect(reportedTrainingProgress(0)).toBe(0)
  for (const v of [undefined, null, NaN, Infinity, -1, 101, "20"])
    expect(reportedTrainingProgress(v)).toBeNull()
})
it("does not display failed initial training data as empty or zero", async () => {
  state.entries["training/datasets"] = { error: new Error("offline") }
  state.entries["training/jobs"] = { error: new Error("offline") }
  await render(<TrainingPage />)
  expect(container.textContent).toContain("Not reported")
  expect(container.textContent).not.toContain("No datasets yet")
})
it("requires explicit model selection and allows clearing an existing assignment", async () => {
  await render(<TrainingPage />)
  await click("Fine-tunes")
  await set("Workflow agent", "agent")
  expect(button("Save Assignment").disabled).toBe(true)
  await click("Use base model only")
  await click("Save Assignment")
  expect(state.assign).toHaveBeenCalledWith("agent", null)
})
it("keeps All agents as instruction scope instead of choosing the first agent", async () => {
  await render(<TrainingPage />)
  await click("Instructions")
  await set("Instruction name", "Escalate")
  await set("Instruction guidance", "Confirm before sending")
  await click("Create Instruction")
  expect(state.createInstruction).toHaveBeenCalledWith({
    name: "Escalate",
    content: "Confirm before sending",
    agent_id: undefined,
  })
})
it("retains bulk draft and makes no upload for a malformed row", async () => {
  await render(<TrainingPage />)
  await click("Add examples")
  await set("Bulk examples", "good => output\nbad")
  await click("Import pasted examples")
  expect(state.uploadRecords).not.toHaveBeenCalled()
  expect(
    container.querySelector<HTMLTextAreaElement>(
      '[aria-label="Bulk examples"]',
    )!.value,
  ).toContain("bad")
  expect(container.textContent).toContain("Fix lines 2")
})
it("retries a partial starter import into the already created dataset", async () => {
  state.createDataset.mockResolvedValue({ id: "starter" })
  state.uploadRecords
    .mockRejectedValueOnce(new Error("offline"))
    .mockResolvedValueOnce({ added: 2 })
  await render(<TrainingPage />)
  await click("Load starter examples")
  await click("Retry starter import")
  expect(state.createDataset).toHaveBeenCalledTimes(1)
  expect(state.uploadRecords).toHaveBeenNthCalledWith(
    2,
    "starter",
    expect.any(Array),
  )
})
it("retains deletion confirmation and dataset on failure", async () => {
  state.deleteDataset.mockRejectedValue(new Error("offline"))
  await render(<TrainingPage />)
  await click("Delete")
  const confirm = [...container.querySelectorAll<HTMLButtonElement>("button")]
    .filter((b) => b.textContent === "Delete")
    .at(-1)!
  await act(async () => confirm.click())
  expect(container.textContent).toContain("Delete Examples?")
  expect(container.textContent).toContain("Your edits are retained")
})
it("does not create a progress gauge when job progress is omitted", async () => {
  state.entries["training/jobs"] = {
    data: {
      jobs: [
        {
          id: "job",
          dataset_id: "dataset",
          status: "training",
          model_base: "base",
        },
      ],
    },
  }
  await render(<TrainingPage />)
  await click("Jobs (1)")
  expect(container.textContent).toContain("Progress not reported")
  expect(container.querySelector('[role="progressbar"]')).toBeNull()
})
it("requires every multi-agent subtask to be complete", async () => {
  await render(
    <StartSwarmDialog open onOpenChange={vi.fn()} onStarted={vi.fn()} />,
  )
  await set("Objective", "Research options")
  await set("Task for subtask 1", "Compare")
  await click("Add subtask")
  expect(button("Start multi-agent run").disabled).toBe(true)
  await click("Start multi-agent run")
  expect(state.start).not.toHaveBeenCalled()
})
it("blocks dismissal and duplicate starts while pending, retaining failed drafts", async () => {
  const pending = deferred<never>()
  state.start.mockReturnValue(pending.promise)
  const close = vi.fn()
  await render(
    <StartSwarmDialog open onOpenChange={close} onStarted={vi.fn()} />,
  )
  await set("Objective", "Research options")
  await set("Task for subtask 1", "Compare")
  await click("Start multi-agent run")
  await click("Dismiss")
  expect(close).not.toHaveBeenCalled()
  expect(state.start).toHaveBeenCalledTimes(1)
  await act(async () => pending.reject(new Error("offline")))
  expect(container.querySelector<HTMLTextAreaElement>("textarea")!.value).toBe(
    "Research options",
  )
  expect(container.textContent).toContain(
    "Your objective and subtasks are retained",
  )
})
it("retains cached recommendation after refresh failure, including a zero estimate", async () => {
  state.entries["agent-swarm/run"].error = new Error("offline")
  await render(
    <SwarmRunDetailPanel
      swarmRunId="run"
      onClose={vi.fn()}
      onMutateList={vi.fn()}
    />,
  )
  expect(container.textContent).toContain("Evidence to retain")
  expect(container.textContent).toContain("Could not refresh run evidence")
  expect(container.textContent).toContain("0%")
  expect(container.textContent).toContain("Council estimate")
})
it("confirms cancellation and caches the API result without a fallible refresh", async () => {
  state.cancel.mockResolvedValue({ ...run, status: "cancelled" })
  await render(
    <SwarmRunDetailPanel
      swarmRunId="run"
      onClose={vi.fn()}
      onMutateList={vi.fn()}
    />,
  )
  await click("Cancel run")
  expect(state.cancel).not.toHaveBeenCalled()
  await click("Confirm cancellation")
  expect(state.cancel).toHaveBeenCalledWith("run")
  expect(state.mutate).toHaveBeenCalledWith(
    expect.objectContaining({ status: "cancelled" }),
    { revalidate: false },
  )
})
it("retains cancellation confirmation after failure and blocks pending close", async () => {
  const pending = deferred<never>()
  state.cancel.mockReturnValue(pending.promise)
  await render(
    <SwarmRunDetailPanel
      swarmRunId="run"
      onClose={vi.fn()}
      onMutateList={vi.fn()}
    />,
  )
  await click("Cancel run")
  await click("Confirm cancellation")
  expect(
    container.querySelector<HTMLButtonElement>('[aria-label="Close detail"]')!
      .disabled,
  ).toBe(true)
  await act(async () => pending.reject(new Error("offline")))
  expect(container.textContent).toContain("Could not cancel this run")
  expect(button("Confirm cancellation")).toBeTruthy()
})
it("does not imply zero subtasks when evidence was omitted", async () => {
  state.entries["agent-swarm/run"] = { data: { ...run, subtasks: undefined } }
  await render(
    <SwarmRunDetailPanel
      swarmRunId="run"
      onClose={vi.fn()}
      onMutateList={vi.fn()}
    />,
  )
  expect(container.textContent).toContain("Subtask evidence not reported")
  expect(button("Aggregate")).toBeUndefined()
})

it("retains each dataset preparation draft after closing and reopening", async () => {
  await render(<TrainingPage />)
  await click("Add examples")
  await set("Example input", "Keep this draft")
  await set("Expected output", "Preferred answer")
  await click("Cancel")
  await click("Add examples")
  expect(
    container.querySelector<HTMLTextAreaElement>(
      '[aria-label="Example input"]',
    )!.value,
  ).toBe("Keep this draft")
  expect(
    container.querySelector<HTMLTextAreaElement>(
      '[aria-label="Expected output"]',
    )!.value,
  ).toBe("Preferred answer")
})
it("does not announce a failed aggregate response as a recommendation", async () => {
  state.aggregate.mockResolvedValue({
    ...run,
    status: "failed",
    finalRecommendation: null,
  })
  await render(
    <SwarmRunDetailPanel
      swarmRunId="run"
      onClose={vi.fn()}
      onMutateList={vi.fn()}
    />,
  )
  await click("Aggregate")
  expect(container.textContent).toContain(
    "The council could not produce a recommendation",
  )
  expect(state.mutate).toHaveBeenCalledWith(
    expect.objectContaining({ status: "failed" }),
    { revalidate: false },
  )
})

it("freezes training creation during persistence and retains a failed name", async () => {
  const pending = deferred<never>()
  state.createDataset.mockReturnValue(pending.promise)
  await render(<TrainingPage />)
  await set("Dataset name", "Important teaching set")
  await click("Create Examples dataset")
  expect(
    container
      .querySelector('[aria-label="Dataset name"]')!
      .matches(":disabled"),
  ).toBe(true)
  expect(state.createDataset).toHaveBeenCalledTimes(1)
  await act(async () => pending.reject(new Error("offline")))
  expect(
    container.querySelector<HTMLInputElement>('[aria-label="Dataset name"]')!
      .value,
  ).toBe("Important teaching set")
  expect(container.textContent).toContain("Your edits are retained")
})
it("catches asynchronous file-read failure before any document import", async () => {
  state.entries["training/datasets"] = {
    data: {
      datasets: [
        {
          id: "docs",
          name: "Policies",
          type: "documents",
          record_count: 0,
          status: "ready",
        },
      ],
    },
  }
  await render(<TrainingPage />)
  await click("Add documents")
  const input = container.querySelector<HTMLInputElement>('input[type="file"]')!
  const file = new File(["policy"], "policy.txt", { type: "text/plain" })
  Object.defineProperty(file, "text", {
    value: () => Promise.reject(new Error("Could not read policy.txt")),
  })
  Object.defineProperty(input, "files", { configurable: true, value: [file] })
  await act(async () =>
    input.dispatchEvent(new Event("change", { bubbles: true })),
  )
  expect(container.textContent).toContain("Could not read policy.txt")
  expect(input.matches(":disabled")).toBe(false)
})
