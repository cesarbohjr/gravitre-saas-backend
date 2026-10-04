// @vitest-environment jsdom
import React, { act } from "react"
import { createRoot, type Root } from "react-dom/client"
import { beforeEach, afterEach, expect, it, vi } from "vitest"
import { AgentIdentityEditor } from "@/components/gravitre/agent-identity-editor"
import {
  AgentCapabilitiesEditorCard,
  AgentPersonalityEditorCard,
} from "@/components/gravitre/agent-profile-editors"
import { AgentPolicyEditor } from "@/components/agents/agent-policy-editor"
import { AgentAutonomyPanel } from "@/components/agents/agent-autonomy-panel"
import { AgentKnowledgeRetrievalTab } from "@/components/agents/knowledge/agent-knowledge-retrieval-tab"
import { AgentKnowledgeAddSheet } from "@/components/agents/knowledge/agent-knowledge-add-sheet"
import { AgentKnowledgeSourcesTab } from "@/components/agents/knowledge/agent-knowledge-sources-tab"
import { AgentKnowledgeExpertPacksTab } from "@/components/agents/knowledge/agent-knowledge-expert-packs-tab"
import type { Agent } from "@/types/api"
import type { AgentKnowledgeState } from "@/components/agents/knowledge/use-agent-knowledge"
import { toast } from "sonner"
const state = vi.hoisted(() => ({
  update: vi.fn(),
  upload: vi.fn(),
  upsert: vi.fn(),
  retrieve: vi.fn(),
  sync: vi.fn(),
  mutate: vi.fn(),
  data: undefined as unknown,
  error: undefined as unknown,
}))
vi.mock("swr", () => ({
  default: () => ({
    data: state.data,
    error: state.error,
    isLoading: false,
    mutate: state.mutate,
  }),
  mutate: state.mutate,
}))
vi.mock("@/lib/api", () => ({
  agentsApi: { update: state.update, uploadAvatar: state.upload },
  agentIdentityApi: { upsert: state.upsert, get: vi.fn() },
  agentKnowledgeApi: {
    testRetrieval: state.retrieve,
    syncAssignment: state.sync,
  },
}))
vi.mock("@/lib/use-org-admin", () => ({
  useOrgAdmin: () => ({ isAdmin: false }),
}))
vi.mock("@/lib/view-mode-context", () => ({
  useViewModeSafe: () => ({ isLite: false }),
}))
vi.mock("@/components/gravitre/agent-identity-avatar", () => ({
  AgentIdentityAvatar: () => null,
}))
vi.mock("@/components/gravitre/agent-identity-picker", () => ({
  AgentIdentityPicker: () => null,
}))
vi.mock("@/components/gravitre/agent-voice-assignment", () => ({
  AgentVoiceAssignment: () => null,
}))
vi.mock("sonner", () => ({ toast: { success: vi.fn(), error: vi.fn() } }))
;(
  globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }
).IS_REACT_ACT_ENVIRONMENT = true
const agent = {
  id: "agent",
  name: "Research",
  department: "Support",
  capabilities: [],
  permissions: ["HubSpot", "Custom CRM scope"],
  guardrails: ["Custom safeguard"],
} as unknown as Agent
let root: Root, container: HTMLDivElement
beforeEach(() => {
  vi.clearAllMocks()
  state.data = undefined
  state.error = undefined
  state.mutate.mockResolvedValue(undefined)
  container = document.createElement("div")
  document.body.append(container)
  root = createRoot(container)
})
afterEach(() => {
  act(() => root.unmount())
  container.remove()
})
const click = (text: string, scope: ParentNode = document) =>
  act(() =>
    [...scope.querySelectorAll<HTMLButtonElement>("button")]
      .find((b) => b.textContent?.trim() === text)!
      .click(),
  )
const type = (el: HTMLInputElement, value: string) =>
  act(() => {
    Object.getOwnPropertyDescriptor(
      HTMLInputElement.prototype,
      "value",
    )!.set!.call(el, value)
    el.dispatchEvent(new Event("input", { bubbles: true }))
  })
const workspace = () =>
  ({
    assignments: [
      {
        id: "assignment",
        sourceType: "rag_source",
        sourceId: "source",
        label: "Runbook",
      },
    ],
    orgSources: [],
    assignedSourceIds: new Set(),
    assignedPackIds: new Set(),
    sourceIngestionById: new Map(),
    mutateAssignments: vi.fn(),
    removeAssignment: vi.fn().mockResolvedValue(false),
    assigningKey: null,
    removingId: null,
    loading: false,
    orgSourcesLoading: false,
  }) as unknown as AgentKnowledgeState
