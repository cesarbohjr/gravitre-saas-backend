// @vitest-environment jsdom
import React, { act } from "react"
import { createRoot, type Root } from "react-dom/client"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"

const mocks = vi.hoisted(() => ({
  swr: {} as Record<string, { data?: unknown; error?: Error }>,
  admin: { isAdmin: true, loading: false },
  mutate: vi.fn(),
  apiFetch: vi.fn(),
  toastSuccess: vi.fn(),
  toastError: vi.fn(),
}))

vi.mock("swr", () => ({
  default: (key: string | null) => ({ ...(typeof key === "string" ? mocks.swr[key] ?? {} : {}), mutate: mocks.mutate }),
}))
vi.mock("sonner", () => ({ toast: { success: mocks.toastSuccess, error: mocks.toastError } }))
vi.mock("@/lib/fetcher", () => ({ apiFetch: mocks.apiFetch, fetcher: vi.fn() }))
vi.mock("@/lib/use-org-admin", () => ({ useOrgAdmin: () => mocks.admin }))
vi.mock("next/link", () => ({ default: ({ children, href, ...rest }: { children: React.ReactNode; href: string }) => <a href={href} {...rest}>{children}</a> }))

import { TrustSafetyRoles } from "@/components/trust-safety/trust-safety-roles"
import { AuditEventPanel, auditErrorText } from "@/components/trust-safety/trust-safety-audit-detail"
import { ROLE_PERMISSIONS_KEY, draftProblem, draftsFromMatrix, type RolePermissionsResponse } from "@/lib/settings-api/roles"
import type { AuditEvent } from "@/lib/settings-api/audit"

;(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true

let root: Root
let container: HTMLDivElement
const render = (node: React.ReactNode) => act(() => root.render(node))
const byLabel = (label: string) => container.querySelector<HTMLElement>(`[aria-label="${label}"]`)
const button = (text: string) => [...container.querySelectorAll("button")].find((el) => el.textContent?.trim() === text)
const click = async (el: Element | null | undefined) => {
  expect(el).toBeTruthy()
  await act(async () => {
    ;(el as HTMLElement).click()
  })
}
function type(el: HTMLInputElement, value: string) {
  act(() => {
    Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, "value")!.set!.call(el, value)
    el.dispatchEvent(new Event("input", { bubbles: true }))
  })
}

const CAPS = [
  { key: "run_ai_chat", capability: "Run Gravitre AI and chat", area: "Insights" },
  { key: "approve_writes", capability: "Approve write actions", area: "Govern" },
]
const matrix = (over: Partial<RolePermissionsResponse> = {}): RolePermissionsResponse => ({
  roles: ["admin", "member", "viewer", "support_lead"],
  role_names: { admin: "Admin", member: "Member", viewer: "Viewer", support_lead: "Support lead" },
  role_descriptions: { admin: "All", member: "Builds", viewer: "Reads", support_lead: "Tickets" },
  custom_roles: ["support_lead"],
  locked_roles: ["admin"],
  capabilities: CAPS.map((cap) => ({
    ...cap,
    access: { admin: true, member: true, viewer: cap.key === "run_ai_chat", support_lead: cap.key === "approve_writes" },
  })),
  member_counts: { owner: 1, admin: 1, member: 2, viewer: 0, support_lead: 0 },
  ...over,
})

beforeEach(() => {
  container = document.createElement("div")
  document.body.appendChild(container)
  root = createRoot(container)
  mocks.swr = { [ROLE_PERMISSIONS_KEY]: { data: matrix() } }
  mocks.admin = { isAdmin: true, loading: false }
  mocks.apiFetch.mockReset()
  mocks.mutate.mockReset()
})

afterEach(() => {
  act(() => root.unmount())
  container.remove()
})

