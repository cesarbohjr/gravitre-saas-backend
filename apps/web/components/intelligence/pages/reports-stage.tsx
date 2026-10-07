"use client"

/**
 * Reports (Understand / Reports) — template switcher, period, three stat cards,
 * the evidence trail behind the latest outcome, saved views and scheduled reports.
 * Every number comes from the canonical snapshot, agent ROI, connectors or audit APIs.
 */
import { useMemo } from "react"
import useSWR from "swr"
import { EvidenceTrail } from "@/components/intelligence/reports/evidence-trail"
import {
  REPORT_PERIODS,
  TEMPLATE_BLURBS,
  buildTemplateKpis,
  pickTrailPath,
  type KpiEvidence,
  type ReportPeriodDays,
} from "@/components/intelligence/reports/report-model"
import { SavedViewsPanel } from "@/components/intelligence/reports/saved-views-panel"
import { ScheduledReportsPanel } from "@/components/intelligence/reports/scheduled-reports-panel"
import { IntelligenceFreshnessBar } from "@/components/intelligence/shell/intelligence-freshness-bar"
import { auditApi, connectorsApi, enterpriseApi, type IntelligencePageContextResponse } from "@/lib/api"
import { RADIUS, TYPE } from "@/lib/design-system"
import {
  REPORT_TEMPLATES,
  type ReportTemplateId,
  type SavedIntelligenceView,
} from "@/lib/intelligence/saved-intelligence-views"
import { isSnapshotMetricsReady, type SnapshotLoadState } from "@/lib/intelligence/snapshot-state"
import { cn } from "@/lib/utils"

const EVIDENCE_TAG: Record<KpiEvidence, { label: string; className: string }> = {
  measured: {
    label: "Measured",
    className: "bg-[color:var(--g-brand-soft)] text-[color:var(--g-brand-active)]",
  },
  estimated: {
    label: "Estimated",
    className: "bg-[color:var(--g-approval-soft)] text-[color:var(--warning-text)]",
  },
  none: {
    label: "No evidence",
    className: "bg-[color:var(--g-surface-2)] text-[color:var(--g-text-secondary)]",
  },
}

