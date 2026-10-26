// @vitest-environment jsdom
import React, { act } from "react"
import { createRoot, type Root } from "react-dom/client"
import { afterEach, beforeEach, expect, it } from "vitest"
import { SettingsShell } from "@/components/settings/settings-shell"
;(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true
let root: Root
let container: HTMLDivElement
beforeEach(() => {
  container = document.createElement("div"); document.body.append(container); root = createRoot(container)
})
afterEach(() => { act(() => root.unmount()); container.remove() })
const render = (isAdmin = false, hideHeader = false, activeSection: "profile" | "organization" = "profile") =>
  act(() => root.render(<SettingsShell activeSection={activeSection} isAdmin={isAdmin} hideHeader={hideHeader}><p>Profile form</p></SettingsShell>))
const pills = () => container.querySelector<HTMLElement>("nav.gs-pills")!
const rail = () => container.querySelector<HTMLElement>("aside.gs-nav")!

it("gives iPad and phone a scrolling row of section pills with real hrefs", () => {
  render()
  const row = pills()
  expect(row.getAttribute("aria-label")).toBe("Settings sections")
  expect(row.querySelector('a[href="/settings/profile"]')?.getAttribute("aria-current")).toBe("page")
  expect(row.querySelector('a[href="/settings?section=organization"]')?.getAttribute("aria-current")).toBeNull()
  expect(row.querySelector('a[href="/trust-safety?tab=security"]')?.textContent).toBe("Security")
  expect(container.textContent).toContain("Profile form")
})

it("keeps admin-only sections out of the row and rail for members", () => {
  render(false)
  expect(pills().querySelector('a[href="/trust-safety?tab=roles"]')).toBeNull()
  expect(rail().textContent).not.toContain("Admins only")
})

it("lists the Admin group, marked admins only, for admins", () => {
  render(true, false, "organization")
  const admin = [...rail().querySelectorAll(".gs-group")].find((group) => group.textContent?.startsWith("Admin"))!
  expect(admin.textContent).toContain("Admins only")
  expect([...admin.querySelectorAll("a")].map((a) => a.textContent)).toEqual([
    "Role permissions",
    "Human in the loop",
    "Enterprise",
    "Federation and B2B",
    "Environments",
    "Audit trail",
    "MCP servers",
  ])
  expect(rail().querySelector('a[href="/settings?section=organization"]')?.getAttribute("aria-current")).toBe("page")
  expect(pills().querySelector('a[href="/trust-safety?tab=policies"]')?.textContent).toBe("Human in the loop")
})

it("does not add a second heading when a standalone route supplies its own hero", () => {
  render(false, true); expect(container.querySelector("h1")).toBeNull()
})

it("filters the rail with the search field and keeps real hrefs", () => {
  render(true)
  const input = rail().querySelector<HTMLInputElement>('input[type="search"]')!
  const type = (value: string) => act(() => {
    Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, "value")!.set!.call(input, value)
    input.dispatchEvent(new Event("input", { bubbles: true }))
  })
  type("addons")
  expect([...rail().querySelectorAll("nav a")].map((a) => a.getAttribute("href"))).toEqual(["/settings?section=meson-addons"])
  type("zzz")
  expect(rail().textContent).toContain("No settings match")
})
