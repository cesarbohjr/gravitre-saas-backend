"use client"

/**
 * Forecasts (/intelligence/predictive): stat cards, the "What's coming, and
 * when" timeline, a detail panel for the selected forecast, the full list and
 * "Did it happen?" outcome capture.
 *
 * Sources: page-context `snapshot.predictions` + open workflow failure
 * predictions. Actions: failure alerts dismiss through
 * `POST /api/workflows/failure-predictions/{id}/dismiss`; everything else
 * records through `POST /api/assistant/recommendation-feedback`.
 */
import { useEffect, useMemo, useState } from "react"
import useSWR from "swr"
import { toast } from "@/components/intelligence/overlays/toast"
import { ShareFindingDialog, type ShareableFinding } from "@/components/intelligence/overlays/share-finding-dialog"
import { IntelStat } from "@/components/intelligence/shell/intel-stat"
import { Button } from "@/components/ui/button"
import { PredictionRiskOpportunityTopology } from "@/components/intelligence/prediction-risk-opportunity-topology"
import {
  ForecastDetail,
  ForecastList,
  ForecastOutcomeCard,
  type ForecastOutcome,
} from "@/components/intelligence/forecasts/forecast-detail"
import {
  buildForecasts,
  forecastAreas,
  summarizeForecasts,
  type FailureAlertWithEvidence,
  type Forecast,
} from "@/components/intelligence/forecasts/forecast-model"
import { assistantApi, intelligenceFindingsApi, workflowsApi, type IntelligencePageContextResponse } from "@/lib/api"
import { APP_ROUTES } from "@/lib/app-routes"
import { isSnapshotMetricsReady, type SnapshotLoadState } from "@/lib/intelligence/snapshot-state"
import { TYPE } from "@/lib/design-system"
import { cn } from "@/lib/utils"

function feedbackDepartment(forecast: Forecast): string | undefined {
  if (forecast.origin !== "prediction" || !forecast.area) return undefined
  return forecast.area.toLowerCase().replace(/\s+/g, "_")
}

function feedbackId(forecast: Forecast, purpose: "relevance" | "outcome"): string {
  return `forecast-${purpose}:${forecast.key}`
}

