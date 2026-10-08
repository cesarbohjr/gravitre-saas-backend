// @vitest-environment jsdom
import React, { act } from "react"
import { createRoot, type Root } from "react-dom/client"
import { afterEach, beforeEach, expect, it, vi } from "vitest"

const state = vi.hoisted(() => ({
  entries: {} as Record<string, { data?: unknown; error?: Error; isLoading?: boolean }>,
  isAdmin: true,
  clone: vi.fn(),
}))

vi.mock("swr", () => ({
  default: (key: unknown) => ({
    ...(key ? state.entries[typeof key === "string" ? key : JSON.stringify(key)] : {}),
    mutate: vi.fn(),
  }),
}))
vi.mock("@/lib/api", () => ({
  marketplaceApi: { getAsset: vi.fn(), assetEntitlement: vi.fn(), cloneAsset: state.clone, uninstallAsset: vi.fn(), listAssets: vi.fn() },
  departmentPipelinesApi: { byDepartment: vi.fn() },
}))
vi.mock("next/navigation", () => ({
  usePathname: () => "/marketplace/assets/weekly-team-status-report",
  useParams: () => ({ slug: "weekly-team-status-report" }),
  useSearchParams: () => new URLSearchParams(),
  useRouter: () => ({ replace: vi.fn(), push: vi.fn() }),
}))
vi.mock("@/lib/auth-context", () => ({ useAuth: () => ({ user: { id: "user" } }) }))
vi.mock("@/lib/use-org-admin", () => ({ useOrgAdmin: () => ({ isAdmin: state.isAdmin }) }))
vi.mock("@/components/gravitre/app-shell", () => ({
  AppShell: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
}))
vi.mock("@/components/marketplace/install-experience", () => ({
  InstallStepperSheet: ({ open }: { open: boolean }) => (open ? <div data-testid="install-sheet" /> : null),
}))
vi.mock("@/components/marketplace/asset-reviews-section", () => ({ AssetReviewsSection: () => null }))
vi.mock("@/components/gravitre/provider-logo", () => ({ ProviderLogo: () => <span /> }))
vi.mock("sonner", () => ({ toast: { success: vi.fn(), error: vi.fn(), info: vi.fn(), message: vi.fn() } }))

import AssetDetailPage from "@/app/(app)/marketplace/assets/[slug]/page"

;(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true
let root: Root
let host: HTMLDivElement

const asset = {
  id: "asset-1",
  slug: "weekly-team-status-report",
  title: "Weekly Team Status Report",
  description: "Turns the week's agent activity into one update.",
  assetType: "workflow",
  category: "workflow",
  department: "Revenue Operations",
  tags: ["workflow", "revenue-operations"],
  pricingType: "free",
  priceCents: 0,
  canInstall: true,
  installed: false,
  connectorsReady: true,
  requiredConnectorsConnected: 0,
  requiredConnectorsTotal: 0,
  connectorChecklist: [
    { connectorType: "slack", label: "Slack", required: false, connected: false, connectPath: "/connectors/slack", ready: true },
  ],
  config: {
    steps: [
      { id: "collect", name: "Collect status themes", type: "agent", metadata: { task: "Draft weekly bullets." } },
      { id: "approve", name: "Share it", type: "approval_gate" },
    ],
  },
}

beforeEach(() => {
  state.entries = {}
  state.isAdmin = true
  host = document.createElement("div")
  document.body.append(host)
  root = createRoot(host)
})
afterEach(() => {
  act(() => root.unmount())
  host.remove()
})

function render(data: unknown = asset) {
  state.entries[JSON.stringify(["marketplace-asset", "weekly-team-status-report"])] = { data: { asset: data } }
  act(() => root.render(<AssetDetailPage />))
}

it("renders the design: breadcrumb, hero with category art, steps with the approval gate", () => {
  render()
  const crumbs = [...host.querySelectorAll('nav[aria-label="Breadcrumb"] a')].map((a) => a.getAttribute("href"))
  expect(crumbs).toEqual(["/marketplace/assets", "/marketplace/assets?department=Revenue%20Operations"])
  expect(host.querySelector("h1")?.textContent).toBe("Weekly Team Status Report")
  expect(host.textContent).toContain("Workflow template · Revenue Operations")
  expect(host.querySelector('.td-hero-art img')?.getAttribute("src")).toBe("/illustrations/market-revenue.svg")
  const gate = host.querySelector(".td-step.gate")
  expect(gate?.textContent).toContain("02 · Approval gate")
  expect(gate?.textContent).toContain("Share it")
  expect(host.textContent).toContain("No required apps")
})

it("shows install readiness, Connect links and details from real asset data", () => {
  render()
  expect(host.textContent).toContain("Ready to install")
  expect(host.querySelector('.td-app a')?.getAttribute("href")).toBe("/connectors/slack")
  const details = host.querySelector(".td-details")?.textContent ?? ""
  expect(details).toContain("Workflow")
  expect(details).toContain("Free")
  expect(details).toMatch(/Approval gates1/)
})

it("wires Install to the install sheet and Clone as draft to the clone API", async () => {
  state.clone.mockResolvedValue({ asset: { title: "Copy" } })
  render()
  const buttons = [...host.querySelectorAll("button")]
  act(() => buttons.find((b) => b.textContent === "Install to workspace")!.click())
  expect(host.querySelector('[data-testid="install-sheet"]')).not.toBeNull()
  await act(async () => buttons.find((b) => b.textContent === "Clone as draft")!.click())
  expect(state.clone).toHaveBeenCalledWith("weekly-team-status-report")
})

it("leaves out What you get when the asset defines no outputs and never shows sample numbers", () => {
  render()
  expect(host.textContent).not.toContain("What you get")
  render({ ...asset, config: { ...asset.config, outputs: [{ title: "Weekly status", type: "report", metrics: ["Runs"], sections: ["Wins"] }] } })
  expect(host.textContent).toContain("What you get")
  expect(host.textContent).toContain("Sample layout")
  expect(host.querySelector(".td-metric b")?.textContent).toBe("[#]")
  expect(host.querySelector('.td-spot img')?.getAttribute("src")).toBe("/illustrations/spot-report-easel.svg")
})

it("asks non-admins to involve an admin instead of offering install", () => {
  state.isAdmin = false
  render()
  expect([...host.querySelectorAll("button")].some((b) => b.textContent === "Install to workspace")).toBe(false)
  expect(host.textContent).toContain("An org admin or owner installs templates")
})
