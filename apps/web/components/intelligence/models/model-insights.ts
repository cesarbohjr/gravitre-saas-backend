/**
 * Models v2 — pure helpers that turn the real registry payloads
 * (`GET /api/ml/models`, `GET /api/ml/models/{id}` version metrics,
 * `GET /api/training/jobs`) into what the Models page shows.
 *
 * Nothing here invents a value: every helper returns `null` (rendered as the
 * design's own "—" / "Not measured yet" empty states) when the registry has
 * not reported the field.
 */
import type { MlModelDetail, MlModelSummary, MlModelVersion, TrainingJob } from "@/types/api"

export type MetricSpec = {
  key: string
  label: string
  higherIsBetter: boolean
}

/** Order matters: the first metric a model reports becomes its headline metric. */
export const METRIC_SPECS: MetricSpec[] = [
  { key: "accuracy", label: "Accuracy", higherIsBetter: true },
  { key: "precision", label: "Precision", higherIsBetter: true },
  { key: "f1_score", label: "F1 score", higherIsBetter: true },
  { key: "auc_roc", label: "AUC", higherIsBetter: true },
  { key: "r2_score", label: "R²", higherIsBetter: true },
  { key: "mae", label: "Mean error", higherIsBetter: false },
  { key: "mse", label: "Squared error", higherIsBetter: false },
]

const DAY_MS = 24 * 60 * 60 * 1000

function finite(value: unknown): number | null {
  return typeof value === "number" && Number.isFinite(value) ? value : null
}

function parseTime(value: string | null | undefined): number | null {
  if (!value) return null
  const t = Date.parse(value)
  return Number.isNaN(t) ? null : t
}

export function sortedVersions(detail: MlModelDetail | null | undefined): MlModelVersion[] {
  return [...(detail?.versions ?? [])].sort((a, b) => a.version - b.version)
}

export function formatMetricValue(value: number): string {
  if (Math.abs(value) >= 100) return Math.round(value).toLocaleString()
  return value.toFixed(2)
}

export type HeadlineMetric = {
  spec: MetricSpec
  value: number
  version: number
  /** Points from versions trained in the last 30 days (oldest first). */
  series30d: number[]
  previous: number | null
}

/** Headline metric from the newest version that reports any known metric. */
export function headlineMetric(
  detail: MlModelDetail | null | undefined,
  now: number = Date.now(),
): HeadlineMetric | null {
  const versions = sortedVersions(detail)
  for (let i = versions.length - 1; i >= 0; i -= 1) {
    const metrics = versions[i].metrics ?? {}
    const spec = METRIC_SPECS.find((s) => finite(metrics[s.key]) != null)
    if (!spec) continue
    const scored = versions
      .map((v) => ({ v, value: finite((v.metrics ?? {})[spec.key]) }))
      .filter((row): row is { v: MlModelVersion; value: number } => row.value != null)
    const latestIndex = scored.findIndex((row) => row.v.version === versions[i].version)
    const previous = latestIndex > 0 ? scored[latestIndex - 1].value : null
    const series30d = scored
      .filter((row) => {
        const t = parseTime(row.v.createdAt)
        return t != null && now - t <= 30 * DAY_MS
      })
      .map((row) => row.value)
    return {
      spec,
      value: finite(metrics[spec.key]) as number,
      version: versions[i].version,
      series30d,
      previous,
    }
  }
  return null
}

export type DriftLevel = "stable" | "watch" | "high"

export const DRIFT_LABEL: Record<DriftLevel, string> = {
  stable: "Stable",
  watch: "Watch",
  high: "High",
}

/**
 * Data drift, only when the training pipeline recorded it in the latest
 * version's `custom_metrics`. The registry has no separate drift endpoint, so
 * a model without it reads "Not measured yet".
 */
export function driftLevel(detail: MlModelDetail | null | undefined): DriftLevel | null {
  const versions = sortedVersions(detail)
  const latest = versions[versions.length - 1]
  const custom = (latest?.metrics?.custom_metrics ?? null) as Record<string, unknown> | null
  if (!custom || typeof custom !== "object") return null
  for (const key of ["data_drift", "drift_status", "drift"]) {
    const raw = custom[key]
    if (typeof raw !== "string") continue
    const s = raw.trim().toLowerCase()
    if (s === "stable" || s === "low" || s === "none") return "stable"
    if (s === "watch" || s === "medium" || s === "moderate") return "watch"
    if (s === "high" || s === "severe" || s === "drifting") return "high"
  }
  for (const key of ["psi", "population_stability_index", "drift_score", "data_drift_score"]) {
    const score = finite(custom[key])
    if (score == null) continue
    if (score < 0.1) return "stable"
    if (score < 0.25) return "watch"
    return "high"
  }
  return null
}

export function isInProduction(model: MlModelSummary): boolean {
  return model.deployedVersion != null || model.status === "deployed"
}

/** Version row for the live (deployed) version, when the registry lists it. */
export function liveVersion(
  model: MlModelSummary,
  detail: MlModelDetail | null | undefined,
): MlModelVersion | null {
  const target = model.deployedVersion ?? (model.status === "deployed" ? model.currentVersion : null)
  if (target == null) return null
  return sortedVersions(detail).find((v) => v.version === target) ?? null
}

