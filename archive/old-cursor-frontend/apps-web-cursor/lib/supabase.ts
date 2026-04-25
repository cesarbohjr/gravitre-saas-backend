import { createClient as createSupabaseClient } from "@supabase/supabase-js";

/**
 * FE-00: Browser Supabase client for session (token for GET /api/auth/me).
 * Uses NEXT_PUBLIC_* env vars only.
 */
export function createClient() {
  const url = process.env.NEXT_PUBLIC_SUPABASE_URL;
  const anonKey = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY;
  if (!url || !anonKey) {
    throw new Error("Missing NEXT_PUBLIC_SUPABASE_URL or NEXT_PUBLIC_SUPABASE_ANON_KEY");
  }
  return createSupabaseClient(url, anonKey);
}
