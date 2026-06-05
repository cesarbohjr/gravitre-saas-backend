import type { Provider } from "@supabase/supabase-js"

import { getAuthRedirectUrl } from "@/lib/auth-redirect"
import { markAuthTransition } from "@/lib/auth-transition"
import { createClient } from "@/lib/supabase/client"

type OAuthResult =
  | { ok: true }
  | { ok: false; error: string }

function safeDecode(value: string): string {
  try {
    return decodeURIComponent(value)
  } catch {
    return value
  }
}

export async function beginOAuthSignIn(
  provider: Provider,
  redirectPath: string = "/operator",
  isSignup: boolean = false,
): Promise<OAuthResult> {
  const redirectTo = getAuthRedirectUrl(redirectPath, isSignup)
  if (!redirectTo) {
    return {
      ok: false,
      error: "Authentication redirect URL is not configured. Please contact support.",
    }
  }

  const supabase = createClient()
  const { data, error } = await supabase.auth.signInWithOAuth({
    provider,
    options: {
      redirectTo,
      skipBrowserRedirect: true,
      ...(provider === "azure" && {
        scopes: "email profile openid",
      }),
    },
  })

  if (error) {
    return { ok: false, error: error.message }
  }

  if (!data?.url) {
    return {
      ok: false,
      error: "Unable to start OAuth sign-in. Please try again.",
    }
  }

  const expectedOrigin = new URL(redirectTo).origin
  try {
    const oauthUrl = new URL(data.url)
    const redirectParam = oauthUrl.searchParams.get("redirect_to")

    if (redirectParam) {
      const decodedRedirect = safeDecode(redirectParam)
      const actualOrigin = new URL(decodedRedirect).origin
      if (actualOrigin !== expectedOrigin) {
        return {
          ok: false,
          error:
            "OAuth redirect mismatch detected. Verify NEXT_PUBLIC_APP_URL in Vercel and Site URL/Redirect URLs in Supabase Auth settings.",
        }
      }
    }
  } catch {
    return {
      ok: false,
      error: "OAuth URL validation failed. Please try again.",
    }
  }

  if (typeof window === "undefined") {
    return {
      ok: false,
      error: "Unable to continue OAuth sign-in in this environment.",
    }
  }

  markAuthTransition()
  window.location.assign(data.url)
  return { ok: true }
}
