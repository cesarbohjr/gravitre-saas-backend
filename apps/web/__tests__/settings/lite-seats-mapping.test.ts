import { describe, expect, it } from "vitest"
import {
  filterDepartments,
  knowledgePackOptions,
  liteTotals,
  pageSlice,
  planLabel,
  seatBarWidth,
  toOptions,
  type LiteDepartment,
} from "@/lib/settings-api/lite"

const dept = (id: string, name: string, alloc: number, used: number): LiteDepartment => ({
  id,
  name,
  lite_seat_allocation: alloc,
  used_seats: used,
})

describe("Lite seats mapping", () => {
  it("shows Unlimited with the real plan name when the plan has no cap", () => {
    const t = liteTotals({
      summary: { included: null, included_display: "Unlimited", unlimited: true, allocated: 3, used: 1, plan_code: "command" },
      departments: [dept("a", "Sales", 2, 1), dept("b", "Ops", 1, 0)],
    })
    expect(t).toEqual({ includedLabel: "Unlimited", planLabel: "Command plan", allocated: 3, departments: 2, used: 1 })
  })

  it("shows the real included number and never invents a plan", () => {
    const t = liteTotals({ summary: { included: 5, included_display: "5", unlimited: false, allocated: 0, used: 0 }, departments: [] })
    expect(t.includedLabel).toBe("5")
    expect(t.planLabel).toBeNull()
    expect(planLabel("")).toBeNull()
    expect(planLabel("control")).toBe("Control plan")
  })

  it("falls back to department sums when the summary is missing", () => {
    const t = liteTotals({ departments: [dept("a", "Sales", 2, 1), dept("b", "Ops", 3, 2)] })
    expect(t.allocated).toBe(5)
    expect(t.used).toBe(3)
  })

  it("draws no bar for unallocated or unused departments and caps at 100%", () => {
    expect(seatBarWidth(0, 0)).toBe("0%")
    expect(seatBarWidth(0, 4)).toBe("0%")
    expect(seatBarWidth(1, 100)).toBe("4%")
    expect(seatBarWidth(5, 2)).toBe("100%")
  })

  it("searches by name and pages 10 at a time", () => {
    const rows = Array.from({ length: 23 }, (_, i) => dept(String(i), i % 2 ? `Sales ${i}` : `Ops ${i}`, 1, 0))
    expect(filterDepartments(rows, "sales").length).toBe(11)
    const p3 = pageSlice(rows, 3)
    expect(p3).toMatchObject({ page: 3, pageCount: 3, from: 21, to: 23, total: 23 })
    expect(p3.rows).toHaveLength(3)
    expect(pageSlice([], 4)).toMatchObject({ page: 1, pageCount: 1, from: 0, to: 0, total: 0 })
  })

  it("builds pickers from real lists only", () => {
    expect(toOptions([{ id: "w2", name: "Zeta" }, { id: "w1", name: "Alpha" }, { id: "w1", name: "Dup" }])).toEqual([
      { id: "w1", name: "Alpha" },
      { id: "w2", name: "Zeta" },
    ])
    expect(
      knowledgePackOptions([
        { installedEntityId: "rag-1", asset: { title: "Brand voice", assetType: "knowledge_pack" } },
        { installedEntityId: "wf-1", asset: { title: "Lead routing", assetType: "workflow" } },
        { installedEntityId: null, asset: { title: "Broken", assetType: "knowledge_pack" } },
      ]),
    ).toEqual([{ id: "rag-1", name: "Brand voice" }])
  })
})
