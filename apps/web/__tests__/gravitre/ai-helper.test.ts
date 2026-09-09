// @vitest-environment jsdom
/**
 * GravitreAIHelper — Phase 2 of the "Gravitre AI Agent Workspace" redesign.
 *
 * `GRAVITRE_AI_FLOAT_ENABLED` is read at module-import time (same pattern as
 * lib/marketing-flags.ts), so flag-dependent cases below set the env var and
 * `vi.resetModules()` before dynamically re-importing both the provider and
 * the Helper — the same technique used in ai-workspace-flags.test.ts.
 *
 * No @testing-library/react in this repo (confirmed in Phase 1) — tests use
 * `react-dom/client` + `act` directly, following
 * __tests__/gravitre/ai-workspace-provider.test.ts's established pattern.
 */
import { act, createElement } from "react"
import { createRoot, type Root } from "react-dom/client"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"

;(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true

const pathnameState: { value: string } = { value: "/dashboard" }
const routerPush = vi.fn()

vi.mock("next/navigation", () => ({
  usePathname: () => pathnameState.value,
  useParams: () => ({}),
  useRouter: () => ({ push: routerPush }),
}))

// Static import is safe — this is a pure function, independent of the flag.
import { shouldShowGravitreAIHelper } from "@/components/gravitre/ai-helper"
import type { GravitreAIWorkspaceContextValue } from "@/components/gravitre/ai-workspace-provider"

const ENV_KEY = "NEXT_PUBLIC_AI_FLOAT_ENABLED"
const originalValue = process.env[ENV_KEY]

let container: HTMLDivElement
let root: Root | null = null

beforeEach(() => {
  pathnameState.value = "/dashboard"
  routerPush.mockClear()
  container = document.createElement("div")
  document.body.appendChild(container)
})

afterEach(() => {
  if (root) {
    act(() => {
      root!.unmount()
    })
    root = null
  }
  container.remove()
  if (originalValue === undefined) delete process.env[ENV_KEY]
  else process.env[ENV_KEY] = originalValue
  vi.resetModules()
})

async function renderHelper(sink?: { value: GravitreAIWorkspaceContextValue | null }) {
  const { GravitreAIWorkspaceProvider, useGravitreAIWorkspace } = await import(
    "@/components/gravitre/ai-workspace-provider"
  )
  const { GravitreAIHelper } = await import("@/components/gravitre/ai-helper")
  function Probe() {
    if (sink) sink.value = useGravitreAIWorkspace()
    return null
  }
  root = createRoot(container)
  act(() => {
    root!.render(
      createElement(
        GravitreAIWorkspaceProvider,
        null,
        createElement(Probe, null),
        createElement(GravitreAIHelper, null),
      ),
    )
  })
}

describe("shouldShowGravitreAIHelper", () => {
  it("hides on /ai and any /ai/ sub-path — mirrors shouldShowMesonToolbar's exact /ai check", () => {
    expect(shouldShowGravitreAIHelper("/ai")).toBe(false)
    expect(shouldShowGravitreAIHelper("/ai/")).toBe(false)
    expect(shouldShowGravitreAIHelper("/ai/anything")).toBe(false)
  })

  it("shows on every other route", () => {
    expect(shouldShowGravitreAIHelper("/dashboard")).toBe(true)
    expect(shouldShowGravitreAIHelper("/agents/42/chat")).toBe(true)
    expect(shouldShowGravitreAIHelper("/")).toBe(true)
  })
})

describe("GravitreAIHelper", () => {
  it("renders nothing when the flag is off (default) — this is the zero-visible-change safety proof", async () => {
    delete process.env[ENV_KEY]
    vi.resetModules()
    await renderHelper()
    expect(container.querySelector("[data-gravitre-ai-helper]")).toBeNull()
    expect(container.innerHTML).toBe("")
  })

  it("renders the bubble when the flag is on and the route is not /ai", async () => {
    process.env[ENV_KEY] = "true"
    vi.resetModules()
    pathnameState.value = "/dashboard"
    await renderHelper()
    expect(container.querySelector("[data-gravitre-ai-helper]")).not.toBeNull()
  })

  it("still renders nothing on /ai even when the flag is on", async () => {
    process.env[ENV_KEY] = "true"
    vi.resetModules()
    pathnameState.value = "/ai"
    await renderHelper()
    expect(container.querySelector("[data-gravitre-ai-helper]")).toBeNull()
  })

  it("clicking the bubble sets presentationMode to 'float' and navigates to /ai", async () => {
    process.env[ENV_KEY] = "true"
    vi.resetModules()
    pathnameState.value = "/dashboard"
    const sink: { value: GravitreAIWorkspaceContextValue | null } = { value: null }
    await renderHelper(sink)
    const button = container.querySelector("[data-gravitre-ai-helper]") as HTMLButtonElement
    expect(button).toBeTruthy()
    expect(sink.value?.presentationMode).toBe("expanded")
    act(() => {
      button.click()
    })
    expect(routerPush).toHaveBeenCalledWith("/ai")
    expect(sink.value?.presentationMode).toBe("float")
  })
})
