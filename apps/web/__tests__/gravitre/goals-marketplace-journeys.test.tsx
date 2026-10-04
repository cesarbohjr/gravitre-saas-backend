// @vitest-environment jsdom
import React, { act } from "react"
import { createRoot, type Root } from "react-dom/client"
import { beforeEach, afterEach, expect, it, vi } from "vitest"
import { GoalWorkflowWizard } from "@/components/gravitre/goal-workflow-wizard"
import {
  AssetPricingEditor,
  formatAssetPriceLabel,
} from "@/components/marketplace/asset-pricing-editor"
import { AssetOutcomeEditor } from "@/components/marketplace/asset-outcome-editor"
import { AssetVersionHistory } from "@/components/marketplace/asset-version-history"
import { MarketplaceDecisionDialog } from "@/components/marketplace/marketplace-decision-dialog"
import { AssetReviewsSection } from "@/components/marketplace/asset-reviews-section"
import PublisherPage from "@/app/marketplace/publisher/page"
import OrgAdminPage from "@/app/marketplace/org-admin/page"
import AssetDetailPage from "@/app/marketplace/assets/[slug]/page"
import { EngineSettingsTab } from "@/app/admin/intelligence/_components/engine-settings-tab"
import { fetchGoalList } from "@/lib/goals-list"
const state = vi.hoisted(() => ({
  fetch: vi.fn(),
  mutate: vi.fn(),
  rollback: vi.fn(),
  uninstall: vi.fn(),
  approve: vi.fn(),
  upsert: vi.fn(),
  remove: vi.fn(),
  settings: vi.fn(),
  entries: {} as Record<
    string,
    { data?: unknown; error?: Error; isLoading?: boolean }
  >,
}))
vi.mock("swr", () => ({
  default: (key: string | null) => ({
    ...(key
      ? state.entries[typeof key === "string" ? key : JSON.stringify(key)]
      : {}),
    mutate: state.mutate,
  }),
}))
vi.mock("@/lib/fetcher", () => ({ apiFetch: state.fetch, ApiError: Error }))
vi.mock("@/lib/api", () => ({
  connectorsApi: { list: vi.fn() },
  intelligenceApi: {
    engineSettings: vi.fn(),
    updateEngineSettings: state.settings,
  },
  marketplaceApi: {
    rollbackAssetVersion: state.rollback,
    listAssetVersions: vi.fn(),
    listAssetReviews: vi.fn(),
    getAsset: vi.fn(),
    getPublisherProfile: vi.fn(),
    billingStatus: vi.fn(),
    listOrgAssets: vi.fn(),
    approveOrgAsset: state.approve,
    getAssetEntitlement: vi.fn(),
    uninstallAsset: state.uninstall,
    upsertAssetReview: state.upsert,
    deleteAssetReview: state.remove,
  },
}))
vi.mock("@/components/marketplace/asset-save-button", () => ({
  AssetSaveButton: () => <button>Save asset</button>,
}))
vi.mock("next/navigation", () => ({
  usePathname: () => "/marketplace",
  useParams: () => ({ slug: "pack" }),
  useSearchParams: () => new URLSearchParams(),
  useRouter: () => ({ replace: vi.fn(), push: vi.fn() }),
}))
vi.mock("@/lib/auth-context", () => ({
  useAuth: () => ({ user: { id: "user" } }),
}))
vi.mock("@/lib/use-org-admin", () => ({
  useOrgAdmin: () => ({ isAdmin: true }),
}))
vi.mock("@/components/gravitre/app-shell", () => ({
  AppShell: ({ children }: { children: React.ReactNode }) => (
    <div>{children}</div>
  ),
}))
vi.mock("@/components/marketplace/department-pipeline-panel", () => ({
  DepartmentPipelineByDepartment: () => null,
}))
vi.mock("@/components/marketplace/marketplace-asset-overview", () => ({
  MarketplaceAssetOverview: () => null,
}))
vi.mock("@/components/ui/dropdown-menu", () => {
  const Box = ({ children }: { children: React.ReactNode }) => (
    <div>{children}</div>
  )
  return {
    DropdownMenu: Box,
    DropdownMenuTrigger: Box,
    DropdownMenuContent: Box,
    DropdownMenuItem: ({
      children,
      onSelect,
      disabled,
    }: {
      children: React.ReactNode
      onSelect: () => void
      disabled: boolean
    }) => (
      <button data-mobile-menu disabled={disabled} onClick={onSelect}>
        {children}
      </button>
    ),
  }
})
vi.mock("sonner", () => ({ toast: { success: vi.fn(), error: vi.fn() } }))
vi.mock("@/components/ui/dialog", () => {
  const Box = ({ children }: { children: React.ReactNode }) => (
    <div>{children}</div>
  )
  return {
    Dialog: ({
      open,
      children,
      onOpenChange,
    }: {
      open: boolean
      children: React.ReactNode
      onOpenChange: (open: boolean) => void
    }) =>
      open ? (
        <div>
          {children}
          <button onClick={() => onOpenChange(false)}>Dismiss</button>
        </div>
      ) : null,
    DialogContent: Box,
    DialogHeader: Box,
    DialogTitle: Box,
    DialogDescription: Box,
    DialogFooter: Box,
  }
})
;(
  globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }
).IS_REACT_ACT_ENVIRONMENT = true
let root: Root
let host: HTMLDivElement
beforeEach(() => {
  vi.clearAllMocks()
  state.entries = {}
  host = document.createElement("div")
  document.body.append(host)
  root = createRoot(host)
  state.mutate.mockResolvedValue(undefined)
})
afterEach(() => {
  act(() => root.unmount())
  host.remove()
})
function render(element: React.ReactNode) {
  act(() => root.render(element))
}
function button(label: string) {
  const found = [...host.querySelectorAll("button")].find(
    (b) => b.textContent === label,
  )
  if (!found) throw new Error(`Missing button: ${label}`)
  return found
}
async function click(label: string) {
  await act(async () => {
    button(label).click()
  })
}
function change(selector: string, value: string) {
  const input = host.querySelector(selector) as
    | HTMLInputElement
    | HTMLTextAreaElement
  act(() => {
    Object.getOwnPropertyDescriptor(
      input instanceof HTMLTextAreaElement
        ? HTMLTextAreaElement.prototype
        : HTMLInputElement.prototype,
      "value",
    )!.set!.call(input, value)
    input.dispatchEvent(new Event("input", { bubbles: true }))
  })
}
function response(body: unknown, ok = true) {
  return { ok, json: async () => body }
}
function deferred<T>() {
  let resolve!: (value: T) => void
  const promise = new Promise<T>((r) => {
    resolve = r
  })
  return { promise, resolve }
}

