import { PRODUCTION_SUPABASE_AUTH_URL, publicAppUrl } from "@/lib/public-urls"

const SUPABASE_HOST_SUFFIX = ".supabase.co"

function trimUrl(url: string | undefined): string {
  return (url ?? "").trim().replace(/[\r\n]+/g, "").replace(/\/+$/, "")
}

function isInternalSupabaseHost(url: string): boolean {
  return url.toLowerCase().includes(SUPABASE_HOST_SUFFIX)
}

/**
 * Public Supabase Auth/API base URL exposed to browsers.
 * Never returns the raw *.supabase.co project URL in production when a branded
 * URL is configured (custom domain or same-origin /auth/v1 proxy on gravitre.app).
 */
export function getSupabasePublicUrl(): string {
  const authUrl = trimUrl(process.env.NEXT_PUBLIC_SUPABASE_AUTH_URL)
  if (authUrl && !isInternalSupabaseHost(authUrl)) {
    return authUrl
  }

  const configured = trimUrl(process.env.NEXT_PUBLIC_SUPABASE_URL)
  if (configured && !isInternalSupabaseHost(configured)) {
    return configured
  }

  if (process.env.NODE_ENV === "production") {
    const branded = trimUrl(PRODUCTION_SUPABASE_AUTH_URL)
    if (branded && !isInternalSupabaseHost(branded)) {
      return branded
    }
    return publicAppUrl()
  }

  return configured || "https://placeholder.supabase.co"
}

/** Server/build-only project URL used to proxy /auth/v1 on gravitre.app. */
export function getSupabaseProjectUrl(): string | undefined {
  const explicit = trimUrl(process.env.SUPABASE_PROJECT_URL)
  if (explicit) return explicit

  const configured = trimUrl(process.env.NEXT_PUBLIC_SUPABASE_URL)
  if (configured && isInternalSupabaseHost(configured)) {
    return configured
  }

  const serverUrl = trimUrl(process.env.SUPABASE_URL)
  if (serverUrl && isInternalSupabaseHost(serverUrl)) {
    return serverUrl
  }

  return undefined
}

/** Server-side Supabase URL for service-role REST (direct project host). */
export function getSupabaseServiceUrl(): string {
  const project = getSupabaseProjectUrl()
  if (project) return project

  const configured = trimUrl(process.env.NEXT_PUBLIC_SUPABASE_URL)
  if (configured) return configured

  throw new Error("Supabase project URL is not configured")
}

/** Strip internal Supabase hosts from user-visible error text. */
export function sanitizeAuthErrorMessage(message: string | undefined | null): string {
  const text = (message ?? "").trim()
  if (!text) return ""
  return text
    .replace(/https?:\/\/[a-z0-9-]+\.supabase\.co/gi, "Gravitre")
    .replace(/\b[a-z0-9-]+\.supabase\.co\b/gi, "gravitre.app")
}
