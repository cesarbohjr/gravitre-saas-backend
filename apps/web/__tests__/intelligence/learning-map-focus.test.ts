import { describe, expect, it } from "vitest"
import {
  buildLearningInsightMapHref,
  buildLearningInsightVisualization,
  learningInsightNodeId,
  parseIntelligenceMapDeepLink,
} from "@/lib/intelligence/learning-map-focus"

describe("learning-map-focus", () => {
  it("normalizes learning node ids", () => {
    expect(learningInsightNodeId("l1")).toBe("learning:l1")
    expect(learningInsightNodeId("learning:l1")).toBe("learning:l1")
  })

  it("builds learns-lens visualization", () => {
    const viz = buildLearningInsightVisualization("l1")
    expect(viz.lens).toBe("learns")
    expect(viz.focusNodeIds).toEqual(["learning:l1"])
  })

  it("builds overview deep link href", () => {
    const href = buildLearningInsightMapHref("l1")
    expect(href).toContain("/intelligence?")
    expect(href).toContain("lens=learns")
    expect(href).toContain("focus=learning%3Al1")
  })

  it("parses deep link search params", () => {
    const params = new URLSearchParams("lens=learns&focus=learning:l1")
    expect(parseIntelligenceMapDeepLink(params)).toEqual({
      lens: "learns",
      focusNodeId: "learning:l1",
    })
  })
})
