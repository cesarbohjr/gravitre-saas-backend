import { createServerClient } from "@supabase/ssr"
import { cookies } from "next/headers"

import { getSupabaseServerAuthConfig } from "@/lib/supabase/url"

export async function createSupabaseServerClient() {
  const cookieStore = await cookies()
  // Project host, not the branded same-origin proxy — see getSupabaseServerAuthConfig.
  const { url, cookieName } = getSupabaseServerAuthConfig()

  return createServerClient(
    url,
    process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!,
    {
      ...(cookieName ? { cookieOptions: { name: cookieName } } : {}),
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
            // The `setAll` method was called from a Server Component.
            // This can be ignored if you have middleware refreshing user sessions.
          }
        },
      },
    }
  )
}
