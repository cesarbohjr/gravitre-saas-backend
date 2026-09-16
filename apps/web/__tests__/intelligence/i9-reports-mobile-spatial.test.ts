/** @vitest-environment jsdom */
import { afterEach, describe, expect, it } from "vitest"
import {
  deleteSavedIntelligenceView,
  readSavedIntelligenceViews,
  saveIntelligenceView,
} from "@/lib/intelligence/saved-intelligence-views"
import { focusedRelationshipPaths } from "@/lib/intelligence/mobile-relationship-paths"
import { projectSpatialPoint } from "@/lib/intelligence/graph"
import type { MapTopology } from "@/components/intelligence/map/map-topology"

const ORG = "org-i9-test"

afterEach(() => {
  if (typeof window !== "undefined") {
    window.localStorage.removeItem(`gravitre.intelligence.saved-views.v1.${ORG}`)
  }
})

describe("saved-intelligence-views", () => {
  it("round-trips a saved template view without inventing metrics", () => {
    const views = saveIntelligenceView(ORG, {
      label: "Business · 30d",
      templateId: "business",
      periodDays: 30,
    })
    expect(views).toHaveLength(1)
    expect(readSavedIntelligenceViews(ORG)[0]?.templateId).toBe("business")
    expect(deleteSavedIntelligenceView(ORG, views[0]!.id)).toHaveLength(0)
  })

  it("rejects malformed stored JSON", () => {
    window.localStorage.setItem(`gravitre.intelligence.saved-views.v1.${ORG}`, "not-json")
    expect(readSavedIntelligenceViews(ORG)).toEqual([])
  })
})

describe("mobile relationship paths", () => {
  it("extracts labeled paths and skips unlabeled endpoints", () => {
    const topology: MapTopology = {
      caption: "test",
      nodes: [
        { id: "a", kind: "agent", label: "Closer", emphasis: 1 },
        { id: "b", kind: "department", label: "Sales", emphasis: 1 },
      ],
      edges: [
        { id: "e1", fromId: "a", toId: "b", state: "idle", opacity: 1, edgeType: "USED_BY" },
        { id: "e2", fromId: "missing", toId: "b", state: "idle", opacity: 1 },
      ],
    }
    const paths = focusedRelationshipPaths(topology)
    expect(paths).toHaveLength(1)
    expect(paths[0]?.fromLabel).toBe("Closer")
    expect(paths[0]?.edgeType).toContain("used")
  })
})

describe("spatial projection", () => {
  it("keeps reduced-motion callers able to skip via identity-ish center handling", () => {
    const projected = projectSpatialPoint({ x: 500, y: 260 })
    expect(Number.isFinite(projected.x)).toBe(true)
    expect(Number.isFinite(projected.y)).toBe(true)
    expect(projected).not.toEqual({ x: 0, y: 0 })
  })
})
