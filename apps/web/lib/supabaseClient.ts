import { createClient } from "@supabase/supabase-js"

const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL
const supabaseAnonKey = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY

const fallbackUrl = "https://placeholder.supabase.co"
const fallbackAnonKey = "placeholder-anon-key"

if ((!supabaseUrl || !supabaseAnonKey) && typeof window !== "undefined") {
  console.warn("Supabase public env vars are missing; auth will not work until configured.")
}

export const supabaseClient = createClient(supabaseUrl ?? fallbackUrl, supabaseAnonKey ?? fallbackAnonKey, {
  auth: {
    persistSession: true,
    autoRefreshToken: true,
    detectSessionInUrl: true,
  },
})
