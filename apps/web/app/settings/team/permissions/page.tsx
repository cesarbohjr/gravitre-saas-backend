"use client"

import Link from "next/link"
import { AppShell } from "@/components/gravitre/app-shell"
import { Button } from "@/components/ui/button"
import { Shield, Check, X } from "lucide-react"

const PERMISSION_ROWS = [
  { capability: "View dashboards & intelligence", admin: true, member: true, viewer: true },
  { capability: "Run Gravitre AI & chat", admin: true, member: true, viewer: true },
  { capability: "Create agents & workflows", admin: true, member: true, viewer: false },
  { capability: "Install marketplace packs", admin: true, member: false, viewer: false },
  { capability: "Manage connectors", admin: true, member: true, viewer: false },
  { capability: "Approve write actions", admin: true, member: true, viewer: false },
  { capability: "Org settings & billing", admin: true, member: false, viewer: false },
  { capability: "Team invites & roles", admin: true, member: false, viewer: false },
  { capability: "Audit log export", admin: true, member: false, viewer: false },
]

function Cell({ allowed }: { allowed: boolean }) {
  return allowed ? (
    <Check className="mx-auto h-4 w-4 text-emerald-500" aria-label="Allowed" />
  ) : (
    <X className="mx-auto h-4 w-4 text-muted-foreground/40" aria-label="Not allowed" />
  )
}

export default function PermissionsMatrixPage() {
  return (
    <AppShell title="Role permissions">
      <div className="mx-auto max-w-4xl px-4 py-8 md:px-6">
        <div className="mb-8">
          <div className="mb-2 flex items-center gap-2">
            <Shield className="h-5 w-5 text-primary" />
            <h1 className="text-2xl font-semibold text-foreground">Role permissions</h1>
          </div>
          <p className="text-sm text-muted-foreground text-pretty">
            What each workspace role can access. Custom enterprise roles may override these defaults.
          </p>
        </div>

        <div className="overflow-x-auto rounded-xl border border-border">
          <table className="w-full min-w-[640px] text-sm">
            <thead>
              <tr className="border-b border-border bg-muted/40 text-left">
                <th className="px-4 py-3 font-medium text-foreground">Capability</th>
                <th className="px-4 py-3 text-center font-medium text-foreground">Admin</th>
                <th className="px-4 py-3 text-center font-medium text-foreground">Member</th>
                <th className="px-4 py-3 text-center font-medium text-foreground">Viewer</th>
              </tr>
            </thead>
            <tbody>
              {PERMISSION_ROWS.map((row) => (
                <tr key={row.capability} className="border-b border-border/60 last:border-0">
                  <td className="px-4 py-3 text-foreground">{row.capability}</td>
                  <td className="px-4 py-3"><Cell allowed={row.admin} /></td>
                  <td className="px-4 py-3"><Cell allowed={row.member} /></td>
                  <td className="px-4 py-3"><Cell allowed={row.viewer} /></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

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
