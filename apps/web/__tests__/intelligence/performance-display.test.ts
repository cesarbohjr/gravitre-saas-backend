import { describe, expect, it } from "vitest"
import {
  outcomeHeadline,
  pickPrimaryOutcomePath,
  roiMetricDisplay,
  roiMetricIsUnknown,
  unknownStepCopy,
} from "@/lib/intelligence/performance-display"
import type { OutcomeAttributionPath } from "@/lib/api"
import type { AgentRoiMetric } from "@/types/api"

function path(presentStepCount: number, id: string): OutcomeAttributionPath {
  return {
    id,
    scopeId: id,
    scopeLabel: id,
    presentStepCount,
    complete: false,
    steps: [],
  }
}

describe("performance-display", () => {
  it("picks the path with the most present steps", () => {
    const chosen = pickPrimaryOutcomePath([path(2, "a"), path(5, "b"), path(1, "c")])
    expect(chosen?.id).toBe("b")
  })

  it("treats insufficient ROI provenance as unknown, not zero", () => {
    const metric: AgentRoiMetric = {
      label: "Hours saved",
      value: 0,
      unit: "hours",
      provenance: "insufficient_data",
    }
    expect(roiMetricIsUnknown(metric)).toBe(true)
    expect(roiMetricDisplay(metric).value).toBe("—")
    expect(roiMetricDisplay(metric).hint).toBe("Not enough verified data yet")
  })

  it("labels estimates without inventing measured status", () => {
    const metric: AgentRoiMetric = {
      label: "Hours saved",
      value: 3.5,
      unit: "hours",
      provenance: "estimate",
    }
    const display = roiMetricDisplay(metric)
    expect(display.unknown).toBe(false)
    expect(display.value).toContain("h")
    expect(display.hint.toLowerCase()).toContain("estimate")
  })

  it("uses a present outcome label and never invents a result", () => {
    expect(
      outcomeHeadline({
        id: "p",
        scopeId: "p",
        scopeLabel: "Scope only",
        presentStepCount: 2,
        complete: false,
        steps: [
          {
            kind: "action",
            title: "Action",
            label: "contacts.update",
            present: true,
            evidence: [],
          },
          {
            kind: "outcome",
            title: "Outcome",
            label: "Contact assigned",
            present: true,
            evidence: ["record 12"],
          },
        ],
      }),
    ).toBe("Contact assigned")
    expect(outcomeHeadline(null)).toBeNull()
  })

  it("maps unknown step quality notes to human copy", () => {
    expect(
      unknownStepCopy({
        kind: "outcome",
        title: "Outcome",
        label: "Not enough verified data yet",
        present: false,
        evidence: [],
        qualityNote: "INSUFFICIENT_EVIDENCE",
      }),
    ).toBe("Not enough verified evidence yet")
  })
})
