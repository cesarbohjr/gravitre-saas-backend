export type DesktopSession = {
  accessToken: string
  /** Renews the session through /api/auth/companion-refresh. Empty for sessions from older web builds. */
  refreshToken: string
  /** Unix seconds; null when the web page did not say. */
  expiresAt: number | null
  orgId: string
  environment: string
  apiBase: string
  appBase: string
}

const KEY = "gravitre.desktop.session"
const PENDING_KEY = "gravitre.desktop.signin"
/** A sign-in started here is only accepted for this long; the screen says it timed out after that. */
export const PENDING_TTL_MS = 5 * 60 * 1000

const API_HOSTS = [/^gravitre\.app$/, /\.gravitre\.app$/, /\.up\.railway\.app$/, /^localhost$/, /^127\.0\.0\.1$/]

export function loadSession(): DesktopSession | null {
  try {
    const raw = localStorage.getItem(KEY)
    if (!raw) return null
    const parsed = JSON.parse(raw) as Partial<DesktopSession>
    if (!parsed.accessToken || !parsed.orgId || !parsed.apiBase) return null
    return {
      accessToken: parsed.accessToken,
      refreshToken: parsed.refreshToken || "",
      expiresAt: typeof parsed.expiresAt === "number" ? parsed.expiresAt : null,
      orgId: parsed.orgId,
      environment: parsed.environment || "production",
      apiBase: parsed.apiBase,
      appBase: parsed.appBase || "https://gravitre.app",
    }
  } catch {
    return null
  }
}

export function saveSession(session: DesktopSession) {
  localStorage.setItem(KEY, JSON.stringify(session))
}

export function clearSession() {
  localStorage.removeItem(KEY)
}

/** Six characters people can read aloud: no 0/O or 1/I. */
export function newSignInCode(): string {
  const alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
  const bytes = new Uint8Array(6)
  crypto.getRandomValues(bytes)
  return Array.from(bytes, (b) => alphabet[b % alphabet.length]).join("")
}

export function savePendingSignIn(code: string) {
  localStorage.setItem(PENDING_KEY, JSON.stringify({ code, startedAt: Date.now() }))
}

export type PendingSignIn = { code: string; startedAt: number; expired: boolean }

/** The sign-in this computer started; `expired` once the browser hasn't answered in time. */
export function loadPendingSignIn(): PendingSignIn | null {
  try {
    const raw = localStorage.getItem(PENDING_KEY)
    if (!raw) return null
    const parsed = JSON.parse(raw) as { code?: string; startedAt?: number }
    if (!parsed.code || !parsed.startedAt) return null
    return { code: parsed.code, startedAt: parsed.startedAt, expired: Date.now() - parsed.startedAt > PENDING_TTL_MS }
  } catch {
    return null
  }
}

export function clearPendingSignIn() {
  localStorage.removeItem(PENDING_KEY)
}

export function formatCode(code: string): string {
  return code.length === 6 ? `${code.slice(0, 3)} ${code.slice(3)}` : code
}

function allowedBase(value: string, fallback: string): string {
  try {
    const url = new URL(value)
    const local = url.hostname === "localhost" || url.hostname === "127.0.0.1"
    if (url.protocol !== "https:" && !local) return fallback
    if (!API_HOSTS.some((re) => re.test(url.hostname))) return fallback
    return url.origin
  } catch {
    return fallback
  }
}

export type AuthDeepLink = { session: DesktopSession; code: string }

/**
 * gravitre://auth?access_token&refresh_token&expires_at&org_id&code&api_base&app_base
 * The caller must check `code` against the sign-in it started.
 */
export function parseAuthDeepLink(url: string): AuthDeepLink | null {
  try {
    const parsed = new URL(url)
    if (parsed.protocol !== "gravitre:") return null
    const host = parsed.hostname || parsed.pathname.replace(/^\/*/, "").split("/")[0]
    if (host !== "auth") return null
    const q = parsed.searchParams
    const accessToken = q.get("access_token") || ""
    const orgId = q.get("org_id") || ""
    if (!accessToken || !orgId) return null
    const expiresAt = Number(q.get("expires_at"))
    return {
      code: (q.get("code") || "").toUpperCase().replace(/\s+/g, ""),
      session: {
        accessToken,
        refreshToken: q.get("refresh_token") || "",
        expiresAt: Number.isFinite(expiresAt) && expiresAt > 0 ? expiresAt : null,
        orgId,
        environment: q.get("environment") || "production",
        apiBase: allowedBase(q.get("api_base") || "", "https://gravitre-saas-backend-production.up.railway.app"),
        appBase: allowedBase(q.get("app_base") || "", "https://gravitre.app"),
      },
    }
  } catch {
    return null
  }
}
