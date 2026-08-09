/**
 * Parse /api/voice/tts failure JSON (FastAPI detail + Next proxy wrapper).
 * Kept free of fetcher/supabase imports so unit tests stay light.
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

export function parseTtsErrorBody(raw: unknown, status: number): TtsSynthesizeError {
  let detail = `TTS failed (${status})`
  let errorClass: string | null = null
  let billingIssue = status === 402

  const dig = (node: unknown): void => {
    if (!node || typeof node !== "object") return
    const obj = node as Record<string, unknown>
    if (typeof obj.error_class === "string") errorClass = obj.error_class
    if (typeof obj.billing_issue === "boolean") billingIssue = obj.billing_issue
    // App http_exception_handler: { success:false, error, details, detail:{message,…} }
    if (typeof obj.error === "string" && obj.error.trim()) {
      detail = obj.error.trim()
    }
    if (typeof obj.message === "string" && obj.message.trim()) {
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
      detail = rawDetail
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
    detail,
  }
}