describe("Role permissions editor", () => {
  it("toggles a capability, adds a role and saves the full role list", async () => {
    mocks.apiFetch.mockResolvedValue(new Response(JSON.stringify(matrix()), { status: 200 }))
    render(<TrustSafetyRoles />)
    expect(container.textContent).toContain("Support lead")
    await click(button("Edit roles"))

    const viewerApprove = byLabel("Viewer: Approve write actions") as HTMLButtonElement
    expect(viewerApprove.getAttribute("aria-checked")).toBe("false")
    await click(viewerApprove)
    expect(viewerApprove.getAttribute("aria-checked")).toBe("true")
    expect((byLabel("Admin: Approve write actions") as HTMLButtonElement).disabled).toBe(true)

    await click(button("New role"))
    type(byLabel("Name of new role") as HTMLInputElement, "Auditor")
    await click(button("Save changes"))

    expect(mocks.apiFetch).toHaveBeenCalledTimes(1)
    const [url, init] = mocks.apiFetch.mock.calls[0]
    expect(url).toBe(ROLE_PERMISSIONS_KEY)
    expect(init.method).toBe("PUT")
    const sent = JSON.parse(init.body).roles
    expect(sent.map((r: { name: string }) => r.name)).toEqual(["Admin", "Member", "Viewer", "Support lead", "Auditor"])
    expect(sent[2].capabilities).toEqual(["run_ai_chat", "approve_writes"])
    expect(sent[4].key).toBeUndefined()
    expect(mocks.mutate).toHaveBeenCalled()
    expect(mocks.toastSuccess).toHaveBeenCalledWith("Role permissions saved", expect.anything())
    expect(button("Edit roles")).toBeTruthy()
  })

  it("deletes an empty custom role but not one with people on it", async () => {
    mocks.apiFetch.mockResolvedValue(new Response(JSON.stringify(matrix()), { status: 200 }))
    mocks.swr = { [ROLE_PERMISSIONS_KEY]: { data: matrix({ member_counts: { owner: 1, admin: 1, member: 2, support_lead: 3 } }) } }
    render(<TrustSafetyRoles />)
    await click(button("Edit roles"))
    expect((byLabel("Delete Support lead") as HTMLButtonElement).disabled).toBe(true)
    expect(byLabel("Delete Member")).toBeNull()

    act(() => root.unmount())
    root = createRoot(container)
    mocks.swr = { [ROLE_PERMISSIONS_KEY]: { data: matrix() } }
    render(<TrustSafetyRoles />)
    await click(button("Edit roles"))
    await click(byLabel("Delete Support lead"))
    await click(button("Save changes"))
    const sent = JSON.parse(mocks.apiFetch.mock.calls[0][1].body).roles
    expect(sent.map((r: { key: string }) => r.key)).toEqual(["admin", "member", "viewer"])
  })

  it("shows the server's reason when saving fails and keeps the edits", async () => {
    mocks.apiFetch.mockResolvedValue(new Response(JSON.stringify({ detail: "Two roles are named Ops." }), { status: 400 }))
    render(<TrustSafetyRoles />)
    await click(button("Edit roles"))
    await click(byLabel("Member: Approve write actions"))
    await click(button("Save changes"))
    expect(container.querySelector('[role="alert"]')?.textContent).toContain("Two roles are named Ops.")
    expect(button("Discard")).toBeTruthy()
  })

  it("hides editing from members", () => {
    mocks.admin = { isAdmin: false, loading: false }
    render(<TrustSafetyRoles />)
    expect(button("Edit roles")).toBeUndefined()
    expect(container.textContent).toContain("Only owners and admins can change roles.")
  })

  it("flags duplicate and empty names before saving", () => {
    const drafts = draftsFromMatrix(matrix())
    expect(draftProblem(drafts)).toBeNull()
    expect(draftProblem([...drafts, { ...drafts[3], id: "x", key: "", name: "member" }])).toBe("Two roles are named member.")
    expect(draftProblem([...drafts, { ...drafts[3], id: "y", key: "", name: "  " }])).toBe("Every role needs a name.")
  })
})

describe("Audit event details panel", () => {
  const failed: AuditEvent = {
    id: "evt-1",
    action: "connector.sync" as AuditEvent["action"],
    entity_type: "connector",
    entity_id: "c-1",
    entity_name: "HubSpot",
    user_name: "Cesar",
    user_email: "cesar@example.com",
    created_at: "2026-10-21T03:00:00Z",
    outcome: "error",
    details: { failure_reason: "Token expired; reconnect HubSpot", records: 0 },
  }

  it("shows the full failure and closes with Hide or Escape", async () => {
    const onClose = vi.fn()
    render(<AuditEventPanel log={failed} onClose={onClose} />)
    expect(container.querySelector('[role="alert"]')?.textContent).toContain("Token expired; reconnect HubSpot")
    expect(container.textContent).toContain("evt-1")
    expect(document.activeElement).toBe(byLabel("Hide event details"))
    await click(button("Show raw details"))
    expect(container.querySelector("pre")?.textContent).toContain("failure_reason")
    await click(byLabel("Hide event details"))
    expect(onClose).toHaveBeenCalledTimes(1)
    act(() => {
      window.dispatchEvent(new KeyboardEvent("keydown", { key: "Escape" }))
    })
    expect(onClose).toHaveBeenCalledTimes(2)
  })

  it("marks a successful event and reads error text from the event", () => {
    render(<AuditEventPanel log={{ ...failed, outcome: "success", details: {} }} onClose={() => {}} />)
    expect(container.textContent).toContain("Succeeded")
    expect(container.querySelector('[role="alert"]')).toBeNull()
    expect(auditErrorText({ ...failed, error_message: "Boom" })).toBe("Boom")
    expect(auditErrorText({ ...failed, details: {} })).toBe("Failed")
  })
})
