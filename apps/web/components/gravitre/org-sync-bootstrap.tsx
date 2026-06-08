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
    if (user) void ensureSelectedOrg(true)
  }, [user])

  return null
}
