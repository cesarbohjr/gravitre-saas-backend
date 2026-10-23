// @vitest-environment jsdom
import React, { act } from "react"
import { createRoot, type Root } from "react-dom/client"
import { afterEach, beforeEach, expect, it, vi } from "vitest"
const state = vi.hoisted(() => ({ apiFetch: vi.fn(), mutate: vi.fn() }))
vi.mock("swr", () => ({ default: () => ({ data: { blueprints: [{ id: "revenue-operations", title: "Revenue Operations", playCount: 8, agentCount: 2, skillPackages: ["skills"] }] }, mutate: state.mutate }) }))
vi.mock("@/lib/org-context", () => ({ getQuickOrgId: () => "org" }))
vi.mock("@/lib/fetcher", () => ({ apiFetch: state.apiFetch, fetcher: vi.fn(), formatUnknownError: (e: Error) => e.message }))
import { OutcomePackBlueprints } from "@/components/marketplace/outcome-pack-blueprints"
;(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true
let host: HTMLDivElement
let root: Root
beforeEach(() => { vi.clearAllMocks(); host = document.createElement("div"); document.body.append(host); root = createRoot(host) })
afterEach(async () => { await act(async () => root.unmount()); host.remove() })
it("creates a private draft from the selected server blueprint without caller configuration", async () => {
  const refresh = vi.fn()
  state.apiFetch.mockResolvedValue({ ok: true })
  await act(async () => root.render(<OutcomePackBlueprints onCreated={refresh} />))
  expect(host.textContent).toContain("8 Plays")
  expect(host.textContent).toContain("no production certification")
  await act(async () => (host.querySelector("button") as HTMLButtonElement).click())
  expect(state.apiFetch).toHaveBeenCalledWith("/api/marketplace/outcome-pack-blueprints/revenue-operations/draft", { method: "POST" })
  expect(refresh).toHaveBeenCalledOnce()
  expect(host.textContent).toContain("Workspace draft ready")
})
