import { describe, expect, it } from "vitest"
import type { CanvasWorkflowNode } from "@/lib/workflows/builder-persistence"
import {
  evaluateNodeReadiness,
  showPathConditions,
} from "@/lib/workflows/builder-node-readiness"

function base(partial: Partial<CanvasWorkflowNode> & Pick<CanvasWorkflowNode, "type">): CanvasWorkflowNode {
  return {
    id: "n1",
    name: "Step",
    config: {},
    position: { x: 0, y: 0 },
    connections: [],
    ...partial,
  }
}

describe("builder-node-readiness", () => {
  it("requires agent_id and task for agent nodes", () => {
    const incomplete = evaluateNodeReadiness(base({ type: "agent", name: "Agent" }))
    expect(incomplete.ready).toBe(false)
    expect(incomplete.missing.some((m) => m.includes("agent"))).toBe(true)

    const ready = evaluateNodeReadiness(
      base({
        type: "agent",
        name: "Lead Enrichment",
        description: "Enrich",
        config: { agent_id: "a1", task: "Enrich leads" },
      }),
    )
    expect(ready.ready).toBe(true)
  })

  it("requires task instructions", () => {
    expect(evaluateNodeReadiness(base({ type: "task", name: "Fetch" })).ready).toBe(false)
    expect(
      evaluateNodeReadiness(
        base({ type: "task", name: "Fetch", config: { instruction: "Pull KEV feed" } }),
      ).ready,
    ).toBe(true)
  })

  it("requires connector action", () => {
    expect(
      evaluateNodeReadiness(base({ type: "connector", name: "GSC", vendor: "google_search_console" }))
        .ready,
    ).toBe(false)
    expect(
      evaluateNodeReadiness(
        base({
          type: "connector",
          name: "GSC",
          vendor: "google_search_console",
          selectedAction: "sites.list",
        }),
      ).ready,
    ).toBe(true)
  })

  it("AI decision needs named paths + instructions; not per-path conditions", () => {
    const missingPaths = evaluateNodeReadiness(
      base({
        type: "decision",
        decisionConfig: { strategy: "ai-assisted", conditions: "Pick best path" },
        outputPaths: [{ id: "p1", label: "Only one" }],
      }),
    )
    expect(missingPaths.ready).toBe(false)

    const ready = evaluateNodeReadiness(
      base({
        type: "decision",
        decisionConfig: {
          strategy: "ai-assisted",
          objective: "Route by risk",
          conditions: "Choose high vs low risk",
        },
        outputPaths: [
          { id: "p1", label: "High risk" },
          { id: "p2", label: "Low risk" },
        ],
      }),
    )
    expect(ready.ready).toBe(true)
    expect(showPathConditions("ai-assisted")).toBe(false)
  })

  it("rule-based decision requires per-path conditions (unless default)", () => {
    expect(showPathConditions("rule-based")).toBe(true)
    const incomplete = evaluateNodeReadiness(
      base({
        type: "decision",
        decisionConfig: { strategy: "rule-based", conditions: "If score > 80" },
        outputPaths: [
          { id: "p1", label: "High" },
          { id: "p2", label: "Low", isDefault: true },
        ],
      }),
    )
    expect(incomplete.ready).toBe(false)
    expect(incomplete.missing.some((m) => m.includes("When to take"))).toBe(true)

    const ready = evaluateNodeReadiness(
      base({
        type: "decision",
        decisionConfig: { strategy: "rule-based", conditions: "If score > 80" },
        outputPaths: [
          { id: "p1", label: "High", condition: "score > 80" },
          { id: "p2", label: "Low", isDefault: true },
        ],
      }),
    )
    expect(ready.ready).toBe(true)
  })
})
