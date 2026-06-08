export const DEFAULT_DEMO_ORG_ID = "00000000-0000-0000-0000-000000000001"
export const SECONDARY_DEMO_ORG_ID = "11111111-1111-4111-8111-111111111111"

export const ORG_STORAGE_KEY = "gravitre:selectedOrg"

export interface SelectedOrg {
  id: string
  name: string
}

let cachedOrgId: string | null | undefined

/** Remove demo org ids left by older builds — they cause assistant chat 403s. */
export function purgeStaleDemoOrgFromStorage(): boolean {
  if (typeof window === "undefined") return false
  const stored = getSelectedOrgFromStorage()
  if (
    stored?.id === DEFAULT_DEMO_ORG_ID ||
    stored?.id === SECONDARY_DEMO_ORG_ID
  ) {
    window.localStorage.removeItem(ORG_STORAGE_KEY)
    cachedOrgId = undefined
    return true
  }
  return false
}

// Purge immediately when this module loads in the browser (before React mounts).
if (typeof window !== "undefined") {
  purgeStaleDemoOrgFromStorage()
}

export function invalidateOrgCache() {
  cachedOrgId = undefined
}

export function getSelectedOrgFromStorage(): SelectedOrg | null {
  if (typeof window === "undefined") return null
  const raw = window.localStorage.getItem(ORG_STORAGE_KEY)
  if (!raw) return null
  try {
    const parsed = JSON.parse(raw) as Partial<SelectedOrg>
    if (!parsed.id || !parsed.name) return null
    return { id: parsed.id, name: parsed.name }
  } catch {
    return null
  }
}

export function setSelectedOrgInStorage(org: SelectedOrg) {
  if (typeof window === "undefined") return
  window.localStorage.setItem(ORG_STORAGE_KEY, JSON.stringify(org))
  cachedOrgId = org.id
}

let syncInFlight: Promise<string | null> | null = null

/**
 * Resolve org id from the user's memberships (authoritative).
 * Replaces stale demo-org entries in localStorage that cause chat 403s.
 */
export async function ensureSelectedOrg(force = false): Promise<string | null> {
  if (typeof window === "undefined") return null
  if (!force && cachedOrgId !== undefined) return cachedOrgId
  if (!force && syncInFlight) return syncInFlight

  syncInFlight = (async () => {
    try {
      const { organizationsApi } = await import("@/lib/api")
      const { organizations } = await organizationsApi.list()
      const rows = organizations ?? []
      const membershipIds = new Set(rows.map((org) => org.id))

      if (membershipIds.size === 0) {
        window.localStorage.removeItem(ORG_STORAGE_KEY)
        cachedOrgId = null
        return null
      }

      const stored = getSelectedOrgFromStorage()
      if (stored?.id && membershipIds.has(stored.id)) {
        cachedOrgId = stored.id
        return stored.id
      }

      const first = rows[0]
      if (first?.id && first?.name) {
        setSelectedOrgInStorage({ id: first.id, name: first.name })
        cachedOrgId = first.id
        return first.id
      }

      cachedOrgId = null
      return null
    } catch {
      purgeStaleDemoOrgFromStorage()
      cachedOrgId = null
      return null
    } finally {
      syncInFlight = null
    }
  })()

  return syncInFlight
}

/** Chat requests must not send a stale body org_id — backend resolves org from JWT. */
export function buildChatOrgPayload(): Record<string, never> {
  return {}
}
