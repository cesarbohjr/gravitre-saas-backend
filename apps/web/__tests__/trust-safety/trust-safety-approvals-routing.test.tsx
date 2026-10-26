// @vitest-environment jsdom
import React, { act } from "react"
import { createRoot, type Root } from "react-dom/client"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"

const mocks = vi.hoisted(() => ({
  swr: {} as Record<string, { data?: unknown; error?: Error }>,
  admin: { isAdmin: true, loading: false },
  mutate: vi.fn(),
  apiFetch: vi.fn(),
  updateApprovalRules: vi.fn(),
  toastSuccess: vi.fn(),
  toastError: vi.fn(),
}))

vi.mock("swr", () => ({
  default: (key: string | readonly unknown[] | null) => ({
    ...(typeof key === "string" ? mocks.swr[key] ?? {} : {}),
    mutate: mocks.mutate,
  }),
  useSWRConfig: () => ({ mutate: vi.fn() }),
}))
vi.mock("sonner", () => ({ toast: { success: mocks.toastSuccess, error: mocks.toastError } }))
vi.mock("@/lib/fetcher", () => ({ apiFetch: mocks.apiFetch, fetcher: vi.fn() }))
vi.mock("@/lib/auth-context", () => ({ useAuth: () => ({ user: { id: "u1" } }) }))
vi.mock("@/lib/use-org-admin", () => ({ useOrgAdmin: () => mocks.admin }))
vi.mock("@/lib/api", () => ({
  approvalsApi: { approve: vi.fn(), reject: vi.fn() },
  settingsApi: { updateApprovalRules: mocks.updateApprovalRules },
}))
vi.mock("next/navigation", () => ({ useRouter: () => ({ push: vi.fn() }) }))
vi.mock("next/link", () => ({ default: ({ children, href, ...rest }: { children: React.ReactNode; href: string }) => <a href={href} {...rest}>{children}</a> }))

import { TrustSafetyApprovals, approverChoice } from "@/components/trust-safety/trust-safety-approvals"
import { usePolicyState } from "@/components/trust-safety/trust-safety-policies"
import type { RolePermissionsResponse } from "@/lib/settings-api/roles"

;(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true

const rules = { customerEmailApproval: true, twoApprovalsHighRisk: false, autoApproveReadOnly: false, escalatePastDue: false, sla: "4h", slaMinutes: 240 }

function matrix(memberApproves: boolean, viewerApproves = false): RolePermissionsResponse {
  return {
    roles: ["admin", "member", "viewer"],
    locked_roles: ["admin"],
    custom_roles: [],
    capabilities: [
      { key: "approve_writes", capability: "Approve write actions", access: { admin: true, member: memberApproves, viewer: viewerApproves } },
      { key: "run_ai_chat", capability: "Run Gravitre AI and chat", access: { admin: true, member: true, viewer: true } },
    ],
    member_counts: { admin: 1, member: 2, viewer: 0 },
  }
}

let root: Root
let container: HTMLDivElement

function Approvals() {
  const policy = usePolicyState()
  return <TrustSafetyApprovals policy={policy} onViewPast={() => {}} onViewPolicies={() => {}} />
}

beforeEach(() => {
  vi.clearAllMocks()
  mocks.mutate.mockResolvedValue(undefined)
  mocks.admin = { isAdmin: true, loading: false }
  container = document.createElement("div")
  document.body.append(container)
  root = createRoot(container)
})

afterEach(() => {
  act(() => root.unmount())
  container.remove()
})

describe("Approvals routing", () => {
  it("reads who can approve from the Approve write actions permission", () => {
    expect(approverChoice(matrix(false))).toBe("admins")
    expect(approverChoice(matrix(true))).toBe("members")
    expect(approverChoice(matrix(true, true))).toBe("custom")
    expect(approverChoice(undefined)).toBeNull()
  })

  it("saves who can approve through the role permissions endpoint and skip read only through the approval rules", async () => {
    mocks.swr = {
      "/api/approvals": { data: { approvals: [] } },
      "/api/org/role-permissions": { data: matrix(true) },
      "/api/settings/approval-rules": { data: { rules } },
    }
    mocks.apiFetch.mockResolvedValue({ ok: true, json: async () => matrix(false) })
    mocks.updateApprovalRules.mockResolvedValue({ rules: { ...rules, autoApproveReadOnly: true } })
    act(() => root.render(<Approvals />))

    expect(container.textContent).not.toContain("Decide from chat")
    const select = container.querySelector<HTMLSelectElement>('aside[aria-label="Approval routing"] select')!
    expect(select.value).toBe("members")
    await act(async () => {
      Object.getOwnPropertyDescriptor(HTMLSelectElement.prototype, "value")!.set!.call(select, "admins")
      select.dispatchEvent(new Event("change", { bubbles: true }))
    })
    const [url, init] = mocks.apiFetch.mock.calls[0]
    expect(url).toBe("/api/org/role-permissions")
    const sent = JSON.parse(init.body).roles as Array<{ key: string; capabilities: string[] }>
    expect(sent.find((r) => r.key === "member")?.capabilities).not.toContain("approve_writes")
    expect(sent.find((r) => r.key === "admin")?.capabilities).toContain("approve_writes")
    expect(mocks.toastSuccess).toHaveBeenCalledWith("Approvers updated", expect.anything())

    const skip = container.querySelector<HTMLButtonElement>('[aria-label="Skip approval for read only actions"]')!
    expect(skip.getAttribute("aria-checked")).toBe("false")
    await act(async () => skip.click())
    expect(mocks.updateApprovalRules).toHaveBeenCalledWith({ autoApproveReadOnly: true })
  })

  it("shows routing read only to members", () => {
    mocks.admin = { isAdmin: false, loading: false }
    mocks.swr = {
      "/api/approvals": { data: { approvals: [] } },
      "/api/org/role-permissions": { data: matrix(true) },
      "/api/settings/approval-rules": { data: { rules } },
    }
    act(() => root.render(<Approvals />))
    expect(container.querySelector<HTMLSelectElement>('aside[aria-label="Approval routing"] select')!.disabled).toBe(true)
    expect(container.querySelector<HTMLButtonElement>('[aria-label="Skip approval for read only actions"]')!.disabled).toBe(true)
    expect(container.textContent).toContain("Only owners and admins can change routing.")
  })
})
