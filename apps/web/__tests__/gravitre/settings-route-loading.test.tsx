// @vitest-environment jsdom
import React, { act } from "react"
import { createRoot, type Root } from "react-dom/client"
import { afterEach, beforeEach, expect, it, vi } from "vitest"
import SettingsPage from "@/app/settings/page"
const mocks = vi.hoisted(() => ({ error: undefined as Error | undefined, loading: false, retry: vi.fn(), router: { push: vi.fn(), replace: vi.fn() } }))
vi.mock("swr", () => ({ default: (key: string) => key === "/api/settings/organization" ? { data: undefined, error: mocks.error, isLoading: mocks.loading, mutate: mocks.retry } : { data: undefined, mutate: vi.fn() } }))
vi.mock("next/navigation", () => ({ useRouter: () => mocks.router, useSearchParams: () => ({ get: () => "organization" }), usePathname: () => "/settings" }))
vi.mock("@/lib/auth-context", () => ({ useAuth: () => ({ user: { id: "owner" }, loading: false }) }))
vi.mock("@/lib/use-org-admin", () => ({ useOrgAdmin: () => ({ isAdmin: true, loading: false }) }))
vi.mock("@/components/gravitre/app-shell", () => ({ AppShell: ({ children }: { children: React.ReactNode }) => <main>{children}</main> }))
vi.mock("@/components/gravitre/model-selector", () => ({ ModelSelector: () => null }))
vi.mock("@/components/settings/memory-entity-embeddings-settings", () => ({ MemoryEntityEmbeddingsSettings: () => null }))
vi.mock("@/lib/api", () => ({ settingsApi: {}, ssoApi: {} }))
vi.mock("@/lib/fetcher", () => ({ apiFetch: vi.fn(), fetcher: vi.fn() }))
;(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true
let root: Root
let container: HTMLDivElement
beforeEach(() => {
  mocks.error = undefined; mocks.loading = false; vi.clearAllMocks()
  vi.stubGlobal("matchMedia", vi.fn(() => ({ addEventListener() {}, removeEventListener() {} })))
  container = document.createElement("div"); document.body.append(container); root = createRoot(container)
})
afterEach(() => { act(() => root.unmount()); container.remove(); vi.unstubAllGlobals() })
it("keeps the organization editor unavailable during the initial fetch", () => {
  mocks.loading = true; act(() => root.render(<SettingsPage />))
  expect(container.textContent).toContain("Loading organization settings")
  expect(container.querySelector("form")).toBeNull()
})
it("shows retry instead of a blank organization form after a failed fetch", () => {
  mocks.error = new Error("Failed"); act(() => root.render(<SettingsPage />))
  expect(container.querySelector('[role="alert"]')?.textContent).toContain("Could not load organization settings")
  expect(container.querySelector("form")).toBeNull()
  act(() => [...container.querySelectorAll<HTMLButtonElement>("button")].find(button => button.textContent === "Retry organization")!.click())
  expect(mocks.retry).toHaveBeenCalledOnce()
})
