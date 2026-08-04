"use client"

import useSWR from "swr"
import Link from "next/link"
import { StatCard, StatsGrid } from "@/components/gravitre/page-header"
import { CardSkeleton, StatsSkeleton } from "@/components/gravitre/loading-state"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { LearningConfidenceBadge } from "@/components/intelligence/learning-confidence-badge"
import { intelligenceApi } from "@/lib/api"
import { APP_ROUTES } from "@/lib/app-routes"
import { SURFACE_COPY } from "@/lib/surface-copy"
import { formatPercent, readNumber, readString } from "@/lib/intelligence/helpers"
import {
  formatHealthScore,
  healthLabelClass,
  healthLabelText,
  scoreLabelText,
} from "@/lib/intelligence/visibility-helpers"
import { useViewModeSafe } from "@/lib/view-mode-context"
import type { DomainHealthEntry } from "@/lib/intelligence/visibility-types"
import { Gauge, Heartbeat, Sparkle } from "@phosphor-icons/react"

function DomainHealthTile({ entry }: { entry: DomainHealthEntry }) {
  return (
    <Card className="border-border/70">
      <CardHeader className="pb-2">
        <div className="flex items-start justify-between gap-2">
          <CardTitle className="text-sm font-semibold">{readString(entry.domain, "Domain")}</CardTitle>
          <Badge variant="outline" className={healthLabelClass(entry.health_label)}>
            {healthLabelText(entry.health_label)}
          </Badge>
        </div>
      </CardHeader>
      <CardContent className="space-y-2 text-xs text-muted-foreground">
        <div className="flex justify-between">
          <span>Health score</span>
          <span className="font-medium tabular-nums text-foreground">
            {entry.health_score != null ? `${formatHealthScore(entry.health_score)}/100` : "—"}
          </span>
        </div>
        <div className="flex justify-between">
          <span>Learning</span>
          <LearningConfidenceBadge
            learning={{ level: entry.learning_confidence, insufficient_data: entry.learning_confidence === "insufficient_data" }}
            showSamples={false}
          />
        </div>
        <div className="flex justify-between">
          <span>Freshness</span>
          <span className="capitalize text-foreground">{readString(entry.freshness, "—")}</span>
        </div>
        <div className="flex justify-between">
          <span>Optimization</span>
          <span className="tabular-nums text-foreground">{readNumber(entry.optimization_recommendations, 0)}</span>
        </div>
      </CardContent>
    </Card>
  )
}

export function IntelligenceHealthGrid({ orgScopedKey }: { orgScopedKey: string | null }) {
  const { isAdmin } = useViewModeSafe()

  const { data: trust, error: trustError, isLoading: trustLoading } = useSWR(
    orgScopedKey ? ["visibility/trust", orgScopedKey] : null,
    () => intelligenceApi.visibilityTrustHealth(),
    { revalidateOnFocus: false, shouldRetryOnError: false },
  )
  const { data: maturity, isLoading: maturityLoading } = useSWR(
    orgScopedKey ? ["visibility/maturity", orgScopedKey] : null,
    () => intelligenceApi.visibilityMaturity(),
    { revalidateOnFocus: false, shouldRetryOnError: false },
  )
  const { data: domainHealth, isLoading: domainLoading } = useSWR(
    orgScopedKey && isAdmin ? ["visibility/domain", orgScopedKey] : null,
    () => intelligenceApi.visibilityDomainHealth(),
    { revalidateOnFocus: false, shouldRetryOnError: false },
  )

  const disabled = trust?.status === "disabled" || trustError
  if (disabled) return null

  const avgConfidence = trust?.confidence?.average
  const maturityView = maturity?.maturity
  const domains = domainHealth?.domains ?? []

  return (
    <section className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="text-base font-semibold text-foreground">{SURFACE_COPY.insightsHealth.title}</h2>
          <p className="mt-1 text-sm text-muted-foreground text-pretty">{SURFACE_COPY.insightsHealth.subtitle}</p>
        </div>
        {isAdmin ? (
          <Button variant="outline" size="sm" asChild>
            <Link href={APP_ROUTES.intelligenceReports}>{SURFACE_COPY.insightsHealth.reportsLink}</Link>
          </Button>
        ) : null}
      </div>

      {trustLoading || maturityLoading ? (
        <StatsSkeleton count={4} />
      ) : (
        <StatsGrid columns={4}>
          <StatCard
            label="Trust confidence (7d avg)"
            value={avgConfidence != null ? formatPercent(avgConfidence) : "—"}
            variant={avgConfidence != null ? "success" : "warning"}
          />
          <StatCard
            label="Maturity level"
            value={maturityView?.level != null ? `L${maturityView.level}` : "—"}
            variant="info"
          />
          <StatCard
            label="Maturity stage"
            value={readString(maturityView?.label, "—")}
          />
          <StatCard
            label="Stale source warnings"
            value={readNumber(trust?.stale_source_warnings?.length, 0)}
            variant={readNumber(trust?.stale_source_warnings?.length, 0) > 0 ? "warning" : "success"}
          />
        </StatsGrid>
      )}

      {maturityView ? (
        <div className="rounded-2xl border border-border/70 bg-card p-4 md:p-5">
          <div className="flex items-start gap-3">
            <Sparkle className="h-5 w-5 shrink-0 text-primary" weight="duotone" aria-hidden />
            <div>
              <p className="text-sm font-medium text-foreground">
                Level {maturityView.level} — {readString(maturityView.label, "Connected")}
              </p>
              <p className="mt-1 text-sm text-muted-foreground text-pretty">
                {readString(maturityView.description, "Intelligence maturity is building from connected sources and outcomes.")}
              </p>
            </div>
          </div>
        </div>
      ) : null}

      {isAdmin ? (
        <div className="space-y-3">
          <div className="flex items-center gap-2">
            <Heartbeat className="h-4 w-4 text-primary" weight="duotone" aria-hidden />
            <h3 className="text-sm font-semibold text-foreground">Domain health</h3>
          </div>
          {domainLoading ? (
            <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
              {Array.from({ length: 3 }).map((_, i) => (
                <CardSkeleton key={i} showIcon={false} lines={4} />
              ))}
            </div>
          ) : domains.length ? (
            <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
              {domains.slice(0, 9).map((entry) => (
                <DomainHealthTile key={readString(entry.domain ?? entry.department, "domain")} entry={entry} />
              ))}
            </div>
          ) : (
            <p className="text-sm text-muted-foreground">Domain health unavailable — insufficient_data.</p>
          )}
        </div>
      ) : (
        <p className="text-xs text-muted-foreground">
          Domain-level health details are available to org admins in Executive reports.
        </p>
      )}

      {trust?.optimization_state ? (
        <div className="flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
          <Gauge className="h-4 w-4" aria-hidden />
          <span>
            Pending optimization recommendations:{" "}
            {readNumber(trust.optimization_state.pending_recommendations, 0)} ·{" "}
            {scoreLabelText(trust.data_coverage)}
          </span>
        </div>
      ) : null}
    </section>
  )
}
