"use client"

/**
 * Enterprise > Command center (design p18): health ring, weighted dimensions
 * and recommendations from GET /api/enterprise/integration-health and
 * /integration-suggestions, plus the existing score history, active risks and
 * workflow failure predictions. Nothing here is sample data.
 */
import { useCallback, useState } from "react"
import Link from "next/link"
import { useRouter } from "next/navigation"
import useSWR from "swr"
import { toast } from "@/components/agents/overlays/toast"
import { Activity, AlertTriangle, Camera, Gauge, Lightbulb, RefreshCw, ShieldAlert, Sparkles, TrendingUp } from "lucide-react"
import { enterpriseApi, workflowsApi } from "@/lib/api"
import type { IntegrationHealthScore, IntegrationSuggestionApplyResponse } from "@/types/api"
import {
  DIMENSION_LABELS,
  healthBand,
  recommendationLevel,
  scoreTone,
} from "@/lib/settings-api/enterprise"
import { ApplySuggestionResultSheet } from "@/components/enterprise/apply-suggestion-result-sheet"
import {
  FailureAlertRow,
  FAILURE_SEVERITY_META,
  groupFailureAlertsBySeverity,
} from "@/components/workflows/failure-prediction-alerts"
import { SetError, SetPill, SetSkeleton, formatMoment } from "./settings-kit"

const LOOKBACK_DAYS = 30
const RING_C = 440

function HealthRing({ health }: { health: IntegrationHealthScore }) {
  const band = healthBand(health.grade)
  const score = Math.max(0, Math.min(100, Math.round(health.score)))
  return (
    <svg width="170" height="170" role="img" aria-label={`Integration health score ${score} of 100, ${band.label}`}>
      <circle cx="85" cy="85" r="70" fill="none" className="ent-ring-track" strokeWidth="12" />
      <circle
        cx="85"
        cy="85"
        r="70"
        fill="none"
        className={`gs-ring ent-ring-${band.tone}`}
        strokeWidth="12"
        strokeLinecap="round"
        strokeDasharray={`${Math.round((score / 100) * RING_C)} ${RING_C}`}
        transform="rotate(-90 85 85)"
      />
      <text x="85" y="88" textAnchor="middle" className="ent-ring-num">
        {score}
      </text>
      <text x="85" y="112" textAnchor="middle" className={`ent-ring-band ${band.tone}`}>
        {band.label}
      </text>
    </svg>
  )
}

