"use client"

import Link from "next/link"
import { ShieldCheck, PlugZap, Database, Workflow } from "lucide-react"
import { Button } from "@/components/ui/button"

/** No example results or readiness claims. Live execution remains gated by canonical workflows. */
export function ProspectingReadiness({ workflowCount }: { workflowCount: number }) {
  const steps = [
    { title: "Prospect database", detail: "Tenant-scoped PostgreSQL migration required", icon: Database },
    { title: "Enrichment connections", detail: "Hunter, Emailable, Apollo; Snov and MillionVerifier optional", icon: PlugZap },
    { title: "Canonical workflow", detail: workflowCount ? `${workflowCount} workflow bindings present; review execution policy` : "Bind a reviewed prospecting workflow to activate", icon: Workflow },
    { title: "Governed admission", detail: "Identity, email, source permissions and CASL review required", icon: ShieldCheck },
  ]
  return (
    <section className="rounded-[12px] border border-divide bg-[color:var(--g-surface-1)] p-4" aria-label="Prospecting setup requirements">
      <h2 className="text-[15px] font-semibold">Prospecting setup</h2>
      <p className="mt-1 text-xs leading-5 text-muted-foreground">
        Discover and qualify businesses, then review contacts before any CRM action. No email sending is enabled.
      </p>
      <ol className="mt-4 space-y-3">
        {steps.map(({ title, detail, icon: Icon }, index) => (
          <li key={title} className="flex items-start gap-3">
            <span className="rounded-md bg-[color:var(--g-surface-2)] p-2"><Icon className="size-4" aria-hidden /></span>
            <div className="min-w-0">
              <p className="text-sm font-medium">{index + 1}. {title}</p>
              <p className="text-xs text-muted-foreground">{detail}</p>
            </div>
          </li>
        ))}
      </ol>
      <div className="mt-4 flex flex-wrap gap-2">
        <Button variant="outline" size="sm" asChild><Link href="/connectors">Manage connections</Link></Button>
        <Button variant="outline" size="sm" asChild><Link href="/workflows">Review workflows</Link></Button>
      </div>
    </section>
  )
}
