"use client"

import { AppShell } from "@/components/gravitre/app-shell"
import { EnvironmentsSettings } from "@/components/settings/env-pipeline"

/** Environments (Settings Pages Redesign p20), in the Settings sidebar under Governance. */
export default function EnvironmentsPage() {
  return (
    <AppShell title="Environments">
      <EnvironmentsSettings />
    </AppShell>
  )
}
