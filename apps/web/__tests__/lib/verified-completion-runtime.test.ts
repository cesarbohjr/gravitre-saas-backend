import { describe, expect, it } from "vitest"
import { AI_RUNTIME_STATE_COPY, deriveAiRuntimeState } from "@/lib/gravitre-ai-runtime-state"

describe("verified completion runtime boundary", () => {
  it("shows verifying rather than completed while source proof is pending", () => {
    expect(deriveAiRuntimeState({
      status: "ready",
      executionResult: { success: true, structured: { verification: { required: true, verified: false, state: "verifying" } } },
    })).toBe("verifying")
    expect(AI_RUNTIME_STATE_COPY.verifying.label).toBe("Verifying")
  })
  it("allows completed only after verification", () => {
    expect(deriveAiRuntimeState({
      status: "ready",
      executionResult: { success: true, structured: { verification: { required: true, verified: true, state: "verified" } } },
    })).toBe("completed")
  })
})
