"use client"

import { AppShell } from "@/components/gravitre/app-shell"
import { AuditTrail } from "@/components/settings/audit-trail"

/** Audit trail (Settings Pages Redesign p19), in the Settings sidebar under Governance. */
export default function AuditPage() {
  return (
    <AppShell title="Audit trail">
      <AuditTrail />
    </AppShell>
  )
}
