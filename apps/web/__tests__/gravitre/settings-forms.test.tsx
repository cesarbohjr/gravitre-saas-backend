// @vitest-environment jsdom
import React, { act } from "react"
import { createRoot, type Root } from "react-dom/client"
import { afterEach, beforeEach, expect, it, vi } from "vitest"
import { OrganizationSettings } from "@/components/settings/organization-settings"
import { NotificationSettings } from "@/components/settings/notification-settings"
import { SecuritySettings } from "@/components/settings/security-settings"
import { TeamSettings } from "@/components/settings/team-settings"
import { AIModelsSettings } from "@/components/settings/ai-models-settings"
import { ApprovalRulesSettings } from "@/components/settings/approval-rules-settings"

const mocks = vi.hoisted(() => ({
  swr: {} as Record<string, { data?: unknown; error?: Error; isLoading?: boolean }>,
  mutate: vi.fn(), updateOrg: vi.fn(), uploadOrgLogo: vi.fn(), removeOrgLogo: vi.fn(), updateWorkspace: vi.fn(),
  updateApprovalRules: vi.fn(), getPreferences: vi.fn(), updatePreferences: vi.fn(), deleteOrg: vi.fn(),
  success: vi.fn(), error: vi.fn(), refresh: vi.fn(),
}))
vi.mock("swr", () => ({ default: (key: string) => ({ ...(mocks.swr[key] ?? {}), mutate: mocks.mutate }) }))
vi.mock("@/lib/api", () => ({
  settingsApi: { updateOrg: mocks.updateOrg, uploadOrgLogo: mocks.uploadOrgLogo, removeOrgLogo: mocks.removeOrgLogo, updateWorkspace: mocks.updateWorkspace, updateApprovalRules: mocks.updateApprovalRules, getMemoryEntityEmbeddings: vi.fn().mockResolvedValue({ memoryEntityEmbeddings: { enabled: false, connectors: [] } }), updateMemoryEntityEmbeddings: vi.fn() },
  notificationsApi: { getPreferences: mocks.getPreferences, updatePreferences: mocks.updatePreferences },
  organizationsApi: { delete: mocks.deleteOrg },
  ssoApi: { getConfig: vi.fn().mockResolvedValue(null), saveConfig: vi.fn(), enable: vi.fn(), disable: vi.fn(), deleteConfig: vi.fn(), initLogin: vi.fn() },
}))
vi.mock("@/lib/fetcher", () => ({ apiFetch: vi.fn(), fetcher: vi.fn() }))
vi.mock("@/lib/org-context", () => ({ clearSelectedOrgFromStorage: vi.fn(), invalidateOrgCache: vi.fn() }))
vi.mock("next/image", () => ({ default: ({ unoptimized: _u, ...props }: Record<string, unknown>) => <img {...(props as React.ImgHTMLAttributes<HTMLImageElement>)} /> }))
vi.mock("sonner", () => ({ toast: { success: mocks.success, error: mocks.error } }))
;(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true
let root: Root
let container: HTMLDivElement
const organization = { id: "org-real", name: "Service team", slug: "service-team", primaryDomain: "team.example", logoUrl: "/team-logo.svg" }
const prefs = {
  approval_needed: { bell_enabled: true, email_enabled: true, slack_enabled: false },
  run_failed: { bell_enabled: true, email_enabled: false, slack_enabled: true },
  source_attention: { bell_enabled: true, email_enabled: true, slack_enabled: false },
  weekly_summary: { bell_enabled: true, email_enabled: false, slack_enabled: false },
}
const org = (isAdmin = true) => act(() => root.render(<OrganizationSettings orgData={organization} isAdmin={isAdmin} onUpdate={mocks.refresh} />))
const notification = () => act(() => root.render(<NotificationSettings />))
function input(id: string, value: string) {
  const element = container.querySelector<HTMLInputElement>(`#${id}`)!
  act(() => { Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, "value")!.set!.call(element, value); element.dispatchEvent(new Event("input", { bubbles: true })) })
}
const button = (text: string) => [...container.querySelectorAll("button")].find((el) => el.textContent?.trim() === text)
const click = (el: Element | undefined | null) => act(() => { (el as HTMLElement).click() })
const saveChanges = () => act(async () => { button("Save changes")!.click() })
beforeEach(() => {
  vi.clearAllMocks()
  mocks.swr = {
    "/api/settings/workspace": { data: { workspace: { accentColor: "#2E9E5B", timeZone: "America/Vancouver" } } },
    "notification-event-preferences": { data: { preferences: prefs } },
    "/api/settings/approval-rules": { data: { rules: { customerEmailApproval: true, twoApprovalsHighRisk: false, autoApproveReadOnly: false, escalatePastDue: false, sla: "4h", slaMinutes: 240 } } },
  }
  mocks.updateOrg.mockResolvedValue({ organization }); mocks.refresh.mockResolvedValue(undefined)
  mocks.updateWorkspace.mockResolvedValue({ workspace: { accentColor: "#5B5BD6", timeZone: "Europe/London" } })
  mocks.updatePreferences.mockResolvedValue({ ok: true, preferences: prefs })
  mocks.mutate.mockResolvedValue(undefined)
  container = document.createElement("div"); document.body.append(container); root = createRoot(container)
})
afterEach(() => { act(() => root.unmount()); container.remove() })
it("saves an edited workspace name and keeps the slug, domain and logo", async () => {
  org(); expect(container.textContent).not.toContain("Unsaved changes")
  input("organization-name", "New service team")
  expect(container.textContent).toContain("Unsaved changes")
  await saveChanges()
  expect(mocks.updateOrg).toHaveBeenCalledWith({ name: "New service team", slug: "service-team", primaryDomain: "team.example", logoUrl: "/team-logo.svg" })
  expect(mocks.updateWorkspace).not.toHaveBeenCalled()
  expect(container.textContent).toContain("Saved")
})
it("saves accent colour and time zone through the workspace endpoint", async () => {
  org()
  expect(container.querySelector('[aria-label="Gravitre green"]')!.getAttribute("aria-pressed")).toBe("true")
  click(container.querySelector('[aria-label="Indigo"]'))
  const zone = container.querySelector<HTMLSelectElement>("#organization-timezone")!
  expect(zone.value).toBe("America/Vancouver")
  act(() => { Object.getOwnPropertyDescriptor(HTMLSelectElement.prototype, "value")!.set!.call(zone, "Europe/London"); zone.dispatchEvent(new Event("change", { bubbles: true })) })
  await saveChanges()
  expect(mocks.updateWorkspace).toHaveBeenCalledWith({ accentColor: "#5B5BD6", timeZone: "Europe/London" })
  expect(mocks.updateOrg).not.toHaveBeenCalled()
})
it("discards unsaved workspace edits", () => {
  org(); input("organization-name", "Draft name")
  click(button("Discard"))
  expect(container.querySelector<HTMLInputElement>("#organization-name")!.value).toBe("Service team")
})
it("preserves unsaved organization edits through a background data update", () => {
  org(); input("organization-name", "Draft name")
  act(() => root.render(<OrganizationSettings orgData={{ ...organization, name: "Refetched name" }} isAdmin onUpdate={mocks.refresh} />))
  expect(container.querySelector<HTMLInputElement>("#organization-name")!.value).toBe("Draft name")
})
it("keeps workspace writes unavailable for non-admin members", () => {
  org(false)
  expect(container.querySelector<HTMLInputElement>("#organization-name")!.disabled).toBe(true)
  expect(container.textContent).toContain("Only owners and admins")
  expect(container.textContent).not.toContain("Delete workspace")
})
it("shows a workspace save error without a false saved state", async () => {
  mocks.updateOrg.mockRejectedValue(new Error("Update denied")); org()
  input("organization-name", "Other")
  await saveChanges()
  expect(container.querySelector('[role="alert"]')?.textContent).toContain("Update denied")
  expect(container.textContent).toContain("Unsaved changes")
})
it("uploads a logo file through the organization logo endpoint", async () => {
  mocks.uploadOrgLogo.mockResolvedValue({ logoUrl: "data:image/png;base64,abc" })
  org()
  const file = new File(["logo"], "logo.png", { type: "image/png" })
  const field = container.querySelector<HTMLInputElement>("#organization-logo-file")!
  await act(async () => {
    Object.defineProperty(field, "files", { value: [file], configurable: true })
    field.dispatchEvent(new Event("change", { bubbles: true }))
  })
  expect(mocks.uploadOrgLogo).toHaveBeenCalledWith(file)
  expect(container.querySelector("img")?.getAttribute("src")).toBe("data:image/png;base64,abc")
})
it("keeps invalid logo URLs from breaking the preview or reaching the save endpoint", async () => {
  org(); input("organization-logoUrl", "not a URL")
  expect(container.querySelector("img")?.getAttribute("src")).toBe("/team-logo.svg")
  await saveChanges(); expect(mocks.updateOrg).not.toHaveBeenCalled()
  expect(container.querySelector('[role="alert"]')?.textContent).toContain("valid logo image URL")
})
it("shows each event by channel from the saved per-person preferences", () => {
  notification()
  const box = (label: string) => container.querySelector<HTMLInputElement>(`[aria-label="${label}"]`)!
  expect(box("A request is waiting on you by Email").checked).toBe(true)
  expect(box("A run failed by Slack").checked).toBe(true)
  expect(box("Weekly summary by Email").checked).toBe(false)
  expect(box("A source needs attention by In app").checked).toBe(true)
  expect(container.querySelector('a')?.getAttribute("href")).toBe("/connectors")
})
it("blocks edits during loading or failed preferences and offers retry", () => {
  mocks.swr["notification-event-preferences"] = { isLoading: true }; notification()
  expect(container.querySelector('input[type="checkbox"]')).toBeNull(); expect(container.textContent).toContain("Loading notification preferences")
  mocks.swr["notification-event-preferences"] = { error: new Error("Failed") }; notification()
  expect(container.querySelector('[role="alert"]')).not.toBeNull()
  click(button("Retry")); expect(mocks.mutate).toHaveBeenCalledOnce()
})
it("saves a changed notification matrix to the preferences endpoint", async () => {
  notification()
  click(container.querySelector('[aria-label="Weekly summary by Email"]'))
  await saveChanges()
  expect(mocks.updatePreferences).toHaveBeenCalledWith({ ...prefs, weekly_summary: { bell_enabled: true, email_enabled: true, slack_enabled: false } })
  expect(mocks.mutate).toHaveBeenCalledWith({ preferences: prefs }, { revalidate: false })
})
it("keeps failed preference writes visible without claiming success", async () => {
  mocks.updatePreferences.mockRejectedValue(new Error("Could not save")); notification()
  click(container.querySelector('[aria-label="A run failed by Email"]'))
  await saveChanges()
  expect(container.querySelector('[role="alert"]')?.textContent).toContain("Could not save")
  expect(container.textContent).toContain("Unsaved changes")
})
it("saves the human in the loop rules and decision SLA", async () => {
  mocks.updateApprovalRules.mockResolvedValue({ rules: {} })
  act(() => root.render(<ApprovalRulesSettings />))
  const toggle = container.querySelector('[role="switch"][aria-label="Escalate past due requests"]')!
  expect(toggle.getAttribute("aria-checked")).toBe("false")
  click(toggle)
  const sla = container.querySelector<HTMLSelectElement>("#decision-sla")!
  act(() => { Object.getOwnPropertyDescriptor(HTMLSelectElement.prototype, "value")!.set!.call(sla, "1bd"); sla.dispatchEvent(new Event("change", { bubbles: true })) })
  await saveChanges()
  expect(mocks.updateApprovalRules).toHaveBeenCalledWith({ customerEmailApproval: true, twoApprovalsHighRisk: false, autoApproveReadOnly: false, escalatePastDue: true, sla: "1bd" })
})
it("does not offer fake 2FA or IP allowlist saves on Security", () => {
  act(() => root.render(<SecuritySettings />))
  expect(container.textContent).toContain("Organization-wide 2FA enforcement is not available")
  expect(container.textContent).toContain("IP restriction is not available")
  expect(container.textContent).not.toContain("Enable 2FA")
  expect(container.textContent).not.toContain("Save allowlist")
})
it("shows team loading and error without inventing members", () => {
  act(() => root.render(<TeamSettings members={[]} isLoading isAdmin onUpdate={mocks.refresh} />))
  expect(container.textContent).toContain("Loading team members")
  act(() => root.render(<TeamSettings members={[]} error={new Error("Denied")} onRetry={mocks.mutate} isAdmin onUpdate={mocks.refresh} />))
  expect(container.querySelector('[role="alert"]')).not.toBeNull()
  act(() => container.querySelector("button")!.click())
  expect(mocks.mutate).toHaveBeenCalledOnce()
})
it("does not present unsaved workspace model defaults as persistable", () => {
  act(() => root.render(<AIModelsSettings isAdmin />))
  expect(container.textContent).toContain("no organization API for workspace default models")
  expect(container.textContent).not.toContain("Saved!")
})
