import { describe, expect, it } from "vitest"
import {
  applyEnrichmentWorkflowSetup,
  isEnrichmentWorkflowCanvas,
} from "@/lib/workflows/enrichment-workflow-setup"
import type { CanvasWorkflowNode } from "@/lib/workflows/builder-persistence"

function node(
  partial: Partial<CanvasWorkflowNode> & Pick<CanvasWorkflowNode, "id" | "type" | "name">,
): CanvasWorkflowNode {
  return {
    config: {},
    position: { x: 0, y: 0 },
    connections: [],
    ...partial,
  }
}

describe("enrichment-workflow-setup", () => {
  it("detects apollo/clay/hubspot canvases", () => {
    expect(
      isEnrichmentWorkflowCanvas([
        { name: "List Apollo contact lists", vendor: "apollo" },
        { name: "Push leads to Clay", vendor: "clay" },
        { name: "Add contacts to HubSpot" },
      ]),
    ).toBe(true)
  })

  it("binds Lead Enrichment Coordinator and fills instructions", () => {
    const nodes = [
      node({ id: "1", type: "task", name: "List Apollo contact lists" }),
      node({ id: "2", type: "task", name: "Search Apollo contacts in MSP" }),
      node({ id: "3", type: "agent", name: "Populate Apollo list if empty" }),
      node({ id: "4", type: "task", name: "Push leads to Clay" }),
      node({ id: "5", type: "task", name: "Pull Clay enriched outputs" }),
      node({ id: "6", type: "task", name: "Sync enriched records to HubSpot" }),
      node({ id: "7", type: "agent", name: "Add contacts to HubSpot static list" }),
    ]
    const result = applyEnrichmentWorkflowSetup(nodes, [
      {
        id: "agent-1",
        name: "Lead Enrichment Coordinator",
        capabilities: ["enrichment"],
        config: { slug: "lead-enrichment-coordinator" },
      },
    ])
    expect(result.changed).toBe(true)
    expect(result.boundAgents).toBe(2)
    expect(result.filledInstructions).toBeGreaterThanOrEqual(5)
    expect(result.nodes[0].type).toBe("connector")
    expect(result.nodes[0].selectedAction).toBe("lists.list")
    expect(result.nodes[0].config.action).toBe("apollo.lists.list")
    expect(result.nodes[2].config.agent_id).toBe("agent-1")
    expect(String(result.nodes[2].config.task)).toContain("apollo.lists.add")
    expect(String(result.nodes[6].config.task)).toContain("hubspot.lists.add_contact")
  })
})
