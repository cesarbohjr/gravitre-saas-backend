// @vitest-environment jsdom
import React, { act } from "react"
import { createRoot, type Root } from "react-dom/client"
import { afterEach, beforeEach, expect, it, vi } from "vitest"
import { ModelStudioStage } from "@/components/intelligence/pages/model-studio-stage"

const state = vi.hoisted(() => ({ entries: {} as Record<string, { data?: unknown; error?: Error; isLoading?: boolean }>, save: vi.fn(), refresh: vi.fn() }))
vi.mock("swr", () => ({ default: (key: string | string[] | null) => ({ ...(key ? state.entries[Array.isArray(key) ? key[0] : key] : {}), mutate: state.refresh }) }))
vi.mock("next/navigation", () => ({ useRouter: () => ({ push: vi.fn() }) }))
vi.mock("@/hooks/use-mobile", () => ({ useIsMobile: () => false }))
vi.mock("@/components/intelligence/shell", () => ({ IntelligenceAskCommandSurface: () => null }))
vi.mock("@/lib/api", () => ({ trainingApi: { createExternalDatasetReference: state.save }, mlModelsApi: {}, agentsApi: {}, workflowsApi: {}, playsApi: {} }))
;(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true
let host: HTMLDivElement, root: Root
beforeEach(() => {
  vi.clearAllMocks()
  state.entries = {
    "external-dataset-providers-studio": { data: { providers: [{ id: "provider-a", label: "Provider A" }] } },
    "external-dataset-search": { data: { datasets: [{ dataset_id: "provider/customers", description: "Customer examples" }] } },
    "external-dataset-inspect": { data: { dataset: { dataset_id: "provider/customers", fileCount: 0 } } },
    "ml-models-list-studio": { data: { models: [{ id: "model-a", name: "Customer classifier", status: "ready", modelType: "classifier", currentVersion: 1 }] } },
    "external-dataset-references-studio": { data: { references: [] } },
  }
  state.refresh.mockResolvedValue(undefined)
  host = document.createElement("div"); document.body.append(host); root = createRoot(host)
})
afterEach(() => { act(() => root.unmount()); host.remove() })
async function click(text: string) {
  const button = [...host.querySelectorAll<HTMLButtonElement>("button")].find(b => b.textContent?.trim() === text)
  expect(button, text).toBeTruthy(); await act(async () => button!.click())
}
async function chooseTarget() {
  const select = host.querySelector<HTMLSelectElement>('[aria-label="Dataset target"]')!
  await act(async () => { select.value = "model-a"; select.dispatchEvent(new Event("change", { bubbles: true })) })
}
async function inspect() {
  await act(async () => root.render(<ModelStudioStage enabled />))
  await click("02Train")
  // Search result fixture is returned only once a search is staged.
  const input = host.querySelector<HTMLInputElement>('[aria-label="Search datasets"]')!
  await act(async () => {
    Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, "value")!.set!.call(input, "customers")
    input.dispatchEvent(new Event("input", { bubbles: true }))
  })
  await click("Search")
  const dataset = [...host.querySelectorAll<HTMLButtonElement>("button")].find(b => b.textContent?.includes("provider/customers"))!
  expect(dataset).toBeTruthy(); await act(async () => dataset.click())
}
it("retains dataset and purpose when target loading fails, with an independent retry", async () => {
  state.entries["ml-models-list-studio"] = { error: new Error("offline") }
  await inspect()
  expect(host.textContent).toContain("Could not load dataset targets")
  expect(host.textContent).toContain("provider/customers")
  expect(host.querySelector<HTMLSelectElement>('select[aria-label="Dataset target"]')?.disabled).toBe(true)
  const retry = [...host.querySelectorAll<HTMLButtonElement>("button")].filter(b => b.textContent === "Try again").at(-1)!
  await act(async () => retry.click())
  expect(state.refresh).toHaveBeenCalled()
})
it("preserves a refused reference draft and never claims indexing", async () => {
  state.save.mockRejectedValue(new Error("Target denied"))
  await inspect(); await chooseTarget(); await click("Save dataset reference")
  expect(host.querySelector('[role="alert"]')?.textContent).toContain("Target denied")
  expect(host.querySelector<HTMLSelectElement>('[aria-label="Dataset target"]')?.value).toBe("model-a")
  expect(host.querySelector('[role="status"]')).toBeNull()
})
it("prevents duplicate saves and freezes the selected scope while pending", async () => {
  let resolve!: (value: unknown) => void
  state.save.mockImplementation(() => new Promise(done => { resolve = done }))
  await inspect(); await chooseTarget(); await click("Save dataset reference"); await click("Saving reference…")
  expect(state.save).toHaveBeenCalledTimes(1)
  expect(host.querySelector<HTMLSelectElement>('[aria-label="Dataset target"]')?.disabled).toBe(true)
  await click("01Create")
  expect(host.textContent).toContain("Saving reference…")
  await act(async () => resolve({ id: "reference-a" }))
  expect(state.save).toHaveBeenCalledWith(expect.objectContaining({ datasetId: "provider/customers", targetType: "model", targetId: "model-a", purpose: "training", accessMode: "reference" }))
})
it("retains acknowledged save when the workspace list refresh rejects", async () => {
  state.save.mockResolvedValue({ id: "reference-a" })
  state.refresh.mockRejectedValue(new Error("refresh offline"))
  await inspect(); await chooseTarget(); await click("Save dataset reference")
  expect(host.querySelector('[role="status"]')?.textContent).toContain("Reference saved for model model-a")
  expect(host.querySelector('[role="status"]')?.textContent).toContain("does not import or index provider files")
  expect(host.querySelector('[role="alert"]')).toBeNull()
})
it("shows saved purpose, target and access provenance without inventing materialization", async () => {
  state.entries["external-dataset-references-studio"] = { data: { references: [{ id: "reference-a", provider: "provider-a", external_dataset_id: "provider/customers", purpose: "evaluation", target_type: "model", target_id: "model-a", access_mode: "reference" }] } }
  await inspect()
  const ledger = host.querySelector('[aria-label="Saved dataset references"]')!
  expect(ledger.textContent).toContain("evaluation · model · model-a")
  expect(ledger.textContent).toContain("Reference metadata; no import or indexing confirmed")
})
