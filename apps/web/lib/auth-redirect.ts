/**
 * Generates the OAuth redirect URL that points to the auth callback route.
 * The callback route will handle token exchange and then redirect to the final destination.
 */
const CANONICAL_HOST = "gravitre.app"
const CANONICAL_ORIGIN = `https://${CANONICAL_HOST}`

function safeHost(value: string): string | null {
  try {
    return new URL(value).host.toLowerCase()
  } catch {
    return null
  }
}

function resolveBaseOrigin(configuredBase: string): string {
  const configuredHost = configuredBase ? safeHost(configuredBase) : null

  if (typeof window !== "undefined") {
    const currentOrigin = window.location.origin
    const currentHost = window.location.host.toLowerCase()
    if (currentHost.endsWith(CANONICAL_HOST)) {
      return currentOrigin
    }
    if (configuredBase && configuredHost?.endsWith(CANONICAL_HOST)) {
      return configuredBase.replace(/\/+$/, "")
    }
    if (currentHost.startsWith("localhost")) {
      return currentOrigin
    }
    return CANONICAL_ORIGIN
  }

  if (configuredBase && configuredHost?.endsWith(CANONICAL_HOST)) {
    return configuredBase.replace(/\/+$/, "")
  }
  return CANONICAL_ORIGIN
}

export function getAuthRedirectUrl(finalDestination: string = "/operator"): string | undefined {
  const normalizedDest = finalDestination.startsWith("/") ? finalDestination : `/${finalDestination}`
  const configuredBase = (process.env.NEXT_PUBLIC_APP_URL || "").trim()
  const callbackPath = normalizedDest.startsWith("/auth/callback")
    ? normalizedDest
    : `/auth/callback?next=${encodeURIComponent(normalizedDest)}`
  return `${resolveBaseOrigin(configuredBase)}${callbackPath}`
}
