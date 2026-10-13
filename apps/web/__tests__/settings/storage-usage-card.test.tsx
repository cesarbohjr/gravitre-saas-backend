// @vitest-environment jsdom
import React, { act } from "react"
import { createRoot, type Root } from "react-dom/client"
import { afterEach, beforeEach, expect, it, vi } from "vitest"
import type { StorageUsage } from "@/lib/api"
import { StorageUsageCard, formatBytes } from "@/components/settings/storage-usage-card"

const GIB = 1024 ** 3
const mocks = vi.hoisted(() => ({ data: undefined as StorageUsage | undefined }))
vi.mock("swr", () => ({ default: () => ({ data: mocks.data, error: undefined }) }))
vi.mock("@/lib/api", () => ({ storageApi: { getUsage: vi.fn() } }))
;(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true

let root: Root
let container: HTMLDivElement
const base: StorageUsage = {
  meterEnabled: true,
  enforcementEnabled: false,
  limitBytes: 5 * GIB,
  warnRatio: 0.8,
  state: "ok",
  percentUsed: null,
  categories: ["knowledge", "memories", "conversations", "audit", "files"],
  snapshot: null,
}
const render = () => act(() => root.render(<StorageUsageCard />))

beforeEach(() => {
  container = document.createElement("div")
  document.body.append(container)
  root = createRoot(container)
})
afterEach(() => {
  act(() => root.unmount())
  container.remove()
})

it("formats bytes", () => {
  expect(formatBytes(0)).toBe("0 B")
  expect(formatBytes(1536)).toBe("1.5 KB")
  expect(formatBytes(5 * GIB)).toBe("5.0 GB")
  expect(formatBytes(null)).toBe("—")
})

it("renders nothing while the meter is off", () => {
  mocks.data = { ...base, meterEnabled: false }
  render()
  expect(container.innerHTML).toBe("")
})

it("shows an empty state before the first snapshot", () => {
  mocks.data = { ...base }
  render()
  expect(container.textContent).toContain("first measurement")
})

it("shows used vs limit by category and the warning", () => {
  mocks.data = {
    ...base,
    state: "warn",
    percentUsed: 85,
    enforcementEnabled: true,
    snapshot: {
      capturedAt: "2026-10-13T03:00:00Z",
      snapshotDate: "2026-10-13",
      totalBytes: 4.25 * GIB,
      categories: { knowledge: { bytes: 4 * GIB, rows: 10 }, audit: { bytes: 0.25 * GIB, rows: 5 } },
    },
  }
  render()
  const text = container.textContent ?? ""
  expect(text).toContain("4.3 GB")
  expect(text).toContain("/ 5.0 GB")
  expect(text).toContain("85%")
  expect(text).toContain("Knowledge4.0 GB")
  expect(text).toContain("Audit log256 MB")
  expect(text).toContain("New syncs and uploads pause when it is full")
})
