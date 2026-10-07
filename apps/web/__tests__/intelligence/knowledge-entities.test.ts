import { describe, expect, it } from "vitest"
import { countKnownEntities } from "@/components/intelligence/knowledge/knowledge-entities"

describe("countKnownEntities", () => {
  it("counts knowledge nodes plus each distinct end of active links", () => {
    const nodes = [{ id: "n1" }, { id: "n2" }]
    const relationships = [
      { source_entity_type: "agent", source_entity_id: "a1", target_entity_type: "term", target_entity_id: "t1" },
      { source_entity_type: "term", source_entity_id: "t1", target_entity_type: "department", target_entity_id: "d1" },
      // An end that is a knowledge node is not counted twice.
      { source_entity_type: "company", source_entity_id: "n1", target_entity_type: "agent", target_entity_id: "a1" },
    ]
    expect(countKnownEntities(nodes, relationships)).toBe(5)
  })

  it("skips archived links and test data", () => {
    const relationships = [
      { source_entity_type: "agent", source_entity_id: "a1", target_entity_type: "term", target_entity_id: "t1", archived_at: "2026-01-01" },
      { source_entity_type: "agent", source_entity_id: "smoke-a", target_entity_type: "term", target_entity_id: "t2" },
    ]
    expect(countKnownEntities([{ id: "smoke-node" }], relationships)).toBe(0)
  })
})
