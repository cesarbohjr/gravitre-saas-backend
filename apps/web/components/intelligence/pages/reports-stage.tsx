"use client"

/**
 * I9 — Reports: saved views + templates. Composes existing intelligence surfaces.
 */
import { useMemo, useState } from "react"
import useSWR from "swr"
import { EmptyState } from "@/components/gravitre/empty-state"
import { GravitreMetric } from "@/components/gravitre/nodus-product"
import { SegmentedControl } from "@/components/gravitre/filter-chip"
import { AgentContributionCard } from "@/components/intelligence/agent-contribution-card"
import { BusinessPredictionCard } from "@/components/intelligence/business-prediction-card"
import { OutcomeAttributionFlow } from "@/components/intelligence/outcome-attribution-flow"
import { IntelligenceAskCommandSurface } from "@/components/intelligence/shell"
import { Button } from "@/components/ui/button"
import { enterpriseApi, type IntelligencePageContextResponse } from "@/lib/api"
import { readNumber } from "@/lib/intelligence/helpers"
import { formatPredictions } from "@/lib/intelligence/prediction-display"
import { formatQualityFlagsHuman, qualityFlagToCopy } from "@/lib/intelligence/quality-copy"
import {
  REPORT_TEMPLATES,
  deleteSavedIntelligenceView,
  readSavedIntelligenceViews,
  saveIntelligenceView,
  type ReportTemplateId,
  type SavedIntelligenceView,
} from "@/lib/intelligence/saved-intelligence-views"
import { pickPrimaryOutcomePath } from "@/lib/intelligence/performance-display"
import { isSnapshotMetricsReady, type SnapshotLoadState } from "@/lib/intelligence/snapshot-state"
import { TYPE } from "@/lib/design-system"
import { cn } from "@/lib/utils"

