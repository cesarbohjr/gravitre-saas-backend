import type { Provider } from "@supabase/supabase-js"

import { markAuthTransition } from "@/lib/auth-transition"
import { getAppOrigin } from "@/lib/auth-session"
import { createClient } from "@/lib/supabase/client"

type OAuthResult =
  | { ok: true }
  | { ok: false; error: string }

export async function beginOAuthSignIn(
  provider: Provider,
  redirectPath: string = "/operator",
  isSignup: boolean = false
): Promise<OAuthResult> {
  if (typeof window === "undefined") {
    return {
      ok: false,
      error: "Unable to continue OAuth sign-in in this environment.",
    }
  }

  const normalizedDest = redirectPath.startsWith("/")
    ? redirectPath
    : `/${redirectPath}`
  const typeParam = isSignup ? "&type=signup" : ""
  const origin = getAppOrigin() || window.location.origin
  const redirectTo = `${origin}/auth/callback?next=${encodeURIComponent(normalizedDest)}${typeParam}`

  const supabase = createClient()

  const { error } = await supabase.auth.signInWithOAuth({
    provider,
    options: {
      redirectTo,
      ...(provider === "azure" && {
        scopes: "email profile openid",
      }),
    },
  })

  if (error) {
    return { ok: false, error: error.message }
  }

  markAuthTransition()
  return { ok: true }
}
