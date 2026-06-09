export const DEFAULT_DEMO_ORG_ID = "00000000-0000-0000-0000-000000000001"
export const SECONDARY_DEMO_ORG_ID = "11111111-1111-4111-8111-111111111111"

export const ORG_STORAGE_KEY = "gravitre:selectedOrg"

export interface SelectedOrg {
  id: string
  name: string
}

let cachedOrgId: string | null | undefined

/** Legacy demo org ids — only purge when they are not in the user's membership list. */
export function purgeStaleDemoOrgFromStorage(validMembershipIds?: Set<string>): boolean {
  if (typeof window === "undefined") return false
  const stored = getSelectedOrgFromStorage()
  if (!stored?.id) return false

  const isLegacyDemo =
    stored.id === DEFAULT_DEMO_ORG_ID || stored.id === SECONDARY_DEMO_ORG_ID
  if (!isLegacyDemo) return false

  if (validMembershipIds?.has(stored.id)) {
    return false
  }

  window.localStorage.removeItem(ORG_STORAGE_KEY)
  cachedOrgId = undefined
  return true
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

function pickPreferredOrg(
  rows: Array<{ id: string; name?: string | null }>,
  preferredOrgId?: string | null,
): SelectedOrg | null {
  if (rows.length === 0) return null

  if (preferredOrgId) {
    const match = rows.find((org) => org.id === preferredOrgId)
    if (match?.id) {
      return { id: match.id, name: match.name || "Organization" }
    }
  }

  const nonDemo = rows.find(
    (org) => org.id !== DEFAULT_DEMO_ORG_ID && org.id !== SECONDARY_DEMO_ORG_ID,
  )
  const chosen = nonDemo ?? rows[0]
  if (!chosen?.id) return null
  return { id: chosen.id, name: chosen.name || "Organization" }
}

async function resolveOrgFromAuthMe(): Promise<string | null> {
  try {
    const { authApi } = await import("@/lib/api")
    const me = await authApi.me()
    const orgRows =
      (me as { organizations?: Array<{ id: string; name?: string | null }> }).organizations ?? []
    const preferredOrgId = (me as { org_id?: string | null }).org_id ?? null
    const selected = pickPreferredOrg(orgRows, preferredOrgId)
    if (!selected) return null
    setSelectedOrgInStorage(selected)
    cachedOrgId = selected.id
    return selected.id
  } catch {
    return null
  }
}

let syncInFlight: Promise<string | null> | null = null

/**
 * Resolve org id from the user's memberships (authoritative).
 * Falls back to /api/auth/me when the backend organizations list is unavailable.
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

      purgeStaleDemoOrgFromStorage(membershipIds)

      if (membershipIds.size === 0) {
        const fromMe = await resolveOrgFromAuthMe()
        cachedOrgId = fromMe
        return fromMe
      }

      const stored = getSelectedOrgFromStorage()
      if (stored?.id && membershipIds.has(stored.id)) {
        cachedOrgId = stored.id
        return stored.id
      }

      const first = pickPreferredOrg(rows)
      if (first) {
        setSelectedOrgInStorage(first)
        cachedOrgId = first.id
        return first.id
      }

      cachedOrgId = null
      return null
    } catch {
      const fromMe = await resolveOrgFromAuthMe()
      if (fromMe) {
        cachedOrgId = fromMe
        return fromMe
      }
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
