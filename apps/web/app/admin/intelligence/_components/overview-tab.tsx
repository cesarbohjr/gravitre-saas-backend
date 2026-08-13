"use client"

import type { ComponentType } from "react"
import { motion } from "framer-motion"
import useSWR from "swr"
import { Badge } from "@/components/ui/badge"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { EmptyState } from "@/components/gravitre/empty-state"
import { AdaptiveDataView } from "@/components/gravitre/adaptive-data-view"
import type { IntelligenceSnapshot } from "@/lib/api"
import { intelligenceApi } from "@/lib/api"
import type { IconProps } from "@phosphor-icons/react"
import { ChartBar, BookOpen, Stack, Warning, ChatCircleDots, Brain } from "@phosphor-icons/react"
import { cn } from "@/lib/utils"
import { BanditStatusCard } from "./bandit-status-card"
import { MemoryConflictsCard } from "./memory-conflicts-card"
import { formatTime, readNumber } from "./shared"
import { statusLabel, surfaceLabel } from "@/lib/learning-ui-copy"
import { SURFACE_COPY } from "@/lib/surface-copy"

type Row = Record<string, unknown>

const STAT_TONES = {
  emerald: "bg-emerald-500/10 text-emerald-600 ring-emerald-500/20 dark:text-emerald-400",
  sky: "bg-sky-500/10 text-sky-600 ring-sky-500/20 dark:text-sky-400",
  amber: "bg-amber-500/10 text-amber-600 ring-amber-500/20 dark:text-amber-400",
} as const

/** A layered KPI tile with a brand-tinted icon chip, hover lift, and entrance. */
function StatTile({
  icon: Icon,
  label,
  value,
  tone,
  emphasize,
  delay = 0,
}: {
  icon: ComponentType<IconProps>
  label: string
  value: string | number
  tone: keyof typeof STAT_TONES
  emphasize?: boolean
  delay?: number
}) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.4, ease: [0.16, 1, 0.3, 1], delay }}
      className="group flex items-center gap-4 rounded-2xl border border-border/70 bg-card p-4 shadow-sm transition-all duration-300 hover:-translate-y-0.5 hover:border-emerald-500/30 hover:shadow-md hover:shadow-emerald-500/5"
    >
      <span
        className={cn(
          "flex h-11 w-11 shrink-0 items-center justify-center rounded-xl ring-1 ring-inset transition-transform duration-300 group-hover:scale-105",
          STAT_TONES[tone],
        )}
      >
        <Icon className="h-5 w-5" weight="duotone" aria-hidden />
      </span>
      <div className="min-w-0">
        <p className="text-sm text-muted-foreground">{label}</p>
        <p
          className={cn(
            "text-2xl font-semibold tabular-nums",
            emphasize ? "text-amber-600 dark:text-amber-400" : "text-foreground",
          )}
        >
          {value}
        </p>
      </div>
    </motion.div>
  )
}

