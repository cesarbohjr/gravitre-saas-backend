"use client"

import useSWR from "swr"
import { Badge } from "@/components/ui/badge"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { LearningConfidenceBadge } from "@/components/intelligence/learning-confidence-badge"
import { intelligenceApi } from "@/lib/api"
import { formatPercent, readNumber, readString } from "@/lib/intelligence/helpers"
import {
  formatHealthScore,
  freshnessLabelText,
  healthLabelClass,
  healthLabelText,
} from "@/lib/intelligence/visibility-helpers"
import type { AgentVisibilityProfile } from "@/lib/intelligence/visibility-types"
import { Brain, ChartLineUp, Heartbeat, ShieldCheck, Wrench } from "@phosphor-icons/react"

export function AgentIntelligenceVisibilitySection({
  agentId,
  orgScopedKey,
  compact = false,
}: {
  agentId: string
  orgScopedKey: string | null
  compact?: boolean
}) {
  const { data, isLoading } = useSWR(
    orgScopedKey && agentId ? ["visibility/agent", orgScopedKey, agentId] : null,
    () => intelligenceApi.visibilityAgent(agentId),
    { revalidateOnFocus: false, shouldRetryOnError: false },
  )

  if (data?.status === "disabled") return null

  const profile = data as AgentVisibilityProfile | undefined
  const knowledge = profile?.knowledge_health
  const domain = profile?.domain_health
  const capability = profile?.capability_visibility
  const outcome = profile?.outcome_summary
  const tools = capability?.capabilities ?? []

  return (
    <section className={`space-y-3 ${compact ? "" : "rounded-2xl border border-border/70 bg-card p-4 md:p-5"}`}>
      {!compact ? (
        <div>
          <h2 className="text-base font-semibold text-foreground">Intelligence visibility</h2>
          <p className="mt-1 text-sm text-muted-foreground text-pretty">
            Agent-scoped knowledge health, learning confidence, freshness, domain signals, and capabilities.
          </p>
        </div>
      ) : null}

      {isLoading && !profile ? (
        <p className="text-sm text-muted-foreground">Loading agent intelligence visibility…</p>
      ) : (
        <div className={`grid gap-3 ${compact ? "sm:grid-cols-2" : "sm:grid-cols-2 lg:grid-cols-3"}`}>
          <Card className="border-border/70">
            <CardHeader className="pb-2">
              <CardTitle className="flex items-center gap-2 text-sm text-muted-foreground">
                <Brain className="h-4 w-4 text-primary" weight="duotone" aria-hidden />
                Knowledge health
              </CardTitle>
            </CardHeader>
            <CardContent className="text-sm">
              <p className="font-medium text-foreground">
                {readNumber(knowledge?.assignment_count, 0)} assignment(s)
                {readNumber(knowledge?.stale_assignment_count, 0) > 0
                  ? ` · ${readNumber(knowledge?.stale_assignment_count, 0)} stale`
                  : ""}
              </p>
              <p className="mt-1 text-xs text-muted-foreground">
                {freshnessLabelText(knowledge?.freshness_status)}
              </p>
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
              <LearningConfidenceBadge learning={profile?.learning_confidence} />
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
              {freshnessLabelText(profile?.freshness)}
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
              {domain ? (
                <>
                  <Badge variant="outline" className={healthLabelClass(domain.health_label)}>
                    {readString(domain.domain, profile?.department ?? undefined)} · {healthLabelText(domain.health_label)}
                  </Badge>
                  <p className="text-xs text-muted-foreground">
                    Score {domain.health_score != null ? `${formatHealthScore(domain.health_score)}/100` : "—"}
                  </p>
                </>
              ) : (
                <p className="text-sm text-muted-foreground">— insufficient_data</p>
              )}
            </CardContent>
          </Card>

          <Card className="border-border/70">
            <CardHeader className="pb-2">
              <CardTitle className="flex items-center gap-2 text-sm text-muted-foreground">
                <ChartLineUp className="h-4 w-4 text-primary" weight="duotone" aria-hidden />
                Outcomes
              </CardTitle>
            </CardHeader>
            <CardContent className="text-sm">
              {outcome?.status === "ok" && outcome.score != null ? (
                <p className="font-medium text-foreground">
                  Success rate {formatPercent(outcome.score)} · {readNumber(outcome.events_count, 0)} events
                </p>
              ) : (
                <p className="text-muted-foreground">
                  — insufficient_data
                  {outcome?.events_found != null ? ` (${outcome.events_found}/${outcome.min_required ?? 5} events)` : ""}
                </p>
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
            <CardContent className="space-y-2">
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
              {readNumber(profile?.optimization_recommendations, 0) > 0 ? (
                <p className="text-xs text-muted-foreground">
                  {readNumber(profile?.optimization_recommendations, 0)} optimization recommendation(s) for this agent&apos;s domain — advisory only.
                </p>
              ) : null}
            </CardContent>
          </Card>
        </div>
      )}

      <Badge variant="outline" className="border-amber-500/30 bg-amber-500/5 text-amber-900 dark:text-amber-200">
        Advisory only — visibility signals do not auto-execute changes
      </Badge>
    </section>
  )
}
