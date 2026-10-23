import { expect, it } from "vitest"
import { outcomePackComposition } from "@/lib/outcome-pack-composition"

it("projects declared pack components without inferring verification or measured results", () => {
  const result = outcomePackComposition({ marketplace_version: "3.0", agents: [{}], plays: [{ name: "Containment", workflow_steps: [{ type: "approval" }] }], knowledge: [{}, {}], dataset: { metrics: [{ key: "mttr" }] }, dashboard: { title: "Metrics" }, runtime_profiles: [{ status: "production_verified", actions: ["okta.users.get", "okta.users.get", "okta.users.suspend"] }], skill_bindings: { a: "skills", b: "skills" } })
  expect(result).toEqual({ agents: 1, plays: 1, knowledge: 2, metrics: 1, dashboards: 1, actions: ["okta.users.get", "okta.users.suspend"], skillPackages: ["skills"], approvalPlays: ["Containment"] })
  expect(result).not.toHaveProperty("verified")
  expect(result).not.toHaveProperty("measuredOutcomes")
})
it("handles missing or malformed config safely", () => {
  expect(outcomePackComposition(undefined)).toBeNull()
  expect(outcomePackComposition({ marketplace_version: "3.0", agents: null, plays: [null, "x"], runtime_profiles: [] })?.plays).toBe(0)
})
