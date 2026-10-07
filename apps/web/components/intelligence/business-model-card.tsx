"use client"

/**
 * Models v2 — one registry model as a card. Every value comes from the real
 * registry (`/api/ml/models`, version metrics from `/api/ml/models/{id}`) and
 * training jobs (`/api/training/jobs`); missing values render the design's own
 * empty states ("—", "Not scored yet", "Not measured yet").
 */
import Link from "next/link"
import { useGravitreAIWorkspace } from "@/components/gravitre/ai-workspace-provider"
import { Button } from "@/components/ui/button"
import {
  DRIFT_LABEL,
  PATH_STEPS,
  activeJob,
  attentionFor,
  daysAgoLabel,
  driftLevel,
  formatMetricValue,
  formatShortDate,
  headlineMetric,
  isInProduction,
  latestVersion,
  liveVersion,
  pathToProduction,
  type DriftLevel,
} from "@/components/intelligence/models/model-insights"
import { TYPE } from "@/lib/design-system"
import { describeStatus } from "@/lib/intelligence/status-language"
import { modelTypeMeta } from "@/lib/ml-registry-catalog"
import { NucleoIntelligence } from "@/components/icons/nucleo/semantic"
import { cn } from "@/lib/utils"
import type { MlModelDetail, MlModelSummary, TrainingJob } from "@/types/api"

const SHADOW_RUN_GAP =
  "Shadow runs are not available yet: the model registry has no shadow-run endpoint. You can go live directly once the offline test looks right."

function Sparkline({ values, tone }: { values: number[]; tone: "brand" | "warning" }) {
  const min = Math.min(...values)
  const max = Math.max(...values)
  const span = max - min || 1
  const d = values
    .map((v, i) => {
      const x = (i / (values.length - 1)) * 100
      const y = 18 - ((v - min) / span) * 14
      return `${i === 0 ? "M" : "L"}${x.toFixed(1)} ${y.toFixed(1)}`
    })
    .join(" ")
  return (
    <svg className="h-[22px] w-full" viewBox="0 0 100 22" preserveAspectRatio="none" aria-hidden>
      <path
        d={d}
        fill="none"
        stroke={tone === "warning" ? "var(--g-warning)" : "var(--g-brand-active)"}
        strokeWidth={1.6}
        vectorEffect="non-scaling-stroke"
      />
    </svg>
  )
}

function DriftBars({ level }: { level: DriftLevel }) {
  const filled = level === "stable" ? 1 : level === "watch" ? 2 : 3
  const color =
    level === "stable" ? "bg-[color:var(--g-brand-active)]" : level === "watch" ? "bg-[color:var(--g-warning)]" : "bg-[color:var(--g-danger)]"
  return (
    <div className="flex gap-[3px]" aria-hidden>
      {[0, 1, 2].map((i) => (
        <span key={i} className={cn("h-1.5 flex-1 rounded-full", i < filled ? color : "bg-[color:var(--g-border-subtle)]")} />
      ))}
    </div>
  )
}

function Tile({
  label,
  value,
  caption,
  tone = "neutral",
  children,
}: {
  label: string
  value: string
  caption?: string | null
  tone?: "neutral" | "warning"
  children?: React.ReactNode
}) {
  return (
    <div
      className={cn(
        "flex min-w-0 flex-col gap-1.5 rounded-[var(--g-radius-tile)] p-3",
        tone === "warning"
          ? "bg-[color:var(--g-approval-surface)] text-[color:var(--g-approval-bright)]"
          : "bg-[color:var(--g-surface-2)]",
      )}
    >
      <span className={cn("text-xs", tone === "warning" ? "" : "text-[color:var(--g-text-muted)]")}>{label}</span>
      <span className="text-xl font-semibold tabular-nums">{value}</span>
      {children}
      {caption ? (
        <span className={cn("text-xs", tone === "warning" ? "" : "text-[color:var(--g-text-muted)]")}>{caption}</span>
      ) : null}
    </div>
  )
}

function DisabledWithReason({ label, reason }: { label: string; reason: string }) {
  return (
    <span title={reason} className="inline-flex" role="button" aria-disabled="true" tabIndex={0} aria-label={`${label} (unavailable). ${reason}`}>
      <Button size="default" disabled aria-hidden tabIndex={-1}>
        {label}
      </Button>
    </span>
  )
}

