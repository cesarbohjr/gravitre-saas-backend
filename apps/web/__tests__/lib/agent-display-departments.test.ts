import { describe, expect, it } from "vitest"
import { normalizeAgentDepartment } from "@/lib/agent-display"
import {
  mapApiDepartmentToFleet,
  mapFleetDepartmentToApi,
} from "@/lib/agent-identity-bridge"
import { FLEET_DEPARTMENT_ORDER } from "@/components/agents/fleet-v4/fleet-department-dnd"

describe("normalizeAgentDepartment", () => {
  it("preserves fleet department labels instead of collapsing to Operations", () => {
    expect(normalizeAgentDepartment("Engineering")).toBe("Engineering")
    expect(normalizeAgentDepartment("Customer Success")).toBe("Customer Success")
    expect(normalizeAgentDepartment("Security")).toBe("Security")
    expect(normalizeAgentDepartment("General")).toBe("General")
    expect(normalizeAgentDepartment("Marketing")).toBe("Marketing")
  })

  it("round-trips every fleet lane through API labels", () => {
    for (const id of FLEET_DEPARTMENT_ORDER) {
      const label = mapFleetDepartmentToApi(id)
      const normalized = normalizeAgentDepartment(label)
      expect(mapApiDepartmentToFleet(normalized).id).toBe(id)
    }
  })
})
