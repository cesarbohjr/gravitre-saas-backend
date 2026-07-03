"use client"

import Link from "next/link"
import useSWR from "swr"
import { AppShell } from "@/components/gravitre/app-shell"
import { Button } from "@/components/ui/button"
import { Shield, Check, X, Loader2 } from "lucide-react"
import { AdaptiveDataView } from "@/components/gravitre/adaptive-data-view"
import { fetcher } from "@/lib/fetcher"
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
  const { data, error, isLoading } = useSWR<OrgRolePermissionsMatrix>(
    "/api/org/role-permissions",
    fetcher,
    { revalidateOnFocus: false },
  )

  const roles = data?.roles ?? ["admin", "member", "viewer"]
  const capabilities = data?.capabilities ?? []

  return (
    <AppShell title="Role permissions">
      <div className="mx-auto max-w-4xl px-4 py-8 md:px-6">
        <div className="mb-8">
          <div className="mb-2 flex items-center gap-2">
            <Shield className="h-5 w-5 text-primary" />
            <h1 className="text-2xl font-semibold text-foreground">Role permissions</h1>
          </div>
          <p className="text-sm text-muted-foreground text-pretty">
            What each workspace role can access. Loaded from org role definitions on the backend.
          </p>
        </div>

        {isLoading && !data ? (
          <div className="flex items-center justify-center py-16 text-muted-foreground">
            <Loader2 className="mr-2 h-5 w-5 animate-spin" />
            Loading permissions…
          </div>
        ) : error ? (
          <div className="rounded-xl border border-destructive/30 bg-destructive/5 px-4 py-3 text-sm text-destructive">
            Could not load role permissions. Try again later.
          </div>
        ) : (
          <AdaptiveDataView className="rounded-xl border-0">
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

        <div className="mt-6 flex flex-wrap gap-3">
          <Button variant="outline" asChild>
            <Link href="/settings/organizations">Manage team</Link>
          </Button>
          <Button variant="ghost" asChild>
            <Link href="/settings">Back to settings</Link>
          </Button>
        </div>
      </div>
    </AppShell>
  )
}
