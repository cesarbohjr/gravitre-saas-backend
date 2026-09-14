import { describe, expect, it } from "vitest"
import {
  createInitialInteractionState,
  graphInteractionController,
} from "@/lib/intelligence/graph/graph-interaction-controller"
import { MIN_ZOOM, MAX_ZOOM } from "@/lib/intelligence/graph/types"

describe("GraphInteractionController", () => {
  it("clamps zoom within bounds", () => {
    let viewport = createInitialInteractionState().viewport
    for (let i = 0; i < 20; i += 1) {
      viewport = graphInteractionController.zoomIn(viewport)
    }
    expect(viewport.scale).toBeLessThanOrEqual(MAX_ZOOM)

    for (let i = 0; i < 20; i += 1) {
      viewport = graphInteractionController.zoomOut(viewport)
    }
    expect(viewport.scale).toBeGreaterThanOrEqual(MIN_ZOOM)
  })

  it("resets viewport to defaults", () => {
    const state = createInitialInteractionState({
      viewport: { scale: 2, translateX: 10, translateY: -5 },
    })
    const reset = graphInteractionController.resetViewport()
    expect(reset.scale).toBe(1)
    expect(reset.translateX).toBe(0)
    expect(reset.translateY).toBe(0)
    expect(state.viewport.scale).toBe(2)
  })

  it("toggles pin state", () => {
    const initial = createInitialInteractionState()
    const pinned = graphInteractionController.togglePin(initial, "agent:1", { x: 100, y: 200 })
    expect(pinned.pinnedNodeIds.has("agent:1")).toBe(true)
    expect(pinned.pinnedPositions.get("agent:1")).toEqual({ x: 100, y: 200 })
    const unpinned = graphInteractionController.togglePin(pinned, "agent:1")
    expect(unpinned.pinnedNodeIds.has("agent:1")).toBe(false)
  })

  it("fitToView returns viewport when positions exist", () => {
    const positions = new Map<string, { x: number; y: number }>([
      ["a", { x: 400, y: 200 }],
      ["b", { x: 600, y: 300 }],
    ])
    const viewport = graphInteractionController.fitToView(positions, ["a", "b"])
    expect(viewport).not.toBeNull()
    expect(viewport!.scale).toBeGreaterThan(0)
  })
})
