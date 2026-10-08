// @vitest-environment jsdom
import React, { act } from "react"
import { createRoot, type Root } from "react-dom/client"
import { afterEach, beforeEach, expect, it, vi } from "vitest"
import { ScheduleItemDialog } from "@/app/(app)/schedules/_components/schedule-item-dialog"
import type { ScheduleOccurrence } from "@/lib/schedules"

const actions = vi.hoisted(() => ({ remove: vi.fn(), close: vi.fn(), refresh: vi.fn() }))
vi.mock("@/lib/schedules/actions", async importOriginal => ({ ...await importOriginal<typeof import("@/lib/schedules/actions")>(), deleteScheduledItem: actions.remove }))
vi.mock("@/components/schedules/schedule-editor-dialog", () => ({ ScheduleEditorDialog: () => null }))
vi.mock("sonner", () => ({ toast: { success: vi.fn(), error: vi.fn() } }))
;(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true
let root: Root
let container: HTMLDivElement
const occurrence: ScheduleOccurrence = {
  key: "occurrence", date: new Date("2026-10-04T10:00:00Z"), projected: true,
  item: { id: "wf-schedule", title: "Daily review", kind: "workflow", status: "scheduled", workflowId: "workflow", cron: "0 10 * * *", timezone: "UTC" },
}
beforeEach(() => {
  vi.clearAllMocks(); actions.remove.mockResolvedValue(undefined)
  vi.stubGlobal("matchMedia", vi.fn(() => ({ addEventListener() {}, removeEventListener() {} })))
  container = document.createElement("div"); document.body.append(container); root = createRoot(container)
})
afterEach(() => { act(() => root.unmount()); container.remove(); vi.unstubAllGlobals() })
function render(width: number) {
  Object.defineProperty(window, "innerWidth", { configurable: true, writable: true, value: width })
  act(() => root.render(<ScheduleItemDialog occurrence={occurrence} open onOpenChange={actions.close} onUpdated={actions.refresh} />))
}
it.each([390, 834, 1440])("preserves occurrence, timezone and live actions at width %i", width => {
  render(width)
  const dialog = document.querySelector('[role="dialog"]')!
  expect(dialog.getAttribute("data-slot")).toBe(width < 1024 ? "sheet-content" : "dialog-content")
  expect(dialog.textContent).toContain("Daily review")
  expect(dialog.textContent).toContain("Timezone: UTC")
  expect(dialog.textContent).toContain("Reschedule")
  expect(dialog.textContent).toContain("Edit schedule")
  expect(dialog.querySelector('a[href="/workflows/workflow"]')).not.toBeNull()
})
it("keeps deletion behind confirmation in the compact sheet and refreshes only after success", async () => {
  render(834)
  act(() => [...document.querySelectorAll<HTMLButtonElement>('[role="dialog"] button')].find(b => b.textContent === "Delete workflow schedule")!.click())
  expect(actions.remove).not.toHaveBeenCalled()
  const confirmation = document.querySelector('[role="alertdialog"]')!
  await act(async () => [...confirmation.querySelectorAll<HTMLButtonElement>("button")].find(b => b.textContent === "Confirm delete")!.click())
  expect(actions.remove).toHaveBeenCalledExactlyOnceWith(occurrence.item)
  expect(actions.close).toHaveBeenCalledWith(false)
  expect(actions.refresh).toHaveBeenCalledOnce()
})
