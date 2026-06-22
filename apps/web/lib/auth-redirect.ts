import { publicAppUrl } from "@/lib/public-urls"

/**
 * Generates the OAuth redirect URL that points to the auth callback route.
 * The callback route will handle token exchange and then redirect to the final destination.
 *
 * @param finalDestination - Where to redirect after successful auth (default: /operator)
 * @param isSignup - Whether this is a signup flow (affects error fallback destination)
 */
export function getAuthRedirectUrl(finalDestination: string = "/operator", isSignup: boolean = false): string | undefined {
  const normalizedDest = finalDestination.startsWith("/") ? finalDestination : `/${finalDestination}`
  const configuredBase = publicAppUrl()

  // Always redirect to /auth/callback, passing the final destination as a query param
  // Include type=signup for signup flows so error fallback goes to /get-started not /login
  const typeParam = isSignup ? "&type=signup" : ""
  const callbackPath = `/auth/callback?next=${encodeURIComponent(normalizedDest)}${typeParam}`

  if (configuredBase) {
    return `${configuredBase.replace(/\/+$/, "")}${callbackPath}`
  }

  if (typeof window !== "undefined") {
    return `${window.location.origin}${callbackPath}`
  }

  return undefined
}
