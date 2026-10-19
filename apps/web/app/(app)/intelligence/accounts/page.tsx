"use client"

import Link from "next/link"
import { AppShell } from "@/components/gravitre/app-shell"
import { EmptyState } from "@/components/gravitre/empty-state"
import { GravitrePageHeader } from "@/components/gravitre/nodus-product"
import { IntelligenceShell } from "@/components/intelligence/shell"
import { AccountHealthPanel } from "@/components/accounts/account-health-panel"
import { useAuth } from "@/lib/auth-context"
import { CONTEXT_HELP_HREF } from "@/lib/context-sources"
import { PAGE_FRAME } from "@/lib/design-system"
import { SURFACE_COPY } from "@/lib/surface-copy"
import { NucleoIntelligence } from "@/components/icons/nucleo/semantic"

const copy = SURFACE_COPY.pages.accounts

/**
 * Intelligence › Accounts. Account health used to sit at the bottom of
 * Forecasts; it is about customers, not predictions, so it has its own tab.
 * /intelligence/predictive#account-health and /intelligence?section=accounts
 * land here.
 */
export default function IntelligenceAccountsPage() {
  const { user } = useAuth()

  if (!user) {
    return (
      <AppShell title={copy.title}>
        <EmptyState title="Sign in required" description="Log in to view accounts." />
      </AppShell>
    )
  }

  return (
    <AppShell title={copy.title}>
      <div className={PAGE_FRAME}>
        <GravitrePageHeader
          eyebrow={copy.eyebrow}
          titleScale="display"
          title={copy.title}
          description={copy.description}
          icon={<NucleoIntelligence className="h-5 w-5" />}
          actions={
            <Link
              href={CONTEXT_HELP_HREF}
              className="text-sm text-muted-foreground underline-offset-2 hover:text-foreground hover:underline"
            >
              How Gravitre uses your context
            </Link>
          }
        />
        <IntelligenceShell activeTab="accounts">
          <AccountHealthPanel />
        </IntelligenceShell>
      </div>
    </AppShell>
  )
}
