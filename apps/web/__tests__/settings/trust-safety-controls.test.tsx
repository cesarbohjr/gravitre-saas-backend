// @vitest-environment jsdom
import React, { act } from "react"
import { createRoot, type Root } from "react-dom/client"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"

const mocks = vi.hoisted(() => ({
  swr: {} as Record<string, { data?: unknown; error?: Error }>,
  admin: { isAdmin: true },
  mutate: vi.fn(),
  updateSecurity: vi.fn(),
  enableSso: vi.fn(),
  updateApprovalRules: vi.fn(),
  createHitlPolicy: vi.fn(),
  updateHitlPolicy: vi.fn(),
  deleteHitlPolicy: vi.fn(),
  toastSuccess: vi.fn(),
  toastError: vi.fn(),
}))

vi.mock("swr", () => ({
  default: (key: string | readonly unknown[] | null) => ({
    ...(typeof key === "string" ? mocks.swr[key] ?? {} : {}),
    mutate: mocks.mutate,
  }),
}))
vi.mock("sonner", () => ({ toast: { success: mocks.toastSuccess, error: mocks.toastError } }))
vi.mock("@/lib/fetcher", () => ({ apiFetch: vi.fn(), fetcher: vi.fn() }))
vi.mock("@/lib/auth-context", () => ({ useAuth: () => ({ user: null }) }))
vi.mock("@/lib/use-org-admin", () => ({ useOrgAdmin: () => mocks.admin }))
vi.mock("@/lib/api", () => ({
  ssoApi: { getConfig: vi.fn(), saveConfig: vi.fn(), enable: mocks.enableSso, disable: vi.fn(), deleteConfig: vi.fn(), initLogin: vi.fn() },
  settingsApi: {
    updateApprovalRules: mocks.updateApprovalRules,
    createHitlPolicy: mocks.createHitlPolicy,
    updateHitlPolicy: mocks.updateHitlPolicy,
    deleteHitlPolicy: mocks.deleteHitlPolicy,
  },
}))
vi.mock("@/lib/settings-api/security", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/lib/settings-api/security")>()
  return { ...actual, securityApi: { ...actual.securityApi, update: mocks.updateSecurity } }
})
vi.mock("@/components/settings/enterprise-residency", () => ({ EnterpriseResidency: () => <div>Residency stub</div> }))
vi.mock("@/components/settings/enterprise-siem", () => ({ EnterpriseSiem: () => <div>SIEM stub</div> }))

import { TrustSafetySecurity, useSecurityState } from "@/components/trust-safety/trust-safety-security"
import { TrustSafetyPolicies, usePolicyState } from "@/components/trust-safety/trust-safety-policies"

