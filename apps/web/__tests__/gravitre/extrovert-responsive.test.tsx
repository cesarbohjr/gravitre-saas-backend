// @vitest-environment jsdom
import React, { act } from "react"
import { createRoot } from "react-dom/client"
import { expect, it, vi } from "vitest"
import { useIsMobile } from "@/hooks/use-mobile"
import { AgentCapabilityOverview } from "@/components/agents/fleet-v4/agent-capability-overview"
import type { FleetAgent } from "@/components/agents/fleet-v4/types"

;(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true

it("folds Builder's inspector at tablet width while preserving the normal phone breakpoint", () => {
  const listeners = new Set<() => void>()
  vi.stubGlobal("matchMedia", vi.fn(() => ({ addEventListener: (_: string, cb: () => void) => listeners.add(cb), removeEventListener: (_: string, cb: () => void) => listeners.delete(cb) })))
  Object.defineProperty(window, "innerWidth", { configurable: true, writable: true, value: 834 })
  const container = document.createElement("div")
  const root = createRoot(container)
  function Harness() { return <div>{String(useIsMobile())}/{String(useIsMobile(1024))}</div> }
  try {
    act(() => root.render(<Harness />))
    expect(container.textContent).toBe("false/true")
    act(() => { window.innerWidth = 1024; listeners.forEach(cb => cb()) })
    expect(container.textContent).toBe("false/false")
    act(() => { window.innerWidth = 390; listeners.forEach(cb => cb()) })
    expect(container.textContent).toBe("true/true")
  } finally {
    act(() => root.unmount())
    expect(listeners.size).toBe(0)
    vi.unstubAllGlobals()
  }
})

it("opens the saved agent ID and does not present permission tools as connected systems", () => {
  const agent: FleetAgent = {
    id: "saved-agent", name: "Service Coordinator", role: "Operations", department: "operations", departmentLabel: "Operations",
    icon: "ops", identityColor: "teal", configState: "enabled", runtimeState: "offline", currentActivity: null,
    tasksToday: 0, successRate: null, model: "—", lastActiveLabel: "Unknown", tools: ["Privileged tool"], workflows: [],
  }
  const onInspect = vi.fn()
  const container = document.createElement("div")
  const root = createRoot(container)
  try {
    act(() => root.render(<AgentCapabilityOverview agent={agent} onInspect={onInspect} />))
    expect(container.textContent).toContain("Not reported")
    expect(container.textContent).toContain("No systems listed")
    expect(container.textContent).not.toContain("Privileged tool")
    expect(container.querySelector("a")?.getAttribute("href")).toBe("/agents/saved-agent")
    act(() => container.querySelector("button")!.click())
    expect(onInspect).toHaveBeenCalledExactlyOnceWith("saved-agent")
    act(() => root.render(<AgentCapabilityOverview agent={agent} connectedSystems={["Service desk"]} onInspect={onInspect} />))
    expect(container.textContent).toContain("Service desk")
  } finally { act(() => root.unmount()) }
})
