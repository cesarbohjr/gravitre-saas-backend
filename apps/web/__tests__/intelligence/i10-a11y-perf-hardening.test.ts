import { describe, expect, it } from "vitest"
import {
  accessibleGraphRows,
  buildRenderPayload,
  graphInteractionController,
  createInitialInteractionState,
  type GraphRenderer,
  type GraphRendererInput,
} from "@/lib/intelligence/graph"
import type { MapTopology } from "@/components/intelligence/map/map-topology"
import { qualityFlagToCopy } from "@/lib/intelligence/quality-copy"

const emptyInput = (): GraphRendererInput => ({
  model: {
    topology: { caption: "t", nodes: [], edges: [] },
    layout: { positions: new Map(), clusters: [], coreId: "__core__" },
    lens: "knows",
    caption: "t",
  },
  viewport: { scale: 1, translateX: 0, translateY: 0 },
  selectedNodeId: null,
  hoveredNodeId: null,
  hoveredEdgeId: null,
  highlightNodeIds: new Set(),
  dimNodeIds: new Set(),
  searchMatchIds: new Set(),
  pathHighlightIds: new Set(),
  kindFilter: null,
  reducedMotion: true,
})

describe("I10 renderer adapter", () => {
  it("swaps a mock GraphRenderer without touching graph semantics", () => {
    const mock: GraphRenderer = {
      id: "mock",
      prepare: () => ({
        nodes: [],
        edges: [],
        corePosition: { x: 1, y: 2 },
      }),
    }
    const payload = buildRenderPayload(mock, emptyInput())
    expect(mock.id).toBe("mock")
    expect(payload.corePosition).toEqual({ x: 1, y: 2 })
  })
})

describe("I10 keyboard traversal", () => {
  it("cycles selected node ids", () => {
    const start = createInitialInteractionState()
    const next = graphInteractionController.cycleKeyboardFocus(start, ["a", "b", "c"], 1)
    expect(next.selectedNodeId).toBe("a")
    const wrap = graphInteractionController.cycleKeyboardFocus(next, ["a", "b", "c"], -1)
    expect(wrap.selectedNodeId).toBe("c")
  })
})

describe("I10 accessible graph list", () => {
  it("projects topology nodes without inventing labels", () => {
    const topology: MapTopology = {
      caption: "acts",
      nodes: [{ id: "agent:1", kind: "agent", label: "Closer", emphasis: 1 }],
      edges: [],
    }
    expect(accessibleGraphRows(topology)).toEqual([
      { id: "agent:1", kind: "agent", label: "Closer", sublabel: undefined },
    ])
  })
})

describe("I10 quality copy", () => {
  it("never returns raw machine tokens for known flags", () => {
    for (const flag of ["INSUFFICIENT_DATA", "NOT_CONFIGURED", "NO_BUSINESS_LEARNING_YET"]) {
      const copy = qualityFlagToCopy(flag)
      expect(copy.includes("_")).toBe(false)
      expect(copy).not.toBe(flag)
    }
  })
})
