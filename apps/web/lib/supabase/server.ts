import { createClient, type SupabaseClient } from "@supabase/supabase-js"
import type { NextRequest } from "next/server"

import { getSupabaseDataUrl, getSupabaseServiceUrl } from "@/lib/supabase/url"

function getSupabaseAnonKey() {
  const value = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY
  if (!value) {
    throw new Error("NEXT_PUBLIC_SUPABASE_ANON_KEY is not configured")
  }
  return value
}

function getSupabaseServiceRoleKey() {
  const value = process.env.SUPABASE_SERVICE_ROLE_KEY?.trim()
  return value || null
}

/**
 * Local development only: lets a route handler without a bearer token run with
 * the service role key, as it used to. Never set this in a deployed environment;
 * the service role bypasses row level security, so any anonymous caller naming
 * an org id would read and write that org's rows.
 */
function unauthenticatedServiceRoleAllowed() {
  if (process.env.NODE_ENV === "production") return false
  return process.env.GRAVITRE_DEV_UNAUTHENTICATED_SERVICE_ROLE === "1"
}

export function getRouteClientAuthMode(request: NextRequest) {
  const authHeaderPresent = Boolean(request.headers.get("authorization"))
  const serviceRoleAvailable = Boolean(getSupabaseServiceRoleKey())
  const usingServiceRole =
    !authHeaderPresent && serviceRoleAvailable && unauthenticatedServiceRoleAllowed()
  const usingAnonKey = !usingServiceRole
  return {
    authHeaderPresent,
    serviceRoleAvailable,
    usingServiceRole,
    usingAnonKey,
  }
}

/**
 * Supabase client for a route handler, acting as the caller.
 *
 * With a bearer token the client uses the anon key plus that token, so row level
 * security scopes every query to the caller's orgs. Without one it uses the anon
 * key alone, which RLS gives no org rows. It never falls back to the service
 * role key: that bypasses RLS, and route handlers take the org id from the
 * caller (query string or x-org-id header), so a fallback would let anyone read
 * or write any org they can name.
 */
export function createSupabaseRouteClient(request: NextRequest): SupabaseClient {
  const authHeader = request.headers.get("authorization")
  const serviceRoleKey = getSupabaseServiceRoleKey()
  const useServiceRole = !authHeader && Boolean(serviceRoleKey) && unauthenticatedServiceRoleAllowed()
  const accessKey = useServiceRole && serviceRoleKey ? serviceRoleKey : getSupabaseAnonKey()
  // Data plane must hit the project host. Branded getSupabasePublicUrl() only
  // proxies /auth/v1 on gravitre.app — /rest/v1 is not rewritten, so using it
  // here breaks org resolution + table queries (e.g. /api/workflows → 403).
  return createClient(getSupabaseDataUrl(), accessKey, {
    global: {
      headers: authHeader ? { Authorization: authHeader } : {},
    },
    auth: {
      persistSession: false,
      autoRefreshToken: false,
    },
  })
}

export function createSupabaseServiceRoleClient(): SupabaseClient | null {
  const serviceRoleKey = getSupabaseServiceRoleKey()
  if (!serviceRoleKey) return null
  return createClient(getSupabaseServiceUrl(), serviceRoleKey, {
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
    return null
  }

  const { data, error } = await supabase
    .from("organization_members")
    .select("org_id")
    .eq("user_id", userId)
    .limit(1)
    .maybeSingle()

  if (error) {
    console.warn("resolveOrgId membership lookup failed", { userId, message: error.message })
    return null
  }

  return data?.org_id ?? null
}
