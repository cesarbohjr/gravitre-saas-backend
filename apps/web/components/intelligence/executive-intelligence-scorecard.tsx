"use client"

import useSWR from "swr"
import { Badge } from "@/components/ui/badge"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { intelligenceApi } from "@/lib/api"
import { formatPercent, readNumber, readString } from "@/lib/intelligence/helpers"
import {
  formatHealthScore,
  healthLabelClass,
  healthLabelText,
  scoreLabelText,
} from "@/lib/intelligence/visibility-helpers"
import { useViewModeSafe } from "@/lib/view-mode-context"
import { ChartLineUp, Gauge, Sparkle } from "@phosphor-icons/react"
import { cn } from "@/lib/utils"

function ScoreBar({ label, value, weight }: { label: string; value: unknown; weight?: number }) {
  const num = typeof value === "number" && !Number.isNaN(value) ? value : null
  return (
    <div>
      <div className="mb-1 flex items-center justify-between text-xs">
        <span className="text-muted-foreground">
          {label}
          {weight != null ? ` (${Math.round(weight * 100)}%)` : ""}
        </span>
        <span className="font-medium tabular-nums text-foreground">
          {num != null ? formatPercent(num) : "—"}
        </span>
      </div>
      <div className="h-1.5 overflow-hidden rounded-full bg-secondary/80">
        <div
          className="h-full rounded-full bg-gradient-to-r from-emerald-500 to-teal-400 transition-all"
          style={{ width: num != null ? `${Math.round(num * 100)}%` : "0%" }}
        />
      </div>
    </div>
  )
}

