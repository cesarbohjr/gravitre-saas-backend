import { describe, expect, it } from "vitest"
import {
  deriveSnapshotLoadState,
  isSnapshotMetricsReady,
} from "@/lib/intelligence/snapshot-state"
import { buildLensMetrics } from "@/components/intelligence/map/build-lens-metrics"

describe("deriveSnapshotLoadState", () => {
  it("returns UNINITIALIZED when disabled", () => {
    expect(
      deriveSnapshotLoadState({
        enabled: false,
        isLoading: false,
        isValidating: false,
        error: undefined,
        data: undefined,
        hadData: false,
      }),
    ).toBe("UNINITIALIZED")
  })

  it("returns LOADING on first fetch", () => {
    expect(
      deriveSnapshotLoadState({
        enabled: true,
        isLoading: true,
        isValidating: true,
        error: undefined,
        data: undefined,
        hadData: false,
      }),
    ).toBe("LOADING")
  })

  it("returns REFRESHING when revalidating with prior data", () => {
    expect(
      deriveSnapshotLoadState({
        enabled: true,
        isLoading: false,
        isValidating: true,
        error: undefined,
        data: { snapshot: { generatedAt: "2026-01-01T00:00:00Z" } } as never,
        hadData: true,
      }),
    ).toBe("REFRESHING")
  })

  it("returns READY when data is present", () => {
    expect(
      deriveSnapshotLoadState({
        enabled: true,
        isLoading: false,
        isValidating: false,
        error: undefined,
        data: { snapshot: { generatedAt: "2026-01-01T00:00:00Z" } } as never,
        hadData: true,
      }),
    ).toBe("READY")
  })
})

describe("buildLensMetrics UNKNOWN ≠ ZERO", () => {
  it("never shows numeric zero while loading", () => {
    const metrics = buildLensMetrics({
      knowledgeGraph: null,
      readiness: null,
      modelCatalog: null,
      coreState: null,
      businessImpact: null,
      outcomesByEvent: {},
      canonicalMetrics: {
        knowledge: { knownEntities: 32 },
        predictions: { activePredictions: 0 },
      },
      loadState: "LOADING",
    })
    expect(metrics.knows.value).toBe("—")
    expect(metrics.predicts.value).toBe("—")
    expect(metrics.knows.hint).toContain("Loading")
  })

  it("shows verified zero only when ready", () => {
    const metrics = buildLensMetrics({
      knowledgeGraph: null,
      readiness: null,
      modelCatalog: null,
      coreState: null,
      businessImpact: null,
      outcomesByEvent: {},
      canonicalMetrics: {
        predictions: { activePredictions: 0 },
      },
      loadState: "READY",
    })
    expect(metrics.predicts.value).toBe("0")
    expect(isSnapshotMetricsReady("READY")).toBe(true)
  })
})
