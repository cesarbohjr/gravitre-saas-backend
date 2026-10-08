// @vitest-environment jsdom
import React, { act } from "react"
import { createRoot, type Root } from "react-dom/client"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"

type SwrResult = { data?: unknown; error?: unknown; isLoading: boolean }
const mocks = vi.hoisted(() => ({
  responses: {} as Record<string, SwrResult>,
}))
vi.mock("swr", () => ({
  default: (key: string | null) => (key ? mocks.responses[key] ?? { isLoading: true } : { isLoading: false }),
}))
vi.mock("@/lib/auth-context", () => ({ useAuth: () => ({ user: { id: "user-1" }, loading: false }) }))
vi.mock("@/lib/fetcher", () => ({ fetcher: vi.fn() }))
vi.mock("@/lib/org-context", () => ({ getQuickOrgId: () => "org-1" }))

import { useOrgAdmin, type OrgAdminState } from "@/lib/use-org-admin"
import { readCachedOrgAdmin, writeCachedOrgAdmin } from "@/lib/org-gate-cache"

;(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true

function Probe() {
  return <pre>{JSON.stringify(useOrgAdmin())}</pre>
}

let root: Root
let container: HTMLDivElement
const render = () => act(() => root.render(<Probe />))
const state = (): OrgAdminState => JSON.parse(container.querySelector("pre")!.textContent!)
const inFlight = () => {
  mocks.responses = {
    "/api/settings/lite-membership": { isLoading: true },
    "/api/auth/me": { isLoading: true },
  }
}

beforeEach(() => {
  window.localStorage.clear()
  inFlight()
  container = document.createElement("div")
  document.body.append(container)
  root = createRoot(container)
})
afterEach(() => {
  act(() => root.unmount())
  container.remove()
})

describe("useOrgAdmin optimistic rendering", () => {
  it("is pending with nothing cached, and never grants admin from nothing", () => {
    render()
    expect(state()).toMatchObject({ pending: true, showAdmin: false, isAdmin: false, confirmed: false })
  })

  it("shows cached admin sections immediately but keeps actions unconfirmed", () => {
    writeCachedOrgAdmin("user-1", "org-1", true)
    render()
    expect(state()).toMatchObject({ pending: false, showAdmin: true, isAdmin: false, confirmed: false })
  })

  it("corrects a stale cached admin when the server says otherwise, and updates the cache", () => {
    writeCachedOrgAdmin("user-1", "org-1", true)
    render()
    mocks.responses = {
      "/api/settings/lite-membership": { data: { is_admin: false }, isLoading: false },
      "/api/auth/me": { data: { role: "member", organizations: [{ id: "org-1", role: "member" }] }, isLoading: false },
    }
    render()
    expect(state()).toMatchObject({ pending: false, showAdmin: false, isAdmin: false, confirmed: true })
    expect(readCachedOrgAdmin("user-1", "org-1")).toBe(false)
  })

  it("confirms admin from the server and caches it per user + org", () => {
    mocks.responses = {
      "/api/settings/lite-membership": { data: { is_admin: true }, isLoading: false },
      "/api/auth/me": { isLoading: true },
    }
    render()
    expect(state()).toMatchObject({ isAdmin: true, showAdmin: true, confirmed: true })
    expect(readCachedOrgAdmin("user-1", "org-1")).toBe(true)
    expect(readCachedOrgAdmin("user-1", "org-2")).toBeUndefined()
    expect(readCachedOrgAdmin("user-2", "org-1")).toBeUndefined()
  })

  it("does not overwrite the cache when both role requests fail", () => {
    writeCachedOrgAdmin("user-1", "org-1", true)
    mocks.responses = {
      "/api/settings/lite-membership": { error: new Error("down"), isLoading: false },
      "/api/auth/me": { error: new Error("down"), isLoading: false },
    }
    render()
    expect(state()).toMatchObject({ isAdmin: false, showAdmin: false, confirmed: true })
    expect(readCachedOrgAdmin("user-1", "org-1")).toBe(true)
  })

  it("survives storage that throws", () => {
    const getItem = vi.spyOn(Storage.prototype, "getItem").mockImplementation(() => {
      throw new Error("blocked")
    })
    const setItem = vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => {
      throw new Error("blocked")
    })
    try {
      render()
      expect(state().pending).toBe(true)
      expect(() => writeCachedOrgAdmin("user-1", "org-1", true)).not.toThrow()
    } finally {
      getItem.mockRestore()
      setItem.mockRestore()
    }
  })
})
