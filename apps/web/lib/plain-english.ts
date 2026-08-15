/** Convert structured/JSON strings into user-facing plain English. */

const PARTIAL_JSON_SUMMARY = /"summary"\s*:\s*"((?:[^"\\]|\\.)*)"/i
const PARTIAL_JSON_NAME = /"name"\s*:\s*"((?:[^"\\]|\\.)*)"/gi
const PARTIAL_JSON_ACTION = /"(?:action|tool)"\s*:\s*"((?:[^"\\]|\\.)*)"/i

function stripCodeFence(text: string): string {
  const trimmed = text.trim()
  const match = trimmed.match(/^```(?:json)?\s*([\s\S]*?)```$/i)
  return match ? match[1].trim() : trimmed
}

function humanizeActionToken(action: string): string {
  const token = action.trim().replace(/[_.]/g, " ")
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

function sampleLabels(rows: unknown[], limit = 5): string[] {
  const labels: string[] = []
  for (const row of rows.slice(0, limit)) {
    if (!row || typeof row !== "object") {
      labels.push(String(row).slice(0, 80))
      continue
    }
    const record = row as Record<string, unknown>
    const props =
      record.properties && typeof record.properties === "object"
        ? (record.properties as Record<string, unknown>)
        : record
    for (const key of ["name", "title", "subject", "email", "fullname", "dealname", "id"]) {
      const val = props[key]
      if (typeof val === "string" && val.trim()) {
        labels.push(val.trim().slice(0, 80))
        break
      }
    }
  }
  return labels.filter(Boolean)
}

function looksLikeToolEnvelope(record: Record<string, unknown>): boolean {
  return (
    "tool" in record ||
    "action" in record ||
    "success" in record ||
    "result" in record ||
    "data" in record
  )
}

function humanizeToolEnvelope(record: Record<string, unknown>): string {
  if (record.success === false || record.error) {
    const err = record.error || record.message || "tool failed"
    return `Tool error: ${String(err)}`
  }
  const action = humanizeActionToken(String(record.action || record.tool || "Tool"))
  const inner = record.result !== undefined ? record.result : record.data
  if (Array.isArray(inner)) {
    const labels = sampleLabels(inner)
    const base = `${action} returned ${inner.length} record(s).`
    return labels.length ? `${base} Including: ${labels.join(", ")}.` : base
  }
  if (inner && typeof inner === "object") {
    const nested = inner as Record<string, unknown>
    for (const key of ["contacts", "companies", "deals", "lists", "items", "results", "records"]) {
      const rows = nested[key]
      if (Array.isArray(rows)) {
        const labels = sampleLabels(rows)
        const base = `${action} returned ${rows.length} ${key}.`
        return labels.length ? `${base} Including: ${labels.slice(0, 3).join(", ")}.` : base
      }
    }
    for (const key of ["name", "title", "subject", "message", "status"]) {
      if (typeof nested[key] === "string" && String(nested[key]).trim()) {
        return `${action}: ${key}=${String(nested[key]).trim()}.`
      }
    }
  }
  return `${action} completed successfully.`
}

function extractFromPartialJson(text: string): string {
  const summary = text.match(PARTIAL_JSON_SUMMARY)?.[1]?.replace(/\\"/g, '"').trim()
  if (summary) return summary
  const names = [...text.matchAll(PARTIAL_JSON_NAME)]
    .map((m) => m[1]?.replace(/\\"/g, '"').trim())
    .filter((n): n is string => Boolean(n))
  const actionRaw = text.match(PARTIAL_JSON_ACTION)?.[1]
  const action = actionRaw ? humanizeActionToken(actionRaw) : "Tool"
  if (names.length) {
    const shown = names.slice(0, 5).join(", ")
    const more = names.length > 5 ? ` (+${names.length - 5} more)` : ""
    return `${action} returned ${names.length} item(s). Including: ${shown}${more}.`
  }
  if (text.includes('"success"') && actionRaw) {
    return `${action} completed. Structured details were returned — ask if you need the next step.`
  }
  return ""
}

export function humanizePlainEnglish(value: unknown, fallback = ""): string {
  if (value == null) return fallback
  if (typeof value === "number" || typeof value === "boolean") return String(value)

  if (Array.isArray(value)) {
    const labels = sampleLabels(value)
    if (labels.length) {
      return `Returned ${value.length} record(s). Including: ${labels.join(", ")}.`
    }
    return fallback || "Details are available in Gravitre — ask if you want help with next steps."
  }

  if (typeof value === "object") {
    const record = value as Record<string, unknown>
    if (looksLikeToolEnvelope(record)) {
      const toolText = humanizeToolEnvelope(record)
      if (toolText) return toolText
    }
    const parts: string[] = []
    for (const key of ["summary", "answer", "message", "explanation", "reason", "description"]) {
      const part = record[key]
      if (typeof part === "string" && part.trim()) {
        parts.push(humanizePlainEnglish(part, part.trim()))
      }
    }
    const decision = formatDecision(record.decision)
    if (decision) parts.push(decision)
    const actions = formatRecommendedActions(record.recommended_actions ?? record.recommendedActions)
    if (actions) parts.push(actions)
    if (parts.length) return parts.join("\n\n").trim()
    if (looksLikeToolEnvelope(record)) {
      return humanizeToolEnvelope(record)
    }
    return fallback || "Details are available in Gravitre — ask if you want help with next steps."
  }

  const text = stripCodeFence(String(value).trim())
  if (!text) return fallback

  if (text.startsWith("{") || text.startsWith("[")) {
    try {
      const parsed = JSON.parse(text) as unknown
      const converted = humanizePlainEnglish(parsed, fallback)
      if (converted && !converted.trim().startsWith("{") && !converted.trim().startsWith("[")) {
        return converted
      }
    } catch {
      const partial = extractFromPartialJson(text)
      if (partial) return partial
    }
  }

  if (text.startsWith("{") || text.startsWith("[")) {
    const partial = extractFromPartialJson(text)
    if (partial) return partial
    return fallback || "Structured tool results came back — ask if you want a plain-language summary."
  }

  return text
}

/** Format assignment deliverables, handoffs, and execution traces for operators. */
export function formatAssignmentOutput(value: unknown): string {
  const humanized = humanizePlainEnglish(value, "")
  if (!humanized) return ""
  const polished = polishAssistantText(humanized)
  // Never leave operators staring at raw JSON in assignment UIs.
  if (polished.trim().startsWith("{") || polished.trim().startsWith("[")) {
    return humanizePlainEnglish(polished, "Structured tool results came back — ask if you want a plain-language summary.")
  }
  return polished
}

/** Polish assistant/operator copy for chat and insight panels. */
export function polishAssistantText(text: string): string {
  const stripped = text
    .replace(/^\s*write_approval_required\s*$/gim, "")
    .replace(/Tool failed\s*\([a-z0-9_]+\)/gi, "")
    .replace(/^\s*[a-z][a-z0-9]*(?:_[a-z0-9]+)+\s*$/gim, "")
    .trim()
  const normalized = humanizePlainEnglish(stripped, stripped).trim()
  if (!normalized) return stripped.trim()

  return normalized
    .replace(/\*\(Source:\s*[^)]+\)\*/gi, "")
    .replace(/\*\*([^*]+)\*\*/g, "$1")
    .replace(/\bat\s+\/([a-z][a-z0-9-]*)\b/gi, (_, path: string) =>
      ` on the ${path.replace(/-/g, " ")} page`,
    )
    .replace(
      /Pipeline health cannot be fully assessed yet because/gi,
      "I can't give a full pipeline health read yet because",
    )
    .replace(/cannot be fully assessed yet because/gi, "isn't fully available yet because")
    .replace(/\bI am unable to\b/gi, "I can't")
    .replace(/\bI apologize\b/gi, "Heads up")
    .replace(/\bPlease note that\b/gi, "")
    .replace(/\bAt this time,?\s*/gi, "")
    .replace(/\bIt appears that\b/gi, "")
    .replace(/\bIn order to\b/gi, "To")
    .replace(/\bIt is recommended that you\b/gi, "I'd")
    .replace(/\bYou should consider\b/gi, "Consider")
    .replace(/\bBased on the available data,?\s*/gi, "")
    .replace(/\bAs an AI language model,?\s*/gi, "")
    .replace(/\bRecommended next steps:\s*/gi, "Next steps:\n")
    .replace(/\bSource:\s*connector status\b/gi, "")
    .replace(/\bWorkflow health:\s*/gi, "Workflows: ")
    .replace(/\bConnector status:\s*/gi, "Connections: ")
    .replace(/\n{3,}/g, "\n\n")
    .trim()
}
