import { createClient, type SupabaseClient } from "@supabase/supabase-js"
import type { NextRequest } from "next/server"

const DEMO_ORG_ID = "00000000-0000-0000-0000-000000000001"

function getSupabaseUrl() {
  const value = process.env.NEXT_PUBLIC_SUPABASE_URL ?? process.env.SUPABASE_URL
  if (!value) {
    throw new Error("Supabase URL is not configured")
  }
  return value
}

function getSupabaseAnonKey() {
  const value = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY
  if (!value) {
    throw new Error("NEXT_PUBLIC_SUPABASE_ANON_KEY is not configured")
  }
  return value
}

export function createSupabaseRouteClient(request: NextRequest): SupabaseClient {
  const authHeader = request.headers.get("authorization")
  return createClient(getSupabaseUrl(), getSupabaseAnonKey(), {
    global: {
      headers: authHeader ? { Authorization: authHeader } : {},
    },
    auth: {
      persistSession: false,
      autoRefreshToken: false,
    },
  })
}

export async function resolveOrgId(
  supabase: SupabaseClient,
  request: NextRequest
): Promise<string | null> {
  const queryOrgId = request.nextUrl.searchParams.get("org_id")
  if (queryOrgId) {
    return queryOrgId
  }

  const explicitOrgId = request.headers.get("x-org-id")
  if (explicitOrgId) {
    return explicitOrgId
  }

  const { data: userData } = await supabase.auth.getUser()
  const userId = userData.user?.id
  if (!userId) {
    return DEMO_ORG_ID
  }

  const { data, error } = await supabase
    .from("organization_members")
    .select("org_id")
    .eq("user_id", userId)
    .limit(1)
    .maybeSingle()

  if (error) {
    return DEMO_ORG_ID
  }

  return data?.org_id ?? DEMO_ORG_ID
}
