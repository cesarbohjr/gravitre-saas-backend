import { createBrowserClient } from "@supabase/ssr"

const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL
const supabaseAnonKey = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY
export const hasSupabasePublicEnv = Boolean(supabaseUrl && supabaseAnonKey)

const fallbackUrl = "https://placeholder.supabase.co"
const fallbackAnonKey = "placeholder-anon-key"

if (!hasSupabasePublicEnv && typeof window !== "undefined") {
  console.warn("Supabase public env vars are missing; auth will not work until configured.")
}

export function createClient() {
  return createBrowserClient(
    supabaseUrl ?? fallbackUrl,
    supabaseAnonKey ?? fallbackAnonKey
  )
}

export const supabaseClient = createClient()
