import { describe, expect, it } from "vitest"
import type { LearningInsightDisplay } from "@/lib/intelligence/learning-insight-display"
import {
  collectInsightFilterOptions,
  filterLearningInsights,
  DEFAULT_LEARNING_FILTERS,
} from "@/lib/intelligence/learning-filters"

const SAMPLE: LearningInsightDisplay[] = [
  {
    id: "a",
    statement: "Verified insight",
    learnedAt: new Date().toISOString(),
    learnedFrom: ["memory_promotion"],
    evidence: ["3 deals"],
    affectedEntities: [],
    resultingChanges: [],
    confidence: "auto_promoted",
    provenance: "memory_promotion · rec-1",
  },
  {
    id: "b",
    statement: "Sparse insight",
    learnedAt: "2020-01-01T00:00:00Z",
    learnedFrom: ["workflow"],
    evidence: [],
    affectedEntities: [],
    resultingChanges: [],
    confidence: "pending",
  },
]

describe("learning-filters", () => {
  it("collects confidence and source options from insights", () => {
    const opts = collectInsightFilterOptions(SAMPLE)
    expect(opts.confidenceOptions).toContain("auto_promoted")
    expect(opts.sourceOptions).toContain("memory_promotion")
    expect(opts.sourceOptions).toContain("workflow")
  })

  it("filters by evidence quality", () => {
    const verified = filterLearningInsights(SAMPLE, {
      ...DEFAULT_LEARNING_FILTERS,
      evidenceQuality: "verified",
    })
    expect(verified).toHaveLength(1)
    expect(verified[0]?.id).toBe("a")

    const needs = filterLearningInsights(SAMPLE, {
      ...DEFAULT_LEARNING_FILTERS,
      evidenceQuality: "needs_evidence",
    })
    expect(needs).toHaveLength(1)
    expect(needs[0]?.id).toBe("b")
  })

  it("filters by confidence and time range", () => {
    const byConf = filterLearningInsights(SAMPLE, {
      ...DEFAULT_LEARNING_FILTERS,
      confidence: "pending",
    })
    expect(byConf).toHaveLength(1)

    const recent = filterLearningInsights(SAMPLE, {
      ...DEFAULT_LEARNING_FILTERS,
      timeRange: "7d",
    })
    expect(recent).toHaveLength(1)
    expect(recent[0]?.id).toBe("a")
  })
})
