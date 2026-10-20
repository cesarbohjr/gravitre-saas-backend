// @vitest-environment jsdom
import React, { act } from "react"
import { createRoot, type Root } from "react-dom/client"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"

const state = vi.hoisted(() => ({ isAdmin: true, models: [] as Array<Record<string, unknown>>, update: vi.fn(), mutate: vi.fn() }))
vi.mock("@/lib/use-org-admin", () => ({ useOrgAdmin: () => ({ isAdmin: state.isAdmin }) }))
vi.mock("@/lib/org-context", () => ({ getQuickOrgId: () => "org-a" }))
vi.mock("@/lib/api", () => ({ mlAdminApi: { trainingPermissions: vi.fn(), updateTrainingPermission: state.update } }))
vi.mock("swr", () => ({ default: () => ({ data: { models: state.models }, mutate: state.mutate }) }))
import { TrainingPermissionDialog } from "@/components/intelligence/training-permission-dialog"

Object.assign(globalThis, { IS_REACT_ACT_ENVIRONMENT: true })
let root: Root | undefined
let container: HTMLDivElement
const model = {
  model_name: "world_model", what: "world model", why: "Bounded forecasting", data: "Measured organization outcomes",
  when: "Next scheduled run after approval", where: "Organization backend", security: "Organization only",
  controls: "Pause or revoke in Intelligence", scope_digest: "a".repeat(64), consent_state: "pending",
  candidate_data_detected: true, observed_count: 500, required_count: 500, eligibility_note: "Validation still required",
}
beforeEach(() => { state.isAdmin = true; state.models = [{ ...model }]; state.update.mockReset().mockResolvedValue({}); state.mutate.mockReset() })
afterEach(async () => { if (root) await act(async () => root?.unmount()); root = undefined; container?.remove() })
async function render() {
  container = document.createElement("div"); document.body.append(container); root = createRoot(container)
  await act(async () => root?.render(<TrainingPermissionDialog />))
}
async function click(label: string) {
  const button = [...document.querySelectorAll("button")].find((node) => node.textContent === label)
  expect(button).toBeTruthy()
  await act(async () => button?.click())
}

describe("training consent dialog", () => {
  it("explains real detection and never trains or approves on render", async () => {
    await render()
    expect(document.querySelector('[role="dialog"]')).toBeTruthy()
    expect(document.body.textContent).toContain("Gravitre has detected data")
    for (const label of ["What", "Why", "Data", "When", "Where", "Security", "Controls"]) expect(document.body.textContent).toContain(label)
    expect(state.update).not.toHaveBeenCalled()
    expect(document.querySelector('a[href="/trust-safety?tab=security"]')).toBeTruthy()
  })
  it("saves exactly the reviewed model and disclosure on explicit approval", async () => {
    await render(); await click("Approve automatic training")
    expect(state.update).toHaveBeenCalledExactlyOnceWith("world_model", "approved", "a".repeat(64))
    expect(state.mutate).toHaveBeenCalledOnce()
  })
  it("allows deferral without approval", async () => {
    await render(); await click("Not now")
    expect(state.update).toHaveBeenCalledExactlyOnceWith("world_model", "deferred", "a".repeat(64))
  })
  it("keeps failed approval visible and reports that it was not saved", async () => {
    state.update.mockRejectedValue(new Error("Permission was not saved"))
    await render(); await click("Approve automatic training")
    expect(document.querySelector('[role="alert"]')?.textContent).toBe("Permission was not saved")
    expect(document.querySelector('[role="dialog"]')).toBeTruthy()
  })
  it("never shows an advanced approval prompt to members", async () => {
    state.isAdmin = false; await render()
    expect(document.querySelector('[role="dialog"]')).toBeNull()
    expect(container.textContent).toBe("")
  })
  it("shows pause and revoke for approved training through review", async () => {
    state.models = [{ ...model, consent_state: "approved" }]
    await render(); expect(document.querySelector('[role="dialog"]')).toBeNull()
    await click("Review"); await click("Pause")
    expect(state.update).toHaveBeenCalledExactlyOnceWith("world_model", "paused", "a".repeat(64))
  })
})
