import { createServerClient } from "@supabase/ssr"
import { cookies } from "next/headers"
import { NextResponse } from "next/server"
import type { NextRequest } from "next/server"

export async function GET(request: NextRequest) {
  const requestUrl = new URL(request.url)
  const code = requestUrl.searchParams.get("code")
  const next = requestUrl.searchParams.get("next") ?? "/dashboard"
  const type = requestUrl.searchParams.get("type") // 'signup', 'recovery', 'invite', etc.
  const error = requestUrl.searchParams.get("error")
  const errorDescription = requestUrl.searchParams.get("error_description")

  // Handle OAuth/email errors from Supabase
  if (error) {
    console.error("[v0] Auth callback error:", error, errorDescription)
    return NextResponse.redirect(
      new URL(`/login?error=${encodeURIComponent(error)}`, requestUrl.origin)
    )
  }

  if (code) {
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
              // Ignore errors in Server Components
            }
          },
        },
      }
    )

    const { error: exchangeError } = await supabase.auth.exchangeCodeForSession(code)

    if (!exchangeError) {
      // Get user to check if they need onboarding
      const { data: { user } } = await supabase.auth.getUser()
      
      // For new signups or users without metadata, redirect to onboarding
      if (type === "signup" || (user && !user.user_metadata?.onboarded)) {
        return NextResponse.redirect(new URL("/onboarding", requestUrl.origin))
      }
      
      // Otherwise redirect to the specified next URL or dashboard
      return NextResponse.redirect(new URL(next, requestUrl.origin))
    }

    console.error("[v0] Code exchange error:", exchangeError.message)
  }

  // Auth error - redirect to login with error
  return NextResponse.redirect(
    new URL("/login?error=auth_callback_error", requestUrl.origin)
  )
}
