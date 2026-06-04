import { createServerClient } from "@supabase/ssr"
import { NextResponse, type NextRequest } from "next/server"

import { getAppOrigin, isSupabaseAuthCookie } from "@/lib/auth-session"

export async function updateSession(request: NextRequest) {
  let supabaseResponse = NextResponse.next({ request })

  const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL
  const supabaseAnonKey = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY
  if (!supabaseUrl || !supabaseAnonKey) {
    return { response: supabaseResponse, user: null }
  }

  const supabase = createServerClient(supabaseUrl, supabaseAnonKey, {
    cookies: {
      getAll() {
        return request.cookies.getAll()
      },
      setAll(cookiesToSet) {
        cookiesToSet.forEach(({ name, value }) => request.cookies.set(name, value))
        supabaseResponse = NextResponse.next({ request })
        cookiesToSet.forEach(({ name, value, options }) =>
          supabaseResponse.cookies.set(name, value, options)
        )
      },
    },
  })

  const {
    data: { user },
  } = await supabase.auth.getUser()

  return { response: supabaseResponse, user }
}

export function redirectToLogin(
  request: NextRequest,
  options?: { staleSession?: boolean }
): NextResponse {
  const appOrigin = getAppOrigin(request) || new URL(request.url).origin
  const loginUrl = new URL("/login", appOrigin)
  const hasSupabaseCookie = request.cookies.getAll().some((c) => isSupabaseAuthCookie(c.name))

  if (options?.staleSession && hasSupabaseCookie) {
    loginUrl.searchParams.set("error", "session_expired")
  }

  const redirect = NextResponse.redirect(loginUrl)
  if (hasSupabaseCookie) {
    for (const cookie of request.cookies.getAll()) {
      if (isSupabaseAuthCookie(cookie.name)) {
        redirect.cookies.set(cookie.name, "", { maxAge: 0, path: "/" })
      }
    }
  }
  return redirect
}
