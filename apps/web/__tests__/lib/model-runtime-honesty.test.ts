import { describe, expect, it } from "vitest"
import { presentModelRuntime, summarizeOrgTraining } from "@/lib/intelligence/model-runtime-honesty"

describe("presentModelRuntime (Module C / Pilot D)", () => {
  it("labels heuristic as Estimate, not TRAINED", () => {
    const p = presentModelRuntime({
      runtime_status: "heuristic",
      catalog_status: "trained",
      artifact_loaded: false,
    })
    expect(p.kind).toBe("heuristic")
    expect(p.label).toMatch(/Estimate/i)
    expect(p.label).not.toMatch(/^TRAINED$/i)
  })

  it("does not treat catalog TRAINED without runtime as live model", () => {
    const p = presentModelRuntime({
      catalog_status: "trained",
      artifact_loaded: false,
    })
    expect(p.kind).toBe("unknown")
    expect(p.label).toBe("Catalog only")
  })

  it("requires artifact for model_loaded when runtime says trained", () => {
    const without = presentModelRuntime({
      runtime_status: "trained",
      artifact_loaded: false,
      catalog_status: "trained",
    })
    expect(without.kind).toBe("heuristic")

    const withArtifact = presentModelRuntime({
      runtime_status: "trained",
      artifact_loaded: true,
      catalog_status: "trained",
    })
    expect(withArtifact.kind).toBe("model_loaded")
    expect(withArtifact.label).toMatch(/artifact loaded/i)
  })

  it("maps data_gate to Insufficient data", () => {
    const p = presentModelRuntime({ runtime_status: "data_gate", catalog_status: "data_gate" })
    expect(p.kind).toBe("data_gate")
    expect(p.label).toBe("Insufficient data")
  })

  it("summarizeOrgTraining counts kinds", () => {
    const { counts } = summarizeOrgTraining({
      a: { model_name: "a", catalog_status: "trained", runtime_status: "heuristic" },
      b: {
        model_name: "b",
        catalog_status: "trained",
        runtime_status: "trained",
        artifact_loaded: true,
      },
      c: { model_name: "c", catalog_status: "data_gate", runtime_status: "data_gate" },
    })
    expect(counts.heuristic).toBe(1)
    expect(counts.model_loaded).toBe(1)
    expect(counts.data_gate).toBe(1)
  })
})
