import { createServerClient } from "@supabase/ssr"
import { NextResponse } from "next/server"
import type { NextRequest } from "next/server"

import { APP_ROUTES } from "@/lib/app-routes"
import {
  clearSupabaseAuthCookiesFromRequest,
  getAppOrigin,
} from "@/lib/auth-session"
import { getSupabasePublicUrl } from "@/lib/supabase/url"

function buildRedirectUrl(request: NextRequest, next: string): URL {
  const origin = getAppOrigin(request) || new URL(request.url).origin
  return new URL(next.startsWith("/") ? next : `/${next}`, origin)
}

function loginRedirect(
  request: NextRequest,
  error: string,
  extra?: Record<string, string>
): NextResponse {
  const origin = getAppOrigin(request) || new URL(request.url).origin
  const url = new URL("/login", origin)
  url.searchParams.set("error", error)
  if (extra) {
    for (const [key, value] of Object.entries(extra)) {
      url.searchParams.set(key, value)
    }
  }
  const response = NextResponse.redirect(url)
  clearSupabaseAuthCookiesFromRequest(request, response)
  return response
}

function createSupabaseWithResponse(
  request: NextRequest,
  response: NextResponse
) {
  return createServerClient(
    getSupabasePublicUrl(),
    process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!,
    {
      cookies: {
        getAll() {
          return request.cookies.getAll()
        },
        setAll(cookiesToSet) {
          cookiesToSet.forEach(({ name, value, options }) =>
            response.cookies.set(name, value, options)
          )
        },
      },
    }
  )
}

export async function GET(request: NextRequest) {
  const requestUrl = new URL(request.url)
  const code = requestUrl.searchParams.get("code")
  const tokenHash = requestUrl.searchParams.get("token_hash")
  const type = requestUrl.searchParams.get("type")
  const next = requestUrl.searchParams.get("next") ?? APP_ROUTES.welcome
  const error = requestUrl.searchParams.get("error")
  const errorDescription = requestUrl.searchParams.get("error_description")

  if (error) {
    console.error("OAuth provider error:", error, errorDescription)
    return loginRedirect(request, "oauth_error", {
      provider_error: error,
    })
  }

  if (code) {
    const redirectUrl = buildRedirectUrl(request, next)
    const response = NextResponse.redirect(redirectUrl)
    const supabase = createSupabaseWithResponse(request, response)

    const { data, error: exchangeError } =
      await supabase.auth.exchangeCodeForSession(code)

    if (exchangeError) {
      console.error("Session exchange error:", exchangeError.message)
      return loginRedirect(request, "auth_callback_failed")
    }

    if (data.session) {
      return response
    }
  }

  if (tokenHash && type) {
    const redirectUrl = buildRedirectUrl(request, next)
    const response = NextResponse.redirect(redirectUrl)
    const supabase = createSupabaseWithResponse(request, response)

    const { error: verifyError } = await supabase.auth.verifyOtp({
      token_hash: tokenHash,
      // magiclink is the admin generate_link / email OTP type used by smoke session mint.
      type: type as
        | "signup"
        | "invite"
        | "recovery"
        | "email"
        | "magiclink"
        | "email_change",
    })

    if (!verifyError) {
      return response
    }

    console.error("Auth OTP verify error:", verifyError.message)
    return loginRedirect(request, "auth_callback_failed")
  }

  if (errorDescription || requestUrl.searchParams.get("error")) {
    return loginRedirect(request, "oauth_error")
  }

  // Implicit/hash flow — fragments are not sent to the server. A 302 to
  // /auth/callback/complete would drop location.hash and leave the browser on
  // /login with no session (confirmed 2026-09-21: magic-link → /ai → /login,
  // hasSession=false). Return a tiny HTML handoff that preserves the hash.
  const completePath = `/auth/callback/complete?next=${encodeURIComponent(next)}`
  const safeCompletePath = completePath.replace(/[^a-zA-Z0-9\-._~:/?#[\]@!$&'()*+,;=%]/g, "")
  const html = `<!DOCTYPE html><html lang="en"><head><meta charset="utf-8"/><title>Finishing sign in</title></head><body><p>Finishing sign in…</p><script>location.replace(${JSON.stringify(safeCompletePath)}+location.hash)</script></body></html>`
  return new NextResponse(html, {
    status: 200,
    headers: {
      "content-type": "text/html; charset=utf-8",
      "cache-control": "no-store",
    },
  })
}