export function BusinessModelCard({
  model,
  detail,
  jobs,
  datasetName,
  showTechnical,
  onRetrain,
  retrainPending,
  onDeploy,
  deployPending,
}: {
  model: MlModelSummary
  detail: MlModelDetail | null | undefined
  jobs: TrainingJob[]
  datasetName: string | null
  showTechnical: boolean
  onRetrain: (model: MlModelSummary) => void
  retrainPending: boolean
  onDeploy: (model: MlModelSummary) => void
  deployPending: boolean
}) {
  const { summonWorkspace } = useGravitreAIWorkspace()
  const live = isInProduction(model)
  const attention = attentionFor(model, detail, jobs)
  const running = activeJob(model, jobs)
  const metric = headlineMetric(detail)
  const drift = driftLevel(detail)
  const latest = latestVersion(detail)
  const liveRow = liveVersion(model, detail)
  const path = pathToProduction(model, detail)
  const typeMeta = modelTypeMeta(model.modelType)
  const purpose = (model.description || "").trim() || typeMeta?.tagline || "Registered model"
  const href = `/models/${model.id}`
  const canDeploy = !live && model.status === "ready" && model.currentVersion > 0
  const sourceLabel = datasetName ?? (model.datasetId ? "a training dataset" : null)
  const versionLabel = model.currentVersion > 0 ? `v${model.currentVersion}` : "Not trained yet"
  const footer = sourceLabel
    ? `${live ? "Trained on" : "Learns from"} ${sourceLabel} · ${versionLabel}`
    : `No training data linked · ${versionLabel}`

  const retrainButton = (
    <Button
      variant="brand"
      onClick={() => onRetrain(model)}
      disabled={retrainPending || running != null}
    >
      {running ? (running.progress ? `Retraining… ${Math.round(running.progress)}%` : "Retraining…") : retrainPending ? "Starting…" : "Retrain"}
    </Button>
  )

  return (
    <article
      className="flex flex-col gap-4 rounded-[var(--g-radius-panel)] border border-[color:var(--g-border-subtle)] bg-[color:var(--g-surface-1)] p-5 sm:p-[22px]"
      data-testid="business-model-card"
      data-review-surface="models-card"
    >
      <div className="flex items-start justify-between gap-3">
        <div className="flex min-w-0 flex-col gap-1">
          <h3 className={TYPE.cardTitle}>{model.name}</h3>
          <p className="text-[13px] text-[color:var(--g-text-secondary)]">{purpose}</p>
        </div>
        <span
          className={cn(
            "shrink-0 rounded-full px-2.5 py-1 text-xs",
            live
              ? "bg-[color:var(--g-brand-soft)] text-[color:var(--g-emerald-deep)]"
              : "bg-[color:var(--g-surface-2)] text-[color:var(--g-text-secondary)]",
          )}
        >
          {live ? "In production" : "Registered"}
        </span>
      </div>

      {live ? (
        <div className="grid grid-cols-1 gap-2.5 sm:grid-cols-3">
          {metric ? (
            <Tile
              label={`${metric.spec.label} · ${metric.series30d.length >= 2 ? "30d" : `v${metric.version}`}`}
              value={formatMetricValue(metric.value)}
              caption={metric.series30d.length >= 2 ? null : "One scored version in 30 days"}
            >
              {metric.series30d.length >= 2 ? (
                <Sparkline values={metric.series30d} tone={attention?.reason === "metric_drop" ? "warning" : "brand"} />
              ) : null}
            </Tile>
          ) : (
            <Tile label="Performance" value="—" caption="Not scored yet" />
          )}
          {drift ? (
            <Tile label="Data drift" value={DRIFT_LABEL[drift]} tone={drift === "stable" ? "neutral" : "warning"}>
              <DriftBars level={drift} />
            </Tile>
          ) : (
            <Tile label="Data drift" value="—" caption="Not measured yet" />
          )}
          {attention ? (
            <Tile
              label="Last trained"
              value={formatShortDate(latest?.createdAt) ?? "—"}
              caption={daysAgoLabel(latest?.createdAt) ?? "Date not reported"}
            />
          ) : (
            <Tile
              label="Live version"
              value={`v${model.deployedVersion ?? model.currentVersion}`}
              caption={formatShortDate(liveRow?.createdAt) ? `Trained ${formatShortDate(liveRow?.createdAt)}` : null}
            />
          )}
        </div>
      ) : (
        <div className="flex flex-col gap-2.5">
          <span className="font-mono text-[11px] uppercase tracking-[0.08em] text-[color:var(--g-text-muted)]">
            Path to production
          </span>
          <ol className="grid grid-cols-4 gap-1.5" aria-label="Path to production">
            {PATH_STEPS.map((step) => {
              const done = path.done[step]
              const current = path.current === step
              return (
                <li key={step} className="flex flex-col gap-1.5" aria-current={current ? "step" : undefined}>
                  <span
                    className={cn(
                      "h-1.5 rounded-full",
                      done ? "bg-[color:var(--g-brand-active)]" : "bg-[color:var(--g-border-subtle)]",
                    )}
                  />
                  <span
                    className={cn(
                      "text-xs",
                      current
                        ? "font-semibold text-[color:var(--g-text-primary)]"
                        : done
                          ? "text-[color:var(--g-text-primary)]"
                          : "text-[color:var(--g-text-muted)]",
                    )}
                  >
                    {step}
                    <span className="sr-only">{done ? " (done)" : current ? " (next)" : ""}</span>
                  </span>
                </li>
              )
            })}
          </ol>
          <p className="text-[13px] leading-relaxed text-[color:var(--g-text-secondary)]">{path.explanation}</p>
        </div>
      )}

      {attention ? (
        <div
          role="note"
          className="flex items-start gap-2.5 rounded-[var(--g-radius-tile)] border border-[color:color-mix(in_srgb,var(--g-warning)_35%,transparent)] bg-[color:var(--g-approval-surface)] px-3.5 py-3"
        >
          <NucleoIntelligence className="mt-0.5 h-4 w-4 shrink-0 text-[color:var(--g-approval-bright)]" aria-hidden />
          <span className="text-[13px] leading-relaxed text-[color:var(--g-text-primary)]">{attention.message}</span>
        </div>
      ) : null}

      {showTechnical ? (
        <dl className="grid grid-cols-2 gap-x-4 gap-y-1 rounded-[var(--g-radius-tile)] border border-dashed border-[color:var(--g-border-default)] px-3 py-2 text-xs sm:grid-cols-4">
          <div className="min-w-0">
            <dt className="text-[color:var(--g-text-muted)]">Type</dt>
            <dd className="truncate">{typeMeta?.label ?? model.modelType.replace(/_/g, " ")}</dd>
          </div>
          <div className="min-w-0">
            <dt className="text-[color:var(--g-text-muted)]">Base model</dt>
            <dd className="truncate font-mono">{model.baseModel ?? "—"}</dd>
          </div>
          <div className="min-w-0">
            <dt className="text-[color:var(--g-text-muted)]">Status</dt>
            <dd className="truncate">{describeStatus(model.status).phrase}</dd>
          </div>
          <div className="min-w-0">
            <dt className="text-[color:var(--g-text-muted)]">Versions</dt>
            <dd className="truncate">
              {model.currentVersion > 0 ? `v${model.currentVersion}` : "—"}
              {model.deployedVersion != null ? ` · live v${model.deployedVersion}` : ""}
            </dd>
          </div>
        </dl>
      ) : null}

      <div className="mt-auto flex flex-wrap items-center justify-between gap-2.5 border-t border-[color:var(--g-border-subtle)] pt-3.5">
        <span className={TYPE.meta}>{footer}</span>
        <div className="flex flex-wrap gap-2">
          {live ? (
            attention ? (
              <>
                <Button variant="outline" asChild>
                  <Link href={href} data-review-cta="open-model">Open</Link>
                </Button>
                {retrainButton}
              </>
            ) : (
              <>
                <Button
                  variant="outline"
                  onClick={() =>
                    summonWorkspace({
                      presentation: "compact",
                      selected: { kind: "model", id: model.id, label: model.name },
                      agentScope: null,
                      composerText: `Explain a recent prediction from the "${model.name}" model: what it predicted, which inputs mattered most, and how confident it was. Use only real prediction evidence.`,
                      submit: false,
                    })
                  }
                >
                  Explain a prediction
                </Button>
                <Button asChild>
                  <Link href={href} data-review-cta="open-model">Open</Link>
                </Button>
              </>
            )
          ) : (
            <>
              <Button variant="outline" asChild>
                <Link href={href} data-review-cta="open-model">Open</Link>
              </Button>
              {attention ? retrainButton : null}
              {canDeploy ? (
                <Button variant="outline" onClick={() => onDeploy(model)} disabled={deployPending}>
                  {deployPending ? "Going live…" : "Go live"}
                </Button>
              ) : null}
              {!attention && path.current === "Offline test" ? (
                running || model.status === "training" || model.status === "validating" ? (
                  <Button disabled>{running?.progress ? `Training… ${Math.round(running.progress)}%` : "Training…"}</Button>
                ) : (
                  <Button onClick={() => onRetrain(model)} disabled={retrainPending}>
                    {retrainPending ? "Starting…" : "Train"}
                  </Button>
                )
              ) : null}
              {path.current === "Shadow run" ? <DisabledWithReason label="Start shadow run" reason={SHADOW_RUN_GAP} /> : null}
            </>
          )}
        </div>
      </div>
    </article>
  )
}
