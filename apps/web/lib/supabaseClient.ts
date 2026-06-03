import { createClient as createBrowserSupabaseClient } from "@/lib/supabase/client"

const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL
const supabaseAnonKey = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY
export const hasSupabasePublicEnv = Boolean(supabaseUrl && supabaseAnonKey)

if (!hasSupabasePublicEnv && typeof window !== "undefined") {
  console.warn("Supabase public env vars are missing; auth will not work until configured.")
}

export function createClient() {
  return createBrowserSupabaseClient()
}

export const supabaseClient = createClient()
