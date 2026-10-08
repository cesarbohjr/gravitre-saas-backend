// @vitest-environment jsdom
import React, { act } from "react"
import { createRoot, type Root } from "react-dom/client"
import { afterEach, beforeEach, expect, it, vi } from "vitest"
import { SettingsShell } from "@/components/settings/settings-shell"
;(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true
let root: Root
let container: HTMLDivElement
let listeners: (() => void)[]
beforeEach(() => {
  Object.defineProperty(window, "innerWidth", { configurable: true, writable: true, value: 834 })
  listeners = []
  vi.stubGlobal("matchMedia", vi.fn(() => ({ addEventListener: (_: string, callback: () => void) => listeners.push(callback), removeEventListener() {} })))
  container = document.createElement("div"); document.body.append(container); root = createRoot(container)
})
afterEach(() => { act(() => root.unmount()); container.remove(); vi.unstubAllGlobals() })
const render = (isAdmin = false, hideHeader = false) => act(() => root.render(<SettingsShell activeSection="profile" isAdmin={isAdmin} hideHeader={hideHeader}><p>Profile form</p></SettingsShell>))
const open = () => act(() => container.querySelector<HTMLButtonElement>('[aria-label="Choose settings section"]')!.click())
it("opens section navigation without requiring state props from standalone pages", () => {
  render(); open()
  const dialog = document.querySelector('[role="dialog"]')!
  expect(dialog.textContent).toContain("Settings sections")
  expect(dialog.querySelector('a[href="/settings/profile"]')?.getAttribute("aria-current")).toBe("page")
  expect(dialog.querySelector('a[href="/settings/team/permissions"]')).toBeNull()
  expect(container.textContent).toContain("Profile form")
})
it("closes the sheet when navigating to a section and retains real hrefs", () => {
  render(true); open()
  const link = document.querySelector<HTMLAnchorElement>('[role="dialog"] a[href="/settings?section=notifications"]')!
  act(() => { const event = new MouseEvent("click", { bubbles: true, cancelable: true }); event.preventDefault(); link.dispatchEvent(event) })
  expect(document.querySelector('[role="dialog"]')).toBeNull()
})
it("restores trigger focus when closed with its keyboard-accessible close control", async () => {
  render(); open()
  act(() => [...document.querySelectorAll<HTMLButtonElement>('[role="dialog"] button')].find(b => b.textContent === "Close")!.click())
  expect(document.querySelector('[role="dialog"]')).toBeNull()
  await act(async () => { await new Promise(resolve => setTimeout(resolve, 20)) })
  expect(document.activeElement?.getAttribute("aria-label")).toBe("Choose settings section")
})
it("closes navigation when resizing from tablet to desktop", () => {
  render(); open()
  act(() => { window.innerWidth = 1440; listeners.forEach(callback => callback()) })
  expect(document.querySelector('[role="dialog"]')).toBeNull()
  expect(container.querySelector('aside')?.className).toContain("lg:block")
})
it("does not add a second heading when a standalone route supplies its own hero", () => {
  render(false, true); expect(container.querySelector("h1")).toBeNull()
})
it("filters the settings links with the search field and keeps real hrefs", () => {
  render(true); open()
  const dialog = document.querySelector('[role="dialog"]')!
  const input = dialog.querySelector<HTMLInputElement>('input[type="search"]')!
  const type = (value: string) => act(() => {
    Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, "value")!.set!.call(input, value)
    input.dispatchEvent(new Event("input", { bubbles: true }))
  })
  type("addons")
  expect([...dialog.querySelectorAll("a")].map((a) => a.getAttribute("href"))).toEqual(["/settings?section=meson-addons"])
  type("zzz")
  expect(dialog.textContent).toContain("No settings match")
})