it("keeps identity drafts when a saved photo refreshes the agent props", async () => {
  state.upload.mockResolvedValue({ avatarUrl: "https://example.com/photo.png" })
  act(() => root.render(<AgentIdentityEditor agent={agent} />))
  click("Edit identity")
  type(
    document.querySelector<HTMLInputElement>("#agent-identity-name")!,
    "Draft name",
  )
  const fileInput =
    document.querySelector<HTMLInputElement>('input[type="file"]')!
  Object.defineProperty(fileInput, "files", {
    value: [new File(["x"], "photo.png", { type: "image/png" })],
  })
  await act(async () =>
    fileInput.dispatchEvent(new Event("change", { bubbles: true })),
  )
  act(() =>
    root.render(
      <AgentIdentityEditor
        agent={{ ...agent, avatarUrl: "https://example.com/photo.png" }}
      />,
    ),
  )
  expect(
    document.querySelector<HTMLInputElement>("#agent-identity-name")?.value,
  ).toBe("Draft name")
  expect(
    document.querySelector<HTMLSelectElement>("#agent-identity-department")
      ?.value,
  ).toBe("Support")
})
it("preserves an identity window and draft when save is rejected", async () => {
  state.update.mockRejectedValue(new Error("Permission denied"))
  act(() => root.render(<AgentIdentityEditor agent={agent} />))
  click("Edit identity")
  type(
    document.querySelector<HTMLInputElement>("#agent-identity-name")!,
    "Draft name",
  )
  await act(async () => click("Save changes"))
  expect(
    document.querySelector('[role="dialog"] [role="alert"]')?.textContent,
  ).toContain("Permission denied")
  expect(
    document.querySelector<HTMLInputElement>("#agent-identity-name")?.value,
  ).toBe("Draft name")
})
it("preserves non-catalog permissions and guardrails when capabilities are saved", async () => {
  state.update.mockImplementation(async (_id, payload) => ({
    ...agent,
    ...payload,
  }))
  act(() => root.render(<AgentCapabilitiesEditorCard agent={agent} />))
  const input = container.querySelector<HTMLInputElement>(
    '[aria-label="Custom capability"]',
  )!
  type(input, "Research legal sources")
  click("Add")
  await act(async () => click("Save capabilities"))
  expect(state.update.mock.calls[0][1].permissions).toContain(
    "Custom CRM scope",
  )
  expect(state.update.mock.calls[0][1].guardrails).toContain("Custom safeguard")
  expect(container.textContent).toContain("All changes saved")
})
it("retains a capability draft across a background agent refresh", () => {
  act(() => root.render(<AgentCapabilitiesEditorCard agent={agent} />))
  type(
    container.querySelector<HTMLInputElement>(
      '[aria-label="Custom capability"]',
    )!,
    "Draft skill",
  )
  click("Add")
  act(() =>
    root.render(
      <AgentCapabilitiesEditorCard
        agent={{ ...agent, capabilities: ["Server refresh"] }}
      />,
    ),
  )
  expect(container.textContent).toContain("Draft skill")
  expect(container.textContent).toContain("Unsaved changes")
})
it("uses native response-style radios and preserves personality drafts on refresh", () => {
  act(() => root.render(<AgentPersonalityEditorCard agent={agent} />))
  const radio = [
    ...container.querySelectorAll<HTMLInputElement>('input[type="radio"]'),
  ].find((input) => !input.checked)!
  act(() => radio.click())
  expect(radio.checked).toBe(true)
  act(() =>
    root.render(
      <AgentPersonalityEditorCard agent={{ ...agent, name: "Refreshed" }} />,
    ),
  )
  expect(radio.checked).toBe(true)
  expect(container.textContent).toContain("Unsaved changes")
})
it("preserves unrelated policy arrays and approval overrides when saving a zero ceiling", async () => {
  const record = {
    trustLevel: "write_with_approval",
    allowedActionKinds: ["read", "write"],
    allowedToolPatterns: ["crm.*"],
    allowedDataScopes: ["org"],
    approvalRuleOverrides: { write: "always_approve" },
    maxActionsPerDay: 10,
    canDelegate: true,
  }
  state.upsert.mockResolvedValue({ identity: record })
  const saved = vi.fn()
  act(() =>
    root.render(
      <AgentPolicyEditor agentId="agent" record={record} onSaved={saved} />,
    ),
  )
  click("Edit policy")
  type(
    document.querySelector<HTMLInputElement>('[aria-label="Actions per day"]')!,
    "0",
  )
  await act(async () => click("Save policy"))
  expect(state.upsert.mock.calls[0][1]).toMatchObject({
    ...record,
    maxActionsPerDay: 0,
  })
  expect(saved).toHaveBeenCalledWith(record)
})
it("does not promise that blank input clears an existing policy limit", async () => {
  act(() =>
    root.render(
      <AgentPolicyEditor
        agentId="agent"
        record={{ maxActionsPerDay: 10 }}
        onSaved={vi.fn()}
      />,
    ),
  )
  click("Edit policy")
  type(
    document.querySelector<HTMLInputElement>('[aria-label="Actions per day"]')!,
    "",
  )
  await act(async () => click("Save policy"))
  expect(state.upsert).not.toHaveBeenCalled()
  expect(document.querySelector('[role="alert"]')?.textContent).toContain(
    "cannot be cleared",
  )
})
it("does not present absent governance evidence as configured policy", () => {
  act(() => root.render(<AgentAutonomyPanel agentId="agent" />))
  expect(container.querySelector("[data-active]")).toBeNull()
  expect(container.textContent).toContain("Daily limits not reported")
  expect(container.textContent).toContain("Connector permissions not reported")
})
it("keeps returned retrieval evidence when the next query fails", async () => {
  state.retrieve
    .mockResolvedValueOnce({
      query: "First",
      matchCount: 1,
      usedAssignedOnly: true,
      sources: [{ title: "Runbook", score: 0, content: "Evidence text" }],
    })
    .mockRejectedValueOnce(new Error("Offline"))
  act(() => root.render(<AgentKnowledgeRetrievalTab agentId="agent" />))
  type(container.querySelector<HTMLInputElement>("input")!, "First")
  await act(async () => click("Test retrieval"))
  type(container.querySelector<HTMLInputElement>("input")!, "Second")
  await act(async () => click("Test retrieval"))
  expect(container.textContent).toContain("Runbook")
  expect(container.textContent).toContain("Relevance: 0.000")
  expect(container.querySelector('[role="alert"]')?.textContent).toContain(
    "Offline",
  )
})
it("labels a zero-match response as returned evidence rather than absent telemetry", async () => {
  state.retrieve.mockResolvedValue({ matchCount: 0, sources: [] })
  act(() => root.render(<AgentKnowledgeRetrievalTab agentId="agent" />))
  type(container.querySelector<HTMLInputElement>("input")!, "Question")
  await act(async () => click("Test retrieval"))
  expect(container.textContent).toContain("No matches were returned")
  expect(container.textContent).not.toContain("No retrieval telemetry")
})
it("routes Existing library to Sources before closing the knowledge picker", () => {
  const close = vi.fn(),
    browse = vi.fn()
  act(() =>
    root.render(
      <AgentKnowledgeAddSheet
        open
        onOpenChange={close}
        onBrowseExpertPacks={vi.fn()}
        onBrowseSources={browse}
      />,
    ),
  )
  const button = [
    ...document.querySelectorAll<HTMLButtonElement>("button"),
  ].find((b) => b.textContent?.includes("Existing library"))!
  act(() => button.click())
  expect(close).toHaveBeenCalledWith(false)
  expect(browse).toHaveBeenCalledOnce()
})
it("exposes remaining available sources instead of silently truncating at 24", () => {
  const ws = workspace()
  ws.assignments = []
  ws.orgSources = Array.from({ length: 25 }, (_, i) => ({
    id: `source-${i}`,
    name: `Source ${i}`,
    type: "file",
    status: "active",
  })) as AgentKnowledgeState["orgSources"]
  act(() =>
    root.render(
      <AgentKnowledgeSourcesTab
        workspace={ws}
        agentId="agent"
        agentName="Research"
      />,
    ),
  )
  expect(container.textContent).not.toContain("Source 24")
  click("Show more sources (1 remaining)")
  expect(container.textContent).toContain("Source 24")
})
it("shows a pack fetch error without inventing an empty catalog", () => {
  state.error = new Error("Offline")
  act(() =>
    root.render(<AgentKnowledgeExpertPacksTab workspace={workspace()} />),
  )
  expect(container.textContent).toContain("Could not refresh expert packs")
  expect(container.textContent).not.toContain("No expert packs are available")
})
it("does not announce successful sync for success false", async () => {
  state.sync.mockResolvedValue({ success: false, message: "Not authorized" })
  const ws = workspace()
  act(() =>
    root.render(
      <AgentKnowledgeSourcesTab
        workspace={ws}
        agentId="agent"
        agentName="Research"
      />,
    ),
  )
  const menu = container.querySelector<HTMLButtonElement>(
    '[aria-label="Actions for Runbook"]',
  )!
  act(() =>
    menu.dispatchEvent(
      new MouseEvent("pointerdown", {
        bubbles: true,
        button: 0,
        ctrlKey: false,
      }),
    ),
  )
  const sync = [
    ...document.querySelectorAll<HTMLElement>('[role="menuitem"]'),
  ].find((el) => el.textContent === "Sync now")!
  await act(async () => sync.click())
  expect(toast.success).not.toHaveBeenCalled()
  expect(ws.mutateAssignments).not.toHaveBeenCalled()
})
