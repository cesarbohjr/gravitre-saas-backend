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

    if (currentHost.endsWith(CANONICAL_HOST) || currentHost.startsWith("localhost")) {
      return currentOrigin
    }
    if (configuredHost?.endsWith(CANONICAL_HOST)) {
      return configuredBase.replace(/\/+$/, "")
    }
    return CANONICAL_ORIGIN
  }

  if (configuredHost?.endsWith(CANONICAL_HOST)) {
    return configuredBase.replace(/\/+$/, "")
  }
  return CANONICAL_ORIGIN
}

/**
 * Generates the OAuth/email redirect URL to the auth callback route.
 * The callback route will complete auth and then route to finalDestination.
 */
export function getAuthRedirectUrl(
  finalDestination: string = "/operator",
  isSignup: boolean = false,
): string {
  const normalizedDest = finalDestination.startsWith("/") ? finalDestination : `/${finalDestination}`
  const configuredBase = (process.env.NEXT_PUBLIC_APP_URL || "").trim()
  const callbackPath = normalizedDest.startsWith("/auth/callback")
    ? normalizedDest
    : `/auth/callback?next=${encodeURIComponent(normalizedDest)}`

  if (!isSignup || callbackPath.includes("type=signup")) {
    return `${resolveBaseOrigin(configuredBase)}${callbackPath}`
  }

  const separator = callbackPath.includes("?") ? "&" : "?"
  return `${resolveBaseOrigin(configuredBase)}${callbackPath}${separator}type=signup`
}