export function ReportsStage({
  pageContext,
  loadState,
  enabled,
  orgId,
  suggestedQuestions,
}: {
  pageContext?: IntelligencePageContextResponse | null
  loadState: SnapshotLoadState
  enabled: boolean
  orgId?: string | null
  suggestedQuestions?: string[]
}) {
  const [template, setTemplate] = useState<ReportTemplateId>("business")
  const [periodDays, setPeriodDays] = useState<7 | 30 | 90>(30)
  const [saved, setSaved] = useState<SavedIntelligenceView[]>(() => readSavedIntelligenceViews(orgId))
  const metricsReady = isSnapshotMetricsReady(loadState)
  const isLoading = loadState === "LOADING" || loadState === "UNINITIALIZED"

  const { data: roi, isLoading: roiLoading } = useSWR(
    enabled && template === "agent" ? ["intelligence/reports/agent-roi", periodDays] : null,
    () => enterpriseApi.getAgentRoi({ periodDays }),
    { revalidateOnFocus: false },
  )

  const outcomeMetrics = pageContext?.metrics.outcomes ?? pageContext?.snapshot.metrics.outcomes ?? {}
  const execMetrics = pageContext?.metrics.execution ?? pageContext?.snapshot.metrics.execution ?? {}
  const measured = metricsReady ? readNumber(outcomeMetrics.measuredOutcomes, null) : null
  const awaiting = metricsReady ? readNumber(execMetrics.awaitingApproval, null) : null
  const predictions = useMemo(
    () => formatPredictions(pageContext?.snapshot.predictions as Record<string, unknown>[] | undefined),
    [pageContext?.snapshot.predictions],
  )
  const paths = pageContext?.outcomePaths ?? []
  const primaryPath = pickPrimaryOutcomePath(paths)
  const qualityNotes = formatQualityFlagsHuman(pageContext?.qualityFlags ?? [])

  function persistSave() {
    if (!orgId) return
    const label = `${REPORT_TEMPLATES.find((t) => t.id === template)?.label} · ${periodDays}d`
    setSaved(saveIntelligenceView(orgId, { label, templateId: template, periodDays }))
  }

  function loadView(view: SavedIntelligenceView) {
    setTemplate(view.templateId)
    setPeriodDays(view.periodDays)
  }

  function removeView(id: string) {
    if (!orgId) return
    setSaved(deleteSavedIntelligenceView(orgId, id))
  }

  return (
    <div className="space-y-6">
      <div className="space-y-3">
        <div>
          <p className={TYPE.eyebrow}>Report templates</p>
          <p className={cn(TYPE.meta, "mt-0.5")}>
            Saved intelligence views from live snapshot data — not a pack of admin tables.
          </p>
        </div>
        <SegmentedControl
          ariaLabel="Report template"
          options={REPORT_TEMPLATES.map((t) => ({ id: t.id, label: t.label }))}
          value={template}
          onChange={setTemplate}
          className="w-full max-w-full flex-wrap"
        />
        <div className="flex flex-wrap items-center gap-2">
          <label className="flex items-center gap-2 text-xs text-muted-foreground">
            Period
            <select
              value={periodDays}
              onChange={(e) => setPeriodDays(Number(e.target.value) as 7 | 30 | 90)}
              className="h-8 rounded-md border border-divide bg-[color:var(--g-surface-1)] px-2 text-xs text-foreground"
            >
              <option value={7}>7 days</option>
              <option value={30}>30 days</option>
              <option value={90}>90 days</option>
            </select>
          </label>
          <Button size="sm" variant="outline" onClick={persistSave} disabled={!orgId}>
            Save this view
          </Button>
        </div>
      </div>

      {saved.length > 0 ? (
        <section className="space-y-2">
          <p className={TYPE.eyebrow}>Saved views</p>
          <ul className="space-y-2">
            {saved.map((view) => (
              <li
                key={view.id}
                className="flex flex-wrap items-center justify-between gap-2 rounded-[var(--np-radius-md)] border border-divide px-3 py-2"
              >
                <button type="button" className="text-left text-sm font-medium" onClick={() => loadView(view)}>
                  {view.label}
                </button>
                <button
                  type="button"
                  className="text-xs text-muted-foreground hover:text-foreground"
                  onClick={() => removeView(view.id)}
                >
                  Remove
                </button>
              </li>
            ))}
          </ul>
        </section>
      ) : (
        <p className={TYPE.meta}>No saved views on this device yet.</p>
      )}

      <div
        role="status"
        className="rounded-[var(--np-radius-md)] border border-dashed border-divide px-3 py-3"
      >
        <p className="text-sm font-medium">Scheduled reports</p>
        <p className={cn(TYPE.meta, "mt-0.5")}>{qualityFlagToCopy("NOT_CONFIGURED")}</p>
      </div>

      {template === "business" ? (
        <div className="space-y-4">
          <section className="grid grid-cols-2 gap-[var(--np-kpi-gap)]">
            <GravitreMetric
              label="Measured outcomes"
              value={measured ?? "—"}
              hint={isLoading ? "Loading intelligence…" : "Canonical IMPROVES window"}
            />
            <GravitreMetric
              label="Attribution steps present"
              value={primaryPath ? primaryPath.presentStepCount : "—"}
              hint={isLoading ? "Loading intelligence…" : "Evidence-backed chain steps"}
            />
          </section>
          <OutcomeAttributionFlow paths={paths} selectedPathId={primaryPath?.id} />
        </div>
      ) : null}

      {template === "agent" ? (
        <div className="space-y-3">
          {roiLoading && !roi ? (
            <p className="text-sm text-muted-foreground">Loading agent contribution…</p>
          ) : !roi || roi.agents.length === 0 ? (
            <EmptyState
              title="No agent contribution in this period"
              description="Agent reports use recorded ROI. Hours saved stay estimates."
            />
          ) : (
            <div className="grid gap-3 md:grid-cols-2">
              {roi.agents.map((agent) => (
                <AgentContributionCard key={agent.agentId} agent={agent} viewMode="agents" />
              ))}
            </div>
          )}
        </div>
      ) : null}

      {template === "prediction" ? (
        predictions.length === 0 ? (
          <EmptyState
            title="No predictions in this snapshot"
            description="Predictions appear here when a snapshot includes them."
          />
        ) : (
          <div className="grid gap-4 md:grid-cols-2">
            {predictions.map((prediction) => (
              <BusinessPredictionCard key={prediction.id} prediction={prediction} />
            ))}
          </div>
        )
      ) : null}

      {template === "governance" ? (
        <div className="space-y-4">
          <GravitreMetric
            label="Awaiting approval"
            value={awaiting ?? "—"}
            hint={isLoading ? "Loading intelligence…" : "Pending governed actions"}
          />
          {qualityNotes.length > 0 ? (
            <ul className="space-y-2">
              {qualityNotes.map((note) => (
                <li key={note} className="rounded-md border border-divide px-3 py-2 text-sm">
                  {note}
                </li>
              ))}
            </ul>
          ) : metricsReady ? (
            <p className={TYPE.meta}>No quality flags on this snapshot.</p>
          ) : (
            <p className="text-sm text-muted-foreground">Loading intelligence…</p>
          )}
        </div>
      ) : null}

      <IntelligenceAskCommandSurface enabled={enabled} pageSuggestedQuestions={suggestedQuestions} />
    </div>
  )
}
