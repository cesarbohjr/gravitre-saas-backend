"use client"

import { useEffect, useState } from "react"
import { AppShell } from "@/components/gravitre/app-shell"
import { HomeDashboard } from "@/components/home/home-dashboard"
import { useAuth } from "@/lib/auth-context"
import { ensureSelectedOrg, getQuickOrgId } from "@/lib/org-context"

export default function HomePage() {
  const { user } = useAuth()
  const [orgId, setOrgId] = useState<string | null>(() => getQuickOrgId())

  useEffect(() => {
    if (user) void ensureSelectedOrg().then(setOrgId)
  }, [user])

  const meta = (user?.user_metadata ?? {}) as Record<string, unknown>
  const userName =
    (typeof meta.full_name === "string" && meta.full_name) ||
    (typeof meta.name === "string" && meta.name) ||
    (user?.email ? user.email.split("@")[0] : null)

  return (
    <AppShell title="Dashboard">
      <HomeDashboard enabled={Boolean(user)} orgId={orgId} userId={user?.id ?? null} userName={userName || null} />
    </AppShell>
  )
}
