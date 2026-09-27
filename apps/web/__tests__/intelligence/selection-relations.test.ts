import { describe, expect, it } from "vitest"
import type { MapNode } from "@/components/intelligence/map/map-topology"
import { relationsForSelection } from "@/lib/intelligence/selection-relations"

const graph = {
  nodes: [
    { id: "core:gravitre", type: "core", businessLabel: "Gravitre" },
    { id: "agent:triage", type: "agent", businessLabel: "Lead triage agent" },
    { id: "entity:northwind", type: "entity", businessLabel: "Northwind Logistics" },
    { id: "entity:playbook", type: "entity", businessLabel: "RevOps playbook" },
  ],
  edges: [
    { id: "e1", type: "READ_FROM", fromId: "agent:triage", toId: "entity:northwind" },
    { id: "e2", type: "USED_BY", fromId: "entity:playbook", toId: "agent:triage" },
    { id: "e3", type: "KNOWS", fromId: "core:gravitre", toId: "agent:triage" },
  ],
}

const satellite = (id: string, label: string) =>
  ({ kind: "satellite", node: { id, kind: "entity-type", label } as MapNode }) as const

describe("relationsForSelection", () => {
  it("lists only edges recorded for the selected node, in both directions", () => {
    const agent = { kind: "agent", agent: { id: "triage", name: "Lead triage agent" } } as never
    expect(relationsForSelection(agent, graph)).toEqual([
      { edgeId: "e1", verb: "Reads from", otherId: "entity:northwind", otherLabel: "Northwind Logistics", direction: "out" },
      { edgeId: "e2", verb: "Uses", otherId: "entity:playbook", otherLabel: "RevOps playbook", direction: "in" },
    ])
  })

  it("returns nothing for a node without edges or without a graph", () => {
    expect(relationsForSelection(satellite("entity:none", "None"), graph)).toEqual([])
    expect(relationsForSelection(satellite("entity:northwind", "Northwind"), undefined)).toEqual([])
    expect(relationsForSelection(null, graph)).toEqual([])
  })

  it("describes a selected edge by its endpoints", () => {
    const [relation] = relationsForSelection({ kind: "edge", edgeId: "e1", label: "reads" }, graph)
    expect(relation?.otherLabel).toBe("Lead triage agent → Northwind Logistics")
    expect(relation?.verb).toBe("Reads from")
  })
})