export function ExecutiveIntelligenceScorecard({ orgScopedKey }: { orgScopedKey: string | null }) {
  const { isAdmin } = useViewModeSafe()
  const { data, error, isLoading } = useSWR(
    orgScopedKey && isAdmin ? ["visibility/executive", orgScopedKey] : null,
    () => intelligenceApi.visibilityExecutive(),
    { revalidateOnFocus: false, shouldRetryOnError: false },
  )

  if (!isAdmin) {
    return (
      <div className="rounded-2xl border border-dashed border-border/70 bg-card/40 p-5 text-sm text-muted-foreground">
        Executive intelligence scorecard is available to org admins.
      </div>
    )
  }

  if (error) {
    return (
      <div className="rounded-2xl border border-border/70 bg-card p-5 text-sm text-muted-foreground">
        Executive intelligence visibility is not enabled for this environment.
      </div>
    )
  }

  const score = data?.intelligence_score
  const breakdown = data?.score_breakdown ?? {}
  const weights = data?.score_weights ?? {}
  const maturity = data?.maturity

  return (
    <section className="space-y-4">
      <div className="grid gap-4 lg:grid-cols-2">
        <Card className="relative overflow-hidden border-border/70 bg-gradient-to-br from-card via-card/95 to-emerald-500/[0.06]">
          <CardHeader>
            <div className="flex items-start gap-3">
              <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-emerald-500/10 ring-1 ring-emerald-500/20">
                <Gauge className="h-5 w-5 text-emerald-600 dark:text-emerald-400" weight="duotone" aria-hidden />
              </span>
              <div>
                <CardTitle className="text-base">Executive intelligence score</CardTitle>
                <p className="mt-1 text-xs text-muted-foreground text-pretty">
                  Weighted composite across trust, learning, freshness, optimization, and domain health.
                </p>
              </div>
            </div>
          </CardHeader>
          <CardContent>
            {isLoading ? (
              <p className="text-sm text-muted-foreground">Loading executive score…</p>
            ) : (
              <>
                <div className="flex items-end gap-3">
                  <span
                    className={cn(
                      "text-5xl font-semibold tabular-nums tracking-tight",
                      score != null ? "text-emerald-600 dark:text-emerald-400" : "text-muted-foreground",
                    )}
                  >
                    {score != null ? Math.round(score * 100) : "—"}
                  </span>
                  <Badge variant="outline">{scoreLabelText(data?.score_label)}</Badge>
                </div>
                <Badge variant="outline" className="mt-4 border-amber-500/30 bg-amber-500/5 text-amber-900 dark:text-amber-200">
                  advisory_only
                </Badge>
              </>
            )}
          </CardContent>
        </Card>

        <Card className="border-border/70">
          <CardHeader>
            <CardTitle className="text-base">Score breakdown</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            <ScoreBar label="Trust" value={breakdown.trust} weight={weights.trust} />
            <ScoreBar label="Learning" value={breakdown.learning} weight={weights.learning} />
            <ScoreBar label="Freshness" value={breakdown.freshness} weight={weights.freshness} />
            <ScoreBar label="Optimization" value={breakdown.optimization} weight={weights.optimization} />
            <ScoreBar label="Domain health" value={breakdown.domain_health} weight={weights.domain_health} />
          </CardContent>
        </Card>
      </div>

      {maturity ? (
        <div className="rounded-2xl border border-border/70 bg-card p-4">
          <div className="flex items-start gap-3">
            <Sparkle className="h-5 w-5 text-violet-500" weight="duotone" aria-hidden />
            <div>
              <p className="text-sm font-medium text-foreground">
                Maturity L{maturity.level} — {readString(maturity.label, "Connected")}
              </p>
              <p className="mt-1 text-sm text-muted-foreground">{readString(maturity.description)}</p>
            </div>
          </div>
        </div>
      ) : null}

      <div className="grid gap-3 sm:grid-cols-2">
        <div className="rounded-xl border border-border/70 bg-card/60 px-4 py-3 text-sm">
          <p className="text-xs text-muted-foreground">Learning velocity</p>
          <p className="mt-1 font-medium capitalize text-foreground">
            {readString(data?.learning_velocity, "unknown")}
          </p>
        </div>
        <div className="rounded-xl border border-border/70 bg-card/60 px-4 py-3 text-sm">
          <p className="text-xs text-muted-foreground">Retrieval ranker examples</p>
          <p className="mt-1 font-medium tabular-nums text-foreground">
            {readNumber(data?.retrieval_ranker_examples) ?? "—"}
          </p>
        </div>
      </div>

      <div className="grid gap-3 md:grid-cols-2">
        <Card className="border-border/70">
          <CardHeader className="pb-2">
            <CardTitle className="text-sm">Top performing domains</CardTitle>
          </CardHeader>
          <CardContent className="text-sm text-muted-foreground">
            {(data?.top_performing_domains ?? []).length ? (
              <ul className="space-y-1">
                {data?.top_performing_domains?.map((domain) => (
                  <li key={domain} className="text-foreground">{domain}</li>
                ))}
              </ul>
            ) : (
              <span>— insufficient_data</span>
            )}
          </CardContent>
        </Card>
        <Card className="border-border/70">
          <CardHeader className="pb-2">
            <CardTitle className="text-sm">Domains needing attention</CardTitle>
          </CardHeader>
          <CardContent className="text-sm">
            {(data?.weak_domains ?? []).length ? (
              <ul className="space-y-1">
                {data?.weak_domains?.map((domain) => (
                  <li key={domain}>
                    <Badge variant="outline" className={healthLabelClass("needs_attention")}>
                      {domain} · {healthLabelText("needs_attention")}
                    </Badge>
                  </li>
                ))}
              </ul>
            ) : (
              <span className="text-muted-foreground">— insufficient_data</span>
            )}
          </CardContent>
        </Card>
      </div>

      <div className="flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
        <ChartLineUp className="h-4 w-4" aria-hidden />
        <span>
          Optimization opportunities: {readNumber(data?.optimization_opportunities, 0)} · Missing knowledge areas:{" "}
          {(data?.missing_knowledge_areas ?? []).length || "—"}
        </span>
      </div>

      {(data?.domain_health ?? []).length ? (
        <div className="overflow-x-auto">
          <table className="w-full min-w-[640px] text-left text-xs">
            <thead>
              <tr className="border-b border-border/60 text-muted-foreground">
                <th className="py-2 pr-3 font-medium">Domain</th>
                <th className="py-2 pr-3 font-medium">Health</th>
                <th className="py-2 pr-3 font-medium">Learning</th>
                <th className="py-2 pr-3 font-medium">Freshness</th>
                <th className="py-2 pr-3 font-medium">Retrieval</th>
                <th className="py-2 font-medium">Optimization</th>
              </tr>
            </thead>
            <tbody>
              {data?.domain_health?.map((row) => (
                <tr key={readString(row.domain ?? row.department, "domain")} className="border-b border-border/40">
                  <td className="py-2 pr-3 font-medium text-foreground">{readString(row.domain, "—")}</td>
                  <td className="py-2 pr-3">
                    {row.health_score != null ? `${formatHealthScore(row.health_score)}/100` : "—"}
                  </td>
                  <td className="py-2 pr-3 capitalize">{readString(row.learning_confidence, "—")}</td>
                  <td className="py-2 pr-3 capitalize">{readString(row.freshness, "—")}</td>
                  <td className="py-2 pr-3">
                    {row.retrieval_effectiveness != null ? formatPercent(row.retrieval_effectiveness) : "—"}
                  </td>
                  <td className="py-2">{readNumber(row.optimization_recommendations, 0)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : null}
    </section>
  )
}
