// @vitest-environment jsdom
import React, { act } from "react"
import { createRoot, type Root } from "react-dom/client"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"
import { TrustSafetyEnvironments } from "@/components/trust-safety/trust-safety-environments"
import {
  buildStages,
  countOrNull,
  normalizeEnvironments,
  sumResource,
  type EnvironmentsPayload,
} from "@/lib/settings-api/environments"

const mocks = vi.hoisted(() => ({
  swr: { data: undefined as EnvironmentsPayload | undefined, error: undefined as Error | undefined, isLoading: false },
  admin: { isAdmin: true, showAdmin: true, loading: false },
  mutate: vi.fn(),
  create: vi.fn(),
  setActive: vi.fn(),
  remove: vi.fn(),
  success: vi.fn(),
  error: vi.fn(),
}))
vi.mock("swr", () => ({ default: () => ({ ...mocks.swr, mutate: mocks.mutate }) }))
vi.mock("@/lib/settings-api/environments", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/lib/settings-api/environments")>()
  return {
    ...actual,
    environmentsSettingsApi: { list: vi.fn(), create: mocks.create, setActive: mocks.setActive, remove: mocks.remove },
  }
})
vi.mock("@/lib/auth-context", () => ({ useAuth: () => ({ user: { id: "env-user" } }) }))
vi.mock("@/lib/use-org-admin", () => ({ useOrgAdmin: () => mocks.admin }))
vi.mock("sonner", () => ({ toast: { success: mocks.success, error: mocks.error } }))
;(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true

const PROD = {
  id: "env-prod",
  name: "production",
  is_active: true,
  is_default: true,
  created_at: "2026-10-01T00:00:00Z",
  resources: { workflows: 0, agents: null, connectors: 3, sources: null },
}

describe("environments model", () => {
  it("maps rows onto the three stages and treats legacy default as production", () => {
    const envs = normalizeEnvironments({ environments: [{ id: "a", name: "default", is_active: true }] })
    const stages = buildStages(envs)
    expect(stages.map((stage) => stage.id)).toEqual(["development", "staging", "production"])
    expect(stages[2].env?.id).toBe("a")
    expect(stages[2].env?.isDefault).toBe(true)
    expect(stages[0].env).toBeNull()
  })

  it("prefers a real production row over a legacy default row", () => {
    const envs = normalizeEnvironments({
      environments: [
        { id: "legacy", name: "default" },
        { id: "real", name: "production" },
      ],
    })
    expect(buildStages(envs)[2].env?.id).toBe("real")
  })

  it("never invents counts: missing stays null, zero reads as None yet", () => {
    const envs = normalizeEnvironments({ environments: [PROD] })
    expect(sumResource(envs, "agents")).toBeNull()
    expect(sumResource(envs, "connectors")).toBe(3)
    expect(countOrNull(sumResource(envs, "workflows"))).toBeNull()
  })
})

let root: Root
let container: HTMLDivElement
const render = () => act(() => root.render(<TrustSafetyEnvironments />))
const button = (text: string) =>
  [...container.querySelectorAll<HTMLButtonElement>("button")].find((b) => b.textContent?.trim() === text)!

beforeEach(() => {
  vi.clearAllMocks()
  mocks.swr = { data: { environments: [PROD], environmentsLimit: 5 }, error: undefined, isLoading: false }
  mocks.admin = { isAdmin: true, showAdmin: true, loading: false }
  container = document.createElement("div")
  document.body.append(container)
  root = createRoot(container)
})
afterEach(() => {
  act(() => root.unmount())
  container.remove()
})

describe("Trust & Safety environments tab", () => {
  it("renders the hero tiles from real data with None yet where nothing is counted", () => {
    render()
    expect(container.textContent).toContain("of 3 stages live")
    expect(container.textContent).toContain("1 of 3Configured")
    expect(container.textContent).toContain("None yetWorkflows")
    expect(container.textContent).toContain("None yetAgents")
    expect(container.textContent).toContain("2 stages not set up")
    expect(container.textContent).not.toContain("Not reported")
  })

  it("shows the selected production detail with real counts", () => {
    render()
    expect(container.textContent).toContain("Default")
    expect(container.textContent).toContain("Connectors3")
    expect(container.textContent).toContain("WorkflowsNone yet")
    expect(container.textContent).toContain("No endpoint yet. It appears after the first deploy.")
  })

  it("selects a stage that is not set up and creates it through the real endpoint", async () => {
    mocks.create.mockResolvedValue({ id: "env-staging", name: "staging" })
    render()
    const stage = [...container.querySelectorAll<HTMLButtonElement>('[aria-label="Pipeline stages"] button')][1]
    act(() => stage.click())
    expect(stage.getAttribute("aria-pressed")).toBe("true")
    expect(container.textContent).toContain("Staging is not set up")
    await act(async () => button("Create Staging").click())
    expect(mocks.create).toHaveBeenCalledWith("staging")
    expect(mocks.mutate).toHaveBeenCalled()
    expect(mocks.success).toHaveBeenCalledWith("Staging created")
  })

  it("hides create for non admins and explains who can", () => {
    mocks.admin = { isAdmin: false, showAdmin: false, loading: false }
    render()
    const stage = [...container.querySelectorAll<HTMLButtonElement>('[aria-label="Pipeline stages"] button')][0]
    act(() => stage.click())
    expect(button("Create Development")).toBeUndefined()
    expect(button("New environment")).toBeUndefined()
    expect(container.textContent).toContain("An owner or admin can create it.")
  })

  it("respects the plan limit for new environments", () => {
    mocks.swr.data = { environments: [PROD], environmentsLimit: 1 }
    render()
    expect(button("New environment")).toBeUndefined()
    const stage = [...container.querySelectorAll<HTMLButtonElement>('[aria-label="Pipeline stages"] button')][1]
    act(() => stage.click())
    expect(button("Create Staging").disabled).toBe(true)
    expect(container.textContent).toContain("Your plan includes 1 environment.")
  })

  it("shows a retryable error instead of an empty pipeline when loading fails", () => {
    mocks.swr = { data: undefined, error: new Error("boom"), isLoading: false }
    render()
    expect(container.textContent).toContain("Environments could not be loaded.")
    act(() => button("Try again").click())
    expect(mocks.mutate).toHaveBeenCalledOnce()
  })
})
