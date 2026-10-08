"use client"

import { useEffect, useMemo } from "react"
import useSWR from "swr"
import { fetcher as apiFetcher } from "@/lib/fetcher"
import { useAuth } from "@/lib/auth-context"
import { getQuickOrgId } from "@/lib/org-context"
import { readCachedOrgAdmin, writeCachedOrgAdmin } from "@/lib/org-gate-cache"

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

export interface OrgAdminState {
  /**
   * Server-confirmed admin in this session (never from cache). Gate admin-only
   * *actions* (mutations, admin-only controls) on this. The backend enforces
   * the role regardless.
   */
  isAdmin: boolean
  /**
   * Best current answer, for deciding what to *show* (e.g. admin nav entries
   * and admin sections): the server's answer once it arrives, otherwise the
   * last confirmed answer cached for this user + org. Corrects itself when the
   * fresh answer differs.
   */
  showAdmin: boolean
  /** The server's answer has arrived (a positive from either endpoint, or both settled). */
  confirmed: boolean
  /** Either role request is still in flight (pre-cache semantics). */
  loading: boolean
  /** Nothing is known yet: no server answer and nothing cached for this user + org. */
  pending: boolean
}

/**
 * Org-scoped admin (owner/admin in organization_members) — not Supabase session metadata.
 *
 * Pages render optimistically from `showAdmin` / `pending`: with a cached
 * answer for this user + org they show their layout and admin sections from
 * the first render, and only admin-only controls wait for `isAdmin`.
 */
export function useOrgAdmin(): OrgAdminState {
  const { user, loading: authLoading } = useAuth()
  const userId = user?.id ?? null
  const orgId = typeof window === "undefined" ? null : getQuickOrgId()

  const { data: membership, error: membershipError, isLoading: membershipLoading } = useSWR<LiteMembershipResponse>(
    user ? "/api/settings/lite-membership" : null,
    apiFetcher,
    { revalidateOnFocus: false },
  )
  const { data: meData, error: meError, isLoading: meLoading } = useSWR<AuthMeResponse>(
    user ? "/api/auth/me" : null,
    apiFetcher,
    { revalidateOnFocus: false },
  )

  const cached = useMemo(() => readCachedOrgAdmin(userId, orgId), [userId, orgId])

  const freshPositive =
    membership?.is_admin === true ||
    isAdminRole(meData?.role) ||
    (meData?.organizations ?? []).some((org) => isAdminRole(org.role))
  const membershipSettled = membership !== undefined || membershipError !== undefined
  const meSettled = meData !== undefined || meError !== undefined
  const settled = Boolean(user) && !membershipLoading && !meLoading && membershipSettled && meSettled
  // A positive from either endpoint is authoritative on its own; a negative
  // needs both answers in.
  const confirmed = freshPositive || settled
  const gotAnswer = membership !== undefined || meData !== undefined

  useEffect(() => {
    if (!userId || !confirmed || !gotAnswer) return
    // Only persist real answers — a transient double failure must not flip a
    // cached admin to non-admin.
    writeCachedOrgAdmin(userId, orgId, freshPositive)
  }, [userId, orgId, confirmed, gotAnswer, freshPositive])

  return {
    isAdmin: freshPositive,
    showAdmin: confirmed ? freshPositive : cached === true,
    confirmed,
    loading: authLoading || membershipLoading || meLoading,
    pending: authLoading || (Boolean(user) && !confirmed && cached === undefined),
  }
}
