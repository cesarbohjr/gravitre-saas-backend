import { describe, expect, it } from "vitest"
import { parseTtsErrorBody } from "@/lib/tts-error"

describe("parseTtsErrorBody", () => {
  it("reads FastAPI nested detail.error_class=billing as calm copy", () => {
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
    expect(parsed.detail).toBe("Voice paused — credits or payment needed")
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
    expect(parsed.detail).toBe("Voice paused — credits or payment needed")
  })

  it("keeps service_failure distinct from billing with calm copy", () => {
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
    expect(parsed.detail).toBe("Voice unavailable right now. Try again in a moment.")
  })

  it("reads live http_exception_handler envelope without leaking QA/upstream blobs", () => {
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
    expect(parsed.detail).toBe("Voice paused — credits or payment needed")
    expect(parsed.detail).not.toContain("qa_force")
    expect(parsed.detail).not.toContain("{")
  })

  it("maps payment_required type blobs to calm billing copy", () => {
    const parsed = parseTtsErrorBody(
      {
        detail: {
          type: "payment_required",
          code: "payment_required",
          message: '{"detail":{"type":"payment_required","status":"quota_exceeded"}}',
        },
      },
      402,
    )
    expect(parsed.billingIssue).toBe(true)
    expect(parsed.detail).toBe("Voice paused — credits or payment needed")
    expect(parsed.detail).not.toMatch(/[{[]/)
  })

  it("maps ElevenLabs paid_plan_required library-voice 402 without leaking JSON", () => {
    const parsed = parseTtsErrorBody(
      {
        error:
          'ElevenLabs voice service unavailable: billing issue (insufficient credits or payment required). Upstream 402. Detail: {"detail":{"type":"payment_required","code":"paid_plan_required","message":"Free users cannot use library voices via the API. Please upgrade your subscription to use this voice.","status":"payment_required","request_id":"0ae58099f986c08ea66658d0007bfbef"}}',
        detail: {
          type: "payment_required",
          code: "paid_plan_required",
          message: "Free users cannot use library voices via the API.",
          status: "payment_required",
        },
      },
      402,
    )
    expect(parsed.billingIssue).toBe(true)
    expect(parsed.errorClass).toBe("billing")
    expect(parsed.detail).toBe("Voice paused — credits or payment needed")
    expect(parsed.detail).not.toContain("ElevenLabs")
    expect(parsed.detail).not.toContain("paid_plan_required")
    expect(parsed.detail).not.toContain("{")
  })
})
