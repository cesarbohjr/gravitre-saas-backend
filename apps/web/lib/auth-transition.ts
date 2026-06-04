/** Grace period after OAuth/password login before treating API 401 as session expiry. */
const REDIRECTING_KEY = "gravitre_auth_redirecting"
const REDIRECT_UNTIL_KEY = "gravitre_auth_redirect_until"
const LOGIN_REDIRECT_KEY = "gravitre_auth_login_redirect"
const DEFAULT_MS = 20_000

export function markAuthTransition(durationMs: number = DEFAULT_MS): void {
  if (typeof window === "undefined") return
  window.sessionStorage.setItem(REDIRECTING_KEY, "1")
  window.sessionStorage.setItem(
    REDIRECT_UNTIL_KEY,
    String(Date.now() + durationMs),
  )
  window.sessionStorage.removeItem(LOGIN_REDIRECT_KEY)
}

export function clearAuthTransition(): void {
  if (typeof window === "undefined") return
  window.sessionStorage.removeItem(REDIRECTING_KEY)
  window.sessionStorage.removeItem(REDIRECT_UNTIL_KEY)
  window.sessionStorage.removeItem(LOGIN_REDIRECT_KEY)
}

export function isAuthTransitionActive(): boolean {
  if (typeof window === "undefined") return false
  const untilRaw = window.sessionStorage.getItem(REDIRECT_UNTIL_KEY)
  if (untilRaw) {
    const until = Number.parseInt(untilRaw, 10)
    if (!Number.isNaN(until) && Date.now() < until) return true
    if (!Number.isNaN(until) && Date.now() >= until) {
      window.sessionStorage.removeItem(REDIRECTING_KEY)
      window.sessionStorage.removeItem(REDIRECT_UNTIL_KEY)
    }
  }
  return window.sessionStorage.getItem(REDIRECTING_KEY) === "1"
}
