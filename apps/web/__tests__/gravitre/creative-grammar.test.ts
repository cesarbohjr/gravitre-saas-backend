import { describe, expect, it } from "vitest"

describe("phase 12 creative grammar", () => {
  it("maps step statuses to grammar tones", async () => {
    const { grammarToneForStepStatus, GRAMMAR_BRAND, GRAMMAR_STEP_TONE } = await import(
      "@/components/gravitre/creative-grammar"
    )
    expect(GRAMMAR_BRAND).toBe("#16a374")
    expect(grammarToneForStepStatus("awaiting_approval")).toBe("waiting")
    expect(grammarToneForStepStatus("running")).toBe("running")
    expect(grammarToneForStepStatus("completed")).toBe("verified")
    expect(grammarToneForStepStatus("failed")).toBe("failed")
    expect(GRAMMAR_STEP_TONE.waiting).toBe("warning")
  })

  it("re-exports EvidenceChip", async () => {
    const { EvidenceChip } = await import("@/components/gravitre/creative-grammar")
    expect(EvidenceChip).toBeTypeOf("function")
  })
})
