"use client"

import { useState } from "react"
import useSWR from "swr"
import Link from "next/link"
import { formatDistanceToNow } from "date-fns"
import { toast } from "sonner"
import { Brain, ArrowCounterClockwise } from "@phosphor-icons/react"
import { AppShell } from "@/components/gravitre/app-shell"
import { EmptyState, ErrorState } from "@/components/gravitre/empty-state"
import { Button } from "@/components/ui/button"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { useAuth } from "@/lib/auth-context"
import { intelligenceApi, memoryPromotionApi } from "@/lib/api"
import { ApiError } from "@/lib/fetcher"
import { plainDecisionReasoning, readString } from "@/lib/intelligence/helpers"
import { MemoryCategoryChip } from "@/components/intelligence/memory-category-chip"

function RelationshipsLens() {
  const { data, isLoading } = useSWR("intelligence/memory/relationships", () => intelligenceApi.relationships())
  if (isLoading) return <p className="text-sm text-muted-foreground">Loading relationships…</p>
  const rows = (data?.relationships as Array<Record<string, unknown>> | undefined) ?? []
  if (rows.length === 0) {
    return (
      <EmptyState
        title="No entity relationships yet"
        description="Relationships populate as the knowledge graph learns from org usage."
      />
    )
  }
  return (
    <ul className="space-y-2 text-sm">
      {rows.slice(0, 20).map((row, index) => (
        <li key={String(row.id ?? index)} className="rounded-lg border border-border/60 px-3 py-2">
          <span className="font-medium">{readString(row.source_entity_type, "entity")}</span> →{" "}
          <span className="font-medium">{readString(row.target_entity_type, "entity")}</span>
          <span className="ml-2 text-muted-foreground">{readString(row.relationship_type, "")}</span>
        </li>
      ))}
    </ul>
  )
}

