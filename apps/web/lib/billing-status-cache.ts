/**
 * Last-known /api/billing/status per user, so the app shell can render on
 * repeat visits instead of holding a full-screen loader for the billing round
 * trip (production p75 ~1.4s) before any page content mounts.
 *
 * The cached value is only a starting point: the shell still revalidates on
 * every load and redirects or shows the expired-trial banner as soon as the
 * fresh status says so. The backend enforces access on its own regardless.
 */
const KEY_PREFIX = "gravitre-billing-status:"
const MAX_AGE_MS = 24 * 60 * 60 * 1000

export function readCachedBillingStatus<T>(userId: string | undefined | null): T | undefined {
  if (!userId || typeof window === "undefined") return undefined
  try {
    const raw = window.localStorage.getItem(KEY_PREFIX + userId)
    if (!raw) return undefined
    const parsed = JSON.parse(raw) as { savedAt?: number; value?: T }
    if (!parsed?.savedAt || Date.now() - parsed.savedAt > MAX_AGE_MS) return undefined
    return parsed.value
  } catch {
    return undefined
  }
}

export function writeCachedBillingStatus(userId: string | undefined | null, value: unknown): void {
  if (!userId || typeof window === "undefined" || value === undefined) return
  try {
    window.localStorage.setItem(KEY_PREFIX + userId, JSON.stringify({ savedAt: Date.now(), value }))
  } catch {
    // Storage full or blocked: the shell just waits for the network as before.
  }
}

export function clearCachedBillingStatus(userId: string | undefined | null): void {
  if (!userId || typeof window === "undefined") return
  try {
    window.localStorage.removeItem(KEY_PREFIX + userId)
  } catch {
    // ignore
  }
}
