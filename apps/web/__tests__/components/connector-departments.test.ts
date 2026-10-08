import { describe, expect, it } from "vitest"
import { CONNECTOR_DEPARTMENTS, connectorInDepartment } from "@/components/connectors/department-filter"
import { CONNECTOR_CATEGORY_META } from "@/lib/connectors"

describe("connector departments", () => {
  it("map only to real catalog categories", () => {
    const known = new Set(Object.keys(CONNECTOR_CATEGORY_META))
    for (const department of CONNECTOR_DEPARTMENTS) {
      expect(department.categories.filter((c) => !known.has(c))).toEqual([])
    }
  })

  it("cover every catalog category", () => {
    const covered = new Set(CONNECTOR_DEPARTMENTS.flatMap((d) => d.categories))
    expect(Object.keys(CONNECTOR_CATEGORY_META).filter((c) => !covered.has(c))).toEqual([])
  })

  it("filters by department and shows everything without one", () => {
    expect(connectorInDepartment("Payments / Finance", "finance")).toBe(true)
    expect(connectorInDepartment("Payments / Finance", "sales")).toBe(false)
    expect(connectorInDepartment("", "sales")).toBe(false)
    expect(connectorInDepartment(undefined, null)).toBe(true)
  })
})
