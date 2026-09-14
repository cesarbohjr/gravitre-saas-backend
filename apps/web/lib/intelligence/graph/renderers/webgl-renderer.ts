/**
 * I2 — WebGL renderer adapter placeholder.
 * Sigma.js or raw WebGL may be wired here in a later phase; graph semantics stay in IntelligenceGraph.
 */
import type { GraphRenderer } from "../graph-renderer"
import { DomSvgGraphRenderer } from "../graph-renderer"

/** Fallback delegates to DOM/SVG until dedicated WebGL node/edge pipeline ships. */
export class WebGlGraphRenderer implements GraphRenderer {
  readonly id = "webgl"
  private readonly fallback = new DomSvgGraphRenderer()

  prepare(input: Parameters<GraphRenderer["prepare"]>[0]) {
    return this.fallback.prepare(input)
  }
}