export function EnterpriseCommandCenter() {
  const router = useRouter()
  const [busy, setBusy] = useState<string | null>(null)
  const [applyingId, setApplyingId] = useState<string | null>(null)
  const [confirming, setConfirming] = useState(false)
  const [applyResult, setApplyResult] = useState<IntegrationSuggestionApplyResponse | null>(null)
  const [applyOpen, setApplyOpen] = useState(false)
  const [dismissingFailure, setDismissingFailure] = useState<string | null>(null)

  const health = useSWR("enterprise-integration-health", () => enterpriseApi.getIntegrationHealth(LOOKBACK_DAYS), {
    revalidateOnFocus: false,
  })
  const history = useSWR("enterprise-integration-health-history", () => enterpriseApi.getIntegrationHealthHistory(30), {
    revalidateOnFocus: false,
  })
  const suggestions = useSWR(
    "enterprise-integration-suggestions",
    () => enterpriseApi.getIntegrationSuggestions({ status: "open" }),
    { revalidateOnFocus: false },
  )
  const failures = useSWR("workflow-failure-predictions", () => workflowsApi.listFailurePredictions({ status: "open" }), {
    revalidateOnFocus: false,
  })

  const refreshAll = useCallback(async () => {
    setBusy("refresh")
    try {
      await Promise.all([health.mutate(), history.mutate(), suggestions.mutate(), failures.mutate()])
    } finally {
      setBusy(null)
    }
  }, [health, history, suggestions, failures])

  const recordSnapshot = async () => {
    setBusy("snapshot")
    try {
      await enterpriseApi.recordIntegrationHealthSnapshot(LOOKBACK_DAYS)
      await Promise.all([health.mutate(), history.mutate()])
      toast.success("Health snapshot recorded")
    } catch {
      toast.error("Could not record a snapshot")
    } finally {
      setBusy(null)
    }
  }

  const scanSuggestions = async () => {
    setBusy("scan")
    try {
      await enterpriseApi.scanIntegrationSuggestions(LOOKBACK_DAYS)
      await suggestions.mutate()
      toast.success("Recommendations updated from audit data")
    } catch {
      toast.error("Could not scan audit data")
    } finally {
      setBusy(null)
    }
  }

  const scanFailures = async () => {
    setBusy("failure-scan")
    try {
      const result = await workflowsApi.scanAllFailurePredictions()
      await failures.mutate()
      const skipped = result.errors.length > 0 ? `, ${result.errors.length} skipped` : ""
      toast.success(`Scanned ${result.scannedCount} workflows: ${result.alertCount} alerts${skipped}`)
    } catch {
      toast.error("Could not scan workflows")
    } finally {
      setBusy(null)
    }
  }

  const dismissSuggestion = async (id: string) => {
    setBusy(id)
    try {
      await enterpriseApi.dismissIntegrationSuggestion(id)
      await suggestions.mutate()
    } catch {
      toast.error("Could not dismiss the recommendation")
    } finally {
      setBusy(null)
    }
  }

  const applySuggestion = async (id: string) => {
    setApplyingId(id)
    try {
      const result = await enterpriseApi.applyIntegrationSuggestion(id)
      await suggestions.mutate()
      setApplyResult(result)
      setApplyOpen(true)
      if (result.requiresApproval) toast.message("Approval required before this write can run")
    } catch {
      toast.error("Could not apply the recommendation")
    } finally {
      setApplyingId(null)
    }
  }

  const confirmSuggestion = async () => {
    const id = applyResult?.suggestion?.id
    if (!id) return
    setConfirming(true)
    try {
      const result = await enterpriseApi.confirmIntegrationSuggestion(id)
      await suggestions.mutate()
      setApplyResult(result)
      toast.success("Recommendation applied")
    } catch {
      toast.error("Could not confirm the recommendation")
    } finally {
      setConfirming(false)
    }
  }

  const continueAfterApply = () => {
    if (applyResult) {
      const suggestionId = applyResult.suggestion?.id
      if (applyResult.workflowId) {
        const suffix = suggestionId ? `?suggestionId=${encodeURIComponent(suggestionId)}` : ""
        router.push(`/workflows/${applyResult.workflowId}/builder${suffix}`)
      } else if (applyResult.redirectPath) {
        router.push(applyResult.redirectPath)
      }
    }
    setApplyOpen(false)
    setApplyResult(null)
  }

  const dismissFailure = async (id: string) => {
    setDismissingFailure(id)
    try {
      await workflowsApi.dismissFailurePrediction(id)
      await failures.mutate()
    } catch {
      toast.error("Could not dismiss the alert")
    } finally {
      setDismissingFailure(null)
    }
  }

  const data = health.data
  const band = data ? healthBand(data.grade) : null
  const dims = Object.entries(data?.dimensions ?? {})
  const weights = data?.weights ?? {}
  const recs = suggestions.data?.suggestions ?? []
  const risks = data?.risks ?? []
  const snapshots = [...(history.data?.snapshots ?? [])].reverse()
  const alerts = failures.data?.alerts ?? []

  return (
    <>
      <div className="ent-intro">
        <p>Customer success view of integration health, recommendations and workflow risk.</p>
        <div className="ent-actions">
          <button type="button" className="gs-btn line sm" disabled={!!busy} onClick={() => void refreshAll()}>
            <RefreshCw size={15} className={busy === "refresh" ? "animate-spin" : undefined} aria-hidden />
            Refresh
          </button>
          <button type="button" className="gs-btn line sm" disabled={!!busy} onClick={() => void recordSnapshot()}>
            <Camera size={15} aria-hidden />
            {busy === "snapshot" ? "Recording…" : "Record snapshot"}
          </button>
        </div>
      </div>

      <section className="gs-card" aria-busy={health.isLoading}>
        {health.error && !data ? (
          <SetError message="Integration health did not load." onRetry={() => void health.mutate()} />
        ) : !data ? (
          <SetSkeleton rows={3} label="Loading integration health" />
        ) : (
          <div className="ent-hero">
            <HealthRing health={data} />
            <div className="ent-hero-text">
              <div style={{ display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap" }}>
                <h3>Integration health</h3>
                {band ? <SetPill tone={band.tone}>{band.label}</SetPill> : null}
              </div>
              <p>
                A composite of connector health, workflow success, agent use and approval speed over the last{" "}
                {data.lookbackDays} days.
              </p>
              <div className="ent-updated">Updated {formatMoment(data.computedAt) ?? "just now"}</div>
            </div>
          </div>
        )}
      </section>

      <div className="ent-grid2">
        <section className="gs-card ent-card">
          <div className="ent-title">
            <Gauge size={17} aria-hidden />
            <h3>Health dimensions</h3>
          </div>
          <p className="ent-card-sub">Four weighted signals behind the score</p>
          {!data ? (
            health.error ? <p className="gs-sub">No dimensions until health loads.</p> : <SetSkeleton rows={4} />
          ) : dims.length === 0 ? (
            <p className="gs-sub">None yet</p>
          ) : (
            dims.map(([key, dim], index) => {
              const tone = scoreTone(dim.score)
              const weight = weights[key]
              return (
                <div key={key} className="ent-dim">
                  <div className="ent-dim-head">
                    <span>
                      {DIMENSION_LABELS[key] ?? dim.label ?? key}
                      {weight != null ? <span className="w"> · {Math.round(weight * 100)}%</span> : null}
                    </span>
                    <span className="gs-mono">{dim.score}</span>
                  </div>
                  <div className="gs-track" role="presentation">
                    <span
                      className={tone === "green" ? undefined : tone}
                      style={{ width: `${Math.max(0, Math.min(100, dim.score))}%`, animationDelay: `${index * 90}ms` }}
                    />
                  </div>
                  {dim.summary ? <div className="ent-dim-sum">{dim.summary}</div> : null}
                </div>
              )
            })
          )}
        </section>

        <section className="gs-card ent-card">
          <div style={{ display: "flex", justifyContent: "space-between", gap: 8, alignItems: "center", flexWrap: "wrap" }}>
            <div className="ent-title">
              <Lightbulb size={17} aria-hidden />
              <h3>Recommendations</h3>
            </div>
            <button type="button" className="gs-btn text sm" disabled={!!busy} onClick={() => void scanSuggestions()}>
              <Sparkles size={14} aria-hidden />
              {busy === "scan" ? "Scanning…" : "Scan audit data"}
            </button>
          </div>
          <p className="ent-card-sub">Suggested fixes for reviews and QBRs</p>
          {suggestions.error && !suggestions.data ? (
            <SetError message="Recommendations did not load." onRetry={() => void suggestions.mutate()} />
          ) : !suggestions.data ? (
            <SetSkeleton rows={3} />
          ) : recs.length === 0 ? (
            <div className="gs-empty" style={{ padding: "18px 8px" }}>
              <b>None yet</b>
              <p>Scan audit data after agents and people use connectors to get tailored next steps.</p>
            </div>
          ) : (
            recs.map((rec) => {
              const level = recommendationLevel(rec.priority)
              const install =
                rec.suggestionType === "install_department_pack"
                  ? rec.packId
                    ? `/marketplace/assets/${encodeURIComponent(rec.packId)}`
                    : "/marketplace/assets?type=department_pack"
                  : null
              return (
                <div key={rec.id} className="ent-rec">
                  <span className={`gs-mono ent-rec-level ${level.tone}`}>{level.label}</span>
                  <div className="ent-rec-text">
                    <b>{rec.title}.</b> {rec.message}
                    <div className="ent-rec-acts">
                      <button
                        type="button"
                        className="gs-btn text sm"
                        disabled={applyingId === rec.id || busy === rec.id}
                        onClick={() => void applySuggestion(rec.id)}
                      >
                        {applyingId === rec.id ? "Applying…" : "Apply"}
                      </button>
                      {install ? (
                        <Link className="gs-btn text sm" href={install}>
                          Install pack
                        </Link>
                      ) : null}
                      {rec.connectorType ? (
                        <Link className="gs-btn text sm" href={`/connectors?type=${encodeURIComponent(rec.connectorType)}`}>
                          Open connectors
                        </Link>
                      ) : null}
                      <button
                        type="button"
                        className="gs-btn text sm"
                        disabled={busy === rec.id}
                        onClick={() => void dismissSuggestion(rec.id)}
                      >
                        {busy === rec.id ? "Dismissing…" : "Dismiss"}
                      </button>
                    </div>
                  </div>
                </div>
              )
            })
          )}
        </section>
      </div>

      <div className="ent-grid2">
        <section className="gs-card ent-card">
          <div className="ent-title">
            <TrendingUp size={17} aria-hidden />
            <h3>Score history</h3>
          </div>
          <p className="ent-card-sub">Recorded snapshots for trend reviews</p>
          {history.error && !history.data ? (
            <SetError message="Snapshots did not load." onRetry={() => void history.mutate()} />
          ) : !history.data ? (
            <SetSkeleton rows={2} />
          ) : snapshots.length < 2 ? (
            <p className="gs-sub">Record at least two snapshots to chart the trend.</p>
          ) : (
            <>
              <div className="ent-spark" role="img" aria-label={`${snapshots.length} snapshots, latest ${snapshots[snapshots.length - 1].score}`}>
                {snapshots.map((snap, i) => (
                  <span
                    key={snap.id}
                    title={`${formatMoment(snap.recordedAt) ?? ""}: ${snap.score}`}
                    style={{ height: `${Math.max(4, snap.score)}%`, animationDelay: `${i * 30}ms` }}
                  />
                ))}
              </div>
              <div className="ent-axis gs-mono">
                <span>{formatMoment(snapshots[0].recordedAt)}</span>
                <span>{formatMoment(snapshots[snapshots.length - 1].recordedAt)}</span>
              </div>
            </>
          )}
        </section>

        <section className="gs-card ent-card">
          <div className="ent-title">
            <AlertTriangle size={17} aria-hidden />
            <h3>Active risks</h3>
          </div>
          <p className="ent-card-sub">Dimensions scoring below 70</p>
          {!data ? (
            <SetSkeleton rows={2} />
          ) : risks.length === 0 ? (
            <p className="gs-sub">None right now.</p>
          ) : (
            risks.map((risk) => (
              <div key={risk.dimension} className="ent-rec">
                <span className={`gs-mono ent-rec-level ${risk.severity === "high" ? "red" : "amber"}`}>
                  {risk.severity === "high" ? "HIGH" : "MEDIUM"}
                </span>
                <div className="ent-rec-text">
                  <b>{DIMENSION_LABELS[risk.dimension] ?? risk.dimension}</b>
                  {risk.summary ? `: ${risk.summary}` : ""} ({risk.score}/100)
                </div>
              </div>
            ))
          )}
        </section>
      </div>

      <section className="gs-card ent-card">
        <div style={{ display: "flex", justifyContent: "space-between", gap: 8, alignItems: "center", flexWrap: "wrap" }}>
          <div className="ent-title">
            <ShieldAlert size={17} aria-hidden />
            <h3>Workflow failure predictions</h3>
          </div>
          <div className="ent-actions">
            <Link className="gs-btn line sm" href="/activity?tab=failures">
              View all
            </Link>
            <button type="button" className="gs-btn line sm" disabled={!!busy} onClick={() => void scanFailures()}>
              <Activity size={15} aria-hidden />
              {busy === "failure-scan" ? "Scanning…" : "Scan workflows"}
            </button>
          </div>
        </div>
        <p className="ent-card-sub">Early warnings from expiring sign ins, rate limits and missing scopes</p>
        {failures.error && !failures.data ? (
          <SetError message="Failure predictions did not load." onRetry={() => void failures.mutate()} />
        ) : !failures.data ? (
          <SetSkeleton rows={2} />
        ) : alerts.length === 0 ? (
          <p className="gs-sub">No open failure alerts.</p>
        ) : (
          <div style={{ display: "grid", gap: 12 }}>
            {groupFailureAlertsBySeverity(alerts).map((group) => (
              <div key={group.severity} style={{ display: "grid", gap: 8 }}>
                <span className="gs-eyebrow">
                  {FAILURE_SEVERITY_META[group.severity].label} · {group.items.length}
                </span>
                {group.items.map((alert) => (
                  <FailureAlertRow
                    key={alert.id}
                    alert={alert}
                    onDismiss={(id) => void dismissFailure(id)}
                    dismissing={dismissingFailure}
                  />
                ))}
              </div>
            ))}
          </div>
        )}
      </section>

      <ApplySuggestionResultSheet
        result={applyResult}
        open={applyOpen}
        onOpenChange={setApplyOpen}
        onContinue={continueAfterApply}
        onConfirm={() => void confirmSuggestion()}
        confirming={confirming}
      />
    </>
  )
}