export default function IntelligenceMemoryPage() {
  const { user } = useAuth()
  const [tab, setTab] = useState("org")
  const [reasonMemoryId, setReasonMemoryId] = useState<string | null>(null)

  const { data: candidatesData, error, mutate } = useSWR(
    user && tab === "org" ? "intelligence/memory/candidates" : null,
    () => memoryPromotionApi.candidates({ status: "pending", limit: 50 }),
  )
  const { data: auditData, mutate: mutateAudit } = useSWR(
    user && tab === "org" ? "intelligence/memory/audit" : null,
    () => memoryPromotionApi.audit({ limit: 50 }),
  )
  const { data: autoData } = useSWR(user && tab === "auto" ? "intelligence/memory/auto" : null, () =>
    memoryPromotionApi.recentAutoPromotions({ limit: 25 }),
  )

  if (!user) {
    return (
      <AppShell title="Organizational Memory">
        <EmptyState title="Sign in required" description="Log in to explore organizational memory." />
      </AppShell>
    )
  }

  if (error) {
    return (
      <AppShell title="Organizational Memory">
        <ErrorState
          title="Unable to load memory data"
          description={error instanceof ApiError ? error.message : "Please try again."}
          onRetry={() => mutate()}
        />
      </AppShell>
    )
  }

  const candidates = candidatesData?.items ?? []
  const auditItems = (auditData?.items as Array<Record<string, unknown>> | undefined) ?? []
  const autoItems = autoData?.items ?? []

  async function handleRollback(memoryId: string) {
    try {
      await memoryPromotionApi.rollback(memoryId, "Rollback from Intelligence memory explorer")
      toast.success("Memory rolled back")
      await Promise.all([mutate(), mutateAudit()])
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Rollback failed")
    }
  }

  return (
    <AppShell title="Organizational Memory">
      <div className="space-y-6 p-4 md:p-6">
        <p className="text-sm text-muted-foreground text-pretty">
          Promoted memories, auto-promotion audit trail, and knowledge graph relationships — org-scoped only.
        </p>

        <Tabs value={tab} onValueChange={setTab}>
          <TabsList className="flex w-full flex-wrap justify-start">
            <TabsTrigger value="org">Organizational memory</TabsTrigger>
            <TabsTrigger value="auto">Auto-promotions</TabsTrigger>
            <TabsTrigger value="graph">Knowledge graph</TabsTrigger>
          </TabsList>

          <TabsContent value="org" className="mt-6 space-y-4">
            {candidates.length === 0 ? (
              <EmptyState
                iconSlot={<Brain className="h-8 w-8 text-primary" weight="duotone" aria-hidden />}
                title="No pending promotion candidates"
                description="Promoted memories appear here when the engine detects recurring org-wide patterns."
              />
            ) : (
              candidates.map((candidate) => {
                const auditMatch = auditItems.find((row) => row.candidate_id === candidate.id)
                return (
                  <article key={candidate.id} className="rounded-2xl border border-border/70 bg-card p-4">
                    <div className="flex flex-wrap items-start justify-between gap-3">
                      <MemoryCategoryChip category={candidate.memory_category} size="md" />
                      <div className="flex gap-2">
                        <Button size="sm" variant="outline" onClick={() => setReasonMemoryId(candidate.id)}>
                          Why was this remembered?
                        </Button>
                      </div>
                    </div>
                    <p className="mt-3 text-sm leading-relaxed text-foreground text-pretty">
                      {candidate.content ?? "—"}
                    </p>
                    <p className="mt-2 text-xs text-muted-foreground">
                      Source: {candidate.source_table ?? "unknown"} · Freshness:{" "}
                      {candidate.updated_at
                        ? formatDistanceToNow(new Date(candidate.updated_at), { addSuffix: true })
                        : "—"}
                    </p>
                    {reasonMemoryId === candidate.id ? (
                      <p className="mt-3 rounded-lg border border-dashed border-border bg-secondary/40 p-3 text-sm text-foreground">
                        {plainDecisionReasoning(
                          auditMatch?.decision_reasoning ?? auditMatch?.decisionReasoning ?? candidate.metadata,
                        )}
                      </p>
                    ) : null}
                  </article>
                )
              })
            )}
          </TabsContent>

          <TabsContent value="auto" className="mt-6 space-y-4">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <p className="text-sm text-muted-foreground">
                Recent automatic promotions from the org learning engine.
              </p>
              <Button variant="outline" size="sm" asChild>
                <Link href="/admin/intelligence">Open full Memory promotion admin</Link>
              </Button>
            </div>
            {autoItems.length === 0 ? (
              <EmptyState title="No recent auto-promotions" description="Auto-promotions appear when thresholds are met." />
            ) : (
              autoItems.map((item, index) => (
                <article key={String(item.memory_id ?? index)} className="rounded-2xl border border-border/70 bg-card p-4">
                  <p className="text-sm text-foreground">{plainDecisionReasoning(item.decisionReasoning ?? item)}</p>
                  <p className="mt-2 text-xs text-muted-foreground">
                    {item.decided_at ? formatDistanceToNow(new Date(String(item.decided_at)), { addSuffix: true }) : "Recently"}
                  </p>
                  {item.memory_id ? (
                    <Button
                      size="sm"
                      variant="ghost"
                      className="mt-3"
                      onClick={() => handleRollback(String(item.memory_id))}
                    >
                      <ArrowCounterClockwise className="mr-2 h-4 w-4" aria-hidden />
                      Rollback
                    </Button>
                  ) : null}
                </article>
              ))
            )}
          </TabsContent>

          <TabsContent value="graph" className="mt-6 space-y-4">
            <p className="text-sm text-muted-foreground text-pretty">
              Memory lens: entity relationships below also indicate which graph nodes have promoted memories attached in
              the promotion audit trail.
            </p>
            <RelationshipsLens />
            {auditItems.length > 0 ? (
              <ul className="space-y-2 text-sm">
                {auditItems.slice(0, 10).map((row, index) => (
                  <li key={String(row.id ?? index)} className="rounded-lg border border-border/60 px-3 py-2">
                    <span className="font-medium">{readString(row.entity_type, "memory")}</span> ·{" "}
                    {plainDecisionReasoning(row.decision_reasoning ?? row.decisionReasoning)}
                  </li>
                ))}
              </ul>
            ) : null}
          </TabsContent>
        </Tabs>
      </div>
    </AppShell>
  )
}
