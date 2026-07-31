import { createBrowserClient } from "@supabase/ssr"

import { getSupabasePublicUrl } from "@/lib/supabase/url"

const supabaseAnonKey =
  process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY ?? "placeholder-anon-key"

export function createClient() {
  return createBrowserClient(getSupabasePublicUrl(), supabaseAnonKey)
}