export function PredictionsStage({
  pageContext,
  loadState,
  failureAlerts,
  failureAlertsLoaded,
  onAlertsChanged,
  onScanWorkflows,
  scanning,
}: {
  pageContext?: IntelligencePageContextResponse | null
  loadState: SnapshotLoadState
  failureAlerts?: FailureAlertWithEvidence[] | null
  failureAlertsLoaded: boolean
  onAlertsChanged: () => void
  onScanWorkflows: () => void
  scanning: boolean
}) {
  const metricsReady = isSnapshotMetricsReady(loadState)
  const isLoading = !metricsReady && !failureAlertsLoaded

  const { data: snoozeData, mutate: refreshSnoozes } = useSWR(
    "intelligence/forecast-snoozes",
    () => intelligenceFindingsApi.forecastSnoozes(),
    { revalidateOnFocus: false },
  )
  const snoozes = useMemo(() => snoozeData?.snoozes ?? [], [snoozeData])
  const [snoozingKey, setSnoozingKey] = useState<string | null>(null)

  const allForecasts = useMemo(
    () =>
      buildForecasts({
        predictions: pageContext?.snapshot.predictions,
        failureAlerts,
      }),
    [pageContext?.snapshot.predictions, failureAlerts],
  )
  // Snoozed forecasts stay off the page until their date, then return on their own.
  const forecasts = useMemo(() => {
    const hidden = new Set(snoozes.map((row) => row.key))
    return allForecasts.filter((row) => !hidden.has(row.key))
  }, [allForecasts, snoozes])
  const snoozedHere = useMemo(
    () => snoozes.filter((row) => allForecasts.some((f) => f.key === row.key)),
    [snoozes, allForecasts],
  )
  const summary = useMemo(() => summarizeForecasts(forecasts), [forecasts])
  const areas = useMemo(() => forecastAreas(forecasts), [forecasts])

  const [area, setArea] = useState<string | null>(null)
  const [selectedKey, setSelectedKey] = useState<string | null>(null)
  const [rejectingKey, setRejectingKey] = useState<string | null>(null)
  const [rejected, setRejected] = useState<Set<string>>(() => new Set())
  const [outcomes, setOutcomes] = useState<Record<string, ForecastOutcome>>({})
  const [savingOutcome, setSavingOutcome] = useState(false)
  const [sharing, setSharing] = useState<ShareableFinding | null>(null)

  const visible = useMemo(
    () => (area ? forecasts.filter((row) => row.area === area) : forecasts),
    [forecasts, area],
  )

  // Keep a valid selection: fall back to the first visible forecast.
  useEffect(() => {
    if (area && !areas.includes(area)) setArea(null)
  }, [area, areas])
  // Only the filtered list can be selected, so changing area never leaves another area's detail open.
  const selected = visible.find((row) => row.key === selectedKey) ?? visible[0] ?? null
  // Picking a dimmed, out-of-area forecast on the timeline clears the filter so the pick shows.
  const selectForecast = (key: string) => {
    if (area && !visible.some((row) => row.key === key)) setArea(null)
    setSelectedKey(key)
  }

  const reject = async (forecast: Forecast) => {
    setRejectingKey(forecast.key)
    try {
      if (forecast.origin === "workflow_alert" && forecast.alertId) {
        await workflowsApi.dismissFailurePrediction(forecast.alertId)
        toast.success("Dismissed. It's off your open forecasts.")
        onAlertsChanged()
      } else {
        await assistantApi.recommendationFeedback({
          recommendation_id: feedbackId(forecast, "relevance"),
          accepted: false,
          department: feedbackDepartment(forecast),
        })
        toast.success(`Thanks. Recorded as not a real ${forecast.kind}.`)
      }
      setRejected((prev) => new Set(prev).add(forecast.key))
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Couldn't save that. Try again.")
    } finally {
      setRejectingKey(null)
    }
  }

  const unsnooze = async (key: string) => {
    try {
      await intelligenceFindingsApi.unsnoozeForecast(key)
      await refreshSnoozes()
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Couldn't bring it back. Try again.")
    }
  }

  const snooze = async (forecast: Forecast) => {
    setSnoozingKey(forecast.key)
    try {
      const saved = await intelligenceFindingsApi.snoozeForecast({ key: forecast.key, title: forecast.title, days: 7 })
      await refreshSnoozes()
      const back = new Date(saved.until).toLocaleDateString("en-US", { month: "short", day: "numeric" })
      toast.success(`Snoozed until ${back}`, {
        description: "Hidden for your whole team. It comes back on its own if it's still open.",
        action: { label: "Undo", onClick: () => void unsnooze(forecast.key) },
      })
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Couldn't snooze that. Try again.")
    } finally {
      setSnoozingKey(null)
    }
  }

  const recordOutcome = async (forecast: Forecast, outcome: ForecastOutcome) => {
    setSavingOutcome(true)
    try {
      await assistantApi.recommendationFeedback({
        recommendation_id: feedbackId(forecast, "outcome"),
        accepted: outcome === "happened",
        department: feedbackDepartment(forecast),
      })
      setOutcomes((prev) => ({ ...prev, [forecast.key]: outcome }))
      toast.success("Outcome recorded.")
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Couldn't record the outcome. Try again.")
    } finally {
      setSavingOutcome(false)
    }
  }

  const recordedCount = Object.keys(outcomes).length
  const split = [
    `${summary.risks} risk${summary.risks === 1 ? "" : "s"}`,
    `${summary.opportunities} opportunit${summary.opportunities === 1 ? "y" : "ies"}`,
    ...(summary.signals > 0 ? [`${summary.signals} signal${summary.signals === 1 ? "" : "s"}`] : []),
  ].join(" · ")

  return (
    <div className="space-y-[22px]">
      <section aria-label="Forecast summary" className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <IntelStat
          label="Active forecasts"
          value={isLoading ? "—" : summary.active}
          hint={isLoading ? "Loading forecasts…" : split}
        />
        <IntelStat
          label="Need you now"
          value={
            failureAlertsLoaded ? (
              <span className={summary.needYouNow > 0 ? "text-[#a3333d] dark:text-[color:var(--g-danger)]" : undefined}>
                {summary.needYouNow}
              </span>
            ) : (
              "—"
            )
          }
          hint={failureAlertsLoaded ? "Due before the next run" : "Loading forecasts…"}
        />
        <IntelStat
          label="Need more evidence"
          value={isLoading ? "—" : summary.needEvidence}
          hint={
            isLoading
              ? "Loading forecasts…"
              : summary.needEvidence === 0
                ? "Every forecast has a source"
                : "Missing evidence or a connected source"
          }
        />
        <IntelStat
          label="Track record"
          value="Not scored yet"
          hint={
            recordedCount > 0
              ? `${recordedCount} outcome${recordedCount === 1 ? "" : "s"} recorded. Scoring isn't live yet`
              : "Mark outcomes below to start it"
          }
        />
      </section>

      <PredictionRiskOpportunityTopology
        forecasts={forecasts}
        areas={areas}
        area={area}
        onAreaChange={setArea}
        selectedKey={selected?.key ?? null}
        onSelect={selectForecast}
      />

      {isLoading ? (
        <p className={TYPE.bodyMuted}>Loading forecasts…</p>
      ) : forecasts.length === 0 && snoozedHere.length === 0 ? (
        <div className="rounded-[var(--np-radius-lg)] border border-dashed border-divide bg-[color:var(--g-surface-2)]/50 px-5 py-10 text-center">
          <p className="text-sm font-medium text-foreground">No forecasts yet</p>
          <p className={cn(TYPE.meta, "mx-auto mt-1 max-w-md")}>
            Forecasts appear when Gravitre spots risks or opportunities in your connected sources, or a workflow is
            likely to fail on its next run.
          </p>
          <Button className="mt-4" size="sm" variant="outline" disabled={scanning} onClick={onScanWorkflows}>
            {scanning ? "Checking workflows…" : "Check my workflows now"}
          </Button>
        </div>
      ) : (
        <div className="grid gap-4 lg:grid-cols-[minmax(0,1.5fr)_minmax(0,1fr)] lg:items-start">
          {selected ? (
            <ForecastDetail
              key={selected.key}
              forecast={selected}
              rejecting={rejectingKey === selected.key}
              rejected={rejected.has(selected.key)}
              onReject={() => void reject(selected)}
              snoozing={snoozingKey === selected.key}
              onSnooze={() => void snooze(selected)}
              onShare={() =>
                setSharing({
                  id: selected.key,
                  title: selected.title,
                  summary: selected.summary,
                  path: APP_ROUTES.intelligencePredictive,
                })
              }
            />
          ) : (
            <div />
          )}
          <div className="space-y-4">
            <ForecastList
              forecasts={visible}
              selectedKey={selected?.key ?? null}
              onSelect={setSelectedKey}
              snoozed={snoozedHere}
              onUnsnooze={(key) => void unsnooze(key)}
            />
            <ForecastOutcomeCard
              forecast={selected}
              recorded={selected ? outcomes[selected.key] : undefined}
              saving={savingOutcome}
              onRecord={(outcome) => {
                if (selected) void recordOutcome(selected, outcome)
              }}
            />
          </div>
        </div>
      )}
      <ShareFindingDialog
        finding={sharing}
        onOpenChange={(open) => {
          if (!open) setSharing(null)
        }}
      />
    </div>
  )
}
