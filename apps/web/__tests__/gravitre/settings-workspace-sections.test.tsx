// @vitest-environment jsdom
import React, { act } from "react"
import { createRoot, type Root } from "react-dom/client"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"

const mocks = vi.hoisted(() => ({
  swr: {} as Record<string, { data?: unknown; error?: unknown; isLoading?: boolean }>,
  mutate: vi.fn(),
  updateSecurity: vi.fn(),
  createKey: vi.fn(),
  revokeKey: vi.fn(),
  rotateKey: vi.fn(),
  savePrefs: vi.fn(),
  updateMemory: vi.fn(),
  enableSso: vi.fn(),
  toastSuccess: vi.fn(),
  toastError: vi.fn(),
}))

vi.mock("swr", () => ({
  default: (key: string | null) => ({ ...(key ? mocks.swr[key] ?? {} : {}), mutate: mocks.mutate }),
}))
vi.mock("sonner", () => ({ toast: { success: mocks.toastSuccess, error: mocks.toastError } }))
vi.mock("@/lib/fetcher", () => ({ apiFetch: vi.fn(), fetcher: vi.fn() }))
vi.mock("@/lib/api", () => ({
  ssoApi: { getConfig: vi.fn(), saveConfig: vi.fn(), enable: mocks.enableSso, disable: vi.fn(), deleteConfig: vi.fn(), initLogin: vi.fn() },
  connectorsApi: { list: vi.fn() },
  settingsApi: { getMemoryEntityEmbeddings: vi.fn(), updateMemoryEntityEmbeddings: mocks.updateMemory },
}))
vi.mock("@/lib/settings-api/security", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/lib/settings-api/security")>()
  return { ...actual, securityApi: { ...actual.securityApi, update: mocks.updateSecurity } }
})
vi.mock("@/lib/settings-api/api-keys", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/lib/settings-api/api-keys")>()
  return {
    ...actual,
    apiKeysApi: { list: vi.fn(), create: mocks.createKey, revoke: mocks.revokeKey, rotate: mocks.rotateKey },
  }
})
vi.mock("@/lib/settings-api/notifications", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/lib/settings-api/notifications")>()
  return { ...actual, browserTimeZone: () => "America/Los_Angeles", notificationPrefsApi: { get: vi.fn(), save: mocks.savePrefs } }
})

