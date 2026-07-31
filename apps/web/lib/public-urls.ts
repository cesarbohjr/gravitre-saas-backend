/** Canonical production URLs (custom domains on Vercel / Railway). */
export const PRODUCTION_APP_URL = "https://gravitre.app"
export const PRODUCTION_API_URL = "https://api.gravitre.app"
/** Optional Supabase Auth custom domain — only use after DNS + Supabase activate (see AUTH_OAUTH_RUNBOOK). */
export const PRODUCTION_SUPABASE_AUTH_URL = "https://auth.gravitre.app"
/** Server-side proxy target until api.gravitre.app DNS points at Railway. */
export const PRODUCTION_BACKEND_URL =
  "https://gravitre-saas-backend-production.up.railway.app"

const LEGACY_PUBLIC_HOSTS = ["vercel.app", "railway.app", "up.railway.app"]

function trimUrl(url: string | undefined): string {
  return (url ?? "").trim().replace(/[\r\n]+/g, "").replace(/\/+$/, "")
}

function isLegacyPlatformHost(url: string): boolean {
  const lowered = url.trim().toLowerCase()
  return LEGACY_PUBLIC_HOSTS.some((host) => lowered.includes(host))
}

export function normalizePublicUrl(url: string | undefined, fallback: string): string {
  const cleaned = trimUrl(url)
  if (!cleaned || isLegacyPlatformHost(cleaned)) {
    return trimUrl(fallback)
  }
  return cleaned
}

export function publicAppUrl(): string {
  return normalizePublicUrl(process.env.NEXT_PUBLIC_APP_URL, PRODUCTION_APP_URL)
}

/** Server-side backend base for /api rewrites and OAuth proxy routes — must be reachable. */
export function backendBaseUrl(): string {
  const raw = trimUrl(process.env.FASTAPI_BASE_URL)
  if (!raw || raw.includes("api.gravitre.app")) {
    return PRODUCTION_BACKEND_URL
  }
  return raw
}

/** User-visible API base (webhooks, docs) — routed through the app domain until api.gravitre.app is live. */
export function publicApiUrl(): string {
  const explicit = trimUrl(process.env.NEXT_PUBLIC_API_URL)
  if (explicit && !isLegacyPlatformHost(explicit) && !explicit.includes("api.gravitre.app")) {
    return explicit
  }
  return `${publicAppUrl()}/api`
}
