"use client"

import useSWR from "swr"
import { Badge } from "@/components/ui/badge"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { LearningConfidenceBadge } from "@/components/intelligence/learning-confidence-badge"
import { intelligenceApi } from "@/lib/api"
import { readNumber, readString } from "@/lib/intelligence/helpers"
import {
  filterDomainHealthForDepartment,
  formatHealthScore,
  freshnessLabelText,
  healthLabelClass,
  healthLabelText,
} from "@/lib/intelligence/visibility-helpers"
import { useViewModeSafe } from "@/lib/view-mode-context"
import { Brain, Heartbeat, ShieldCheck, Wrench } from "@phosphor-icons/react"

export function AgentIntelligenceVisibilitySection({
  orgScopedKey,
  department,
  capabilities,
  compact = false,
}: {
  orgScopedKey: string | null
  department?: string
  capabilities?: string[]
  compact?: boolean
}) {
  const { isAdmin } = useViewModeSafe()

  const { data: trust } = useSWR(
    orgScopedKey ? ["visibility/trust", orgScopedKey] : null,
    () => intelligenceApi.visibilityTrustHealth(),
    { revalidateOnFocus: false, shouldRetryOnError: false },
  )
  const { data: domainHealth } = useSWR(
    orgScopedKey && isAdmin ? ["visibility/domain", orgScopedKey] : null,
    () => intelligenceApi.visibilityDomainHealth(),
    { revalidateOnFocus: false, shouldRetryOnError: false },
  )
  const { data: knowledgeHealth } = useSWR(
    orgScopedKey && isAdmin ? ["visibility/knowledge", orgScopedKey] : null,
    () => intelligenceApi.visibilityKnowledgeHealth(),
    { revalidateOnFocus: false, shouldRetryOnError: false },
  )

  if (trust?.status === "disabled") return null

  const domainEntry = filterDomainHealthForDepartment(domainHealth?.domains, department)
  const staleCount = readNumber((knowledgeHealth?.stale_sources as unknown[] | undefined)?.length, 0)
  const tools = capabilities ?? []

  return (
    <section className={`space-y-3 ${compact ? "" : "rounded-2xl border border-border/70 bg-card p-4 md:p-5"}`}>
      {!compact ? (
        <div>
          <h2 className="text-base font-semibold text-foreground">Intelligence visibility</h2>
          <p className="mt-1 text-sm text-muted-foreground text-pretty">
            Knowledge health, learning confidence, freshness, and domain signals for this agent.
          </p>
        </div>
      ) : null}

      <div className={`grid gap-3 ${compact ? "sm:grid-cols-2" : "sm:grid-cols-2 lg:grid-cols-3"}`}>
        <Card className="border-border/70">
          <CardHeader className="pb-2">
            <CardTitle className="flex items-center gap-2 text-sm text-muted-foreground">
              <Brain className="h-4 w-4 text-primary" weight="duotone" aria-hidden />
              Knowledge health
            </CardTitle>
          </CardHeader>
          <CardContent className="text-sm">
            {isAdmin ? (
              <>
                <p className="font-medium text-foreground">
                  {staleCount > 0 ? `${staleCount} stale source(s)` : "No stale sources flagged"}
                </p>
                <p className="mt-1 text-xs text-muted-foreground">
                  {readString(knowledgeHealth?.freshness_label as string, "insufficient_data")}
                </p>
              </>
            ) : (
              <p className="text-muted-foreground">Org admin view required for knowledge health details.</p>
            )}
          </CardContent>
        </Card>

        <Card className="border-border/70">
          <CardHeader className="pb-2">
            <CardTitle className="flex items-center gap-2 text-sm text-muted-foreground">
              <ShieldCheck className="h-4 w-4 text-primary" weight="duotone" aria-hidden />
              Learning confidence
            </CardTitle>
          </CardHeader>
          <CardContent>
            <LearningConfidenceBadge
              learning={
                trust?.learning_confidence ??
                (domainEntry?.learning_confidence ? { level: domainEntry.learning_confidence } : null)
              }
            />
          </CardContent>
        </Card>

        <Card className="border-border/70">
          <CardHeader className="pb-2">
            <CardTitle className="flex items-center gap-2 text-sm text-muted-foreground">
              <Heartbeat className="h-4 w-4 text-primary" weight="duotone" aria-hidden />
              Freshness
            </CardTitle>
          </CardHeader>
          <CardContent className="text-sm font-medium text-foreground">
            {domainEntry?.freshness
              ? freshnessLabelText(domainEntry.freshness)
              : readString(trust?.freshness?.freshness_label as string, "—")}
          </CardContent>
        </Card>

        <Card className="border-border/70">
          <CardHeader className="pb-2">
            <CardTitle className="flex items-center gap-2 text-sm text-muted-foreground">
              <Heartbeat className="h-4 w-4 text-primary" weight="duotone" aria-hidden />
              Domain health
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-2">
            {domainEntry ? (
              <>
                <Badge variant="outline" className={healthLabelClass(domainEntry.health_label)}>
                  {readString(domainEntry.domain, department)} · {healthLabelText(domainEntry.health_label)}
                </Badge>
                <p className="text-xs text-muted-foreground">
                  Score {domainEntry.health_score != null ? `${formatHealthScore(domainEntry.health_score)}/100` : "—"}
                </p>
              </>
            ) : (
              <p className="text-sm text-muted-foreground">— insufficient_data</p>
            )}
          </CardContent>
        </Card>

        <Card className={`border-border/70 ${compact ? "sm:col-span-2" : "sm:col-span-2 lg:col-span-2"}`}>
          <CardHeader className="pb-2">
            <CardTitle className="flex items-center gap-2 text-sm text-muted-foreground">
              <Wrench className="h-4 w-4 text-primary" weight="duotone" aria-hidden />
              Capability visibility
            </CardTitle>
          </CardHeader>
          <CardContent>
            {tools.length ? (
              <div className="flex flex-wrap gap-2">
                {tools.slice(0, 12).map((tool) => (
                  <Badge key={tool} variant="secondary" className="font-normal">
                    {tool.replace(/_/g, " ")}
                  </Badge>
                ))}
              </div>
            ) : (
              <p className="text-sm text-muted-foreground">No capabilities configured.</p>
            )}
          </CardContent>
        </Card>
      </div>

      <Badge variant="outline" className="border-amber-500/30 bg-amber-500/5 text-amber-900 dark:text-amber-200">
        Advisory only — visibility signals do not auto-execute changes
      </Badge>
    </section>
  )
}
