/**
 * Generates the OAuth redirect URL that points to the auth callback route.
 * The callback route will handle token exchange and then redirect to the final destination.
 */
export function getAuthRedirectUrl(
  finalDestination: string = "/operator",
  isSignup: boolean = false
): string | undefined {
  const normalizedDest = finalDestination.startsWith("/")
    ? finalDestination
    : `/${finalDestination}`
  const typeParam = isSignup ? "&type=signup" : ""
  const callbackPath = `/auth/callback?next=${encodeURIComponent(normalizedDest)}${typeParam}`

  if (typeof window !== "undefined") {
    return `${window.location.origin}${callbackPath}`
  }

  const configuredBase = (process.env.NEXT_PUBLIC_APP_URL || "").trim()
  if (configuredBase) {
    return `${configuredBase.replace(/\/+$/, "")}${callbackPath}`
  }

  return undefined
}
