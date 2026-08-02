import { describe, expect, it } from "vitest"

import { extractApiErrorMessage } from "@/lib/api-error-message"

describe("API error humanization", () => {
  it("extracts message from legacy Python-repr error strings", () => {
    const payload = {
      success: false,
      error:
        "{'message': 'This workflow already has a run in progress (a4886eb2…). Open that run to monitor or cancel it, then try again.', 'detail': 'This workflow already has a run in progress (a4886eb2…). Open that run to monitor or cancel it, then try again.', 'active_run_id': 'a4886eb2-1111-2222-3333-444444444444'}",
      code: "VALIDATION_ERROR",
      details: {},
    }
    const message = extractApiErrorMessage(payload)
    expect(message).toContain("run in progress")
    expect(message).toContain("a4886eb2")
    expect(message).not.toContain("{'message'")
  })

  it("reads structured detail.message", () => {
    const payload = {
      error:
        "This workflow already has a run in progress (a4886eb2…). Open that run to cancel it, then try again.",
      detail: {
        message:
          "This workflow already has a run in progress (a4886eb2…). Open that run to cancel it, then try again.",
        active_run_id: "a4886eb2-1111-2222-3333-444444444444",
      },
      details: { active_run_id: "a4886eb2-1111-2222-3333-444444444444" },
    }
    const message = extractApiErrorMessage(payload)
    expect(message).toContain("run in progress")
    expect(message).toContain("a4886eb2")
  })
})