;(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true

let root: Root
let container: HTMLDivElement
const render = (node: React.ReactNode) => act(() => root.render(node))
const byLabel = (label: string) => container.querySelector<HTMLElement>(`[aria-label="${label}"]`)
const button = (text: string) => [...container.querySelectorAll("button")].find((el) => el.textContent?.trim() === text)
const click = async (el: Element | null | undefined) => {
  await act(async () => {
    ;(el as HTMLElement).click()
  })
}
function choose(el: HTMLSelectElement, value: string) {
  act(() => {
    Object.getOwnPropertyDescriptor(HTMLSelectElement.prototype, "value")!.set!.call(el, value)
    el.dispatchEvent(new Event("change", { bubbles: true }))
  })
}

const controls = (over: Record<string, unknown> = {}) => ({
  requireTwoFactor: false,
  ipAllowlist: { enabled: false, ranges: [] as string[] },
  sessionTimeout: "never",
  enforced: { requireTwoFactor: false, ipAllowlist: false, sessionTimeout: false },
  ...over,
})
const sp = { metadata_url: "https://gravitre.app/api/auth/sso/metadata", entity_id: "https://gravitre.app/api/auth/sso/metadata", acs_url: "https://gravitre.app/api/auth/sso/callback" }
const rules = { customerEmailApproval: true, twoApprovalsHighRisk: false, autoApproveReadOnly: false, escalatePastDue: false, sla: "4h", slaMinutes: 240 }

function SecurityTab() {
  return <TrustSafetySecurity state={useSecurityState()} />
}
function PoliciesTab() {
  return <TrustSafetyPolicies state={usePolicyState()} onOpenAudit={() => {}} />
}

beforeEach(() => {
  vi.clearAllMocks()
  mocks.mutate.mockResolvedValue(undefined)
  mocks.admin = { isAdmin: true }
  mocks.swr = {}
  container = document.createElement("div")
  document.body.append(container)
  root = createRoot(container)
})
afterEach(() => {
  act(() => root.unmount())
  container.remove()
})

describe("Trust & Safety security tab", () => {
  it("shows the saved controls, the SP metadata URL and the not enforced note", () => {
    mocks.swr = {
      "/api/auth/sso/config": { data: null },
      "/api/auth/sso/service-provider": { data: sp },
      "/api/settings/security": { data: { security: controls({ requireTwoFactor: true }) } },
    }
    render(<SecurityTab />)
    expect(byLabel("Require two factor authentication")?.getAttribute("aria-checked")).toBe("true")
    expect(container.textContent).toContain("https://gravitre.app/api/auth/sso/metadata")
    expect(container.textContent).toContain("Sign in does not enforce these controls yet")
    expect(button("Configure")).toBeTruthy()
    expect(container.textContent).toContain("Residency stub")
    expect(container.textContent).toContain("SIEM stub")
  })

  it("saves the session timeout and enables single sign on from the setup stage", async () => {
    mocks.swr = {
      "/api/auth/sso/config": { data: { id: "s", provider_type: "saml", is_enabled: false, saml_entity_id: "x" } },
      "/api/auth/sso/service-provider": { data: sp },
      "/api/settings/security": { data: { security: controls() } },
    }
    mocks.updateSecurity.mockResolvedValue({ security: controls({ sessionTimeout: "8h" }) })
    mocks.enableSso.mockResolvedValue({})
    render(<SecurityTab />)
    choose(byLabel("Session timeout") as HTMLSelectElement, "8h")
    await act(async () => {})
    expect(mocks.updateSecurity).toHaveBeenCalledWith({ sessionTimeout: "8h" })
    expect(button("Edit setup")).toBeTruthy()
    await click(button("Test and enable"))
    expect(mocks.enableSso).toHaveBeenCalledOnce()
  })

  it("keeps controls read only for members and hides residency and SIEM", () => {
    mocks.admin = { isAdmin: false }
    mocks.swr = {
      "/api/auth/sso/config": { data: null },
      "/api/auth/sso/service-provider": { data: sp },
      "/api/settings/security": { data: { security: controls() } },
    }
    render(<SecurityTab />)
    expect((byLabel("Require two factor authentication") as HTMLButtonElement).disabled).toBe(true)
    expect((byLabel("Session timeout") as HTMLSelectElement).disabled).toBe(true)
    expect(button("Configure")).toBeUndefined()
    expect(container.textContent).not.toContain("Residency stub")
  })

  it("links to plans when single sign on is not on the plan", () => {
    mocks.swr = {
      "/api/auth/sso/config": { error: Object.assign(new Error("Feature unavailable"), { status: 403 }) },
      "/api/auth/sso/service-provider": { data: sp },
      "/api/settings/security": { data: { security: controls() } },
    }
    render(<SecurityTab />)
    expect(container.textContent).toContain("Not on this plan")
    expect(container.querySelector('a[href="/settings/billing"]')).not.toBeNull()
  })
})

describe("Trust & Safety policies tab", () => {
  it("saves an approval rule and the decision window through the real endpoint", async () => {
    mocks.swr = { "/api/settings/approval-rules": { data: { rules } }, "/api/settings/hitl-policies": { data: { policies: [] } } }
    mocks.updateApprovalRules.mockResolvedValue({ rules: { ...rules, escalatePastDue: true } })
    render(<PoliciesTab />)
    expect(container.textContent).toContain("of 4 rules on")
    const toggle = byLabel("Escalate past due requests")!
    expect(toggle.getAttribute("aria-checked")).toBe("false")
    await click(toggle)
    expect(mocks.updateApprovalRules).toHaveBeenCalledWith({ escalatePastDue: true })
    choose(byLabel("Decision window") as HTMLSelectElement, "1bd")
    await act(async () => {})
    expect(mocks.updateApprovalRules).toHaveBeenCalledWith({ sla: "1bd" })
  })

  it("lists team policies and creates one with the chosen actions and approvers", async () => {
    mocks.swr = {
      "/api/settings/approval-rules": { data: { rules } },
      "/api/settings/hitl-policies": {
        data: { policies: [{ id: "p1", name: "Finance deletes", enabled: true, scope_type: "org", department_id: null, subject_user_id: null, action_kinds: ["delete"], approver_roles: ["owner"] }] },
      },
    }
    mocks.createHitlPolicy.mockResolvedValue({ policy: {} })
    render(<PoliciesTab />)
    expect(container.textContent).toContain("Finance deletes")
    expect(container.textContent).toContain("Whole organization · Delete · Approved by Owner")
    await click(button("New policy"))
    await click(button("Read"))
    await click(button("Create policy"))
    expect(mocks.createHitlPolicy).toHaveBeenCalledWith(
      expect.objectContaining({ scope_type: "org", action_kinds: ["write", "delete", "read"], approver_roles: ["admin", "owner"], enabled: true }),
    )
  })

  it("shows rules read only to members and hides team policies", () => {
    mocks.admin = { isAdmin: false }
    mocks.swr = { "/api/settings/approval-rules": { data: { rules } } }
    render(<PoliciesTab />)
    expect((byLabel("Customer email waits for approval") as HTMLButtonElement).disabled).toBe(true)
    expect(container.textContent).not.toContain("Policies by team or person")
    expect(button("New policy")).toBeUndefined()
  })
})
