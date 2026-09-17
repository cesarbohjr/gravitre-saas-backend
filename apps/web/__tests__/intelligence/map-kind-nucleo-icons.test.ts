import { createElement } from "react"
import { renderToStaticMarkup } from "react-dom/server"
import { describe, expect, it } from "vitest"
import { MAP_KIND_NUCLEO } from "@/components/intelligence/graph/nodus-graph-node"
import type { MapNodeKind } from "@/components/intelligence/map/map-topology"

const KINDS: MapNodeKind[] = [
  "department",
  "agent",
  "entity-type",
  "model",
  "signal",
  "learning",
]

describe("intelligence map Nucleo Sharp icons", () => {
  it("assigns a unique Nucleo glyph to every node kind", () => {
    const marks = KINDS.map((kind) => renderToStaticMarkup(createElement(MAP_KIND_NUCLEO[kind], { size: 24 })))
    expect(new Set(marks).size).toBe(KINDS.length)
    for (const markup of marks) {
      expect(markup).toMatch(/^<svg[\s>]/)
      expect(markup).toMatch(/<(path|circle|rect|line|polygon)\b/)
    }
  })
})
