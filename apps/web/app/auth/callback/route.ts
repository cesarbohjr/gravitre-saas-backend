import { createServerClient } from "@supabase/ssr"
import { NextResponse } from "next/server"
import type { NextRequest } from "next/server"

function buildRedirectUrl(request: NextRequest, next: string): URL {
  const { origin } = new URL(request.url)
  const forwardedHost = request.headers.get("x-forwarded-host")
  const isLocalEnv = process.env.NODE_ENV === "development"

  if (isLocalEnv) {
    return new URL(next, origin)
  }
  if (forwardedHost) {
    return new URL(next, `https://${forwardedHost}`)
  }
  return new URL(next, origin)
}

function createSupabaseWithResponse(
  request: NextRequest,
  response: NextResponse
) {
  return createServerClient(
    process.env.NEXT_PUBLIC_SUPABASE_URL!,
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
  const next = requestUrl.searchParams.get("next") ?? "/operator"
  const error = requestUrl.searchParams.get("error")
  const errorDescription = requestUrl.searchParams.get("error_description")

  if (error) {
    console.error("OAuth provider error:", error, errorDescription)
    return NextResponse.redirect(
      new URL(
        `/login?error=oauth_error&provider_error=${encodeURIComponent(error)}`,
        requestUrl.origin
      )
    )
  }

  if (code) {
    const redirectUrl = buildRedirectUrl(request, next)
    const response = NextResponse.redirect(redirectUrl)
    const supabase = createSupabaseWithResponse(request, response)

    const { data, error: exchangeError } =
      await supabase.auth.exchangeCodeForSession(code)

    if (exchangeError) {
      console.error("Session exchange error:", exchangeError.message)
      return NextResponse.redirect(
        new URL("/login?error=auth_callback_failed", requestUrl.origin)
      )
    }

    if (data.session) {
      console.log("Session established for:", data.user?.email)
      return response
    }
  }

  if (tokenHash && type) {
    const redirectUrl = buildRedirectUrl(request, next)
    const response = NextResponse.redirect(redirectUrl)
    const supabase = createSupabaseWithResponse(request, response)

    const { error: verifyError } = await supabase.auth.verifyOtp({
      token_hash: tokenHash,
      type: type as "signup" | "invite" | "recovery" | "email" | "email_change",
    })

    if (!verifyError) {
      return response
    }

    console.error("Auth OTP verify error:", verifyError.message)
    return NextResponse.redirect(
      new URL("/login?error=auth_callback_failed", requestUrl.origin)
    )
  }

  if (errorDescription || requestUrl.searchParams.get("error")) {
    return NextResponse.redirect(
      new URL("/login?error=oauth_error", requestUrl.origin)
    )
  }

  // Implicit/hash flow — fragments are not sent to the server.
  return NextResponse.redirect(
    new URL(
      `/auth/callback/complete?next=${encodeURIComponent(next)}`,
      requestUrl.origin
    )
  )
}