it("rejects missing goal-list payload instead of showing an empty workspace", async () => {
  state.fetch.mockResolvedValue(response({}))
  await expect(fetchGoalList()).rejects.toThrow("did not return a goal list")
  state.fetch.mockResolvedValue(response({ goals: [] }))
  await expect(fetchGoalList()).resolves.toEqual([])
})
it("shows unknown prices honestly and preserves real free pricing", () => {
  expect(formatAssetPriceLabel("paid")).toBe("Price not reported")
  expect(formatAssetPriceLabel("unknown", 500)).toBe("Price not reported")
  expect(formatAssetPriceLabel("free", 0)).toBe("Free")
  expect(formatAssetPriceLabel("subscription", 550)).toBe("$5.50/mo")
})
it("does not save zero or negative paid pricing", async () => {
  const save = vi.fn()
  render(<AssetPricingEditor pricingType="paid" priceCents={0} onSave={save} />)
  await click("Save pricing")
  expect(save).not.toHaveBeenCalled()
  expect(host.textContent).toContain("positive USD amount")
  change("input", "-10")
  await click("Save pricing")
  expect(save).not.toHaveBeenCalled()
})
it("retains pricing edits across refresh and failed saves", async () => {
  const save = vi.fn().mockRejectedValue(new Error("Save unavailable"))
  render(
    <AssetPricingEditor pricingType="paid" priceCents={500} onSave={save} />,
  )
  change("input", "12.34")
  render(
    <AssetPricingEditor pricingType="paid" priceCents={900} onSave={save} />,
  )
  expect((host.querySelector("input") as HTMLInputElement).value).toBe("12.34")
  await click("Save pricing")
  expect(save).toHaveBeenCalledWith({ pricingType: "paid", priceCents: 1234 })
  expect(host.textContent).toContain("Save unavailable")
  expect((host.querySelector("input") as HTMLInputElement).value).toBe("12.34")
})
it("locks a pricing write synchronously", async () => {
  const pending = deferred<void>()
  const save = vi.fn().mockReturnValue(pending.promise)
  render(
    <AssetPricingEditor pricingType="paid" priceCents={100} onSave={save} />,
  )
  const action = button("Save pricing")
  act(() => {
    action.click()
    action.click()
  })
  expect(save).toHaveBeenCalledTimes(1)
  await act(async () => pending.resolve())
})
it("gives repeated outcome editors distinct field labels and rejects negative estimates", async () => {
  const save = vi.fn()
  render(
    <>
      <AssetOutcomeEditor onSave={save} />
      <AssetOutcomeEditor onSave={save} />
    </>,
  )
  const ids = [...host.querySelectorAll("input,textarea")].map((i) => i.id)
  expect(new Set(ids).size).toBe(ids.length)
  change('input[type="number"]', "-1")
  await click("Save outcome")
  expect(save).not.toHaveBeenCalled()
  expect(host.textContent).toContain("finite number")
})
it("saves a true zero outcome estimate and retains failed draft text", async () => {
  const save = vi.fn().mockRejectedValue(new Error("Outcome unavailable"))
  render(<AssetOutcomeEditor onSave={save} />)
  change("textarea", "Close the loop")
  change('input[type="number"]', "0")
  await click("Save outcome")
  expect(save).toHaveBeenCalledWith({
    businessOutcome: "Close the loop",
    useCase: undefined,
    estimatedHoursSaved: 0,
  })
  expect(host.textContent).toContain("Outcome unavailable")
  expect((host.querySelector("textarea") as HTMLTextAreaElement).value).toBe(
    "Close the loop",
  )
})
it("confirms the selected restore and keeps confirmed success when refresh fails", async () => {
  state.entries["marketplace-asset-versions:pack"] = {
    data: {
      currentVersion: 2,
      versions: [
        { versionNumber: 1, isCurrent: false, changeSummary: "Earlier config" },
        { versionNumber: 2, isCurrent: true },
      ],
    },
    error: new Error("Refresh failed"),
  }
  state.rollback.mockResolvedValue({})
  state.mutate.mockRejectedValue(new Error("Read failed"))
  render(<AssetVersionHistory slug="pack" />)
  expect(host.textContent).toContain("Earlier config")
  await click("Restore")
  expect(state.rollback).not.toHaveBeenCalled()
  await click("Confirm restore v1")
  expect(state.rollback).toHaveBeenCalledWith("pack", 1)
  expect(
    host.querySelector('[aria-label="Confirm version restore"]'),
  ).toBeNull()
})
it("retains the selected version after a failed restore", async () => {
  state.entries["marketplace-asset-versions:pack"] = {
    data: {
      currentVersion: 2,
      versions: [{ versionNumber: 1, isCurrent: false }],
    },
  }
  state.rollback.mockRejectedValue(new Error("Restore unavailable"))
  render(<AssetVersionHistory slug="pack" />)
  await click("Restore")
  await click("Confirm restore v1")
  expect(host.textContent).toContain("Restore unavailable")
  expect(host.textContent).toContain("Keep current version")
})
it("locks confirmation dismissal while a marketplace decision is pending", async () => {
  const pending = deferred<void>()
  const confirm = vi.fn().mockReturnValue(pending.promise)
  const cancel = vi.fn()
  render(
    <MarketplaceDecisionDialog
      title="Publish publicly?"
      description="Public scope"
      actionLabel="Publish"
      onCancel={cancel}
      onConfirm={confirm}
    />,
  )
  act(() => {
    button("Publish").click()
    button("Dismiss").click()
  })
  expect(cancel).not.toHaveBeenCalled()
  expect(confirm).toHaveBeenCalledTimes(1)
  await act(async () => pending.resolve())
  expect(cancel).toHaveBeenCalledTimes(1)
})
it("goal planning uses actual connections, draft persistence and unreported telemetry", async () => {
  state.entries["goals/create/connectors"] = { data: { connectors: [] } }
  state.fetch
    .mockResolvedValueOnce(response({ goal: { id: "goal-real" } }))
    .mockResolvedValueOnce(
      response({
        goalPlan: {
          proposedSteps: [{ id: "step-real", title: "Review balances" }],
          requiredConnectors: ["hubspot"],
          approvalGates: [{ phase: "pre-launch", required: false }],
        },
      }),
    )
  render(<GoalWorkflowWizard open onOpenChange={vi.fn()} />)
  change("textarea", "Reduce overdue balances")
  await click("Continue")
  expect(host.textContent).toContain("Not connected")
  await click("Generate plan")
  expect(JSON.parse(state.fetch.mock.calls[0][1].body).status).toBe("draft")
  expect(host.textContent).toContain("Review balances")
  expect(host.textContent).toContain("Not reported")
  expect(host.textContent).toContain("Not required by this proposal")
  expect(host.textContent).not.toContain("Build workflow")
  expect(host.querySelector('a[href="/goals/goal-real"]')).not.toBeNull()
})
it("retries failed plan generation on the saved draft without creating another goal", async () => {
  state.fetch
    .mockResolvedValueOnce(response({ goal: { id: "goal-real" } }))
    .mockResolvedValueOnce(response({}, false))
    .mockResolvedValueOnce(response({ goal: { id: "goal-real" } }))
    .mockResolvedValueOnce(response({ goalPlan: { proposedSteps: [] } }))
  render(<GoalWorkflowWizard open onOpenChange={vi.fn()} />)
  change("textarea", "Reduce overdue balances")
  await click("Continue")
  await click("Generate plan")
  expect(host.textContent).toContain("Plan generation failed")
  await click("Generate plan")
  expect(state.fetch.mock.calls[2][0]).toBe("/api/goals/goal-real")
  expect(state.fetch.mock.calls[2][1].method).toBe("PATCH")
  expect(host.textContent).toContain("Proposed steps not reported")
})
it("locks goal dismissal and duplicate save while persistence is pending", async () => {
  const pending = deferred<ReturnType<typeof response>>()
  state.fetch.mockReturnValue(pending.promise)
  const close = vi.fn()
  render(<GoalWorkflowWizard open onOpenChange={close} />)
  change("textarea", "Reduce overdue balances")
  const save = button("Save draft")
  act(() => {
    save.click()
    save.click()
    button("Dismiss").click()
  })
  expect(state.fetch).toHaveBeenCalledTimes(1)
  expect(close).not.toHaveBeenCalled()
  await act(async () =>
    pending.resolve(response({ goal: { id: "goal-real" } })),
  )
  expect(close).toHaveBeenCalledWith(false)
})

