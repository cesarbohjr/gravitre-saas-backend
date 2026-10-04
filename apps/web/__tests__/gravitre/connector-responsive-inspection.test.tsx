// @vitest-environment jsdom
import React, { act } from "react"
import { createRoot, type Root } from "react-dom/client"
import { beforeEach, afterEach, expect, it, vi } from "vitest"
import { ResponsiveConnectorInspector, type OperatingConnector } from "@/components/connectors/connector-operating"
;(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true
const connector: OperatingConnector = { id: "connector-real", name: "Service desk", type: "hubspot", vendorKey: "hubspot", status: "connected", environment: "production", lastSync: "Never" }
let root: Root
let container: HTMLDivElement
const close = vi.fn(), configure = vi.fn(), test = vi.fn(), sync = vi.fn()
const panel = () => <ResponsiveConnectorInspector connector={connector} statusLabel="Connected" attention={null} onClose={close} onConfigure={configure} onTest={test} onSync={sync} />
beforeEach(() => {
  vi.clearAllMocks()
  vi.stubGlobal("matchMedia", vi.fn(() => ({ addEventListener() {}, removeEventListener() {} })))
  container = document.createElement("div"); document.body.append(container); root = createRoot(container)
})
afterEach(() => { act(() => root.unmount()); container.remove(); vi.unstubAllGlobals() })
it("puts the inspector in a tablet sheet without claiming unreported readiness", () => {
  Object.defineProperty(window, "innerWidth", { configurable: true, writable: true, value: 834 })
  act(() => root.render(panel()))
  const dialog = document.querySelector('[role="dialog"]')!
  expect(dialog.textContent).toContain("Availability not reported")
  expect(dialog.textContent).toContain("No catalog entry")
})
it("closes the tablet sheet before opening configuration", () => {
  Object.defineProperty(window, "innerWidth", { configurable: true, writable: true, value: 390 })
  act(() => root.render(panel()))
  act(() => [...document.querySelectorAll('[role="dialog"] button')].find(b => b.textContent?.includes("Configure"))!.click())
  expect(close).toHaveBeenCalledOnce(); expect(configure).toHaveBeenCalledOnce()
  expect(close.mock.invocationCallOrder[0]).toBeLessThan(configure.mock.invocationCallOrder[0])
})
it("keeps desktop context inline", () => {
  Object.defineProperty(window, "innerWidth", { configurable: true, writable: true, value: 1440 })
  act(() => root.render(panel()))
  expect(document.querySelector('[role="dialog"]')).toBeNull()
  expect(container.textContent).toContain("Service desk")
})
