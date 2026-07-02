"use client"

import { useState } from "react"
import useSWR from "swr"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { MemoryCategoryChip, memoryCategoryBreakdown } from "@/components/intelligence/memory-category-chip"
import { plainDecisionReasoning } from "@/lib/intelligence/helpers"
import { agentsApi, memoryPromotionApi } from "@/lib/api"
import type { Agent, AgentMemory } from "@/types/api"
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription } from "@/components/ui/dialog"
import { Button } from "@/components/ui/button"

type PromotionRow = Record<string, unknown>

export function LearningTab({ agent, enabled }: { agent: Agent; enabled: boolean }) {
  const [selectedPromotion, setSelectedPromotion] = useState<PromotionRow | null>(null)

  const { data: memories = [], isLoading: memoriesLoading } = useSWR(
    enabled && agent.id ? ["agent_memories", agent.id] : null,
    () => agentsApi.listMemories(agent.id),
    { revalidateOnFocus: false },
  )

  const { data: auditData, isLoading: auditLoading } = useSWR(
    enabled ? ["memory_promotion_audit"] : null,
    () => memoryPromotionApi.audit({ limit: 50 }),
    { revalidateOnFocus: false },
  )

  if (!enabled) return null

  const oneWeekAgo = new Date()
  oneWeekAgo.setDate(oneWeekAgo.getDate() - 7)
  const memoriesThisWeek = memories.filter((memory: AgentMemory) => {
    const created = memory.createdAt ?? (memory as AgentMemory & { created_at?: string }).created_at
    if (!created) return false
    return new Date(created) > oneWeekAgo
  }).length

  const categoryCounts = memoryCategoryBreakdown(memories)
  const categories = Object.entries(categoryCounts).sort(([, a], [, b]) => b - a)

  const auditItems = (auditData?.items as PromotionRow[] | undefined) ?? []
  const recentPromotions = auditItems.slice(0, 5)

  return (
    <div className="space-y-6">
      <div className="grid gap-4 sm:grid-cols-2">
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">Total memories</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{memoriesLoading ? "…" : memories.length}</div>
            <p className="mt-1 text-xs text-muted-foreground">+{memoriesThisWeek} this week</p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">Categories</CardTitle>
          </CardHeader>
          <CardContent>
            {memoriesLoading ? (
              <p className="text-sm text-muted-foreground">Loading…</p>
            ) : categories.length > 0 ? (
              <div className="flex flex-wrap gap-3">
                {categories.map(([cat, count]) => (
                  <div key={cat} className="flex items-center gap-2">
                    <MemoryCategoryChip category={cat} size="sm" showLabel={false} />
                    <span className="text-sm capitalize">
                      {cat.replace(/_/g, " ")}: {count}
                    </span>
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-sm text-muted-foreground">No memory categories yet.</p>
            )}
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Recent memory promotions</CardTitle>
        </CardHeader>
        <CardContent>
          {auditLoading ? (
            <p className="text-sm text-muted-foreground">Loading audit trail…</p>
          ) : recentPromotions.length > 0 ? (
            <div className="space-y-4">
              {recentPromotions.map((promo, idx) => (
                <div
                  key={String(promo.id ?? promo.candidate_id ?? idx)}
                  className="flex items-start justify-between border-b border-border pb-4 last:border-0 last:pb-0"
                >
                  <div>
                    <p className="text-sm font-medium text-foreground">
                      {String(promo.content ?? "Memory promoted from usage")}
                    </p>
                    <p className="mt-1 text-xs text-muted-foreground">
                      {promo.decided_at ? new Date(String(promo.decided_at)).toLocaleDateString() : "—"}
                    </p>
                  </div>
                  <Button variant="outline" size="sm" onClick={() => setSelectedPromotion(promo)}>
                    Why does this agent remember this?
                  </Button>
                </div>
              ))}
            </div>
          ) : (
            <p className="text-sm text-muted-foreground">No recent promotions in the audit trail.</p>
          )}
        </CardContent>
      </Card>

      <Dialog open={!!selectedPromotion} onOpenChange={(open) => !open && setSelectedPromotion(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Why does this agent remember this?</DialogTitle>
            <DialogDescription>Plain-language promotion reasoning from the audit trail.</DialogDescription>
          </DialogHeader>
          <p className="rounded-md bg-muted p-4 text-sm text-foreground">
            {selectedPromotion
              ? plainDecisionReasoning(
                  selectedPromotion.decisionReasoning ?? selectedPromotion.decision_reasoning,
                )
              : ""}
          </p>
        </DialogContent>
      </Dialog>
    </div>
  )
}
