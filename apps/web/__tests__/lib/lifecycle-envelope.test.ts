import { describe, expect, it } from "vitest"
import {
  actionStatusFromLifecycle,
  mergeTaskStateMonotonic,
  parseLifecycleEnvelope,
  resolveTaskActionStatus,
} from "@/lib/lifecycle-envelope"

describe("parseLifecycleEnvelope", () => {
  it("maps backend customer_stage", () => {
    const view = parseLifecycleEnvelope({
      lifecycle_envelope: {
        customer_stage: "verifying",
        semantic_stage: "EXECUTING",
        execution_verified: false,
        uncertain: false,
      },
    })
    expect(view?.customerStage).toBe("verifying")
  })
})

describe("actionStatusFromLifecycle", () => {
  it("covers approval and terminal states", () => {
    expect(
      actionStatusFromLifecycle({
        customerStage: "accepted",
        semanticStage: "AWAITING_APPROVAL",
        executionVerified: false,
        uncertain: false,
      }),
    ).toBe("pending_approval")
    expect(
      actionStatusFromLifecycle({
        customerStage: "verified",
        semanticStage: "COMPLETED",
        executionVerified: true,
        uncertain: false,
      }),
    ).toBe("completed")
    expect(
      actionStatusFromLifecycle({
        customerStage: "uncertain",
        semanticStage: "OUTCOME_UNCERTAIN",
        executionVerified: false,
        uncertain: true,
      }),
    ).toBe("verifying")
  })
})

describe("resolveTaskActionStatus", () => {
  it("prefers lifecycle envelope over legacy pending status", () => {
    const status = resolveTaskActionStatus(
      { lifecycle_envelope: { customer_stage: "failed", semantic_stage: "FAILED" } },
      { status: "running" },
    )
    expect(status).toBe("failed")
  })
})

describe("mergeTaskStateMonotonic", () => {
  it("drops stale background patch when task_revision regresses", () => {
    const current = { turn_id: "t2", task_revision: 5, lifecycle_envelope: { customer_stage: "verified" } }
    const stale = { turn_id: "t2", task_revision: 3, lifecycle_envelope: { customer_stage: "verifying" } }
    expect(mergeTaskStateMonotonic(current, stale)).toEqual(current)
  })

  it("applies newer revision", () => {
    const current = { turn_id: "t2", task_revision: 3 }
    const newer = { turn_id: "t2", task_revision: 4, lifecycle_envelope: { customer_stage: "verified" } }
    expect(mergeTaskStateMonotonic(current, newer)?.task_revision).toBe(4)
  })
})
