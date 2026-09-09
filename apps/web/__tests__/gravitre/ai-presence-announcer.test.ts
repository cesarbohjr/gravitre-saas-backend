// @vitest-environment jsdom
/**
 * GravitreAIPresenceAnnouncer — Phase 3 (B9: "Presentation-mode changes get
 * an aria-live announcement, following the existing pattern in
 * voice-session-presence.tsx" — role="status" aria-live="polite", text
 * content changes on state change).
 */
import { act, createElement } from "react"
import { createRoot, type Root } from "react-dom/client"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"

;(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true

vi.mock("next/navigation", () => ({
  usePathname: () => "/dashboard",
  useParams: () => ({}),
}))

const ENV_KEY = "NEXT_PUBLIC_AI_FLOAT_ENABLED"
const originalValue = process.env[ENV_KEY]

let container: HTMLDivElement
let root: Root | null = null

beforeEach(() => {
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

async function renderAnnouncer() {
  const { GravitreAIWorkspaceProvider, useGravitreAIWorkspace } = await import(
    "@/components/gravitre/ai-workspace-provider"
  )
  const { GravitreAIPresenceAnnouncer } = await import("@/components/gravitre/ai-presence-announcer")
  type ContextValue = ReturnType<typeof useGravitreAIWorkspace>
  const sink: { value: ContextValue | null } = { value: null }
  function Probe() {
    sink.value = useGravitreAIWorkspace()
    return null
  }
  root = createRoot(container)
  act(() => {
    root!.render(
      createElement(
        GravitreAIWorkspaceProvider,
        null,
        createElement(Probe, null),
        createElement(GravitreAIPresenceAnnouncer, null),
      ),
    )
  })
  return sink
}

describe("GravitreAIPresenceAnnouncer", () => {
  it("renders nothing when the flag is off", async () => {
    delete process.env[ENV_KEY]
    vi.resetModules()
    await renderAnnouncer()
    expect(container.querySelector("[data-gravitre-ai-announcer]")).toBeNull()
  })

  it("renders a polite live region announcing the minimized state by default", async () => {
    process.env[ENV_KEY] = "true"
    vi.resetModules()
    await renderAnnouncer()
    const region = container.querySelector("[data-gravitre-ai-announcer]")
    expect(region).not.toBeNull()
    expect(region?.getAttribute("role")).toBe("status")
    expect(region?.getAttribute("aria-live")).toBe("polite")
    expect(region?.textContent).toMatch(/minimized/i)
  })

  it("announces Float opening when presentationMode/floatWorkspaceOpen change", async () => {
    process.env[ENV_KEY] = "true"
    vi.resetModules()
    const sink = await renderAnnouncer()
    act(() => {
      sink.value!.setPresentationMode("float")
      sink.value!.setFloatWorkspaceOpen(true)
    })
    const region = container.querySelector("[data-gravitre-ai-announcer]")
    expect(region?.textContent).toMatch(/window opened/i)
  })

  it("announces Fullscreen distinctly from Expanded", async () => {
    process.env[ENV_KEY] = "true"
    vi.resetModules()
    const sink = await renderAnnouncer()
    act(() => {
      sink.value!.setFloatWorkspaceOpen(true)
      sink.value!.setPresentationMode("expanded")
    })
    let region = container.querySelector("[data-gravitre-ai-announcer]")
    expect(region?.textContent).toMatch(/expanded/i)

    act(() => {
      sink.value!.setPresentationMode("fullscreen")
    })
    region = container.querySelector("[data-gravitre-ai-announcer]")
    expect(region?.textContent).toMatch(/fullscreen/i)
  })
})
