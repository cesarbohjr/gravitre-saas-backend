"use client"

import { useState } from "react"
import Link from "next/link"
import useSWR from "swr"
import { motion } from "framer-motion"
import { AppShell } from "@/components/gravitre/app-shell"
import { SettingsShell } from "@/components/settings/settings-shell"
import { GlowOrb } from "@/components/gravitre/premium-effects"
import { Button } from "@/components/ui/button"
import { Shield, Check, X, Users } from "lucide-react"
import { AdaptiveDataView } from "@/components/gravitre/adaptive-data-view"
import { Skeleton } from "@/components/ui/skeleton"
import { fetcher } from "@/lib/fetcher"
import { useOrgAdmin } from "@/lib/use-org-admin"
import { useSettingsSectionNav } from "@/lib/settings-nav"
import type { OrgRolePermissionsMatrix } from "@/lib/api"

function Cell({ allowed }: { allowed: boolean }) {
  return allowed ? (
    <Check className="mx-auto h-4 w-4 text-success" aria-label="Allowed" />
  ) : (
    <X className="mx-auto h-4 w-4 text-muted-foreground/40" aria-label="Not allowed" />
  )
}

function roleLabel(role: string): string {
  return role.charAt(0).toUpperCase() + role.slice(1)
}

export default function PermissionsMatrixPage() {
  const { isAdmin, loading: adminLoading } = useOrgAdmin()
  const onSectionChange = useSettingsSectionNav("permissions")
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false)
  const { data, error, isLoading } = useSWR<OrgRolePermissionsMatrix>(
    "/api/org/role-permissions",
    fetcher,
    { revalidateOnFocus: false },
  )

  const roles = data?.roles ?? ["admin", "member", "viewer"]
  const capabilities = data?.capabilities ?? []

  return (
    <AppShell title="Settings">
      <SettingsShell
        activeSection="permissions"
        isAdmin={isAdmin}
        mobileMenuOpen={mobileMenuOpen}
        onMobileMenuOpenChange={setMobileMenuOpen}
        onSectionChange={onSectionChange}
        hideHeader
      >
        <div className="space-y-6 p-4 md:p-6">
          {/* Matches the approvals hero, which previously used a different
              two-hue gradient — sibling settings pages now share one wash. */}
          <div className="relative overflow-hidden rounded-3xl border border-border/60 bg-gradient-to-br from-primary/10 via-card to-primary/5 p-6 md:p-8">
            <div className="pointer-events-none absolute -right-8 -top-10 opacity-60">
              <GlowOrb size={200} color="emerald" intensity={0.22} />
            </div>
            <motion.div
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              className="relative flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between"
            >
              <div className="max-w-xl">
                <div className="mb-3 inline-flex items-center gap-2 rounded-full border border-border/70 bg-background/70 px-3 py-1 text-xs font-medium text-muted-foreground backdrop-blur">
                  <Shield className="h-3.5 w-3.5 text-primary" />
                  Access control
                </div>
                <h1 className="text-2xl font-bold tracking-tight text-foreground md:text-3xl">
                  Role permissions
                </h1>
                <p className="mt-2 text-sm leading-relaxed text-muted-foreground">
                  What each workspace role can access. Loaded from org role definitions on the backend.
                </p>
              </div>
              <div className="rounded-2xl border border-border/70 bg-background/75 px-4 py-3 backdrop-blur">
                <p className="text-[11px] uppercase tracking-wide text-muted-foreground">Roles</p>
                <p className="mt-1 text-2xl font-semibold tabular-nums text-foreground">{roles.length}</p>
              </div>
            </motion.div>
          </div>

          {adminLoading || (isLoading && !data) ? (
            /* Was a centered spinner, which collapsed the layout and then jumped
               when the table arrived. This mirrors the real table's shape. */
            <div className="overflow-hidden rounded-2xl border border-border bg-card/70 shadow-sm">
              <div className="flex gap-4 border-b border-border bg-muted/40 px-4 py-3">
                <Skeleton className="h-4 w-40" />
                {roles.map((role) => (
                  <Skeleton key={role} className="h-4 flex-1" />
                ))}
              </div>
              {Array.from({ length: 6 }).map((_, i) => (
                <div key={i} className="flex items-center gap-4 border-b border-border/60 px-4 py-3 last:border-0">
                  <Skeleton className="h-4 w-40" />
                  {roles.map((role) => (
                    <div key={role} className="flex flex-1 justify-center">
                      <Skeleton className="h-4 w-4 rounded-full" />
                    </div>
                  ))}
                </div>
              ))}
            </div>
          ) : error ? (
            <div className="rounded-2xl border border-destructive/30 bg-destructive/5 px-4 py-3 text-sm text-destructive">
              Could not load role permissions. Try again later.
            </div>
          ) : (
            <AdaptiveDataView className="overflow-hidden rounded-2xl border border-border bg-card/70 shadow-sm">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-border bg-muted/40 text-left">
                    <th className="px-4 py-3 font-medium text-foreground">Capability</th>
                    {roles.map((role) => (
                      <th key={role} className="px-4 py-3 text-center font-medium text-foreground">
                        {roleLabel(role)}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {capabilities.map((row) => (
                    <tr key={row.key} className="border-b border-border/60 last:border-0">
                      <td className="px-4 py-3 text-foreground">{row.capability}</td>
                      {roles.map((role) => (
                        <td key={role} className="px-4 py-3">
                          <Cell allowed={Boolean(row.access[role])} />
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </AdaptiveDataView>
          )}

          <div className="flex flex-wrap gap-3">
            <Button variant="outline" className="gap-2 rounded-xl" asChild>
              <Link href="/settings?section=team">
                <Users className="h-4 w-4" />
                Manage team
              </Link>
            </Button>
            <Button variant="ghost" className="rounded-xl" asChild>
              <Link href="/settings">Back to settings</Link>
            </Button>
          </div>
        </div>
      </SettingsShell>
    </AppShell>
  )
}
