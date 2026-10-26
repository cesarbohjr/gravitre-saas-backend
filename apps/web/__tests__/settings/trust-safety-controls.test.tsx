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
  updateSiem: vi.fn(),
  testSiem: vi.fn(),
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
  enterpriseApi: { getSiem: vi.fn(), updateSiem: mocks.updateSiem, testSiem: mocks.testSiem, updateDataRegion: vi.fn() },
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

import { TrustSafetySecurity, useSecurityState } from "@/components/trust-safety/trust-safety-security"
import { TrustSafetyPolicies, usePolicyState } from "@/components/trust-safety/trust-safety-policies"

;(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true

let root: Root
let container: HTMLDivElement
const render = (node: React.ReactNode) => act(() => root.render(node))
const byLabel = (label: string) => container.querySelector<HTMLElement>(`[aria-label="${label}"]`)
const button = (text: string) => [...container.querySelectorAll("button")].find((el) => el.textContent?.trim() === text)
// Dialogs portal into the body, outside the render container.
const dialogButton = (text: string) =>
  [...document.querySelectorAll<HTMLElement>('[role="dialog"] button')].find((el) => el.textContent?.trim() === text)
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
const residency = {
  region: "us",
  deploymentRegion: "us",
  storagePrefix: "us/org-1",
  migrationSupported: false,
  regions: [
    { id: "eu", label: "European Union", current: false, available: false },
    { id: "us", label: "United States", current: true, available: true },
  ],
}
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
      "/api/enterprise/insights/residency": { data: residency },
      "enterprise-siem": { data: { enabled: false, endpoint: null, hasSecret: false } },
    }
    render(<SecurityTab />)
    expect(byLabel("Require two factor authentication")?.getAttribute("aria-checked")).toBe("true")
    expect(container.textContent).toContain("SP metadata: https://gravitre.app/api/auth/sso/metadata")
    expect(container.textContent).toContain("Sign in does not enforce these controls yet")
    expect(button("Configure")).toBeTruthy()
    expect(container.textContent).toContain("Where your data lives")
    expect(container.textContent).toContain("us/org-1")
    expect(container.textContent).toContain("Not available")
    expect(container.textContent).toContain("Forwarding off")
  })

  it("saves SIEM forwarding with the chosen events and a new signing secret", async () => {
    mocks.swr = {
      "/api/auth/sso/config": { data: null },
      "/api/auth/sso/service-provider": { data: sp },
      "/api/settings/security": { data: { security: controls() } },
      "/api/enterprise/insights/residency": { data: residency },
      "enterprise-siem": { data: { enabled: false, endpoint: null, hasSecret: false } },
    }
    mocks.updateSiem.mockResolvedValue({ enabled: true, endpoint: "https://siem.example.com/hook", hasSecret: true, events: ["audit", "auth", "approvals", "policy"] })
    render(<SecurityTab />)
    await click(byLabel("Forward events"))
    const url = container.querySelector<HTMLInputElement>("#siem-url")!
    act(() => {
      Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, "value")!.set!.call(url, "https://siem.example.com/hook")
      url.dispatchEvent(new Event("input", { bubbles: true }))
    })
    expect(container.textContent).toContain("Forwarding on")
    await click(button("Agent runs"))
    await click(button("Save"))
    expect(mocks.updateSiem).toHaveBeenCalledWith(
      expect.objectContaining({ enabled: true, endpoint: "https://siem.example.com/hook", events: ["audit", "auth", "approvals", "policy"], secret: expect.stringMatching(/^whsec_[0-9a-f]{32}$/) }),
    )
  })

  it("flags a non https SIEM endpoint", () => {
    mocks.swr = {
      "/api/auth/sso/config": { data: null },
      "/api/auth/sso/service-provider": { data: sp },
      "/api/settings/security": { data: { security: controls() } },
      "/api/enterprise/insights/residency": { data: residency },
      "enterprise-siem": { data: { enabled: true, endpoint: "http://siem.example.com", hasSecret: true, events: ["audit"] } },
    }
    render(<SecurityTab />)
    expect(container.textContent).toContain("Use an https endpoint")
    expect(container.textContent).toContain("Needs an endpoint")
    expect(button("Reveal")?.hasAttribute("disabled")).toBe(true)
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
    expect(container.textContent).not.toContain("Where your data lives")
    expect(container.textContent).not.toContain("Forward events")
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
    expect(document.querySelector('[role="dialog"]')?.textContent).toContain("Decide which actions pause for a person")
    await click(dialogButton("Read"))
    await click(dialogButton("Create policy"))
    expect(mocks.createHitlPolicy).toHaveBeenCalledWith(
      expect.objectContaining({ scope_type: "org", action_kinds: ["write", "delete", "read"], approver_roles: ["admin", "owner"], enabled: true }),
    )
  })

  it("edits a team policy in the dialog and asks before deleting one", async () => {
    const policy = { id: "p1", name: "Finance deletes", enabled: true, scope_type: "org", department_id: null, subject_user_id: null, action_kinds: ["delete"], approver_roles: ["owner"] }
    mocks.swr = {
      "/api/settings/approval-rules": { data: { rules } },
      "/api/settings/hitl-policies": { data: { policies: [policy] } },
    }
    mocks.updateHitlPolicy.mockResolvedValue({ policy })
    render(<PoliciesTab />)
    await click(button("Edit"))
    await click(dialogButton("Write"))
    await click(dialogButton("Save policy"))
    expect(mocks.updateHitlPolicy).toHaveBeenCalledWith(
      "p1",
      expect.objectContaining({ name: "Finance deletes", scope_type: "org", action_kinds: ["delete", "write"], approver_roles: ["owner"] }),
    )

    const confirm = vi.spyOn(window, "confirm").mockReturnValue(false)
    await click(byLabel("Delete Finance deletes"))
    expect(confirm).toHaveBeenCalledWith(expect.stringContaining("Delete Finance deletes?"))
    expect(mocks.deleteHitlPolicy).not.toHaveBeenCalled()
    confirm.mockRestore()
  })

  it("offers Undo after a rule changes, which sends the previous value back", async () => {
    mocks.swr = { "/api/settings/approval-rules": { data: { rules } }, "/api/settings/hitl-policies": { data: { policies: [] } } }
    mocks.updateApprovalRules.mockResolvedValue({ rules: { ...rules, twoApprovalsHighRisk: true } })
    render(<PoliciesTab />)
    await click(byLabel("Two approvals for high risk actions"))
    expect(mocks.toastSuccess).toHaveBeenCalledWith("Policy updated", expect.objectContaining({ cancel: expect.objectContaining({ label: "Undo" }) }))
    const undo = mocks.toastSuccess.mock.calls.at(-1)?.[1]?.cancel as { onClick: () => void }
    await act(async () => undo.onClick())
    expect(mocks.updateApprovalRules).toHaveBeenLastCalledWith({ twoApprovalsHighRisk: false })
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
