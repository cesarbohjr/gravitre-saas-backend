"use client"

import { useEffect } from "react"
import { useAuth } from "@/lib/auth-context"
import { ensureSelectedOrg, purgeStaleDemoOrgFromStorage } from "@/lib/org-context"

/** Sync org from memberships on sign-in; clears stale demo org ids automatically. */
export function OrgSyncBootstrap() {
  const { user } = useAuth()

  useEffect(() => {
    purgeStaleDemoOrgFromStorage()
  }, [])

  useEffect(() => {
    if (!user) return
    // Force-resolve on every signed-in session so a stale gravitre:selectedOrg
    // (left after leave/switch/account change) cannot race first org-scoped fetches.
    void ensureSelectedOrg(true)
  }, [user])

  return null
}
