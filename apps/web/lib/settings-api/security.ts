/**
 * Settings > Security: workspace access controls (GET/PATCH
 * /api/settings/security, stored in organizations.settings.securityControls),
 * the SSO service provider URLs (GET /api/auth/sso/service-provider) and the
 * pure helpers behind the posture card and the IP allowlist input.
 */
import { apiFetch, fetcher } from "@/lib/fetcher"
import { extractApiErrorMessage } from "@/lib/api-error-message"
import type { SSOConfiguration } from "@/types/api"

export type SessionTimeout = "never" | "8h" | "24h" | "7d"

export const SESSION_TIMEOUT_OPTIONS: Array<{ id: SessionTimeout; label: string }> = [
  { id: "never", label: "Never" },
  { id: "8h", label: "8 hours" },
  { id: "24h", label: "24 hours" },
  { id: "7d", label: "7 days" },
]

export interface SecurityControls {
  requireTwoFactor: boolean
  ipAllowlist: { enabled: boolean; ranges: string[] }
  sessionTimeout: SessionTimeout
  /** Whether sign in enforces each control today. */
  enforced: { requireTwoFactor: boolean; ipAllowlist: boolean; sessionTimeout: boolean }
}

export type SecurityControlsPatch = {
  requireTwoFactor?: boolean
  ipAllowlist?: { enabled?: boolean; ranges?: string[] }
  sessionTimeout?: SessionTimeout
}

export interface SsoServiceProvider {
  metadata_url: string
  entity_id: string
  acs_url: string
}

export const SECURITY_KEY = "/api/settings/security"
export const SSO_CONFIG_KEY = "/api/auth/sso/config"
export const SSO_SP_KEY = "/api/auth/sso/service-provider"

/** Error with the HTTP status kept, so callers can tell plan gating from failures. */
export class SettingsRequestError extends Error {
  status: number
  constructor(message: string, status: number) {
    super(message)
    this.name = "SettingsRequestError"
    this.status = status
  }
}

/** JSON request for the settings helpers; throws SettingsRequestError with the API's message. */
export async function sendJson<T>(url: string, method: "POST" | "PATCH" | "PUT" | "DELETE", body?: unknown): Promise<T> {
  const response = await apiFetch(url, {
    method,
    headers: body === undefined ? undefined : { "content-type": "application/json" },
    body: body === undefined ? undefined : JSON.stringify(body),
  })
  if (!response.ok) {
    const payload = await response.json().catch(() => ({}))
    throw new SettingsRequestError(extractApiErrorMessage(payload) || `Request failed (${response.status})`, response.status)
  }
  const text = await response.text()
  return (text.trim() ? JSON.parse(text) : {}) as T
}

export const securityApi = {
  get: () => fetcher<{ security: SecurityControls }>(SECURITY_KEY),
  update: (patch: SecurityControlsPatch) => sendJson<{ security: SecurityControls }>(SECURITY_KEY, "PATCH", patch),
  serviceProvider: () => fetcher<SsoServiceProvider>(SSO_SP_KEY),
  /** The SP metadata XML needs the signed-in session, so fetch it and hand the browser a file. */
  downloadMetadata: async () => {
    const response = await apiFetch("/api/auth/sso/metadata")
    if (!response.ok) {
      const payload = await response.json().catch(() => ({}))
      throw new SettingsRequestError(extractApiErrorMessage(payload) || "Could not download metadata", response.status)
    }
    return response.blob()
  },
}

// ---------------------------------------------------------------- IP ranges

function parseIpv4(text: string): number[] | null {
  const parts = text.split(".")
  if (parts.length !== 4) return null
  const out: number[] = []
  for (const part of parts) {
    if (!/^\d{1,3}$/.test(part)) return null
    const n = Number(part)
    if (n > 255) return null
    out.push(n)
  }
  return out
}

function isIpv6(text: string): boolean {
  if (!/^[0-9a-fA-F:.]+$/.test(text) || text.split("::").length > 2) return false
  let groups = text.split(":")
  let budget = 8
  const last = groups[groups.length - 1]
  if (last.includes(".")) {
    if (!parseIpv4(last)) return false
    groups = groups.slice(0, -1)
    budget = 6
  }
  const filled = groups.filter((g) => g !== "")
  if (!filled.every((g) => /^[0-9a-fA-F]{1,4}$/.test(g))) return false
  if (text.includes("::")) return filled.length < budget
  return filled.length === budget && groups.length === budget
}

/**
 * Validate one allowlist entry: an IPv4 or IPv6 address, or a CIDR range.
 * The backend canonicalizes (10.0.0.7/24 becomes 10.0.0.0/24) and re-checks.
 */
export function validateIpRange(input: string): { ok: true; value: string } | { ok: false; error: string } {
  const value = input.trim()
  if (!value) return { ok: false, error: "Enter an IP address or a CIDR range." }
  const [address, prefix, extra] = value.split("/")
  if (extra !== undefined) return { ok: false, error: `${value} is not a valid IP address or CIDR range.` }
  const v4 = parseIpv4(address)
  const v6 = !v4 && isIpv6(address)
  if (!v4 && !v6) return { ok: false, error: `${value} is not a valid IP address or CIDR range.` }
  if (prefix !== undefined) {
    const max = v4 ? 32 : 128
    if (!/^\d{1,3}$/.test(prefix) || Number(prefix) > max) {
      return { ok: false, error: `The range after / must be a number from 0 to ${max}.` }
    }
  }
  return { ok: true, value }
}

// ---------------------------------------------------------------- posture

export type SsoStage = "unavailable" | "none" | "setup" | "enabled"

/** Feature unavailable on this plan (sso_saml) comes back as 403 from /api/auth/sso/config. */
export function isPlanGated(error: unknown): boolean {
  const status = (error as { status?: number } | null)?.status
  const message = error instanceof Error ? error.message : ""
  return status === 403 && /feature unavailable|sso_saml/i.test(message)
}

export function ssoStage(config: SSOConfiguration | null | undefined, error?: unknown): SsoStage {
  if (error && isPlanGated(error)) return "unavailable"
  if (!config) return "none"
  return config.is_enabled ? "enabled" : "setup"
}

export interface Posture {
  score: number
  advice: string
}

export function securityPosture(input: {
  ssoEnabled: boolean
  controls: Pick<SecurityControls, "requireTwoFactor" | "ipAllowlist" | "sessionTimeout"> | null | undefined
}): Posture {
  const tfa = Boolean(input.controls?.requireTwoFactor)
  const ip = Boolean(input.controls?.ipAllowlist.enabled && input.controls.ipAllowlist.ranges.length > 0)
  const timeout = Boolean(input.controls && input.controls.sessionTimeout !== "never")
  const score = [input.ssoEnabled, tfa, ip, timeout].filter(Boolean).length
  const advice =
    score >= 4
      ? "Every control is on. Nice work."
      : !tfa
        ? "Turning on two factor authentication is the quickest win for this workspace."
        : !input.ssoEnabled
          ? "Connect single sign on so access follows your identity provider."
          : !ip
            ? "Add an IP allowlist to limit where people can sign in from."
            : "Set a session timeout so idle sessions sign out."
  return { score, advice }
}
