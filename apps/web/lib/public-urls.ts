/** Canonical production URLs (custom domains on Vercel / Railway). */
export const PRODUCTION_APP_URL = "https://gravitre.app"
export const PRODUCTION_API_URL = "https://api.gravitre.app"

const LEGACY_PUBLIC_HOSTS = ["vercel.app", "railway.app", "up.railway.app"]

function isLegacyPlatformHost(url: string): boolean {
  const lowered = url.trim().toLowerCase()
  return LEGACY_PUBLIC_HOSTS.some((host) => lowered.includes(host))
}

export function normalizePublicUrl(url: string | undefined, fallback: string): string {
  const cleaned = (url ?? "").trim().replace(/\/+$/, "")
  if (!cleaned || isLegacyPlatformHost(cleaned)) {
    return fallback.replace(/\/+$/, "")
  }
  return cleaned
}

export function publicAppUrl(): string {
  return normalizePublicUrl(process.env.NEXT_PUBLIC_APP_URL, PRODUCTION_APP_URL)
}

/** Server-side backend base (OAuth proxy routes). Never expose Railway/Vercel defaults to users. */
export function backendBaseUrl(): string {
  const candidates = [
    process.env.FASTAPI_BASE_URL,
    process.env.NEXT_PUBLIC_API_URL,
  ]
  for (const candidate of candidates) {
    const normalized = normalizePublicUrl(candidate, "")
    if (normalized) return normalized
  }
  return PRODUCTION_API_URL
}

export function publicApiUrl(): string {
  return normalizePublicUrl(process.env.NEXT_PUBLIC_API_URL, PRODUCTION_API_URL)
}
