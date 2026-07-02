import { createClient, type SupabaseClient } from "@supabase/supabase-js"
import type { NextRequest } from "next/server"

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

function getSupabaseServiceRoleKey() {
  const value = process.env.SUPABASE_SERVICE_ROLE_KEY?.trim()
  return value || null
}

export function getRouteClientAuthMode(request: NextRequest) {
  const authHeaderPresent = Boolean(request.headers.get("authorization"))
  const serviceRoleAvailable = Boolean(getSupabaseServiceRoleKey())
  const usingServiceRole = !authHeaderPresent && serviceRoleAvailable
  const usingAnonKey = authHeaderPresent || !serviceRoleAvailable
  return {
    authHeaderPresent,
    serviceRoleAvailable,
    usingServiceRole,
    usingAnonKey,
  }
}

export function createSupabaseRouteClient(request: NextRequest): SupabaseClient {
  const authHeader = request.headers.get("authorization")
  const serviceRoleKey = getSupabaseServiceRoleKey()
  const accessKey = authHeader ? getSupabaseAnonKey() : (serviceRoleKey ?? getSupabaseAnonKey())
  return createClient(getSupabaseUrl(), accessKey, {
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
  return createClient(getSupabaseUrl(), serviceRoleKey, {
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