export function ReportsStage({
  pageContext,
  loadState,
  generatedAt,
  isValidating,
  onRefresh,
  enabled,
  template,
  onTemplateChange,
  periodDays,
  onPeriodChange,
  savedViews,
  canSave,
  onSaveView,
  onLoadView,
  onRemoveView,
}: {
  pageContext?: IntelligencePageContextResponse | null
  loadState: SnapshotLoadState
  generatedAt?: string | null
  isValidating?: boolean
  onRefresh?: () => void
  enabled: boolean
  template: ReportTemplateId
  onTemplateChange: (id: ReportTemplateId) => void
  periodDays: ReportPeriodDays
  onPeriodChange: (days: ReportPeriodDays) => void
  savedViews: SavedIntelligenceView[]
  canSave: boolean
  onSaveView: () => void
  onLoadView: (view: SavedIntelligenceView) => void
  onRemoveView: (id: string) => void
}) {
  const metricsReady = isSnapshotMetricsReady(loadState)
  const snapshotLoading = loadState === "LOADING" || loadState === "UNINITIALIZED"
  const templateLabel = REPORT_TEMPLATES.find((t) => t.id === template)?.label ?? "Business"

  const needsRoi = template === "business" || template === "agent"
  const roiQuery = useSWR(
    enabled && needsRoi ? ["intelligence/reports/agent-roi", periodDays] : null,
    () => enterpriseApi.getAgentRoi({ periodDays }),
    { revalidateOnFocus: false, keepPreviousData: true },
  )
  const connectorsQuery = useSWR(
    enabled && template === "governance" ? "intelligence/reports/connectors" : null,
    () => connectorsApi.list(),
    { revalidateOnFocus: false },
  )
  const auditQuery = useSWR(
    enabled && template === "governance" ? ["intelligence/reports/audit-total", periodDays] : null,
    () => {
      const from = new Date(Date.now() - periodDays * 24 * 60 * 60 * 1000).toISOString()
      return auditApi.list({ from, limit: 1 })
    },
    { revalidateOnFocus: false, shouldRetryOnError: false },
  )

  const kpis = useMemo(
    () =>
      buildTemplateKpis(template, {
        pageContext,
        metricsReady,
        roi: roiQuery.data,
        roiLoading: roiQuery.isLoading,
        roiError: Boolean(roiQuery.error),
        connectors: connectorsQuery.data?.connectors,
        connectorsLoading: connectorsQuery.isLoading,
        connectorsError: Boolean(connectorsQuery.error),
        auditTotal: auditQuery.data?.total ?? null,
        auditLoading: auditQuery.isLoading,
        auditError: Boolean(auditQuery.error),
      }),
    [
      template,
      pageContext,
      metricsReady,
      roiQuery.data,
      roiQuery.isLoading,
      roiQuery.error,
      connectorsQuery.data,
      connectorsQuery.isLoading,
      connectorsQuery.error,
      auditQuery.data,
      auditQuery.isLoading,
      auditQuery.error,
    ],
  )

  const trailPath = useMemo(() => pickTrailPath(pageContext?.outcomePaths), [pageContext?.outcomePaths])
  const snapshotHours = pageContext?.snapshot.timeWindowHours ?? null
  const snapshotDays = snapshotHours ? Math.max(1, Math.round(snapshotHours / 24)) : null
  const snapshotShorter = snapshotDays != null && snapshotDays < periodDays
  // The design has no room for a caveat line, so the window note rides on the period control.
  const periodNote = snapshotShorter
    ? `Snapshot figures cover the last ${snapshotDays === 1 ? "day" : `${snapshotDays} days`}. Agent and audit figures use the full period.`
    : undefined

  return (
    <div className="space-y-6 pt-2">
      <div className="flex flex-wrap items-center gap-3">
        <div
          role="group"
          aria-label="Report template"
          className={cn(RADIUS.control, "inline-flex max-w-full flex-wrap gap-0.5 bg-[color:var(--g-surface-2)] p-1")}
        >
          {REPORT_TEMPLATES.map((t) => {
            const on = t.id === template
            return (
              <button
                key={t.id}
                type="button"
                aria-pressed={on}
                onClick={() => onTemplateChange(t.id)}
                className={cn(
                  RADIUS.control,
                  "min-h-11 px-3 text-sm font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring sm:min-h-8",
                  on
                    ? "bg-[color:var(--g-surface-1)] text-[color:var(--g-text-primary)] shadow-sm"
                    : "text-[color:var(--g-text-secondary)] hover:text-[color:var(--g-text-primary)]",
                )}
              >
                {t.label}
              </button>
            )
          })}
        </div>
        <label className="flex items-center gap-2 text-sm text-[color:var(--g-text-secondary)]">
          Period
          <select
            value={periodDays}
            title={periodNote}
            onChange={(e) => onPeriodChange(Number(e.target.value) as ReportPeriodDays)}
            className="h-11 rounded-[var(--np-radius-md)] border border-[color:var(--g-border-default)] bg-[color:var(--g-surface-1)] px-3 text-sm text-foreground sm:h-9"
          >
            {REPORT_PERIODS.map((p) => (
              <option key={p.days} value={p.days}>
                {p.label}
              </option>
            ))}
          </select>
        </label>
        <IntelligenceFreshnessBar
          className="sm:ml-auto"
          loadState={loadState}
          generatedAt={generatedAt}
          isValidating={isValidating}
          onRefresh={onRefresh}
        />
      </div>

      <section aria-label={`${templateLabel} summary`} className="space-y-3">
        <p className={TYPE.bodyMuted}>{TEMPLATE_BLURBS[template]}</p>
        <div className="grid grid-cols-1 gap-3 md:grid-cols-3">
          {kpis.map((kpi) => {
            const tag = EVIDENCE_TAG[kpi.evidence]
            return (
              <div
                key={kpi.label}
                className={cn(RADIUS.card, "flex min-w-0 flex-col gap-2 border border-[color:var(--g-border-subtle)] bg-[color:var(--g-surface-1)] p-4")}
              >
                <div className="flex items-start justify-between gap-2">
                  <span className={TYPE.metricLabel}>{kpi.label}</span>
                  <span className={cn(RADIUS.tag, "shrink-0 px-1.5 py-0.5 font-mono text-[10px] font-medium", tag.className)}>
                    {tag.label}
                  </span>
                </div>
                <span
                  className={cn(
                    TYPE.metricValue,
                    kpi.evidence === "none" && kpi.value === "—" && "text-[color:var(--g-text-muted)]",
                  )}
                >
                  {kpi.value}
                </span>
                <span className={cn(TYPE.meta, "truncate")}>{kpi.note}</span>
              </div>
            )
          })}
        </div>
      </section>

      <EvidenceTrail path={trailPath} loading={snapshotLoading} />

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <SavedViewsPanel
          views={savedViews}
          currentLabel={`${templateLabel} · ${periodDays} days`}
          canSave={canSave}
          onSave={onSaveView}
          onLoad={onLoadView}
          onRemove={onRemoveView}
        />
        <ScheduledReportsPanel templateLabel={templateLabel} />
      </div>
    </div>
  )
}