it("retains a review draft when background data changes and save fails", async () => {
  state.entries[JSON.stringify(["marketplace-reviews", "pack"])] = {
    data: {
      assetId: "asset",
      myReview: { id: "review", rating: 3, title: "Old", body: "Old body" },
      reviews: [],
    },
  }
  state.upsert.mockRejectedValue(new Error("Review unavailable"))
  render(<AssetReviewsSection assetRef="pack" />)
  change("input", "My retained draft")
  state.entries[JSON.stringify(["marketplace-reviews", "pack"])] = {
    data: {
      assetId: "asset",
      myReview: {
        id: "review",
        rating: 4,
        title: "New server title",
        body: "New body",
      },
      reviews: [],
    },
  }
  render(<AssetReviewsSection assetRef="pack" />)
  expect((host.querySelector("input") as HTMLInputElement).value).toBe(
    "My retained draft",
  )
  await click("Update review")
  expect(host.textContent).toContain("Review unavailable")
  expect((host.querySelector("input") as HTMLInputElement).value).toBe(
    "My retained draft",
  )
})
it("retains cached reviews on error and does not show an empty state without a response", () => {
  const key = JSON.stringify(["marketplace-reviews", "pack"])
  state.entries[key] = { error: new Error("Unavailable") }
  render(<AssetReviewsSection assetRef="pack" />)
  expect(host.textContent).toContain("Could not refresh reviews")
  expect(host.textContent).not.toContain("No reviews returned")
  expect(host.textContent).not.toContain("Submit review")
  state.entries[key] = {
    data: {
      assetId: "asset",
      myReview: null,
      reviews: [{ id: "r", rating: 5, title: "Useful evidence" }],
    },
    error: new Error("Unavailable"),
  }
  render(<AssetReviewsSection assetRef="pack" />)
  expect(host.textContent).toContain("Useful evidence")
})
it("requires review removal confirmation and retains failure for retry", async () => {
  state.entries[JSON.stringify(["marketplace-reviews", "pack"])] = {
    data: {
      assetId: "asset",
      myReview: { id: "review", rating: 4, title: "Mine" },
      reviews: [],
    },
  }
  state.remove.mockRejectedValue(new Error("Removal unavailable"))
  render(<AssetReviewsSection assetRef="pack" />)
  await click("Remove review")
  expect(state.remove).not.toHaveBeenCalled()
  await click("Confirm review removal")
  expect(state.remove).toHaveBeenCalledWith("pack")
  expect(host.textContent).toContain("Removal unavailable")
  expect((host.querySelector("input") as HTMLInputElement).value).toBe("Mine")
})
it("retains invalid admin numeric input and blocks settings write", async () => {
  state.entries["admin/intelligence/engine-settings"] = {
    data: {
      validationEnabled: true,
      rerankingEnabled: true,
      confidenceThreshold: 0.4,
      maxChunks: 8,
      connectorTimeoutSeconds: 30,
    },
  }
  render(<EngineSettingsTab enabled />)
  change("#max-chunks", "0")
  await click("Save settings")
  expect(state.settings).not.toHaveBeenCalled()
  expect((host.querySelector("#max-chunks") as HTMLInputElement).value).toBe(
    "0",
  )
  expect(host.textContent).toContain("Use 1–50 passages")
})
it("preserves admin settings draft across refresh and omits unreported policy", async () => {
  state.entries["admin/intelligence/engine-settings"] = {
    data: {
      validationEnabled: true,
      rerankingEnabled: true,
      confidenceThreshold: 0.4,
      maxChunks: 8,
      connectorTimeoutSeconds: 30,
    },
  }
  state.settings.mockRejectedValue(new Error("Settings unavailable"))
  render(<EngineSettingsTab enabled />)
  change("#max-chunks", "12")
  state.entries["admin/intelligence/engine-settings"] = {
    data: {
      validationEnabled: true,
      rerankingEnabled: true,
      confidenceThreshold: 0.4,
      maxChunks: 4,
      connectorTimeoutSeconds: 30,
    },
    error: new Error("Read unavailable"),
  }
  render(<EngineSettingsTab enabled />)
  expect((host.querySelector("#max-chunks") as HTMLInputElement).value).toBe(
    "12",
  )
  await click("Save settings")
  expect(state.settings).toHaveBeenCalledWith(
    expect.objectContaining({ max_chunks: 12 }),
  )
  expect(state.settings.mock.calls[0][0]).not.toHaveProperty(
    "standing_investigators_enabled",
  )
  expect(host.textContent).toContain("Settings unavailable")
})

