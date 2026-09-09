import { describe, expect, it } from "vitest"
import {
  collectRelationshipTypes,
  countNeedsReview,
  countNewThisWeek,
  entityKey,
  filterAndSortRelationships,
  isSmokeTestEntityId,
  makeLabelFor,
  readNumber,
  relationshipTouchesSmoke,
} from "@/lib/relationships-graph/utils"
import { relationshipTypeLabel } from "@/lib/learning-ui-copy"
import { findRelationshipPaths } from "@/lib/relationships-graph/pathfinding"
import { findLearnedEntityMatches } from "@/lib/relationships-graph/match-candidates"

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

  it("uses API labels when present", () => {
    const labelFor = makeLabelFor(
      {},
      new Map([["agent::agent_1", "Churn Monitoring Agent"]]),
    )
    expect(labelFor("agent", "agent_1")).toBe("Churn Monitoring Agent")
  })

  it("filters smoke test relationships by default", () => {
    const rows = [
      {
        id: "1",
        source_entity_type: "customer",
        source_entity_id: "smoke-churn-acct-001",
        target_entity_type: "agent",
        target_entity_id: "agent_1",
        relationship_type: "tracked-by",
      },
      {
        id: "2",
        source_entity_type: "glossary_term",
        source_entity_id: "term_a",
        target_entity_type: "agent",
        target_entity_id: "agent_1",
        relationship_type: "used_by",
      },
    ]
    const labelFor = makeLabelFor({ term_a: "Acme Term" })
    const hidden = filterAndSortRelationships(rows, {
      query: "",
      typeFilter: "all",
      sortKey: "recent",
      labelFor,
      showTestData: false,
    })
    expect(hidden).toHaveLength(1)
    expect(relationshipTouchesSmoke(rows[0])).toBe(true)
    expect(isSmokeTestEntityId("smoke-churn-acct-001")).toBe(true)
  })
})

describe("entity match candidates", () => {
  it("finds learned entity name matches", () => {
    const rows = [
      {
        id: "1",
        source_entity_type: "customer",
        source_entity_id: "cust_acme",
        target_entity_type: "agent",
        target_entity_id: "agent_1",
        relationship_type: "tracked-by",
        evidence_count: 12,
      },
    ]
    const labelFor = (_t: unknown, id: unknown) => (String(id) === "cust_acme" ? "Acme Corporation" : String(id))
    const matches = findLearnedEntityMatches("Acme", rows, labelFor)
    expect(matches).toHaveLength(1)
    expect(matches[0]?.name).toBe("Acme Corporation")
    expect(matches[0]?.matchScore).toBeGreaterThanOrEqual(60)
  })
})

describe("relationship presentation labels", () => {
  it("maps tracked-by to business language", () => {
    expect(relationshipTypeLabel("tracked-by")).toBe("Tracked by")
    expect(relationshipTypeLabel("used_by")).toBe("Used by")
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
