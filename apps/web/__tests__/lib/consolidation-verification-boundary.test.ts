import { describe, expect, it } from "vitest"
import { deriveAiRuntimeState } from "@/lib/gravitre-ai-runtime-state"
import { actionStatusFromLifecycle, parseLifecycleEnvelope } from "@/lib/lifecycle-envelope"

describe("unverified provider results cannot become Completed", () => {
  it("does not collapse accepted lifecycle into successful completion", () => {
    expect(deriveAiRuntimeState({status: "ready", executionResult: {
      success: true, lifecycle_envelope: {customer_stage: "accepted", execution_verified: false},
    }})).toBe("verifying")
  })
  it("a URL or success boolean is no proof for a verification-required action", () => {
    expect(deriveAiRuntimeState({status: "ready", executionResult: {
      success: true, result_url: "/runs/a", structured: {verification: {required: true, verified: true}},
    } as never})).toBe("verifying")
  })
  it("accepts attributable verifier evidence for an action", () => {
    expect(deriveAiRuntimeState({status: "ready", executionResult: {
      success: true, structured: {verification: {required: true, verified: true, method: "entity_get"}},
    } as never})).toBe("completed")
  })
  it("string false never upgrades a verified envelope", () => {
    const env = parseLifecycleEnvelope({lifecycle_envelope: {customer_stage: "verified", execution_verified: "false"}})
    expect(env?.executionVerified).toBe(false)
    expect(actionStatusFromLifecycle(env)).toBe("verifying")
  })
})