it("mobile asset menu asks for confirmation before uninstall and retains a refused result", async () => {
  state.entries[JSON.stringify(["marketplace-asset", "pack"])] = {
    data: {
      asset: {
        id: "asset",
        slug: "pack",
        title: "Selected pack",
        assetType: "department_pack",
        pricingType: "free",
        installed: true,
        canInstall: false,
        connectorChecklist: [],
        packItems: [],
      },
    },
  }
  state.uninstall.mockResolvedValue({ uninstalled: false })
  render(<AssetDetailPage />)
  const menu = [
    ...host.querySelectorAll<HTMLButtonElement>("button[data-mobile-menu]"),
  ].find((b) => b.textContent?.includes("Uninstall"))!
  expect(menu).toBeDefined()
  await act(async () => menu.click())
  expect(state.uninstall).not.toHaveBeenCalled()
  await click("Confirm uninstall")
  expect(state.uninstall).toHaveBeenCalledWith("pack")
  expect(host.textContent).toContain("did not confirm uninstall")
  expect(host.textContent).toContain("Keep current state")
})

it("does not overwrite a new publisher draft when a profile appears during refresh", () => {
  state.entries["marketplace-publisher-profile"] = { data: { publisher: null } }
  render(<PublisherPage />)
  change("#displayName", "My new publisher draft")
  state.entries["marketplace-publisher-profile"] = {
    data: {
      publisher: {
        displayName: "Background profile",
        slug: "server",
        publicPublishingEnabled: false,
      },
    },
  }
  render(<PublisherPage />)
  expect((host.querySelector("#displayName") as HTMLInputElement).value).toBe(
    "My new publisher draft",
  )
})
it("internal publication requires confirmation and keeps a server-refused decision", async () => {
  state.entries["marketplace-org-admin-drafts"] = { data: { assets: [] } }
  state.entries["marketplace-org-admin-queue"] = {
    data: {
      assets: [
        {
          id: "a",
          slug: "pack",
          title: "Internal draft",
          assetType: "ai_agent",
          pricingType: "free",
        },
      ],
    },
  }
  state.entries["marketplace-org-admin-published"] = { data: { assets: [] } }
  state.entries["marketplace-org-admin-publisher"] = {
    data: { publisher: null },
  }
  state.approve.mockResolvedValue({ approved: false })
  render(<OrgAdminPage />)
  await click("Approve")
  expect(state.approve).not.toHaveBeenCalled()
  expect(host.textContent).toContain("organization’s internal catalog")
  await click("Confirm internal publication")
  expect(state.approve).toHaveBeenCalledWith("pack")
  expect(host.textContent).toContain("did not confirm publication")
  expect(host.textContent).toContain("Keep current state")
})
