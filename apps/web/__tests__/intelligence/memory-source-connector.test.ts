import { describe, expect, it } from "vitest"
import type { PromotionCandidate } from "@/lib/api"
import { candidateToMemoryItem, sourceConnectorLabel } from "@/components/intelligence/knowledge/memory-model"

const base = {
  id: "c1",
  org_id: "o1",
  source_table: "agent_memories",
  content: "Invoices are net 30",
  status: "pending_approval",
} as unknown as PromotionCandidate

describe("Knowledge › Memory: where each memory came from", () => {
  it("names the connected tool first when the backend recorded it", () => {
    const item = candidateToMemoryItem(
      { ...base, sourceConnector: { name: "Sales HubSpot", type: "HubSpot", connected: true } } as PromotionCandidate,
      "pending",
      {},
    )
    expect(item.sources[0]).toEqual({ label: "From Sales HubSpot (HubSpot)", role: "source" })
    expect(item.sources[1].label).toBe("Agent memory")
  })

  it("says when that tool is now disconnected", () => {
    expect(
      sourceConnectorLabel({ ...base, sourceConnector: { name: "HubSpot", type: "HubSpot", connected: false } } as PromotionCandidate),
    ).toBe("From HubSpot, now disconnected")
  })

  it("never guesses a tool when no lineage was recorded", () => {
    expect(sourceConnectorLabel(base)).toBeNull()
    expect(candidateToMemoryItem(base, "pending", {}).sources[0].label).toBe("Agent memory")
  })
})
