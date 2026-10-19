/**
 * Settings > API keys: /api/settings/api-keys (FastAPI settings_api_keys).
 * The full secret comes back only from create and rotate.
 */
import { fetcher } from "@/lib/fetcher"
import { formatDay } from "@/components/settings/settings-kit"
import { sendJson } from "./security"

export type ApiKeyScope = "read" | "read_write" | "workflows"
export type ApiKeyExpiry = "30d" | "90d" | "1y" | "never"

export const API_KEY_SCOPES: Array<{ id: ApiKeyScope; label: string }> = [
  { id: "read", label: "Read only" },
  { id: "read_write", label: "Read and write" },
  { id: "workflows", label: "Workflows only" },
]

export const API_KEY_EXPIRIES: Array<{ id: ApiKeyExpiry; label: string }> = [
  { id: "30d", label: "30 days" },
  { id: "90d", label: "90 days" },
  { id: "1y", label: "1 year" },
  { id: "never", label: "Never" },
]

export interface WorkspaceApiKey {
  id: string
  name: string
  key_prefix: string
  last4?: string | null
  status: "active" | "revoked"
  scope: ApiKeyScope | null
  expires_at: string | null
  expired: boolean
  last_used_at?: string | null
  created_at?: string | null
  /** Only on create and rotate. */
  key?: string
}

export const API_KEYS_KEY = "/api/settings/api-keys"
export const API_REFERENCE_HREF = "/docs/api/authentication"

export const apiKeysApi = {
  list: () => fetcher<{ apiKeys: WorkspaceApiKey[] }>(API_KEYS_KEY),
  create: (input: { name: string; scope: ApiKeyScope; expires_in: ApiKeyExpiry }) =>
    sendJson<{ apiKey: WorkspaceApiKey }>(API_KEYS_KEY, "POST", input),
  rotate: (id: string) => sendJson<{ apiKey: WorkspaceApiKey }>(`${API_KEYS_KEY}/${encodeURIComponent(id)}/rotate`, "POST", {}),
  revoke: (id: string) => sendJson<{ apiKey: WorkspaceApiKey }>(API_KEYS_KEY, "PATCH", { id, status: "revoked" }),
}

export function scopeLabel(scope: ApiKeyScope | null | undefined): string {
  return API_KEY_SCOPES.find((option) => option.id === scope)?.label ?? "Not set"
}

/** "gv_live_AbCd••••••••wxyz" when the last four are known, else prefix plus dots. */
export function maskKey(key: Pick<WorkspaceApiKey, "key_prefix" | "last4">): string {
  return `${key.key_prefix}••••••••${key.last4 ?? ""}`
}

export function expiryLabel(key: Pick<WorkspaceApiKey, "expires_at" | "expired">): string {
  if (!key.expires_at) return "Never"
  const day = formatDay(key.expires_at)
  if (!day) return "Never"
  return key.expired ? `Expired ${day}` : day
}

/** Keys shown in "Your keys": everything not revoked, newest first (the API orders them). */
export function visibleKeys(keys: WorkspaceApiKey[] | undefined): WorkspaceApiKey[] {
  return (keys ?? []).filter((key) => key.status !== "revoked")
}
