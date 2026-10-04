// @vitest-environment jsdom
import React, { act } from "react"
import { createRoot, type Root } from "react-dom/client"
import { afterEach, beforeEach, expect, it, vi } from "vitest"
import NotificationsPage from "@/app/notifications/page"
import type { Notification, NotificationListResponse } from "@/types/api"

const mocks = vi.hoisted(() => ({
  response: { data: undefined as NotificationListResponse | undefined, error: undefined as Error | undefined, isLoading: false },
  mutate: vi.fn(), markRead: vi.fn(), markAllRead: vi.fn(), remove: vi.fn(), archive: vi.fn(), success: vi.fn(), error: vi.fn(),
}))
vi.mock("swr", () => ({ default: () => ({ ...mocks.response, mutate: mocks.mutate }) }))
vi.mock("@/lib/api", () => ({ notificationsApi: { markRead: mocks.markRead, markAllRead: mocks.markAllRead, delete: mocks.remove, archive: mocks.archive } }))
vi.mock("@/lib/auth-context", () => ({ useAuth: () => ({ user: { id: "inbox-user" } }) }))
vi.mock("@/components/gravitre/app-shell", () => ({ AppShell: ({ children }: { children: React.ReactNode }) => <main>{children}</main> }))
vi.mock("next/navigation", () => ({ usePathname: () => "/notifications" }))
vi.mock("sonner", () => ({ toast: { success: mocks.success, error: mocks.error } }))
;(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true

const unread: Notification = { id: "needs-review", title: "Review renewal", body: "Open the approval", type: "approval_needed", url: "/approvals/renewal", is_read: false, is_archived: false, created_at: new Date().toISOString() }
const read: Notification = { ...unread, id: "already-read", title: "Workflow completed", type: "run_completed", url: "/workflows/completed", is_read: true }
let root: Root
let container: HTMLDivElement
const button = (text: string) => [...container.querySelectorAll<HTMLButtonElement>("button")].find(b => b.textContent === text)!
const action = (label: string) => container.querySelector<HTMLButtonElement>(`button[aria-label="${label}"]`)!
const render = () => act(() => root.render(<NotificationsPage />))
beforeEach(() => {
  vi.clearAllMocks()
  mocks.response = { data: { notifications: [unread, read], unread_count: 7 }, error: undefined, isLoading: false }
  mocks.mutate.mockImplementation(async (updater?: (previous: NotificationListResponse | undefined) => NotificationListResponse | undefined) => {
    if (typeof updater === "function") mocks.response.data = updater(mocks.response.data)
  })
  mocks.markRead.mockResolvedValue(undefined); mocks.markAllRead.mockResolvedValue(undefined)
  mocks.remove.mockResolvedValue(undefined); mocks.archive.mockResolvedValue(undefined)
  vi.stubGlobal("matchMedia", vi.fn(() => ({ matches: true, addListener() {}, removeListener() {}, addEventListener() {}, removeEventListener() {} })))
  container = document.createElement("div"); document.body.append(container); root = createRoot(container)
})
afterEach(() => { act(() => root.unmount()); container.remove(); vi.unstubAllGlobals() })

it("keeps destination links separate from actions and discloses loaded count scope", () => {
  render()
  const row = container.querySelector('[data-notification-id="needs-review"]')!
  expect(row.querySelector('a')?.getAttribute("href")).toBe("/approvals/renewal")
  expect(row.querySelector('a button')).toBeNull()
  expect(row.textContent).toContain("Unread")
  expect(container.querySelector('[aria-label="Inbox summary"]')?.textContent).toContain("Unread7")
  expect(container.textContent).toContain("Loaded notifications2")
  expect(container.textContent).toContain("Showing up to 200")
})
it("does not show empty inbox or zero counts while loading", () => {
  mocks.response = { data: undefined, error: undefined, isLoading: true }; render()
  expect(container.textContent).toContain("Loading notifications")
  expect(container.textContent).not.toContain("No notifications")
  expect(button("Mark all read").disabled).toBe(true)
})
it("shows fetch failure and retry instead of all caught up", () => {
  mocks.response = { data: undefined, error: new Error("Unavailable"), isLoading: false }; render()
  expect(container.querySelector('[role="alert"]')?.textContent).toContain("Could not load")
  expect(container.textContent).not.toContain("No notifications")
  expect(container.textContent).toContain("Not reported")
  act(() => button("Retry").click()); expect(mocks.mutate).toHaveBeenCalledOnce()
})
it("preserves cached rows during an error and blocks stale mutations", () => {
  mocks.response.error = new Error("Refresh failed"); render()
  expect(container.textContent).toContain("Showing previously loaded updates")
  expect(container.textContent).toContain("Review renewal")
  expect(action("Delete notification: Review renewal").disabled).toBe(true)
})
it("keeps partial archive failures visible and preserves unread outside loaded results", async () => {
  mocks.archive.mockImplementation((id: string) => id === unread.id ? Promise.reject(new Error("Archive failed")) : Promise.resolve())
  render(); await act(async () => button("Archive loaded").click())
  expect(mocks.response.data?.notifications.map(n => n.id)).toEqual([unread.id])
  expect(mocks.response.data?.unread_count).toBe(7)
  expect(container.textContent).toContain("Review renewal")
  expect(mocks.error).toHaveBeenCalledWith("1 notification could not be archived. Try again.")
  expect(mocks.success).not.toHaveBeenCalled()
})
it("subtracts only successfully archived unread rows from the inbox count", async () => {
  render(); await act(async () => button("Archive loaded").click())
  expect(mocks.response.data?.unread_count).toBe(6)
  expect(mocks.response.data?.notifications).toEqual([])
  expect(mocks.success).toHaveBeenCalledWith("Loaded notifications archived")
})
it("never decrements unread count when opening an already read notification", async () => {
  render()
  await act(async () => {
    const event = new MouseEvent("click", { bubbles: true, cancelable: true }); event.preventDefault()
    container.querySelector('[data-notification-id="already-read"] a')!.dispatchEvent(event)
  })
  expect(mocks.markRead).not.toHaveBeenCalled(); expect(mocks.response.data?.unread_count).toBe(7)
})
it("serializes rapid read clicks and removes read rows from the unread filter", async () => {
  render(); act(() => container.querySelector<HTMLButtonElement>('[aria-label="Read status"] button:nth-child(2)')!.click())
  let finish!: () => void
  mocks.markRead.mockImplementation(() => new Promise<void>(resolve => { finish = resolve }))
  act(() => { action("Mark as read: Review renewal").click(); action("Mark as read: Review renewal").click() })
  expect(mocks.markRead).toHaveBeenCalledOnce()
  expect(button("Archive loaded").disabled).toBe(true)
  await act(async () => finish())
  expect(mocks.response.data?.unread_count).toBe(6)
  expect(container.textContent).toContain("No matching notifications")
})
it("retains a row and count when delete fails", async () => {
  mocks.remove.mockRejectedValue(new Error("Delete failed")); render()
  await act(async () => action("Delete notification: Review renewal").click())
  expect(mocks.response.data?.unread_count).toBe(7)
  expect(container.textContent).toContain("Review renewal")
  expect(mocks.error).toHaveBeenCalledWith("Delete failed")
})
it("does not invent missing unread metrics or timestamps, and tolerates unknown types", () => {
  mocks.response.data = { unread_count: undefined as unknown as number, notifications: [{ ...unread, type: "future_type" as Notification["type"], created_at: "not-a-date" }] }
  render()
  expect(container.textContent).toContain("Time not reported")
  expect(container.querySelector('[aria-label="Inbox summary"]')?.textContent).toContain("UnreadNot reported")
  expect(button("Mark all read").disabled).toBe(true)
})
