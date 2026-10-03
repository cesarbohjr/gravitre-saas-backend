// @vitest-environment jsdom
import React, { act } from "react"
import { createRoot, type Root } from "react-dom/client"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"
import { MarketplaceAssetOverview } from "@/components/marketplace/marketplace-asset-overview"
import { PackContentsPreview } from "@/components/marketplace/marketplace-asset-commerce"
import { PackPreviewSheet } from "@/components/marketplace/pack-preview-sheet"
import { InstallStepperSheet } from "@/components/marketplace/install-experience"
import type { MarketplaceAssetDetail, MarketplaceAssetInstallCheck } from "@/types/api"

const mocks = vi.hoisted(() => ({
  response: { data: undefined as MarketplaceAssetInstallCheck | undefined, error: undefined as Error | undefined, isLoading: false, isValidating: false },
  refresh: vi.fn(), install: vi.fn(), complete: vi.fn(), failure: vi.fn(), success: vi.fn(),
}))
vi.mock("swr", () => ({ default: () => ({ ...mocks.response, mutate: mocks.refresh }) }))
vi.mock("@/lib/api", () => ({ marketplaceApi: { installAsset: mocks.install } }))
vi.mock("@/components/marketplace/department-pipeline-panel", () => ({ DepartmentPipelineByDepartment: () => null }))
vi.mock("@/lib/marketplace-install-error", () => ({ toastMarketplaceInstallFailure: mocks.failure }))
vi.mock("sonner", () => ({ toast: { success: mocks.success } }))

