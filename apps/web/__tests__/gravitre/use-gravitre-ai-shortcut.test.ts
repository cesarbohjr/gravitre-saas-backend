// @vitest-environment jsdom
/**
 * useGravitreAIShortcut — Phase 3 global keyboard shortcut
 * (Ctrl/Cmd+Shift+L). See the hook's own file header for the shortcut
 * audit. `GRAVITRE_AI_FLOAT_ENABLED` is read at module-import time (same
 * pattern as lib/marketing-flags.ts and ai-helper.test.ts), so flag cases
 * set the env var and `vi.resetModules()` before dynamically re-importing.
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

async function renderListener() {
  const { GravitreAIWorkspaceProvider, useGravitreAIWorkspace } = await import(
    "@/components/gravitre/ai-workspace-provider"
  )
  const { GravitreAIShortcutListener } = await import("@/components/gravitre/ai-shortcut-listener")
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
        createElement(GravitreAIShortcutListener, null),
      ),
    )
  })
  return sink
}

function dispatchShortcut(target: EventTarget = window) {
  target.dispatchEvent(
    new KeyboardEvent("keydown", { key: "L", ctrlKey: true, shiftKey: true, bubbles: true, cancelable: true }),
  )
}

describe("useGravitreAIShortcut", () => {
  it("does NOT attach a listener when the flag is off — dispatching the combo changes nothing", async () => {
    delete process.env[ENV_KEY]
    vi.resetModules()
    const sink = await renderListener()
    act(() => {
      dispatchShortcut()
    })
    expect(sink.value?.presentationMode).toBe("expanded")
    expect(sink.value?.floatWorkspaceOpen).toBe(false)
    expect(routerPush).not.toHaveBeenCalled()
  })

  it("opens Float and navigates to /ai when the flag is on and the workspace is closed", async () => {
    process.env[ENV_KEY] = "true"
    vi.resetModules()
    pathnameState.value = "/dashboard"
    const sink = await renderListener()

    act(() => {
      dispatchShortcut()
    })

    expect(sink.value?.presentationMode).toBe("float")
    expect(sink.value?.floatWorkspaceOpen).toBe(true)
    expect(routerPush).toHaveBeenCalledWith("/ai")
  })

  it("does not navigate again if already on /ai", async () => {
    process.env[ENV_KEY] = "true"
    vi.resetModules()
    pathnameState.value = "/ai"
    await renderListener()

    act(() => {
      dispatchShortcut()
    })

    expect(routerPush).not.toHaveBeenCalled()
  })

  it("toggles the workspace closed (fast hide/minimize) when pressed again while open", async () => {
    process.env[ENV_KEY] = "true"
    vi.resetModules()
    pathnameState.value = "/dashboard"
    const sink = await renderListener()

    act(() => {
      dispatchShortcut()
    })
    expect(sink.value?.floatWorkspaceOpen).toBe(true)

    act(() => {
      dispatchShortcut()
    })
    expect(sink.value?.floatWorkspaceOpen).toBe(false)
    expect(sink.value?.presentationMode).toBe("expanded")
  })

  it("ignores the combo when focus is on an editable target", async () => {
    process.env[ENV_KEY] = "true"
    vi.resetModules()
    const sink = await renderListener()
    const input = document.createElement("input")
    container.appendChild(input)

    act(() => {
      dispatchShortcut(input)
    })

    expect(sink.value?.floatWorkspaceOpen).toBe(false)
  })
})
