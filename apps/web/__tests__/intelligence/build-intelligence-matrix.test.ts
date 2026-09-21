import { describe, expect, it } from "vitest"
import { buildIntelligenceMatrix } from "@/lib/intelligence/build-intelligence-matrix"

describe("I3 buildIntelligenceMatrix", () => {
  it("counts agents in acts lens only when type matches emphasis", () => {
    const model = buildIntelligenceMatrix([
      { id: "agent:1", type: "agent", businessLabel: "Sales agent" },
      { id: "entity:contact", type: "entity", businessLabel: "Contact", metadata: { entityType: "contact" } },
    ])

    const agentsActs = model.byKey.get("agents:acts")
    const agentsKnows = model.byKey.get("agents:knows")
    expect(agentsActs?.count).toBe(1)
    expect(agentsKnows?.count).toBe(0)
  })

  it("shows em dash signal when cell empty — count zero", () => {
    const model = buildIntelligenceMatrix([])
    for (const cell of model.cells) {
      expect(cell.count).toBe(0)
      expect(cell.topSignal).toBeNull()
    }
  })

  it("surfaces prediction as top signal in knowledge predicts cell", () => {
    const model = buildIntelligenceMatrix([
      {
        id: "prediction:p1",
        type: "prediction",
        businessLabel: "Churn risk elevated",
      },
    ])
    const cell = model.byKey.get("knowledge:predicts")
    expect(cell?.count).toBe(1)
    expect(cell?.topSignal).toBe("Churn risk elevated")
  })
})