;(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true
const asset: MarketplaceAssetDetail = {
  id: "msp-real", slug: "msp-operations-pack", title: "MSP Operations Pack", description: "Service coordination.", businessOutcome: "Coordinate service requests.",
  assetType: "department_pack", department: "Operations", tags: [], pricingType: "free", canInstall: true, installed: false,
  connectorChecklist: [], connectorsReady: true, requiredConnectorsConnected: 0, requiredConnectorsTotal: 0,
  packItems: [
    { sortOrder: 0, required: true, child: { id: "agent-real", slug: "service-agent", title: "Service coordinator", assetType: "agent" } },
    { sortOrder: 1, required: false, child: { id: "knowledge-real", slug: "service-runbooks", title: "Service runbooks", assetType: "knowledge_pack" } },
  ],
}
let root: Root
let container: HTMLDivElement
function button(text: string) { return [...document.querySelectorAll("button")].find(b => b.textContent?.includes(text))! }
function sheet(selected = asset, open = true, isAdmin = true) {
  return <InstallStepperSheet asset={selected} open={open} isAdmin={isAdmin} onOpenChange={() => {}} onComplete={mocks.complete} />
}
beforeEach(() => {
  vi.clearAllMocks()
  mocks.response = { data: { canInstall: true, connectorChecklist: [], blockers: [], hasEntitlement: true, requiresPayment: false }, error: undefined, isLoading: false, isValidating: false }
  mocks.refresh.mockResolvedValue(mocks.response.data)
  mocks.install.mockResolvedValue({ installed: true, assetId: asset.id, deepLinks: [], entities: {} })
  vi.stubGlobal("matchMedia", vi.fn(() => ({ matches: false, addListener() {}, removeListener() {}, addEventListener() {}, removeEventListener() {} })))
  container = document.createElement("div"); document.body.append(container); root = createRoot(container)
})
afterEach(() => { act(() => root.unmount()); container.remove(); vi.unstubAllGlobals() })

describe("Nested Marketplace flows", () => {
  it("leads the detail with its actual outcome and preserves catalog context", () => {
    act(() => root.render(<MarketplaceAssetOverview asset={asset} needsPurchase={false} isAdmin />))
    expect(container.querySelector("h1")?.textContent).toBe(asset.title)
    expect(container.textContent).toContain(asset.businessOutcome)
    expect(container.textContent).toContain("Included components2")
    expect(container.textContent).not.toMatch(/live|verified|98%/i)
  })
  it("discloses real nested children and their requirement flags", () => {
    act(() => root.render(<PackContentsPreview items={asset.packItems} compact linkChildren />))
    const details = container.querySelector("details")!
    expect(details.open).toBe(false)
    act(() => container.querySelector("summary")!.click())
    expect(details.open).toBe(true)
    expect([...container.querySelectorAll("a")].map(a => a.getAttribute("href"))).toEqual(["/marketplace/assets/service-agent", "/marketplace/assets/service-runbooks"])
    expect(container.textContent).toContain("Required")
    expect(container.textContent).toContain("Optional")
  })
  it("does not call connected apps install-ready when purchase is still required", () => {
    act(() => root.render(<PackPreviewSheet asset={{ ...asset, canInstall: false, pricingType: "one_time", priceCents: 1000, requiresPayment: true }} open onOpenChange={() => {}} />))
    expect(document.body.textContent).toContain("Purchase required")
    expect(document.body.textContent).not.toContain("Ready to install")
    expect([...document.querySelectorAll("a")].some(a => a.textContent === "View pack" && a.getAttribute("href") === "/marketplace/assets/msp-operations-pack")).toBe(true)
  })
  it("blocks installation on a failed readiness check even when cached data says ready", () => {
    mocks.response.error = new Error("Readiness unavailable")
    act(() => root.render(sheet()))
    expect(document.querySelector('[role="alert"]')?.textContent).toContain("Could not check install requirements")
    expect(button("Confirm install")).toBeUndefined()
    act(() => button("Retry check").click())
    expect(mocks.refresh).toHaveBeenCalledOnce()
    expect(mocks.install).not.toHaveBeenCalled()
  })
  it("keeps installation unavailable for non-admin users", () => {
    act(() => root.render(sheet(asset, true, false)))
    expect(button("Confirm install").disabled).toBe(true)
    act(() => button("Confirm install").click())
    expect(mocks.install).not.toHaveBeenCalled()
  })
  it("uses fresh entitlement from the readiness check for an already purchased pack", () => {
    act(() => root.render(sheet({ ...asset, pricingType: "one_time", priceCents: 1000, requiresPayment: true, hasEntitlement: false })))
    expect(button("Confirm install").textContent).not.toContain("$10")
  })
  it("does not show success when the server has not confirmed installation", async () => {
    mocks.install.mockResolvedValue({ installed: false, assetId: asset.id })
    act(() => root.render(sheet()))
    await act(async () => button("Confirm install").click())
    expect(document.querySelector('[role="alert"]')?.textContent).toContain("did not confirm installation")
    expect(mocks.complete).not.toHaveBeenCalled()
    expect(mocks.success).not.toHaveBeenCalled()
  })
  it("shows failure inline and refreshes readiness without claiming an install succeeded", async () => {
    mocks.install.mockRejectedValue(new Error("Required connection expired"))
    act(() => root.render(sheet()))
    await act(async () => button("Confirm install").click())
    expect(document.querySelector('[role="alert"]')?.textContent).toContain("Required connection expired")
    expect(mocks.refresh).toHaveBeenCalledOnce()
    expect(mocks.complete).not.toHaveBeenCalled()
    expect(mocks.success).not.toHaveBeenCalled()
  })
  it("clears success when switching packs or externally closing and reopening", async () => {
    act(() => root.render(sheet()))
    await act(async () => button("Confirm install").click())
    expect(document.body.textContent).toContain(`${asset.title} is installed`)
    expect(document.body.textContent).not.toContain("Live in your workspace")
    expect(mocks.install).toHaveBeenCalledWith(asset.slug)
    const next = { ...asset, id: "hr-real", slug: "hr-operations-pack", title: "HR Operations Pack" }
    act(() => root.render(sheet(next)))
    expect(document.body.textContent).not.toContain(`${asset.title} is installed`)
    expect(button("Confirm install")).toBeDefined()
    await act(async () => button("Confirm install").click())
    act(() => root.render(sheet(next, false)))
    act(() => root.render(sheet(next, true)))
    expect(document.body.textContent).not.toContain(`${next.title} is installed`)
    expect(button("Confirm install")).toBeDefined()
  })
})
