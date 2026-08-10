export type DesktopSession = {
  accessToken: string
  orgId: string
  environment: string
  apiBase: string
  appBase: string
}

const KEY = "gravitre.desktop.session"

export function loadSession(): DesktopSession | null {
  try {
    const raw = localStorage.getItem(KEY)
    if (!raw) return null
    const parsed = JSON.parse(raw) as DesktopSession
    if (!parsed.accessToken || !parsed.orgId || !parsed.apiBase) return null
    return parsed
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

export function parseAuthDeepLink(url: string): DesktopSession | null {
  try {
    const parsed = new URL(url)
    if (parsed.protocol !== "gravitre:") return null
    const host = parsed.hostname || parsed.pathname.replace(/^\/*/, "").split("/")[0]
    if (host !== "auth") return null
    const accessToken = parsed.searchParams.get("access_token") || ""
    const orgId = parsed.searchParams.get("org_id") || ""
    const environment = parsed.searchParams.get("environment") || "production"
    const apiBase = parsed.searchParams.get("api_base") || "https://api.gravitre.app"
    const appBase = parsed.searchParams.get("app_base") || "https://gravitre.app"
    if (!accessToken || !orgId) return null
    return { accessToken, orgId, environment, apiBase, appBase }
  } catch {
    return null
  }
}
