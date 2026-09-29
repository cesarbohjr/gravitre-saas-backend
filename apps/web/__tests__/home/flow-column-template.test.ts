import { describe, expect, it } from "vitest"
import { flowColumnTemplate } from "@/components/home/operating-flow"
import { resultSummaryFor } from "@/lib/assignments-list"

type Lanes = Parameters<typeof flowColumnTemplate>[0]

const lane = (id: Lanes[number]["id"], count: number): Lanes[number] => ({
  id,
  label: id,
  empty: "",
  ask: "",
  items: Array.from({ length: count }, (_, i) => ({ id: `${id}-${i}`, title: "x" })),
})

describe("flowColumnTemplate", () => {
  it("widens populated intervention lanes and narrows empty ones", () => {
    const template = flowColumnTemplate(
      [lane("changed", 2), lane("needs", 3), lane("running", 0), lane("risk", 1), lane("next", 3)],
      () => false,
    )
    expect(template.split(" ")).toEqual([
      "minmax(224px,1fr)",
      "minmax(248px,1.3fr)",
      "minmax(168px,0.6fr)",
      "minmax(248px,1.3fr)",
      "minmax(200px,0.85fr)",
    ])
  })

  it("keeps loading lanes at an even width", () => {
    expect(flowColumnTemplate([lane("needs", 0)], () => true)).toBe("minmax(200px,1fr)")
  })
})

describe("resultSummaryFor", () => {
  it("only reports a result the job itself summarised", () => {
    expect(resultSummaryFor("completed", "Six accounts flagged", "Churn scan")).toBe("Six accounts flagged")
    expect(resultSummaryFor("running", "Six accounts flagged", "Churn scan")).toBeUndefined()
    expect(resultSummaryFor("completed", undefined, "Churn scan")).toBeUndefined()
  })

  it("drops summaries that just repeat the title, brief or a placeholder", () => {
    expect(resultSummaryFor("completed", "Churn scan", "Churn scan")).toBeUndefined()
    expect(resultSummaryFor("completed", "Scan churn", "Churn scan", "Scan churn")).toBeUndefined()
    expect(resultSummaryFor("completed", "Agent task", "Churn scan")).toBeUndefined()
  })
})
