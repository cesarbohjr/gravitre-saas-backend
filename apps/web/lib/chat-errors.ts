/** Map assistant / chat API errors to user-facing toast messages. */
export function parseChatError(error: Error): string {
  const raw = error.message?.trim() ?? ""
  if (!raw) return "Failed to send message"

  const fromBody = (() => {
    try {
      const parsed = JSON.parse(raw) as { detail?: unknown; error?: unknown }
      if (typeof parsed.detail === "string" && parsed.detail) return parsed.detail
      if (typeof parsed.error === "string" && parsed.error) return parsed.error
    } catch {
      // Response body is plain text, not JSON.
    }
    return ""
  })()

  if (fromBody) {
    if (/payment required|budget|usage limit|402/i.test(fromBody)) {
      return "AI usage limit reached — check billing settings"
    }
    if (/too many|rate limit|429/i.test(fromBody)) {
      return "Too many requests — please wait a moment"
    }
    if (/disabled|killswitch|unavailable|503/i.test(fromBody)) {
      return "AI assistant is currently unavailable"
    }
    if (/organization|org_id|forbidden|403/i.test(fromBody)) {
      return "You don't have access to this organization"
    }
    if (/unauthorized|401/i.test(fromBody)) {
      return "Please sign in again to continue"
    }
    if (/FASTAPI_BASE_URL|not configured/i.test(fromBody)) {
      return "AI assistant is not configured"
    }
    if (/unreachable|502|connection/i.test(fromBody)) {
      return "Could not reach the AI backend"
    }
    return fromBody.length <= 180 ? fromBody : `${fromBody.slice(0, 177)}...`
  }

  if (/401|unauthorized/i.test(raw)) return "Please sign in again"
  if (/402|payment required/i.test(raw)) return "Usage limit reached"
  if (/403|forbidden/i.test(raw)) return "Access denied"
  if (/429|rate limit/i.test(raw)) return "Too many requests"
  if (/503|unavailable/i.test(raw)) return "AI assistant is unavailable"
  return raw.length <= 180 ? raw : `${raw.slice(0, 177)}...`
}
