/** Convert structured/JSON strings into user-facing plain English. */

const PARTIAL_JSON_SUMMARY = /"summary"\s*:\s*"((?:[^"\\]|\\.)*)"/i

function stripCodeFence(text: string): string {
  const trimmed = text.trim()
  const match = trimmed.match(/^```(?:json)?\s*([\s\S]*?)```$/i)
  return match ? match[1].trim() : trimmed
}

function humanizeActionToken(action: string): string {
  const token = action.trim().replace(/_/g, " ")
  if (!token) return "No action taken"
  return token.charAt(0).toUpperCase() + token.slice(1)
}

function formatDecision(decision: unknown): string {
  if (decision == null) return ""
  if (typeof decision === "string") return decision.trim()
  if (typeof decision !== "object") return String(decision).trim()
  const record = decision as Record<string, unknown>
  const parts: string[] = []
  if (typeof record.action === "string" && record.action.trim()) {
    parts.push(humanizeActionToken(record.action))
  }
  if (typeof record.reason === "string" && record.reason.trim()) {
    parts.push(record.reason.trim())
  }
  for (const key of ["message", "summary", "explanation"]) {
    const value = record[key]
    if (typeof value === "string" && value.trim()) parts.push(value.trim())
  }
  return parts.join(" ").trim()
}

function formatRecommendedActions(actions: unknown): string {
  if (!Array.isArray(actions)) return ""
  const lines = actions
    .slice(0, 6)
    .map((item) => {
      if (typeof item === "string" && item.trim()) return `• ${item.trim()}`
      if (item && typeof item === "object") {
        const record = item as Record<string, unknown>
        const label = record.label || record.title || record.action
        if (typeof label === "string" && label.trim()) return `• ${label.trim()}`
      }
      return ""
    })
    .filter(Boolean)
  return lines.length ? `Recommended next steps:\n${lines.join("\n")}` : ""
}

export function humanizePlainEnglish(value: unknown, fallback = ""): string {
  if (value == null) return fallback
  if (typeof value === "number" || typeof value === "boolean") return String(value)

  if (typeof value === "object") {
    const record = value as Record<string, unknown>
    const parts: string[] = []
    for (const key of ["summary", "answer", "message", "explanation", "reason", "description"]) {
      const part = record[key]
      if (typeof part === "string" && part.trim()) parts.push(part.trim())
    }
    const decision = formatDecision(record.decision)
    if (decision) parts.push(decision)
    const actions = formatRecommendedActions(record.recommended_actions ?? record.recommendedActions)
    if (actions) parts.push(actions)
    if (parts.length) return parts.join("\n\n").trim()
    return fallback || "Details are available in Gravitre — ask if you want help with next steps."
  }

  const text = stripCodeFence(String(value).trim())
  if (!text) return fallback

  if (text.startsWith("{") || text.startsWith("[")) {
    try {
      const parsed = JSON.parse(text) as unknown
      const converted = humanizePlainEnglish(parsed, fallback)
      if (converted) return converted
    } catch {
      const partial = text.match(PARTIAL_JSON_SUMMARY)?.[1]?.replace(/\\"/g, '"').trim()
      if (partial) return partial
    }
  }

  return text
}

/** Polish assistant/operator copy for chat and insight panels. */
export function polishAssistantText(text: string): string {
  const normalized = humanizePlainEnglish(text, text).trim()
  if (!normalized) return text.trim()

  return normalized
    .replace(/\*\(Source:\s*[^)]+\)\*/gi, "")
    .replace(/\*\*([^*]+)\*\*/g, "$1")
    .replace(/\bat\s+\/([a-z][a-z0-9-]*)\b/gi, (_, path: string) =>
      ` on the ${path.replace(/-/g, " ")} page`,
    )
    .replace(/\n{3,}/g, "\n\n")
    .trim()
}
