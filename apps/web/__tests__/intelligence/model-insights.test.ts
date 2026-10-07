import { describe, expect, it } from "vitest"
import {
  attentionFor,
  driftLevel,
  headlineMetric,
  matchesFilter,
  pathToProduction,
} from "@/components/intelligence/models/model-insights"
import type { MlModelDetail, MlModelSummary, TrainingJob } from "@/types/api"

const NOW = Date.parse("2026-10-07T12:00:00Z")
const daysAgo = (n: number) => new Date(NOW - n * 86_400_000).toISOString()

const base: MlModelSummary = {
  id: "m1",
  name: "Lead fit",
  modelType: "classifier",
  status: "deployed",
  currentVersion: 2,
  deployedVersion: 2,
  datasetId: "ds1",
  baseModel: "xgboost",
}

function detail(versions: MlModelDetail["versions"], model: MlModelSummary = base): MlModelDetail {
  return { ...model, versions }
}

describe("model-insights", () => {
  it("returns no metric, drift or attention when the registry reports none", () => {
    const d = detail([{ version: 1, metrics: {}, createdAt: daysAgo(3) }])
    expect(headlineMetric(d, NOW)).toBeNull()
    expect(driftLevel(d)).toBeNull()
    expect(attentionFor(base, d, [])).toBeNull()
  })

  it("builds a 30d series from versions and flags a real metric drop", () => {
    const d = detail([
      { version: 1, metrics: { accuracy: 0.81 }, createdAt: daysAgo(20) },
      { version: 2, metrics: { accuracy: 0.74 }, createdAt: daysAgo(2) },
    ])
    const metric = headlineMetric(d, NOW)
    expect(metric?.spec.label).toBe("Accuracy")
    expect(metric?.series30d).toEqual([0.81, 0.74])
    expect(attentionFor(base, d, [])?.reason).toBe("metric_drop")
  })

  it("reads drift only from recorded custom metrics", () => {
    const d = detail([{ version: 2, metrics: { custom_metrics: { psi: 0.3 } }, createdAt: daysAgo(1) }])
    expect(driftLevel(d)).toBe("high")
    expect(attentionFor(base, d, [])?.reason).toBe("drift")
  })

  it("flags a failed retraining job newer than the latest version", () => {
    const d = detail([{ version: 2, metrics: {}, createdAt: daysAgo(10) }])
    const jobs = [
      { id: "j1", dataset_id: "ds1", model_base: "xgboost", status: "failed", progress: 0, created_at: daysAgo(1) },
    ] as TrainingJob[]
    expect(attentionFor(base, d, jobs)?.reason).toBe("retrain_failed")
  })

  it("never marks the shadow run step done and filters by production state", () => {
    const registered: MlModelSummary = { ...base, status: "ready", deployedVersion: null }
    const d = detail([{ version: 2, metrics: { f1_score: 0.7 }, createdAt: daysAgo(1) }], registered)
    const path = pathToProduction(registered, d)
    expect(path.done["Offline test"]).toBe(true)
    expect(path.done["Shadow run"]).toBe(false)
    expect(path.current).toBe("Shadow run")
    expect(matchesFilter(registered, "registered")).toBe(true)
    expect(matchesFilter(base, "production")).toBe(true)
  })
})
