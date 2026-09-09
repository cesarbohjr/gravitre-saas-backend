import { describe, expect, it } from "vitest"
import {
  buildOrgSourceAssignmentPayload,
  buildPackAssignmentPayload,
  formatKnowledgeAssignError,
  packAvailabilityLabel,
} from "@/lib/agent-knowledge-assign"
describe("agent-knowledge-assign", () => {
  it("builds pack assignment payload with fabric metadata", () => {
    const payload = buildPackAssignmentPayload({
      id: "pack.sales",
      name: "Sales Intelligence",
      department: "sales",
    })
    expect(payload.sourceType).toBe("knowledge_pack")
    expect(payload.sourceId).toBe("pack.sales")
    expect(payload.metadata).toEqual({ fabric_pack: true })
  })

  it("builds org rag source assignment payload", () => {
    const payload = buildOrgSourceAssignmentPayload({ id: "src-1", name: "Test Sales Knowledge" })
    expect(payload.sourceType).toBe("rag_source")
    expect(payload.sourceId).toBe("src-1")
  })

  it("formats permission errors without generic save copy", () => {
    const forbidden = Object.assign(new Error("Forbidden"), { status: 403, name: "ApiRequestError" })
    const msg = formatKnowledgeAssignError(forbidden, "Sales Intelligence")
    expect(msg).toContain("Sales Intelligence")
    expect(msg).not.toContain("Failed to save knowledge packs")
    expect(msg).toContain("permission")
  })

  it("maps hold packs to coming soon and not assignable", () => {
    const avail = packAvailabilityLabel({ hold: true })
    expect(avail.assignable).toBe(false)
    expect(avail.customerLabel).toBe("Coming soon")
  })
})
