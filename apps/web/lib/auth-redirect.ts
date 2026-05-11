/**
 * Generates the OAuth redirect URL that points to the auth callback route.
 * The callback route will handle token exchange and then redirect to the final destination.
 * 
 * @param finalDestination - Where to redirect after successful auth (default: /dashboard)
 */
export function getAuthRedirectUrl(finalDestination: string = "/dashboard"): string | undefined {
  const normalizedDest = finalDestination.startsWith("/") ? finalDestination : `/${finalDestination}`
  const configuredBase = (process.env.NEXT_PUBLIC_APP_URL || "").trim()

  // Always redirect to /auth/callback, passing the final destination as a query param
  const callbackPath = `/auth/callback?next=${encodeURIComponent(normalizedDest)}`

  if (configuredBase) {
    return `${configuredBase.replace(/\/+$/, "")}${callbackPath}`
  }

  if (typeof window !== "undefined") {
    return `${window.location.origin}${callbackPath}`
  }

  return undefined
}
