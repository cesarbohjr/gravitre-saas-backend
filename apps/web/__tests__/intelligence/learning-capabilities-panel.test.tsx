// @vitest-environment jsdom
import React from "react"
import { renderToStaticMarkup } from "react-dom/server"
import { describe, expect, it, vi } from "vitest"

const state = vi.hoisted(() => ({ isAdmin: false }))
vi.mock("@/lib/use-org-admin", () => ({ useOrgAdmin: () => state }))
vi.mock("swr", () => ({ default: () => ({ data: {
  learningActivity: { enabled: true, activity_status: "not_verified" },
  learningCapabilities: [
    { id: "intent_classifier", label: "Intent capability", capabilities: ["routing"], manual_training_supported: true,
      data_requirement: "50 labeled queries", data_eligibility: { status: "requires_training_validation", observed_counts: {}, note: "Counts are not eligibility" }, verified_outcomes_count: null },
    { id: "sla_breach_predictor", label: "SLA capability", capabilities: [], manual_training_supported: false,
      training_unavailable_reason: "missing_training_columns", data_eligibility: { status: "unavailable", observed_counts: {}, note: "Labels unavailable" }, verified_outcomes_count: null },
  ],
  catalog: { world_model: { status: "planned" } },
  inventory: { world_model: { id: "world_model", label: "World scaffold", visibility: "admin_technical", inference_health: "not_verified" } },
}, mutate: vi.fn() }) }))
import { LearningCapabilitiesPanel } from "@/components/intelligence/learning-capabilities-panel"

describe("learning capability exposure", () => {
  it("members see capabilities and honest unknown outcomes without training or scaffolds", () => {
    state.isAdmin = false
    const html = renderToStaticMarkup(<LearningCapabilitiesPanel enabled technicalInventory />)
    expect(html).toContain("Intent capability")
    expect(html).toContain("Verified outcomes: Not verified")
    expect(html).not.toContain("Request training")
    expect(html).not.toContain("World scaffold")
  })
  it("admins see only supported training and a separate technical inventory", () => {
    state.isAdmin = true
    const html = renderToStaticMarkup(<LearningCapabilitiesPanel enabled technicalInventory />)
    expect(html.match(/Request training/g)?.length).toBe(1)
    expect(html).toContain("World scaffold")
    expect(html).toContain("Administrator technical inventory")
    expect(html).toContain("missing training columns")
  })
  it("the ordinary learning view hides advanced scaffolds even for administrators", () => {
    state.isAdmin = true
    const html = renderToStaticMarkup(<LearningCapabilitiesPanel enabled />)
    expect(html).not.toContain("World scaffold")
  })
})
