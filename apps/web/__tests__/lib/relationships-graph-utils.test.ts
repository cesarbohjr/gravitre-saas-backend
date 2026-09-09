import { describe, expect, it } from "vitest"
import {
  collectRelationshipTypes,
  countNeedsReview,
  countNewThisWeek,
  entityKey,
  filterAndSortRelationships,
  makeLabelFor,
  readNumber,
} from "@/lib/relationships-graph/utils"
import { findRelationshipPaths } from "@/lib/relationships-graph/pathfinding"

describe("relationships-graph utils", () => {
  const labelFor = makeLabelFor({ term_a: "Acme Term" })

  const rows = [
    {
      id: "1",
      source_entity_type: "glossary_term",
      source_entity_id: "term_a",
      target_entity_type: "agent",
      target_entity_id: "agent_1",
      relationship_type: "used_by",
      confidence: 0.4,
      evidence_count: 1,
      created_at: new Date().toISOString(),
    },
    {
      id: "2",
      source_entity_type: "agent",
      source_entity_id: "agent_1",
      target_entity_type: "department",
      target_entity_id: "dept_1",
      relationship_type: "associated_with",
      confidence: 0.9,
      evidence_count: 5,
      created_at: "2020-01-01T00:00:00.000Z",
    },
  ]

  it("builds stable entity keys", () => {
    expect(entityKey("glossary_term", "term_a")).toBe("glossary_term::term_a")
  })

  it("filters by query and type", () => {
    const filtered = filterAndSortRelationships(rows, {
      query: "Acme",
      typeFilter: "all",
      sortKey: "confidence",
      labelFor,
    })
    expect(filtered).toHaveLength(1)
    expect(filtered[0].id).toBe("1")
  })

  it("collects relationship types", () => {
    expect(collectRelationshipTypes(rows)).toEqual(["associated_with", "used_by"])
  })

  it("counts needs review from confidence and evidence heuristics", () => {
    expect(countNeedsReview(rows)).toBe(1)
  })

  it("counts new this week from created_at", () => {
    expect(countNewThisWeek(rows)).toBe(1)
  })

  it("readNumber coerces safely", () => {
    expect(readNumber("0.82")).toBe(0.82)
    expect(readNumber(undefined, 3)).toBe(3)
  })
})

describe("relationships-graph pathfinding", () => {
  it("finds multi-hop paths between entities", () => {
    const rows = [
      {
        id: "a",
        source_entity_type: "glossary_term",
        source_entity_id: "t1",
        target_entity_type: "agent",
        target_entity_id: "ag1",
        relationship_type: "used_by",
      },
      {
        id: "b",
        source_entity_type: "agent",
        source_entity_id: "ag1",
        target_entity_type: "department",
        target_entity_id: "d1",
        relationship_type: "associated_with",
      },
    ]
    const paths = findRelationshipPaths(rows, "glossary_term", "t1", "department", "d1", 3)
    expect(paths.length).toBeGreaterThan(0)
    expect(paths[0]).toHaveLength(2)
  })
})
