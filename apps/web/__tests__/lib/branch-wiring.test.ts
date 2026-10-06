import { describe, expect, it } from "vitest"
import {
  appendConditionClause,
  edgeBranchesFor,
  reconcileBranchTargets,
  restoreBranchTargets,
  unroutedConnections,
} from "@/lib/workflows/branch-wiring"
import { canvasToSavePayload, type CanvasWorkflowNode } from "@/lib/workflows/builder-persistence"
import { mapStepStatusToNodeState } from "@/lib/workflows/run-monitor"

function ifNode(connections: string[], targets: Record<string, string | undefined> = {}): CanvasWorkflowNode {
  return {
    id: "if1",
    type: "if",
    name: "Ready?",
    config: { expression: "$score > 80" },
    position: { x: 0, y: 0 },
    connections,
    outputPaths: [
      { id: "true", label: "True", targetNodeId: targets.true },
      { id: "false", label: "False", isDefault: true, targetNodeId: targets.false },
    ],
  }
}

describe("branch wiring", () => {
  it("routes new connections to free branches in order", () => {
    const node = reconcileBranchTargets(ifNode(["yes", "no"]))
    expect(node.outputPaths?.map((p) => p.targetNodeId)).toEqual(["yes", "no"])
    expect(unroutedConnections(node)).toEqual([])
  })

  it("frees a branch when its connection is removed", () => {
    const node = reconcileBranchTargets(ifNode(["no"], { true: "yes", false: "no" }))
    expect(node.outputPaths?.[0].targetNodeId).toBeUndefined()
    expect(node.outputPaths?.[1].targetNodeId).toBe("no")
  })

  it("returns the same node when nothing changes", () => {
    const node = ifNode(["yes"], { true: "yes" })
    expect(reconcileBranchTargets(node)).toBe(node)
  })

  it("flags connections no branch routes to", () => {
    const node = ifNode(["yes", "no", "extra"], { true: "yes", false: "no" })
    expect(unroutedConnections(node)).toEqual(["extra"])
  })

  it("saves branch labels on edges and restores targets after server id remap", () => {
    const yes: CanvasWorkflowNode = { id: "yes", type: "agent", name: "Yes", config: {}, position: { x: 0, y: 0 }, connections: [] }
    const no: CanvasWorkflowNode = { ...yes, id: "no", name: "No" }
    const payload = canvasToSavePayload([ifNode(["yes", "no"]), yes, no])
    expect(payload.edges).toEqual([
      { fromNodeId: "if1", toNodeId: "yes", edge_type: "branch", condition: { branches: ["true"] } },
      { fromNodeId: "if1", toNodeId: "no", edge_type: "branch", condition: { branches: ["false"] } },
    ])
    const loaded = restoreBranchTargets([ifNode(["yes", "no"], { true: "stale-client-id" })], [
      { from_node_id: "if1", to_node_id: "yes", condition: { branches: ["true"] } },
      { from_node_id: "if1", to_node_id: "no", condition: { branches: ["false"] } },
    ])
    expect(loaded[0].outputPaths?.map((p) => p.targetNodeId)).toEqual(["yes", "no"])
    expect(edgeBranchesFor(loaded[0], "no")).toEqual(["false"])
  })

  it("builds AND / OR clauses with quoted text values", () => {
    const first = appendConditionClause("", { field: "steps.lead_scorer.score", operator: ">", value: "80" }, "and")
    expect(first).toBe("steps.lead_scorer.score > 80")
    expect(appendConditionClause(first, { field: "$region", operator: "==", value: "North America" }, "or")).toBe(
      "steps.lead_scorer.score > 80 or $region == 'North America'",
    )
  })

  it("shows skipped steps as not run", () => {
    expect(mapStepStatusToNodeState("skipped")).toBe("idle")
  })
})
