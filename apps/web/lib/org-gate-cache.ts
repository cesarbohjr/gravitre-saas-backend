/**
 * Last-known results of the org gates (membership resolution and org-admin
 * role), so pages can render their layout and non-admin content on repeat
 * visits instead of holding a spinner for the round trips
 * (/api/settings/lite-membership p75 ~2.6s).
 *
 * A cached value is only a starting point: callers still revalidate on every
 * load and must correct the UI when the fresh answer differs. It never
 * authorises anything — the backend enforces org membership and admin role on
 * every request, and admin-only mutations wait for the confirmed answer.
 *
 * Every access is wrapped: private windows, blocked storage or quota errors
 * fall back to "nothing cached", i.e. the pre-cache behaviour.
 */
const ADMIN_KEY_PREFIX = "gravitre-org-admin:"
const MEMBERSHIP_KEY_PREFIX = "gravitre-org-membership:"
const MAX_AGE_MS = 7 * 24 * 60 * 60 * 1000

type Entry<T> = { savedAt: number; value: T }

function read<T>(key: string): T | undefined {
  if (typeof window === "undefined") return undefined
  try {
    const raw = window.localStorage.getItem(key)
    if (!raw) return undefined
    const parsed = JSON.parse(raw) as Partial<Entry<T>> | null
    if (!parsed || typeof parsed.savedAt !== "number" || Date.now() - parsed.savedAt > MAX_AGE_MS) {
      return undefined
    }
    return parsed.value
  } catch {
    return undefined
  }
}

function write(key: string, value: unknown): void {
  if (typeof window === "undefined") return
  try {
    window.localStorage.setItem(key, JSON.stringify({ savedAt: Date.now(), value }))
  } catch {
    // Storage full or blocked: callers simply wait for the network next time.
  }
}

function remove(key: string): void {
  if (typeof window === "undefined") return
  try {
    window.localStorage.removeItem(key)
  } catch {
    // ignore
  }
}

function adminKey(userId: string, orgId: string | null | undefined): string {
  return `${ADMIN_KEY_PREFIX}${userId}:${orgId || "default"}`
}

/** Last confirmed org-admin answer for this user in this org, if any. */
export function readCachedOrgAdmin(
  userId: string | null | undefined,
  orgId: string | null | undefined,
): boolean | undefined {
  if (!userId) return undefined
  const value = read<unknown>(adminKey(userId, orgId))
  return typeof value === "boolean" ? value : undefined
}

export function writeCachedOrgAdmin(
  userId: string | null | undefined,
  orgId: string | null | undefined,
  isAdmin: boolean,
): void {
  if (!userId) return
  write(adminKey(userId, orgId), isAdmin)
}

export function clearCachedOrgAdmin(userId: string | null | undefined, orgId: string | null | undefined): void {
  if (!userId) return
  remove(adminKey(userId, orgId))
}

/** Org id last confirmed (by membership resolution) for this user, if any. */
export function readCachedOrgMembership(userId: string | null | undefined): string | null | undefined {
  if (!userId) return undefined
  const value = read<unknown>(MEMBERSHIP_KEY_PREFIX + userId)
  return typeof value === "string" || value === null ? value : undefined
}

export function writeCachedOrgMembership(userId: string | null | undefined, orgId: string | null): void {
  if (!userId) return
  write(MEMBERSHIP_KEY_PREFIX + userId, orgId)
}
