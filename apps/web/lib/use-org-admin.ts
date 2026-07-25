"use client"

import useSWR from "swr"
import { fetcher as apiFetcher } from "@/lib/fetcher"
import { useAuth } from "@/lib/auth-context"

type AuthMeResponse = {
  role?: string
  organizations?: Array<{ id?: string; role?: string }>
}

type LiteMembershipResponse = {
  is_admin?: boolean
}

function isAdminRole(role: string | undefined | null): boolean {
  const normalized = String(role ?? "").trim().toLowerCase()
  return normalized === "admin" || normalized === "owner"
}

/** Org-scoped admin (owner/admin in organization_members) — not Supabase session metadata. */
export function useOrgAdmin() {
  const { user, loading: authLoading } = useAuth()
  const { data: membership, isLoading: membershipLoading } = useSWR<LiteMembershipResponse>(
    user ? "/api/settings/lite-membership" : null,
    apiFetcher,
    { revalidateOnFocus: false },
  )
  const { data: meData, isLoading: meLoading } = useSWR<AuthMeResponse>(
    user ? "/api/auth/me" : null,
    apiFetcher,
    { revalidateOnFocus: false },
  )

  const isAdmin =
    membership?.is_admin === true ||
    isAdminRole(meData?.role) ||
    (meData?.organizations ?? []).some((org) => isAdminRole(org.role))

  return {
    isAdmin,
    loading: authLoading || membershipLoading || meLoading,
  }
}
