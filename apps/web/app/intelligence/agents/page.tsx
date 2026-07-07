"use client"

import useSWR from "swr"
import Link from "next/link"
import { AppShell } from "@/components/gravitre/app-shell"
import { EmptyState, ErrorState } from "@/components/gravitre/empty-state"
import { PageHeader } from "@/components/gravitre/page-header"
import { agentsApi } from "@/lib/api"
import { ApiError } from "@/lib/fetcher"
import { getSelectedOrgFromStorage } from "@/lib/org-context"
import { SURFACE_COPY } from "@/lib/surface-copy"
import { Robot } from "@phosphor-icons/react"
import { Card } from "@/components/ui/card"
import { useAuth } from "@/lib/auth-context"

const copy = SURFACE_COPY.hubLinks.agents
const pageCopy = SURFACE_COPY.pages.agents

export default function IntelligenceAgentsPage() {
  const { user } = useAuth()
  const orgId = typeof window !== "undefined" ? getSelectedOrgFromStorage()?.id : undefined
  const { data, error, isLoading, mutate } = useSWR(
    user && orgId ? ["intelligence/agents", orgId] : null,
    () => agentsApi.list(),
    { revalidateOnFocus: false },
  )

  if (!user) {
    return (
      <AppShell title={copy.title}>
        <EmptyState title="Sign in required" description="Log in to view agent profiles." />
      </AppShell>
    )
  }

  if (error) {
    const message = error instanceof ApiError ? error.message : "Failed to load agents."
    return (
      <AppShell title={copy.title}>
        <ErrorState title="Unable to load agents" description={message} onRetry={() => mutate()} />
      </AppShell>
    )
  }

  const agents = data?.agents ?? []

  return (
    <AppShell title={copy.title}>
      <div className="space-y-6 p-4 md:p-6">
        <PageHeader title={copy.title} description={copy.summary} />
        <p className="text-sm text-muted-foreground">{pageCopy.profileListHint}</p>

        {isLoading ? (
          <p className="text-sm text-muted-foreground">Loading agents…</p>
        ) : agents.length === 0 ? (
          <EmptyState
            title="No agents yet"
            description={pageCopy.profileEmpty}
            iconSlot={<Robot className="h-10 w-10 text-muted-foreground/40" weight="duotone" aria-hidden />}
          />
        ) : (
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {agents.map((agent) => (
              <Link key={agent.id} href={`/intelligence/agents/${agent.id}`}>
                <Card className="p-4 transition-colors hover:bg-muted/50">
                  <h3 className="font-semibold text-foreground">{agent.name}</h3>
                  <p className="mt-1 text-sm text-muted-foreground">{agent.role}</p>
                </Card>
              </Link>
            ))}
          </div>
        )}
      </div>
    </AppShell>
  )
}