export function latestVersion(detail: MlModelDetail | null | undefined): MlModelVersion | null {
  const versions = sortedVersions(detail)
  return versions[versions.length - 1] ?? null
}

export function formatShortDate(value: string | null | undefined): string | null {
  const t = parseTime(value)
  if (t == null) return null
  return new Date(t).toLocaleDateString(undefined, { month: "short", day: "numeric" })
}

export function daysAgoLabel(value: string | null | undefined, now: number = Date.now()): string | null {
  const t = parseTime(value)
  if (t == null) return null
  const days = Math.max(0, Math.floor((now - t) / DAY_MS))
  if (days === 0) return "Today"
  if (days === 1) return "1 day ago"
  return `${days} days ago`
}

/** Training jobs that retrain this model (the worker versions models by dataset). */
export function jobsForModel(model: MlModelSummary, jobs: TrainingJob[]): TrainingJob[] {
  if (!model.datasetId) return []
  return jobs
    .filter((job) => job.dataset_id === model.datasetId)
    .sort((a, b) => (parseTime(b.created_at) ?? 0) - (parseTime(a.created_at) ?? 0))
}

export function activeJob(model: MlModelSummary, jobs: TrainingJob[]): TrainingJob | null {
  return jobsForModel(model, jobs).find((job) => job.status === "queued" || job.status === "training") ?? null
}

export type Attention = { reason: "failed" | "retrain_failed" | "drift" | "metric_drop"; message: string }

export function attentionFor(
  model: MlModelSummary,
  detail: MlModelDetail | null | undefined,
  jobs: TrainingJob[],
): Attention | null {
  if (model.status === "failed") {
    return {
      reason: "failed",
      message: "The last training run failed. Open the model to see what went wrong, then retrain.",
    }
  }
  const latest = latestVersion(detail)
  const lastJob = jobsForModel(model, jobs)[0]
  if (lastJob?.status === "failed") {
    const jobTime = parseTime(lastJob.created_at) ?? 0
    const versionTime = parseTime(latest?.createdAt) ?? 0
    if (jobTime > versionTime) {
      return {
        reason: "retrain_failed",
        message: "The latest retraining run did not finish, so the model is still on its previous version.",
      }
    }
  }
  const drift = driftLevel(detail)
  if (drift === "high") {
    return {
      reason: "drift",
      message: "Incoming data has drifted from what this model learned. Retraining on recent data should help.",
    }
  }
  const metric = headlineMetric(detail)
  if (metric && metric.previous != null) {
    const delta = metric.value - metric.previous
    const worse = metric.spec.higherIsBetter ? delta < 0 : delta > 0
    const relative = Math.abs(delta) / Math.max(Math.abs(metric.previous), 1e-9)
    if (worse && relative >= 0.03) {
      const verb = metric.spec.higherIsBetter ? "fell" : "rose"
      return {
        reason: "metric_drop",
        message: `${metric.spec.label} ${verb} from ${formatMetricValue(metric.previous)} to ${formatMetricValue(metric.value)} in the latest version. Retraining on recent data should help.`,
      }
    }
  }
  if (drift === "watch") {
    return {
      reason: "drift",
      message: "Incoming data is starting to differ from what this model learned. Keep an eye on it, or retrain on recent data.",
    }
  }
  return null
}

export const PATH_STEPS = ["Registered", "Offline test", "Shadow run", "Live"] as const
export type PathStep = (typeof PATH_STEPS)[number]

export type PathToProduction = {
  done: Record<PathStep, boolean>
  current: PathStep
  explanation: string
}

/**
 * Registered → Offline test → Shadow run → Live. "Offline test" is done when a
 * version carries evaluation metrics; shadow runs have no backend yet, so that
 * step is never marked done.
 */
export function pathToProduction(
  model: MlModelSummary,
  detail: MlModelDetail | null | undefined,
): PathToProduction {
  const tested = headlineMetric(detail) != null || model.status === "ready"
  const live = isInProduction(model)
  const done: Record<PathStep, boolean> = {
    Registered: true,
    "Offline test": tested || live,
    "Shadow run": false,
    Live: live,
  }
  const current: PathStep = live ? "Live" : tested ? "Shadow run" : "Offline test"
  let explanation: string
  if (current === "Offline test") {
    explanation =
      model.status === "training" || model.status === "validating"
        ? "Training now. When it finishes, an offline test scores it on held-back examples before anything goes live."
        : "Train it on your data first. An offline test then scores it on held-back examples before anything goes live."
  } else if (current === "Shadow run") {
    explanation =
      "A shadow run scores real records next to your current process without changing anything, so you can compare before switching on."
  } else {
    explanation = "Live and available to workflows and agents."
  }
  return { done, current, explanation }
}

export type ModelFilter = "all" | "production" | "registered"

export function matchesFilter(model: MlModelSummary, filter: ModelFilter): boolean {
  if (filter === "production") return isInProduction(model)
  if (filter === "registered") return !isInProduction(model)
  return true
}

export function matchesSearch(model: MlModelSummary, query: string): boolean {
  const q = query.trim().toLowerCase()
  if (!q) return true
  return [model.name, model.description ?? "", model.baseModel ?? ""].some((field) =>
    field.toLowerCase().includes(q),
  )
}
