// @vitest-environment jsdom
import React, { act } from "react"
import { createRoot, type Root } from "react-dom/client"
import { afterEach, beforeEach, expect, it, vi } from "vitest"
import InstalledPage from "@/app/(app)/marketplace/installed/page"
import type { MarketplaceInstall } from "@/types/api"

const mocks = vi.hoisted(() => ({
  isAdmin: false,
  error: undefined as Error | undefined,
  swr: vi.fn(),
  uninstall: vi.fn(),
  refresh: vi.fn(),
}))
vi.mock("swr", () => ({ default: mocks.swr }))
vi.mock("@/lib/api", () => ({
  marketplaceApi: {
    uninstallAsset: mocks.uninstall,
    listInstalls: vi.fn(),
    getAsset: vi.fn(),
  },
}))
vi.mock("@/lib/auth-context", () => ({
  useAuth: () => ({ user: { id: "member-real" } }),
}))
vi.mock("@/lib/use-org-admin", () => ({
  useOrgAdmin: () => ({ isAdmin: mocks.isAdmin }),
}))
vi.mock("@/components/gravitre/app-shell", () => ({
  AppShell: ({ children }: { children: React.ReactNode }) => (
    <main>{children}</main>
  ),
}))
vi.mock("@/components/marketplace/department-pipeline-panel", () => ({
  DepartmentPipelineByDepartment: () => null,
}))
;(
  globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }
).IS_REACT_ACT_ENVIRONMENT = true
const install: MarketplaceInstall = {
  id: "install-real",
  assetId: "pack-real",
  status: "active",
  asset: {
    id: "pack-real",
    slug: "msp-operations-pack",
    title: "MSP Operations Pack",
    assetType: "department_pack",
    department: "Operations",
  },
  deepLinks: Array.from({ length: 6 }, (_, i) => ({
    label: `Provisioned workflow ${i + 1}`,
    entityType: "workflow",
    entityId: `runtime-${i}`,
    path: `/workflows/runtime-${i}`,
  })),
}
let root: Root
let container: HTMLDivElement
beforeEach(() => {
  vi.clearAllMocks()
  mocks.error = undefined
  mocks.isAdmin = false
  Object.defineProperty(window, "innerWidth", {
    configurable: true,
    writable: true,
    value: 834,
  })
  vi.stubGlobal(
    "matchMedia",
    vi.fn(() => ({
      matches: true,
      addEventListener() {},
      removeEventListener() {},
      addListener() {},
      removeListener() {},
    })),
  )
  mocks.swr.mockImplementation((key) =>
    typeof key === "string"
      ? {
          data: { installs: [install] },
          error: mocks.error,
          isLoading: false,
          mutate: mocks.refresh,
        }
      : {
          data: {
            asset: {
              packItems: [
                {
                  sortOrder: 0,
                  required: true,
                  child: {
                    id: "knowledge-real",
                    slug: "service-runbooks",
                    title: "Service runbooks",
                    assetType: "knowledge_pack",
                  },
                },
              ],
            },
          },
          isLoading: false,
          mutate: mocks.refresh,
        },
  )
  container = document.createElement("div")
  document.body.append(container)
  root = createRoot(container)
})
afterEach(() => {
  act(() => root.unmount())
  container.remove()
  vi.unstubAllGlobals()
})

it("opens tablet inspection on selection and retains every runtime link and nested child", () => {
  act(() => root.render(<InstalledPage />))
  expect(document.querySelector('[role="dialog"]')).toBeNull()
  expect(mocks.swr.mock.calls.some(([key]) => Array.isArray(key))).toBe(false)
  act(() =>
    container
      .querySelector('button[aria-pressed="false"]')!
      .dispatchEvent(new MouseEvent("click", { bubbles: true })),
  )
  const dialog = document.querySelector('[role="dialog"]')!
  expect(dialog.textContent).toContain("Provisioned workflow 6")
  expect(
    dialog.querySelector('a[href="/workflows/runtime-5/builder"]'),
  ).not.toBeNull()
  expect(
    dialog.querySelector('a[href="/marketplace/assets/service-runbooks"]'),
  ).not.toBeNull()
  expect(
    mocks.swr.mock.calls.some(
      ([key]) => Array.isArray(key) && key[1] === "msp-operations-pack",
    ),
  ).toBe(true)
  expect(
    [...dialog.querySelectorAll("button")].some((b) =>
      b.textContent?.includes("Uninstall"),
    ),
  ).toBe(false)
})

it("exposes uninstall only for admins in the selected inspector", () => {
  mocks.isAdmin = true
  act(() => root.render(<InstalledPage />))
  act(() =>
    container
      .querySelector('button[aria-pressed="false"]')!
      .dispatchEvent(new MouseEvent("click", { bubbles: true })),
  )
  expect(
    [...document.querySelectorAll('[role="dialog"] button')].some((b) =>
      b.textContent?.includes("Uninstall"),
    ),
  ).toBe(true)
})

it("retains cached installs after a refresh failure without pretending the list is empty", () => {
  mocks.error = new Error("Read failed")
  act(() => root.render(<InstalledPage />))
  expect(container.textContent).toContain("Could not load installed assets")
  expect(container.textContent).not.toContain("Nothing installed yet")
  expect(container.querySelector("button[aria-pressed]")).not.toBeNull()
})
