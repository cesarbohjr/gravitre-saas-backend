import { describe, expect, it } from "vitest"
import { parseTtsErrorBody } from "@/lib/tts-error"

describe("parseTtsErrorBody", () => {
  it("reads FastAPI nested detail.error_class=billing", () => {
    const parsed = parseTtsErrorBody(
      {
        error: "TTS failed",
        detail: {
          detail: "ElevenLabs voice service unavailable: billing issue",
          error_class: "billing",
          billing_issue: true,
          provider: "ElevenLabs",
          upstream_status: 402,
        },
      },
      402,
    )
    expect(parsed.billingIssue).toBe(true)
    expect(parsed.errorClass).toBe("billing")
    expect(parsed.detail.toLowerCase()).toContain("billing")
  })

  it("reads stringified detail from older proxy shape", () => {
    const parsed = parseTtsErrorBody(
      {
        error: "TTS failed",
        detail: JSON.stringify({
          detail: "billing issue",
          error_class: "billing",
          billing_issue: true,
        }),
      },
      402,
    )
    expect(parsed.billingIssue).toBe(true)
    expect(parsed.errorClass).toBe("billing")
  })

  it("keeps service_failure distinct from billing", () => {
    const parsed = parseTtsErrorBody(
      {
        detail: {
          detail: "upstream 500",
          error_class: "service_failure",
          billing_issue: false,
        },
      },
      502,
    )
    expect(parsed.billingIssue).toBe(false)
    expect(parsed.errorClass).toBe("service_failure")
  })

  it("reads live http_exception_handler envelope (detail.message + details)", () => {
    const parsed = parseTtsErrorBody(
      {
        success: false,
        error:
          "ElevenLabs voice service unavailable: billing issue. Detail: qa_force_voice_error=billing",
        code: "VALIDATION_ERROR",
        details: {
          error_class: "billing",
          billing_issue: true,
          provider: "ElevenLabs",
          upstream_status: 402,
        },
        detail: {
          message:
            "ElevenLabs voice service unavailable: billing issue. Detail: qa_force_voice_error=billing",
          error_class: "billing",
          billing_issue: true,
        },
      },
      402,
    )
    expect(parsed.billingIssue).toBe(true)
    expect(parsed.errorClass).toBe("billing")
    expect(parsed.detail).toContain("qa_force_voice_error=billing")
  })
})
