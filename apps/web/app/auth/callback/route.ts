import { createServerClient } from "@supabase/ssr"
import { cookies } from "next/headers"
import { NextResponse } from "next/server"
import type { NextRequest } from "next/server"

export async function GET(request: NextRequest) {
  const requestUrl = new URL(request.url)
  const code = requestUrl.searchParams.get("code")
  const tokenHash = requestUrl.searchParams.get("token_hash")
  const type = requestUrl.searchParams.get("type")
  const next = requestUrl.searchParams.get("next") ?? "/operator"

  const cookieStore = await cookies()
  const supabase = createServerClient(
    process.env.NEXT_PUBLIC_SUPABASE_URL!,
    process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!,
    {
      cookies: {
        getAll() {
          return cookieStore.getAll()
        },
        setAll(cookiesToSet) {
          try {
            cookiesToSet.forEach(({ name, value, options }) =>
              cookieStore.set(name, value, options)
            )
          } catch {
            // Server component — cookies set by middleware
          }
        },
      },
    }
  )

  if (code) {
    const { error } = await supabase.auth.exchangeCodeForSession(code)

    if (!error) {
      return NextResponse.redirect(new URL(next, requestUrl.origin))
    }

    console.error("Auth callback error:", error.message)
    return NextResponse.redirect(
      new URL("/login?error=auth_callback_failed", requestUrl.origin)
    )
  }

  if (tokenHash && type) {
    const { error } = await supabase.auth.verifyOtp({
      token_hash: tokenHash,
      type: type as "signup" | "invite" | "recovery" | "email" | "email_change",
    })

    if (!error) {
      return NextResponse.redirect(new URL(next, requestUrl.origin))
    }

    console.error("Auth OTP verify error:", error.message)
    return NextResponse.redirect(
      new URL("/login?error=auth_callback_failed", requestUrl.origin)
    )
  }

  // Implicit/hash flow requires a client page (fragments are not sent to the server).
  const urlError =
    requestUrl.searchParams.get("error_description") ||
    requestUrl.searchParams.get("error")
  if (urlError) {
    return NextResponse.redirect(
      new URL("/login?error=oauth_error", requestUrl.origin)
    )
  }

  return NextResponse.redirect(
    new URL("/auth/callback/complete", requestUrl.origin)
  )
}
