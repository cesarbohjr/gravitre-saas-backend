/** Pull a human message out of a Python-repr / JSON-ish error blob. */
export function humanizeEmbeddedErrorString(raw: string): string | null {
  const text = raw.trim()
  if (!text) return null
  const nestedMatch = text.match(/['"](?:message|detail)['"]\s*:\s*['"]([^'"]+)['"]/)
  if (nestedMatch?.[1]?.trim()) return nestedMatch[1].trim()
  const activeMatch = text.match(/['"]active_run_id['"]\s*:\s*['"]([0-9a-f-]{8,})['"]/i)
  if (activeMatch?.[1] && /run in progress|active run/i.test(text)) {
    return activeRunConflictMessage(activeMatch[1])
  }
  return null
}

export function activeRunConflictMessage(activeRunId: string): string {
  return (
    `This workflow already has a run in progress (${activeRunId.slice(0, 8)}…). ` +
    "Open that run to cancel it, then try again."
  )
}

/** Normalize API error JSON into a toast-safe string. */
export function extractApiErrorMessage(payload: unknown): string | null {
  if (!payload || typeof payload !== "object") return null
  const data = payload as Record<string, unknown>

  const detail = data.detail
  if (typeof detail === "string" && detail.trim()) {
    return humanizeEmbeddedErrorString(detail) ?? detail
  }
  if (detail && typeof detail === "object") {
    const detailObj = detail as Record<string, unknown>
    const detailMessage = detailObj.message
    if (typeof detailMessage === "string" && detailMessage.trim()) return detailMessage
    const nestedDetail = detailObj.detail
    if (typeof nestedDetail === "string" && nestedDetail.trim()) {
      return humanizeEmbeddedErrorString(nestedDetail) ?? nestedDetail
    }
    const activeRunId = detailObj.active_run_id
    if (typeof activeRunId === "string" && activeRunId.trim()) {
      return activeRunConflictMessage(activeRunId)
    }
  }
  if (Array.isArray(detail)) {
    const first = detail[0]
    if (first && typeof first === "object") {
      const msg = (first as Record<string, unknown>).msg
      if (typeof msg === "string" && msg.trim()) return msg
    }
  }

  const details = data.details
  if (details && typeof details === "object") {
    const detailsObj = details as Record<string, unknown>
    const detailsMessage = detailsObj.message ?? detailsObj.reason
    if (typeof detailsMessage === "string" && detailsMessage.trim()) return detailsMessage
    const activeRunId = detailsObj.active_run_id
    if (typeof activeRunId === "string" && activeRunId.trim()) {
      return activeRunConflictMessage(activeRunId)
    }
  }

  const error = data.error
  if (typeof error === "string" && error.trim()) {
    return humanizeEmbeddedErrorString(error) ?? error
  }
  if (error && typeof error === "object") {
    const errorObj = error as Record<string, unknown>
    const nested = errorObj.message ?? errorObj.detail
    if (typeof nested === "string" && nested.trim()) {
      return humanizeEmbeddedErrorString(nested) ?? nested
    }
    if (typeof errorObj.code === "string" && errorObj.code.trim()) return errorObj.code
  }

  const message = data.message
  if (typeof message === "string" && message.trim()) return message
  return null
}
