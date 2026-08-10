/**
 * Parse /api/voice/tts failure JSON (FastAPI detail + Next proxy wrapper).
 * Kept free of fetcher/supabase imports so unit tests stay light.
 *
 * `detail` is always customer-safe copy for UI — never upstream JSON blobs.
 */

export type TtsSynthesizeError = {
  ok: false
  status: number
  errorClass: string | null
  billingIssue: boolean
  detail: string
  /** Provider not configured / entitlement miss — caller may fall back to browser TTS. */
  disabled?: boolean
}

const BILLING_MESSAGE = "Voice paused — credits or payment needed"
const SERVICE_MESSAGE = "Voice unavailable right now. Try again in a moment."

function looksTechnical(text: string): boolean {
  const t = text.trim()
  if (!t) return true
  if (t.startsWith("{") || t.startsWith("[")) return true
  if (/["']detail["']\s*:/.test(t)) return true
  if (
    /payment_required|paid_plan_required|error_class|billing_issue|upstream_status|qa_force_voice/i.test(
      t,
    )
  ) {
    return true
  }
  if (/ElevenLabs|Deepgram|TTS failed\s*\(|\bupstream\b|\bHTTP\s*\d{3}\b/i.test(t)) return true
  return false
}

/** Customer UI never sees upstream provider/ops text — only calm fixed copy. */
function customerSafeDetail(billingIssue: boolean, _rawDetail: string): string {
  return billingIssue ? BILLING_MESSAGE : SERVICE_MESSAGE
}

export function parseTtsErrorBody(raw: unknown, status: number): TtsSynthesizeError {
  let detail = `TTS failed (${status})`
  let errorClass: string | null = null
  let billingIssue = status === 402

  const dig = (node: unknown): void => {
    if (!node || typeof node !== "object") return
    const obj = node as Record<string, unknown>
    if (typeof obj.error_class === "string") errorClass = obj.error_class
    if (typeof obj.billing_issue === "boolean") billingIssue = obj.billing_issue
    if (
      obj.type === "payment_required" ||
      obj.code === "payment_required" ||
      obj.code === "paid_plan_required" ||
      obj.status === "payment_required"
    ) {
      billingIssue = true
      if (!errorClass) errorClass = "billing"
    }
    // App http_exception_handler: { success:false, error, details, detail:{message,…} }
    if (typeof obj.error === "string" && obj.error.trim() && !looksTechnical(obj.error)) {
      detail = obj.error.trim()
    }
    if (typeof obj.message === "string" && obj.message.trim() && !looksTechnical(obj.message)) {
      detail = obj.message.trim()
    }
    if (obj.details && typeof obj.details === "object") {
      dig(obj.details)
    }
    if (typeof obj.detail === "string" && obj.detail.trim()) {
      const rawDetail = obj.detail.trim()
      if (rawDetail.startsWith("{") || rawDetail.startsWith("[")) {
        try {
          dig(JSON.parse(rawDetail))
          return
        } catch {
          // plain string detail
        }
      }
      if (!looksTechnical(rawDetail)) detail = rawDetail
      return
    }
    if (obj.detail && typeof obj.detail === "object") {
      dig(obj.detail)
    }
  }

  dig(raw)
  if (!errorClass && billingIssue) errorClass = "billing"
  if (errorClass === "billing") billingIssue = true

  return {
    ok: false,
    status,
    errorClass,
    billingIssue,
    detail: customerSafeDetail(billingIssue, detail),
  }
}
