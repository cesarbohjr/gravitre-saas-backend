// @vitest-environment jsdom
import React, { act } from "react"
import { createRoot, type Root } from "react-dom/client"
import { afterEach, beforeEach, expect, it, vi } from "vitest"
import { OrganizationSettings } from "@/components/settings/organization-settings"
import { NotificationSettings } from "@/components/settings/notification-settings"
import { SecuritySettings } from "@/components/settings/security-settings"
import { TeamSettings } from "@/components/settings/team-settings"
import { AIModelsSettings } from "@/components/settings/ai-models-settings"

const mocks = vi.hoisted(() => ({
  response: { data: undefined as { notifications: { emailEnabled: boolean; slackEnabled: boolean; recipients: string[] } } | undefined, error: undefined as Error | undefined, isLoading: false },
  mutate: vi.fn(), updateOrg: vi.fn(), uploadOrgLogo: vi.fn(), removeOrgLogo: vi.fn(), update: vi.fn(), success: vi.fn(), error: vi.fn(), refresh: vi.fn(),
}))
vi.mock("swr", () => ({ default: () => ({ ...mocks.response, mutate: mocks.mutate }) }))
vi.mock("@/lib/api", () => ({
  settingsApi: { updateOrg: mocks.updateOrg, uploadOrgLogo: mocks.uploadOrgLogo, removeOrgLogo: mocks.removeOrgLogo, getMemoryEntityEmbeddings: vi.fn().mockResolvedValue({ memoryEntityEmbeddings: { enabled: false, connectors: [] } }), updateMemoryEntityEmbeddings: vi.fn() },
  ssoApi: { getConfig: vi.fn().mockResolvedValue(null), saveConfig: vi.fn(), enable: vi.fn(), disable: vi.fn(), deleteConfig: vi.fn(), initLogin: vi.fn() },
}))
vi.mock("@/lib/fetcher", () => ({ apiFetch: mocks.update, fetcher: vi.fn() }))
vi.mock("sonner", () => ({ toast: { success: mocks.success, error: mocks.error } }))
;(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true
let root: Root
let container: HTMLDivElement
const organization = { id: "org-real", name: "Service team", slug: "service-team", primaryDomain: "team.example", logoUrl: "/team-logo.svg" }
const org = (isAdmin = true) => act(() => root.render(<OrganizationSettings orgData={organization} isAdmin={isAdmin} onUpdate={mocks.refresh} />))
const notification = (isAdmin = true) => act(() => root.render(<NotificationSettings isAdmin={isAdmin} />))
function input(id: string, value: string) {
  const element = container.querySelector<HTMLInputElement>(`#${id}`)!
  act(() => { Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, "value")!.set!.call(element, value); element.dispatchEvent(new Event("input", { bubbles: true })) })
}
const submit = () => container.querySelector("form")!.dispatchEvent(new Event("submit", { bubbles: true, cancelable: true }))
beforeEach(() => {
  vi.clearAllMocks()
  mocks.response = { data: { notifications: { emailEnabled: false, slackEnabled: true, recipients: ["owner@team.example"] } }, error: undefined, isLoading: false }
  mocks.updateOrg.mockResolvedValue({ organization }); mocks.refresh.mockResolvedValue(undefined)
  mocks.update.mockResolvedValue({ ok: true, json: async () => mocks.response.data })
  mocks.mutate.mockResolvedValue(undefined)
  container = document.createElement("div"); document.body.append(container); root = createRoot(container)
})
afterEach(() => { act(() => root.unmount()); container.remove() })
it("loads saved organization fields and preserves its logo in the save payload", async () => {
  org(); input("organization-name", "New service team")
  await act(async () => submit())
  expect(mocks.updateOrg).toHaveBeenCalledWith({ name: "New service team", slug: "service-team", primaryDomain: "team.example", logoUrl: "/team-logo.svg" })
  expect(container.textContent).toContain("Changes saved")
})
it("preserves unsaved organization edits through a background data update", () => {
  org(); input("organization-name", "Draft name")
  act(() => root.render(<OrganizationSettings orgData={{ ...organization, name: "Refetched name" }} isAdmin onUpdate={mocks.refresh} />))
  expect(container.querySelector<HTMLInputElement>("#organization-name")!.value).toBe("Draft name")
})
it("keeps organization writes unavailable for non-admin members", async () => {
  org(false); expect(container.querySelector("fieldset")!.disabled).toBe(true)
  await act(async () => submit()); expect(mocks.updateOrg).not.toHaveBeenCalled()
})
it("shows an organization save error without a false saved state", async () => {
  mocks.updateOrg.mockRejectedValue(new Error("Update denied")); org()
  await act(async () => submit())
  expect(container.querySelector('[role="alert"]')?.textContent).toContain("Update denied")
  expect(mocks.success).not.toHaveBeenCalled()
})
it("uses reported channel preferences and recipients instead of sample addresses", () => {
  notification()
  expect(container.querySelector<HTMLInputElement>('[aria-label="Email notifications"]')!.checked).toBe(false)
  expect(container.querySelector<HTMLInputElement>('[aria-label="Slack notifications"]')!.checked).toBe(true)
  expect(container.querySelector<HTMLInputElement>("#notification-recipients")!.value).toBe("owner@team.example")
  expect(container.querySelector('a')?.getAttribute("href")).toBe("/connectors")
})
it("blocks edits during loading or failed preferences and offers retry", () => {
  mocks.response.data = undefined; mocks.response.isLoading = true; notification()
  expect(container.querySelector("form")).toBeNull(); expect(container.textContent).toContain("Loading notification preferences")
  mocks.response.isLoading = false; mocks.response.error = new Error("Failed"); notification()
  expect(container.querySelector('[role="alert"]')).not.toBeNull()
  act(() => container.querySelector<HTMLButtonElement>("button")!.click()); expect(mocks.mutate).toHaveBeenCalledOnce()
})
it("saves valid deduplicated addresses and channel toggles to the dedicated endpoint", async () => {
  notification(); input("notification-recipients", "owner@team.example, owner@team.example; ops@team.example")
  await act(async () => submit())
  const [url, request] = mocks.update.mock.calls[0]
  expect(url).toBe("/api/settings/notifications"); expect(request.method).toBe("PATCH")
  expect(JSON.parse(request.body)).toEqual({ emailEnabled: false, slackEnabled: true, recipients: ["owner@team.example", "ops@team.example"] })
  expect(mocks.mutate).toHaveBeenCalledWith(mocks.response.data, { revalidate: false })
})
it("rejects invalid recipients and preserves input for correction", async () => {
  notification(); input("notification-recipients", "invalid-address")
  await act(async () => submit())
  expect(mocks.update).not.toHaveBeenCalled(); expect(container.querySelector('[role="alert"]')?.textContent).toContain("valid email addresses")
})
it("keeps failed preference writes visible without claiming success", async () => {
  mocks.update.mockResolvedValue({ ok: false }); notification()
  await act(async () => submit())
  expect(container.querySelector('[role="alert"]')?.textContent).toContain("Could not save")
  expect(mocks.success).not.toHaveBeenCalled()
})
it("blocks preference writes for non-admin members even when submitted directly", async () => {
  notification(false); await act(async () => submit())
  expect(mocks.update).not.toHaveBeenCalled(); expect(container.querySelector("fieldset")!.disabled).toBe(true)
})
it("uploads a logo file through the organization logo endpoint", async () => {
  mocks.uploadOrgLogo.mockResolvedValue({ logoUrl: "data:image/png;base64,abc" })
  org()
  const input = container.querySelector<HTMLInputElement>("#organization-logo-file")!
  const file = new File(["logo"], "logo.png", { type: "image/png" })
  await act(async () => {
    Object.defineProperty(input, "files", { value: [file], configurable: true })
    input.dispatchEvent(new Event("change", { bubbles: true }))
  })
  expect(mocks.uploadOrgLogo).toHaveBeenCalledWith(file)
  expect(container.querySelector("img")?.getAttribute("src")).toBe("data:image/png;base64,abc")
  expect(container.textContent).toContain("Changes saved")
})
it("keeps invalid logo edits from breaking the preview or reaching the save endpoint", async () => {
  org(); input("organization-logoUrl", "not a URL")
  expect(container.querySelector("img")?.getAttribute("src")).toBe("/team-logo.svg")
  await act(async () => submit()); expect(mocks.updateOrg).not.toHaveBeenCalled()
  expect(container.querySelector('[role="alert"]')?.textContent).toContain("valid logo image URL")
})
it("does not save preferences when the server omits channel or recipient fields", () => {
  mocks.response.data = { notifications: {} } as typeof mocks.response.data
  notification(); expect(container.querySelector("form")).toBeNull()
  expect(container.querySelector('[role="alert"]')).not.toBeNull()
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
it("serializes repeated preference submissions until the server responds", async () => {
  let finish!: (result: unknown) => void
  mocks.update.mockImplementation(() => new Promise(resolve => { finish = resolve }))
  notification(); act(() => { submit(); submit() })
  expect(mocks.update).toHaveBeenCalledOnce(); expect(container.querySelector("fieldset")!.disabled).toBe(true)
  await act(async () => finish({ ok: true, json: async () => mocks.response.data }))
  expect(container.textContent).toContain("Preferences saved")
})
