// @vitest-environment jsdom
import React, { act } from "react"
import { createRoot, type Root } from "react-dom/client"
import { afterEach, beforeEach, expect, it, vi } from "vitest"
import { TeamSettings } from "@/components/settings/team-settings"

const mocks = vi.hoisted(() => ({
  swr: {} as Record<string, { data?: unknown; error?: Error; isLoading?: boolean }>,
  mutate: vi.fn(),
  resend: vi.fn(),
  updateMemberRole: vi.fn(),
  success: vi.fn(),
  error: vi.fn(),
}))
vi.mock("swr", () => ({ default: (key: string) => ({ ...(mocks.swr[key] ?? {}), mutate: mocks.mutate }) }))
vi.mock("@/lib/api", () => ({
  settingsApi: { inviteMember: vi.fn(), updateMember: vi.fn(), removeMember: vi.fn() },
  organizationsApi: { updateMemberRole: mocks.updateMemberRole, removeMember: vi.fn() },
}))
vi.mock("@/lib/fetcher", () => ({ apiFetch: vi.fn(), fetcher: vi.fn() }))
vi.mock("@/lib/settings-api/team", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/lib/settings-api/team")>()
  return { ...actual, teamApi: { resendInvite: mocks.resend } }
})
vi.mock("@/components/gravitre/user-account-avatar", () => ({ UserAccountAvatar: () => <span /> }))
vi.mock("sonner", () => ({ toast: { success: mocks.success, error: mocks.error } }))
;(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true

let root: Root
let container: HTMLDivElement
const members = [
  { id: "p1", email: "owner@x.com", full_name: "Olive Owner", role: "owner", userId: "u1", orgId: "org-1" },
  { id: "p2", email: "new@x.com", full_name: "", role: "viewer", userId: "u2", orgId: "org-1" },
]
const render = (isAdmin = true) =>
  act(() => root.render(<TeamSettings members={members} isAdmin={isAdmin} onUpdate={async () => {}} />))
const buttons = (label: string) => [...container.querySelectorAll("button")].filter((b) => b.textContent?.trim() === label)

beforeEach(() => {
  vi.clearAllMocks()
  mocks.swr = {
    "/api/org/invites": { data: { invites: [{ user_id: "u2", email: "new@x.com", role: "viewer", invited_at: null }] } },
    "/api/settings/lite-seats": { data: { summary: { included: 2, allocated: 5, used: 1 }, departments: [] } },
  }
  mocks.resend.mockResolvedValue({ ok: true, email: "new@x.com" })
  mocks.mutate.mockResolvedValue(undefined)
  container = document.createElement("div")
  document.body.append(container)
  root = createRoot(container)
})
afterEach(() => {
  act(() => root.unmount())
  container.remove()
})

it("shows real counts, pending status and resend for pending invites", async () => {
  render()
  const stats = [...container.querySelectorAll(".gs-stat")].map((el) => el.textContent)
  expect(stats[0]).toContain("Members1")
  expect(stats[1]).toContain("Pending invites1")
  expect(stats[2]).toContain("Lite seats5")
  expect(container.textContent).toContain("Pending")
  expect(buttons("Edit")).toHaveLength(1)
  await act(async () => buttons("Resend")[0].click())
  expect(mocks.resend).toHaveBeenCalledWith("u2")
  expect(container.textContent).toContain("Bring in the people who approve the work")
  expect(container.querySelector('a[href="/settings?section=lite-seats"]')).not.toBeNull()
})

it("filters by the Pending tab", () => {
  render()
  act(() => [...container.querySelectorAll('[role="tab"]')].find((t) => t.textContent?.startsWith("Pending"))!.dispatchEvent(new MouseEvent("click", { bubbles: true })))
  expect(container.textContent).not.toContain("Olive Owner")
  expect(container.textContent).toContain("new@x.com")
})

it("keeps admin actions disabled for members", () => {
  render(false)
  expect(container.textContent).toContain("Admin or owner permission is required")
  expect(buttons("Invite member")[0].disabled).toBe(true)
  expect(buttons("Edit")[0].disabled).toBe(true)
  expect(buttons("Resend")[0].disabled).toBe(true)
})

it("does not invent pending invites when they cannot be checked", () => {
  mocks.swr["/api/org/invites"] = { error: new Error("nope") }
  mocks.swr["/api/settings/lite-seats"] = {}
  render()
  const stats = [...container.querySelectorAll(".gs-stat")].map((el) => el.textContent)
  expect(stats[1]).toContain("n/a")
  expect(stats[2]).toContain("None yet")
  expect(container.textContent).toContain("Could not check which invites are still pending")
})