export function OverviewTab({
  data,
  isLoading,
}: {
  data: IntelligenceSnapshot | undefined
  isLoading: boolean
}) {
  const { data: learningProgress, isLoading: progressLoading } = useSWR(
    "admin/intelligence/learning-progress",
    () => intelligenceApi.learningProgress(),
    { revalidateOnFocus: false },
  )

  const volume = data?.queryVolume
  const clusters = (data?.clusters ?? []) as Row[]
  const gaps = (data?.knowledgeGaps ?? []) as Row[]
  const glossary = (data?.glossary ?? []) as Row[]
  const failedRecent = (data?.recentFailedSearches ?? []) as Row[]
  const showLearningEmpty =
    !progressLoading && learningProgress && learningProgress.hasAnySnapshot === false

  return (
    <div className="space-y-6">
      {showLearningEmpty ? (
        <Card>
          <CardContent className="pt-6">
            <EmptyState
              title="Still learning your organization"
              description={`Gravitre needs a bit more usage before it can surface real patterns. ${SURFACE_COPY.learningAdmin.learningProgressHint(
                learningProgress.queryRows,
                learningProgress.queryRowsNeeded,
                learningProgress.workflowRows,
                learningProgress.workflowRowsNeeded,
              )}`}
              iconSlot={
                <Brain className="h-6 w-6 text-emerald-500" weight="duotone" aria-hidden />
              }
              size="md"
            />
          </CardContent>
        </Card>
      ) : null}
      <div className="grid gap-4 md:grid-cols-3">
        <StatTile
          icon={ChatCircleDots}
          label="Questions logged"
          value={isLoading ? "…" : (volume?.totalLogged ?? 0)}
          tone="emerald"
          delay={0}
        />
        <StatTile
          icon={Stack}
          label="Unique question themes"
          value={isLoading ? "…" : (volume?.distinctNormalized ?? 0)}
          tone="sky"
          delay={0.05}
        />
        <StatTile
          icon={Warning}
          label={SURFACE_COPY.learningAdmin.failedSearchesTitle}
          value={isLoading ? "…" : (volume?.failedSearchCount ?? 0)}
          tone="amber"
          emphasize
          delay={0.1}
        />
      </div>

      <Card>
        <CardHeader>
          <div className="flex items-center gap-2">
            <Warning className="h-5 w-5 text-amber-500" weight="duotone" aria-hidden />
            <CardTitle>{SURFACE_COPY.learningAdmin.knowledgeGapsTitle}</CardTitle>
          </div>
          <CardDescription>
            Themes where searches failed often — plus what documentation would help next.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          {isLoading ? (
            <p className="text-sm text-muted-foreground">Loading…</p>
          ) : gaps.length === 0 ? (
            <p className="text-sm text-muted-foreground">
              No knowledge gaps yet. They appear once enough unanswered searches cluster into a theme.
            </p>
          ) : (
            gaps.map((gap) => (
              <div key={String(gap.id ?? gap.description)} className="rounded-lg border border-border p-4">
                <div className="flex flex-wrap items-center gap-2">
                  <Badge variant="destructive">
                    {readNumber(gap.failed_query_count ?? gap.failedQueryCount)} unanswered
                  </Badge>
                  <Badge variant="outline" className="capitalize">
                    {String(gap.status ?? "open").replace(/_/g, " ")}
                  </Badge>
                </div>
                <p className="mt-2 font-medium">{String(gap.description ?? "")}</p>
                {gap.suggested_content || gap.suggestedContent ? (
                  <p className="mt-2 text-sm text-muted-foreground">
                    {String(gap.suggested_content ?? gap.suggestedContent)}
                  </p>
                ) : null}
                <p className="mt-2 text-xs text-muted-foreground">
                  Identified {formatTime(gap.identified_at ?? gap.identifiedAt)}
                </p>
              </div>
            ))
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <div className="flex items-center gap-2">
            <Stack className="h-5 w-5 text-emerald-600 dark:text-emerald-400" weight="duotone" aria-hidden />
            <CardTitle>{SURFACE_COPY.learningAdmin.queryClustersTitle}</CardTitle>
          </div>
          <CardDescription>Recurring question themes from real usage — useful for training and docs.</CardDescription>
        </CardHeader>
        <CardContent>
          {isLoading ? (
            <p className="text-sm text-muted-foreground">Loading…</p>
          ) : clusters.length === 0 ? (
            <p className="text-sm text-muted-foreground">
              No themes yet. Themes appear after roughly 40 unique questions have been logged.
            </p>
          ) : (
            <div className="space-y-3">
              {clusters.map((cluster) => (
                <div key={String(cluster.id ?? cluster.cluster_label)} className="rounded-lg border border-border p-4">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="font-medium">{String(cluster.cluster_label ?? "Theme")}</span>
                    <Badge variant="secondary">{readNumber(cluster.member_query_count)} queries</Badge>
                    {readNumber(cluster.failed_search_count) > 0 ? (
                      <Badge variant="outline">{readNumber(cluster.failed_search_count)} failed</Badge>
                    ) : null}
                  </div>
                  {Array.isArray(cluster.representative_queries) && cluster.representative_queries.length > 0 ? (
                    <ul className="mt-2 list-inside list-disc text-sm text-muted-foreground">
                      {(cluster.representative_queries as string[]).slice(0, 4).map((q) => (
                        <li key={q}>{q}</li>
                      ))}
                    </ul>
                  ) : null}
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <div className="flex items-center gap-2">
            <BookOpen className="h-5 w-5 text-emerald-600 dark:text-emerald-400" weight="duotone" aria-hidden />
            <CardTitle>Company glossary</CardTitle>
          </div>
          <CardDescription>
            Company terms Gravitre noticed. Items stay <Badge variant="outline">needs review</Badge> until you
            approve them on the Memory tab.
          </CardDescription>
        </CardHeader>
        <CardContent>
          {isLoading ? (
            <p className="text-sm text-muted-foreground">Loading…</p>
          ) : glossary.length === 0 ? (
            <p className="text-sm text-muted-foreground">No glossary candidates extracted yet.</p>
          ) : (
            <AdaptiveDataView className="border-0">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-border text-left text-muted-foreground">
                    <th className="py-2 pr-4 font-medium">Term</th>
                    <th className="py-2 pr-4 font-medium">Type</th>
                    <th className="py-2 pr-4 font-medium">Times seen</th>
                    <th className="py-2 pr-4 font-medium">Team</th>
                    <th className="py-2 font-medium">Status</th>
                  </tr>
                </thead>
                <tbody>
                  {glossary.map((term) => (
                    <tr key={String(term.id ?? term.term)} className="border-b border-border">
                      <td className="py-2 pr-4 font-medium">{String(term.term ?? "")}</td>
                      <td className="py-2 pr-4 capitalize">{String(term.term_type ?? "").replace(/_/g, " ")}</td>
                      <td className="py-2 pr-4 tabular-nums">{String(term.frequency ?? 0)}</td>
                      <td className="py-2 pr-4">{String(term.associated_department ?? "—")}</td>
                      <td className="py-2">
                        <Badge variant="secondary">{statusLabel(term.status ?? "candidate")}</Badge>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </AdaptiveDataView>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <div className="flex items-center gap-2">
            <ChatCircleDots className="h-5 w-5 text-emerald-600 dark:text-emerald-400" weight="duotone" aria-hidden />
            <CardTitle>Recent unanswered searches</CardTitle>
          </div>
          <CardDescription>Latest questions that did not find a good answer — before they form a theme.</CardDescription>
        </CardHeader>
        <CardContent>
          {isLoading ? (
            <p className="text-sm text-muted-foreground">Loading…</p>
          ) : failedRecent.length === 0 ? (
            <p className="text-sm text-muted-foreground">No unanswered searches logged recently.</p>
          ) : (
            <ul className="space-y-2">
              {failedRecent.map((row) => (
                <li key={String(row.id ?? row.query_text)} className="rounded-lg border border-border p-3 text-sm">
                  <div className="flex flex-wrap gap-2">
                    {row.surface ? <Badge variant="outline">{surfaceLabel(row.surface)}</Badge> : null}
                    {row.department ? <Badge variant="secondary">{String(row.department)}</Badge> : null}
                  </div>
                  <p className="mt-1">{String(row.query_text ?? row.normalized_query_text ?? "")}</p>
                  <p className="mt-1 text-xs text-muted-foreground">{formatTime(row.created_at)}</p>
                </li>
              ))}
            </ul>
          )}
        </CardContent>
      </Card>

      <BanditStatusCard enabled />
      <MemoryConflictsCard enabled />

      <div className="flex items-start gap-2.5 rounded-xl border border-dashed border-border bg-secondary/40 px-4 py-3 text-sm text-muted-foreground">
        <ChartBar className="mt-0.5 h-4 w-4 shrink-0" weight="duotone" aria-hidden />
        <p className="leading-relaxed text-pretty">
          Overview is observational. Approve shared memories on Memory, review answer quality on Quality, and manage
          relationships on Relationships.
        </p>
      </div>
    </div>
  )
}