import { SecuritySettings } from "@/components/settings/security-settings"
import { ApiKeysSettings } from "@/components/settings/api-keys-settings"
import { NotificationSettings } from "@/components/settings/notification-settings"
import { AIModelsSettings } from "@/components/settings/ai-models-settings"
import { securityPosture, ssoStage, validateIpRange } from "@/lib/settings-api/security"
import { expiryLabel, maskKey } from "@/lib/settings-api/api-keys"
import { slackConnected } from "@/lib/settings-api/notifications"
import { appChips, scopeText } from "@/lib/settings-api/ai-models"

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
function type(el: HTMLInputElement, value: string) {
  act(() => {
    Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, "value")!.set!.call(el, value)
    el.dispatchEvent(new Event("input", { bubbles: true }))
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
const ssoConfig = { id: "s", org_id: "o", provider_type: "saml", is_enabled: true, saml_entity_id: "https://idp.example/x", auto_provision_users: true, default_role: "member", created_at: "2026-10-01" }

beforeEach(() => {
  vi.clearAllMocks()
  mocks.mutate.mockResolvedValue(undefined)
  mocks.swr = {}
  container = document.createElement("div")
  document.body.append(container)
  root = createRoot(container)
})
afterEach(() => {
  act(() => root.unmount())
  container.remove()
})

describe("security helpers", () => {
  it("validates IPv4, IPv6 and CIDR ranges", () => {
    expect(validateIpRange("10.0.0.0/24")).toEqual({ ok: true, value: "10.0.0.0/24" })
    expect(validateIpRange(" 192.168.1.5 ").ok).toBe(true)
    expect(validateIpRange("2001:db8::/32").ok).toBe(true)
    expect(validateIpRange("::1").ok).toBe(true)
    for (const bad of ["10.0.0.300/24", "10.0.0.0/33", "office", "10.0.0/24", "1:2:3", "", "2001:db8::/129"]) {
      expect(validateIpRange(bad).ok).toBe(false)
    }
  })

  it("scores posture from the real controls and picks the next advice", () => {
    const all = { requireTwoFactor: true, ipAllowlist: { enabled: true, ranges: ["10.0.0.0/24"] }, sessionTimeout: "24h" as const }
    expect(securityPosture({ ssoEnabled: true, controls: all })).toEqual({ score: 4, advice: "Every control is on. Nice work." })
    expect(securityPosture({ ssoEnabled: false, controls: null }).score).toBe(0)
    // An allowlist that is on but empty does not count.
    expect(securityPosture({ ssoEnabled: true, controls: { ...all, ipAllowlist: { enabled: true, ranges: [] } } }).advice).toMatch(/IP allowlist/)
    expect(securityPosture({ ssoEnabled: true, controls: { ...all, requireTwoFactor: false } }).advice).toMatch(/two factor/)
  })

  it("maps the SSO config to a stage, including plan gating", () => {
    expect(ssoStage(null)).toBe("none")
    expect(ssoStage({ ...ssoConfig, is_enabled: false } as never)).toBe("setup")
    expect(ssoStage(ssoConfig as never)).toBe("enabled")
    expect(ssoStage(undefined, Object.assign(new Error("Feature unavailable"), { status: 403 }))).toBe("unavailable")
  })
})

describe("Security", () => {
  it("shows posture, SSO status and the real SP metadata URL", () => {
    mocks.swr = {
      "/api/auth/sso/config": { data: ssoConfig },
      "/api/auth/sso/service-provider": { data: sp },
      "/api/settings/security": { data: { security: controls({ requireTwoFactor: true, ipAllowlist: { enabled: true, ranges: ["10.0.0.0/24"] } }) } },
    }
    render(<SecuritySettings isAdmin />)
    expect(container.querySelector("h1")?.textContent).toBe("Security")
    expect(container.querySelector(".security-score b")?.textContent).toBe("3")
    expect(container.textContent).toContain("Set a session timeout")
    expect(container.textContent).toContain("Enabled")
    expect(container.textContent).toContain("SP metadata: https://gravitre.app/api/auth/sso/metadata")
    expect(button("Manage")).toBeTruthy()
    expect(byLabel("Require two factor authentication")?.getAttribute("aria-checked")).toBe("true")
    expect(container.textContent).toContain("Sign in does not enforce it yet")
    expect(container.textContent).toContain("10.0.0.0/24")
  })

  it("validates a range before saving and saves a good one", async () => {
    mocks.swr = {
      "/api/auth/sso/config": { data: null },
      "/api/auth/sso/service-provider": { data: sp },
      "/api/settings/security": { data: { security: controls({ ipAllowlist: { enabled: true, ranges: [] } }) } },
    }
    mocks.updateSecurity.mockResolvedValue({ security: controls({ ipAllowlist: { enabled: true, ranges: ["10.0.0.0/24"] } }) })
    render(<SecuritySettings isAdmin />)
    expect(container.textContent).toContain("Not configured")
    expect(container.textContent).toContain("No ranges yet")
    const input = byLabel("Add IP range") as HTMLInputElement
    type(input, "10.0.0.300/24")
    await click(button("Add"))
    expect(container.querySelector('[role="alert"]')?.textContent).toContain("not a valid IP address")
    expect(mocks.updateSecurity).not.toHaveBeenCalled()
    type(input, "10.0.0.0/24")
    await click(button("Add"))
    expect(mocks.updateSecurity).toHaveBeenCalledWith({ ipAllowlist: { ranges: ["10.0.0.0/24"] } })
  })

  it("saves the session timeout and keeps controls read only for members", async () => {
    mocks.swr = {
      "/api/auth/sso/config": { data: { ...ssoConfig, is_enabled: false } },
      "/api/auth/sso/service-provider": { data: sp },
      "/api/settings/security": { data: { security: controls() } },
    }
    mocks.updateSecurity.mockResolvedValue({ security: controls({ sessionTimeout: "8h" }) })
    render(<SecuritySettings isAdmin />)
    expect(container.textContent).toContain("Setting up")
    expect(button("Test and enable")).toBeTruthy()
    choose(byLabel("Session timeout") as HTMLSelectElement, "8h")
    await act(async () => {})
    expect(mocks.updateSecurity).toHaveBeenCalledWith({ sessionTimeout: "8h" })

    render(<SecuritySettings isAdmin={false} />)
    expect((byLabel("Require two factor authentication") as HTMLButtonElement).disabled).toBe(true)
    expect((byLabel("Session timeout") as HTMLSelectElement).disabled).toBe(true)
    expect(button("Test and enable")).toBeUndefined()
    expect(container.textContent).toContain("Only owners and admins can change security settings")
  })

  it("shows plan gating instead of an error when SSO is not on the plan", () => {
    mocks.swr = {
      "/api/auth/sso/config": { error: Object.assign(new Error("Feature unavailable"), { status: 403 }) },
      "/api/auth/sso/service-provider": { data: sp },
      "/api/settings/security": { data: { security: controls() } },
    }
    render(<SecuritySettings isAdmin />)
    expect(container.textContent).toContain("Not on your plan")
    expect(container.querySelector('a[href="/settings/billing"]')).not.toBeNull()
  })
})

describe("API keys", () => {
  it("formats masked keys and expiry", () => {
    expect(maskKey({ key_prefix: "gv_live_AbCd", last4: "wxyz" })).toBe("gv_live_AbCd••••••••wxyz")
    expect(expiryLabel({ expires_at: null, expired: false })).toBe("Never")
    expect(expiryLabel({ expires_at: "2026-01-02T00:00:00Z", expired: true })).toMatch(/^Expired /)
  })

  it("shows the empty state with the API reference", () => {
    mocks.swr = { "/api/settings/api-keys": { data: { apiKeys: [] } } }
    render(<ApiKeysSettings isAdmin />)
    expect(container.textContent).toContain("No API keys yet")
    expect(container.querySelector('[data-illustration="settings-api-keys"]')).not.toBeNull()
    expect(container.querySelector('a[href="/docs/api/authentication"]')?.textContent).toBe("API reference")
    expect(container.querySelector('a[href="/audit"]')?.textContent).toBe("Audit trail")
  })

  it("creates a key with scope and expiry and reveals it once", async () => {
    mocks.swr = { "/api/settings/api-keys": { data: { apiKeys: [] } } }
    mocks.createKey.mockResolvedValue({ apiKey: { id: "k1", name: "Warehouse", key: "gv_live_secretvalue1234" } })
    render(<ApiKeysSettings isAdmin />)
    expect((button("Create key") as HTMLButtonElement).disabled).toBe(true)
    type(container.querySelector('input[placeholder^="For example"]') as HTMLInputElement, "Warehouse")
    const [scope, expires] = container.querySelectorAll<HTMLSelectElement>(".apikeys-form select")
    choose(scope, "read_write")
    choose(expires, "1y")
    await click(button("Create key"))
    expect(mocks.createKey).toHaveBeenCalledWith({ name: "Warehouse", scope: "read_write", expires_in: "1y" })
    expect(container.textContent).toContain("Copy your key now.")
    expect(container.textContent).toContain("gv_live_secretvalue1234")
  })

  it("lists keys and revokes only after confirming", async () => {
    mocks.swr = {
      "/api/settings/api-keys": {
        data: {
          apiKeys: [
            { id: "k1", name: "Warehouse", key_prefix: "gv_live_AbCd", last4: "wxyz", status: "active", scope: "read", expires_at: null, expired: false, created_at: "2026-10-18T00:00:00Z" },
            { id: "k2", name: "Old", key_prefix: "gv_live_Zz", status: "revoked", scope: null, expires_at: null, expired: false },
          ],
        },
      },
    }
    mocks.revokeKey.mockResolvedValue({ apiKey: { id: "k1", status: "revoked" } })
    render(<ApiKeysSettings isAdmin />)
    expect(container.textContent).toContain("1 active")
    expect(container.textContent).toContain("gv_live_AbCd••••••••wxyz")
    expect(container.textContent).toContain("Read only")
    expect(container.textContent).not.toContain("Old")
    await click(byLabel("Revoke Warehouse"))
    expect(mocks.revokeKey).not.toHaveBeenCalled()
    const confirm = [...document.querySelectorAll("button")].find((el) => el.textContent === "Revoke key")
    await click(confirm)
    expect(mocks.revokeKey).toHaveBeenCalledWith("k1")
  })

  it("keeps API keys admin only", () => {
    render(<ApiKeysSettings isAdmin={false} />)
    expect(container.textContent).toContain("Owner or admin permission is required")
    expect(button("Create key")).toBeUndefined()
  })
})

const prefs = {
  approval_needed: { bell_enabled: true, email_enabled: true, slack_enabled: false },
  run_failed: { bell_enabled: true, email_enabled: false, slack_enabled: true },
  source_attention: { bell_enabled: true, email_enabled: true, slack_enabled: false },
  run_completed: { bell_enabled: true, email_enabled: false, slack_enabled: false },
  weekly_summary: { bell_enabled: true, email_enabled: true, slack_enabled: false },
}

describe("Notifications", () => {
  it("detects a connected Slack connector", () => {
    expect(slackConnected([{ vendor: "slack", status: "healthy" }])).toBe(true)
    expect(slackConnected([{ vendor: "slack", status: "error" }, { vendor: "hubspot", status: "active" }])).toBe(false)
  })

  it("shows the matrix and holds Slack switches while Slack is not connected", () => {
    mocks.swr = {
      "notification-event-preferences": { data: { preferences: prefs, quietHours: { enabled: false, from: "20:00", to: "08:00", timezone: "UTC" } } },
      "/api/connectors": { data: { connectors: [{ vendor: "hubspot", status: "active" }] } },
    }
    render(<NotificationSettings />)
    expect(container.querySelector("h1")?.textContent).toBe("Notifications")
    expect(byLabel("A request is waiting on you by email")?.getAttribute("aria-checked")).toBe("true")
    expect(byLabel("A run finished in app")?.getAttribute("aria-checked")).toBe("true")
    expect((byLabel("A run failed in Slack") as HTMLButtonElement).disabled).toBe(true)
    expect(container.textContent).toContain("Slack is not connected")
    expect(container.querySelector('a[href="/connectors"]')?.textContent).toBe("Connect to Slack")
    expect(container.textContent).not.toContain("Someone mentions you")
    expect(container.textContent).not.toContain("Usage and billing alerts")
  })

  it("resets to defaults and saves with quiet hours in the person's time zone", async () => {
    mocks.swr = {
      "notification-event-preferences": { data: { preferences: prefs, quietHours: { enabled: false, from: "20:00", to: "08:00", timezone: "UTC" } } },
      "/api/connectors": { data: { connectors: [{ vendor: "slack", status: "active" }] } },
    }
    mocks.savePrefs.mockResolvedValue({ ok: true, preferences: prefs })
    render(<NotificationSettings />)
    expect(container.textContent).toContain("Slack is connected")
    expect((byLabel("A run failed in Slack") as HTMLButtonElement).disabled).toBe(false)
    await click(button("Reset to defaults"))
    await click(container.querySelector('[role="switch"][aria-label="Quiet hours"]'))
    expect(container.textContent).toContain("Pacific")
    choose(byLabel("Quiet from") as HTMLSelectElement, "21:00")
    await click(button("Save changes"))
    const [matrix, quiet] = mocks.savePrefs.mock.calls[0]
    expect(matrix.run_failed).toEqual({ email_enabled: true, slack_enabled: false, bell_enabled: true })
    expect(matrix.weekly_summary).toEqual({ email_enabled: false, slack_enabled: false, bell_enabled: true })
    expect(quiet).toEqual({ enabled: true, from: "21:00", to: "08:00", timezone: "America/Los_Angeles" })
  })

  it("blocks edits while loading or failed and offers retry", async () => {
    mocks.swr = { "notification-event-preferences": { isLoading: true } }
    render(<NotificationSettings />)
    expect(container.querySelector('[role="switch"]')).toBeNull()
    mocks.swr = { "notification-event-preferences": { error: new Error("nope") } }
    render(<NotificationSettings />)
    await click(button("Try again"))
    expect(mocks.mutate).toHaveBeenCalled()
  })
})

describe("AI models", () => {
  it("builds app chips from connected apps and keeps saved picks", () => {
    const chips = appChips(
      [
        { vendor: "slack", status: "active" },
        { vendor: "HubSpot", status: "healthy" },
        { vendor: "jira", status: "error" },
        { vendor: "slack", status: "active" },
      ],
      ["asana"],
    )
    expect(chips.map((c) => c.id)).toEqual(["hubspot", "slack", "asana"])
    expect(chips[2].stale).toBe(true)
    expect(scopeText(chips, [])).toBe("Applies to every connected app.")
    expect(scopeText(chips, ["slack"])).toBe("Applies to Slack only.")
  })

  it("shows managed routing and saves the Memory app scope", async () => {
    mocks.swr = {
      "/api/settings/memory-entity-embeddings": { data: { memoryEntityEmbeddings: { enabled: true, connectors: [] } } },
      "/api/connectors": { data: { connectors: [{ vendor: "slack", status: "active" }, { vendor: "hubspot", status: "active" }] } },
    }
    mocks.updateMemory.mockResolvedValue({ memoryEntityEmbeddings: { enabled: true, connectors: ["slack"] } })
    render(<AIModelsSettings isAdmin />)
    expect(container.textContent).toContain("Managed by Gravitre for every workspace")
    expect(container.textContent).toContain("Applies to every connected app.")
    await click(button("Slack"))
    expect(container.textContent).toContain("Applies to Slack only.")
    await click(button("Save changes"))
    expect(mocks.updateMemory).toHaveBeenCalledWith({ enabled: true, connectors: ["slack"] })
  })

  it("keeps Memory read only for members", () => {
    mocks.swr = {
      "/api/settings/memory-entity-embeddings": { data: { memoryEntityEmbeddings: { enabled: false, connectors: [] } } },
      "/api/connectors": { data: { connectors: [] } },
    }
    render(<AIModelsSettings isAdmin={false} />)
    expect((byLabel("Enable entity matching") as HTMLButtonElement).disabled).toBe(true)
    expect(container.textContent).toContain("Only owners and admins can change this setting.")
  })
})
