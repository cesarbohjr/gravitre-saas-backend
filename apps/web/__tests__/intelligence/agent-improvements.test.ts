import { describe, expect, it } from "vitest"
import {
  EMPTY_IMPROVEMENT_SELECTION,
  buildAgentModelChoices,
  buildImprovementRequest,
  isStepConfirmed,
  summarizeStep,
  type AgentImprovementSelection,
  type AgentImprovementState,
  type AgentImprovementStep,
} from "@/lib/intelligence/agent-improvements"

function select(patch: Partial<AgentImprovementSelection>): AgentImprovementSelection {
  return { ...EMPTY_IMPROVEMENT_SELECTION, ...patch }
}

const state: AgentImprovementState = {
  agentId: "a1",
  name: "Sales",
  storage: "agent",
  model: "gpt-5.5",
  trainedModelId: "ft-1",
  instructions: [{ id: "i1", name: "Model Studio note", content: "Be brief." }],
  knowledgeSourceIds: ["src-1"],
  supportsKnowledge: true,
}

function step(patch: Partial<AgentImprovementStep>): AgentImprovementStep {
  return { kind: "model", status: "applied", message: "", target: null, verified: true, ...patch }
}

describe("buildAgentModelChoices", () => {
  it("drops auto and duplicates and keeps order", () => {
    const choices = buildAgentModelChoices([
      { id: "auto", label: "Auto" },
      { id: "gpt-5.5", label: "GPT-5.5" },
      { id: "gpt-5.5", label: "dup" },
      { id: "claude-sonnet-4-6", label: "Claude Sonnet 4.6", description: "Best for writing" },
    ])
    expect(choices.map((c) => c.id)).toEqual(["gpt-5.5", "claude-sonnet-4-6"])
    expect(choices[1].description).toBe("Best for writing")
  })
})

describe("buildImprovementRequest", () => {
  it("requires at least one improvement", () => {
    expect(buildImprovementRequest(EMPTY_IMPROVEMENT_SELECTION)).toEqual({
      ok: false,
      error: "Choose at least one improvement.",
    })
  })

  it("rejects a checked improvement with no value", () => {
    const res = buildImprovementRequest(select({ instruction: { enabled: true, text: "   " } }))
    expect(res.ok).toBe(false)
    const model = buildImprovementRequest(select({ model: { enabled: true, value: "" } }))
    expect(model.ok).toBe(false)
  })

  it("ignores unchecked values and builds the body for checked ones", () => {
    const res = buildImprovementRequest(
      select({
        instruction: { enabled: true, text: "  Be brief.  " },
        model: { enabled: false, value: "gpt-5.5" },
        fineTune: { enabled: true, id: "ft-1" },
        knowledge: { enabled: true, ids: ["src-1", "src-1", " "] },
      }),
    )
    expect(res).toEqual({
      ok: true,
      body: { instruction: { content: "Be brief." }, trainedModelId: "ft-1", knowledgeSourceIds: ["src-1"] },
    })
  })

  it("blocks knowledge when the agent cannot take it", () => {
    const res = buildImprovementRequest(select({ knowledge: { enabled: true, ids: ["src-1"] } }), {
      supportsKnowledge: false,
    })
    expect(res.ok).toBe(false)
  })
})

describe("isStepConfirmed", () => {
  const request = { instruction: { content: "Be brief." } }

  it("checks each kind against the re-fetched state", () => {
    expect(isStepConfirmed(step({ kind: "model", target: "gpt-5.5" }), state, request)).toBe(true)
    expect(isStepConfirmed(step({ kind: "model", target: "gpt-5.4-mini" }), state, request)).toBe(false)
    expect(isStepConfirmed(step({ kind: "fine_tune", target: "ft-1" }), state, request)).toBe(true)
    expect(isStepConfirmed(step({ kind: "knowledge", target: "src-2" }), state, request)).toBe(false)
    expect(isStepConfirmed(step({ kind: "instruction", target: "Model Studio note" }), state, request)).toBe(true)
  })

  it("never confirms a failed step or missing state", () => {
    expect(isStepConfirmed(step({ kind: "model", target: "gpt-5.5", status: "failed" }), state, request)).toBe(false)
    expect(isStepConfirmed(step({ kind: "model", target: "gpt-5.5" }), null, request)).toBe(false)
  })
})

describe("summarizeStep", () => {
  it("uses friendly names and outcome", () => {
    const line = summarizeStep(step({ kind: "model", target: "gpt-5.5" }), true, { models: { "gpt-5.5": "GPT-5.5" } })
    expect(line).toEqual({ label: "Model: GPT-5.5", outcome: "confirmed", detail: "Applied and confirmed." })
    expect(summarizeStep(step({ status: "failed", message: "Nope", target: "x" }), false).outcome).toBe("failed")
    expect(summarizeStep(step({ target: "x" }), false).outcome).toBe("not_confirmed")
  })
})
