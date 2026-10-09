import { describe, expect, it } from "vitest"
import { councilSeats } from "@/components/agents/suite/council-preview"
import type { RosterAgent } from "@/lib/agents-roster"

function agent(id: string, department: RosterAgent["department"], extra: Partial<RosterAgent> = {}): RosterAgent {
  return {
    id,
    name: id,
    role: "",
    description: "x",
    department,
    departmentLabel: department,
    model: "",
    apps: [],
    capabilities: [],
    status: "active",
    state: "ready",
    gated: false,
    output: null,
    stats: null,
    tasksToday: 0,
    successToday: null,
    success7d: null,
    lastActiveAt: null,
    ...extra,
  }
}

describe("councilSeats", () => {
  const labels = new Map()

  it("seats the question's departments first, one real agent each", () => {
    const seats = councilSeats(
      [agent("s1", "sales"), agent("f1", "finance"), agent("m1", "marketing"), agent("s2", "sales", { tasksToday: 3 })],
      ["finance", "sales"],
      labels,
    )
    expect(seats.map((s) => s.department)).toEqual(["finance", "sales", "marketing"])
    expect(seats[1].agent?.id).toBe("s2")
    expect(seats.map((s) => s.involved)).toEqual([true, true, false])
  })

  it("leaves a department seat empty when nobody there is set up", () => {
    const seats = councilSeats([agent("o1", "operations", { state: "not_set_up" })], ["security"], labels)
    expect(seats).toHaveLength(1)
    expect(seats[0]).toMatchObject({ department: "security", agent: null, involved: true })
  })
})
