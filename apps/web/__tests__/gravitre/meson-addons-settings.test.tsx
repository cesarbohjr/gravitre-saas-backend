// @vitest-environment jsdom
import React, { act } from "react"
import { createRoot, type Root } from "react-dom/client"
import { afterEach, beforeEach, expect, it, vi } from "vitest"

const state = vi.hoisted(() => ({
  entry: {} as { data?: unknown; error?: Error; isLoading?: boolean },
  fetch: vi.fn(),
  toggle: vi.fn(),
  mutate: vi.fn(),
}))
vi.mock("swr", () => ({ default: () => ({ ...state.entry, mutate: state.mutate }) }))
vi.mock("@/lib/fetcher", () => ({ apiFetch: state.fetch, fetcher: vi.fn() }))
vi.mock("@/lib/api", () => ({ settingsApi: { toggleMesonAddon: state.toggle } }))
vi.mock("sonner", () => ({ toast: { success: vi.fn(), error: vi.fn() } }))

import { MesonAddonsSettings } from "@/components/settings/meson-addons-settings"

;(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true
let root: Root
let host: HTMLDivElement
beforeEach(() => {
  vi.clearAllMocks()
  state.mutate.mockResolvedValue(undefined)
  host = document.createElement("div")
  document.body.append(host)
  root = createRoot(host)
})
afterEach(() => {
  act(() => root.unmount())
  host.remove()
})
const render = (isAdmin = true) => act(() => root.render(<MesonAddonsSettings isAdmin={isAdmin} />))
const voiceSwitch = () => host.querySelector<HTMLButtonElement>('[role="switch"][aria-labelledby="ma-voice-title"]')!

it("shows the real voice state and the empty addons state with billing link", () => {
  state.entry = { data: { addons: [], monthly_total_usd: 0, voice: { enabled: false } } }
  render()
  expect(host.querySelector("h1")?.textContent).toBe("Meson Addons")
  expect(host.textContent).toContain("Whole organization.")
  expect(host.querySelector('img[data-illustration="header-empty-desk"]')).not.toBeNull()
  expect(voiceSwitch().getAttribute("aria-checked")).toBe("false")
  expect(host.textContent).toContain("Off")
  expect(host.querySelector('a[href="/connectors"]')?.textContent).toContain("Open Connectors")
  expect(host.textContent).toContain("No paid addons to add right now")
  expect(host.querySelector('img[data-illustration="moment-no-addons"]')).not.toBeNull()
  expect(host.querySelector('a[href="/settings/billing"]')?.textContent).toBe("View Billing & Plan")
})

it("toggles org voice through the voice access API for admins", async () => {
  state.entry = { data: { addons: [], voice: { enabled: true } } }
  state.fetch.mockResolvedValue({ ok: true })
  render()
  await act(async () => voiceSwitch().click())
  expect(state.fetch).toHaveBeenCalledWith(
    "/api/settings/voice-access",
    expect.objectContaining({ method: "PATCH", body: JSON.stringify({ enabled: false }) }),
  )
  expect(host.textContent).toContain("Saved for everyone in this workspace")
})

it("keeps controls read-only for non-admins", () => {
  state.entry = {
    data: {
      addons: [{ id: "a", code: "research", name: "Research", description: "Live research", monthly_price_usd: 49, enabled: true }],
      monthly_total_usd: 49,
      voice: { enabled: true },
    },
  }
  render(false)
  expect(voiceSwitch().disabled).toBe(true)
  const addonSwitch = host.querySelector<HTMLButtonElement>('[role="switch"][aria-labelledby="ma-addon-research"]')!
  expect(addonSwitch.disabled).toBe(true)
  expect(host.textContent).toContain("$49.00/mo")
  expect(host.textContent).toContain("Only owners and admins can change this.")
})

it("lists purchasable addons and toggles them through the addons API", async () => {
  state.entry = {
    data: {
      addons: [{ id: "a", code: "research", name: "Research", description: "Live research", monthly_price_usd: 49, enabled: false }],
      monthly_total_usd: 0,
      voice: { enabled: true },
    },
  }
  state.toggle.mockResolvedValue({})
  render()
  await act(async () => host.querySelector<HTMLButtonElement>('[role="switch"][aria-labelledby="ma-addon-research"]')!.click())
  expect(state.toggle).toHaveBeenCalledWith("research", true)
})

it("shows a retry when the addons request fails", () => {
  state.entry = { error: new Error("down") }
  render()
  expect(host.querySelector('[role="alert"]')?.textContent).toContain("Could not load Meson addons")
})
