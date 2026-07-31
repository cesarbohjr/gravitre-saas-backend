import { createClient as createBrowserSupabaseClient } from "@/lib/supabase/client"

const supabaseAnonKey = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY
export const hasSupabasePublicEnv = Boolean(supabaseAnonKey)

if (!hasSupabasePublicEnv && typeof window !== "undefined") {
  console.warn("Supabase public env vars are missing; auth will not work until configured.")
}

export function createClient() {
  return createBrowserSupabaseClient()
}

export const supabaseClient = createClient()
