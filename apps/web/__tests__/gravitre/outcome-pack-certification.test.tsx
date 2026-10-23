// @vitest-environment jsdom
import React, { act } from "react"
import { createRoot, type Root } from "react-dom/client"
import { afterEach, beforeEach, expect, it, vi } from "vitest"
const state = vi.hoisted(() => ({ data: undefined as unknown, error: undefined as unknown, mutate: vi.fn(), apiFetch: vi.fn() }))
vi.mock("swr", () => ({ default: () => ({ data: state.data, error: state.error, mutate: state.mutate }) }))
vi.mock("@/lib/org-context", () => ({ getQuickOrgId: () => "org" }))
vi.mock("@/lib/fetcher", () => ({ apiFetch: state.apiFetch, fetcher: vi.fn(), formatUnknownError: (e: Error) => e.message }))
import { OutcomePackCertification } from "@/components/marketplace/outcome-pack-certification"
;(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true
let host: HTMLDivElement
let root: Root
beforeEach(() => {
  vi.clearAllMocks()
  state.data = undefined
  state.error = undefined
  host = document.createElement("div")
  document.body.append(host)
  root = createRoot(host)
})
afterEach(async () => { await act(async () => root.unmount()); host.remove() })
async function render() { await act(async () => root.render(<OutcomePackCertification assetRef="pack/name" />)) }
it("withholds readiness for missing or inconsistent evidence", async () => {
  state.data = { publishReady: true, certification: { level: "governed", publishReady: true } }
  await render()
  expect(host.textContent).toContain("Production evidence required before publication")
})
it("shows readiness only for authoritative production certification", async () => {
  state.data = { publishReady: true, certification: { level: "production_verified", publishReady: true } }
  await render()
  expect(host.textContent).toContain("Production evidence verified for this configuration")
  state.error = new Error("offline")
  await render()
  expect(host.textContent).toContain("Evidence unavailable")
  expect(host.textContent).not.toContain("Production evidence verified for this configuration")
})
it("configuration checks cannot present fixture results as publication proof", async () => {
  state.data = { publishReady: false, certification: null }
  state.apiFetch.mockResolvedValue({ ok: true, json: async () => ({ publishReady: true, report: { findings: [{ code: "MISSING", message: "Skill review required" }] } }) })
  await render()
  await act(async () => { (Array.from(host.querySelectorAll("button")).find(b => b.textContent === "Check configuration") as HTMLButtonElement).click() })
  expect(state.apiFetch).toHaveBeenCalledWith("/api/marketplace/assets/pack%2Fname/certification/run", expect.objectContaining({ body: JSON.stringify({ mode: "fixture" }) }))
  expect(host.textContent).toContain("Production evidence is still required")
  expect(host.textContent).toContain("Skill review required")
  expect(state.mutate).toHaveBeenCalledOnce()
})
it("production collection sends only mode and refreshes server status", async () => {
  state.data = { publishReady: false, certification: null }
  state.apiFetch.mockResolvedValue({ ok: true, json: async () => ({}) })
  await render()
  await act(async () => { (Array.from(host.querySelectorAll("button")).find(b => b.textContent === "Collect production evidence") as HTMLButtonElement).click() })
  expect(state.apiFetch).toHaveBeenCalledWith(expect.any(String), expect.objectContaining({ body: JSON.stringify({ mode: "production" }) }))
  expect(state.mutate).toHaveBeenCalledOnce()
})
