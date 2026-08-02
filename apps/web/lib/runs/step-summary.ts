const UUID_PATTERN =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i

const ERROR_TRANSLATIONS: Array<{ pattern: RegExp; message: string; fix?: string }> = [
  {
    pattern: /agent step requires metadata\.agent_id or config\.agent_id/i,
    message: "This workflow step is missing the agent it should run.",
    fix: "Open the workflow builder, select this agent step, and choose an agent from the team.",
  },
  {
    pattern: /connector.*auth|unauthorized|401|403|token.*expired|reconnect/i,
    message: "The connector lost authentication and could not complete the step.",
    fix: "Reconnect the connector, then retry this step.",
  },
  {
    pattern: /timeout|timed out/i,
    message: "The step took too long and was stopped.",
    fix: "Increase the step timeout or retry during off-peak hours.",
  },
  {
    pattern: /approval.*required|awaiting approval/i,
    message: "This step is waiting for someone to approve it before it can continue.",
    fix: "Review the approval queue and approve or reject the pending action.",
  },
]

function isUuid(value: string): boolean {
  return UUID_PATTERN.test(value)
}

function titleCase(value: string): string {
  return value
    .replace(/[._-]+/g, " ")
    .split(" ")
    .filter(Boolean)
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1).toLowerCase())
    .join(" ")
}

function humanizeKey(key: string): string {
  return titleCase(key.replace(/([a-z])([A-Z])/g, "$1 $2"))
}

function formatPrimitive(value: unknown): string | null {
  if (value == null || value === "") return null
  if (typeof value === "boolean") return value ? "Yes" : "No"
  if (typeof value === "number") return String(value)
  if (typeof value === "string") {
    const trimmed = value.trim()
    if (!trimmed) return null
    if (isUuid(trimmed)) return null
    if (trimmed.startsWith("{") || trimmed.startsWith("[")) return null
    return trimmed
  }
  return null
}

export type StepErrorSummary = {
  title: string
  fix?: string
}

export function summarizeStepError(message: string | null | undefined): StepErrorSummary | null {
  if (!message?.trim()) return null
  const trimmed = message.trim()
  for (const rule of ERROR_TRANSLATIONS) {
    if (rule.pattern.test(trimmed)) {
      return { title: rule.message, fix: rule.fix }
    }
  }
  if (trimmed.startsWith("ERROR:")) {
    return { title: trimmed.replace(/^ERROR:\s*/i, "") }
  }
  return { title: trimmed }
}

export function summarizeStepPayload(
  value: Record<string, unknown> | null | undefined,
): { summary: string; bullets: string[] } | null {
  if (!value || Object.keys(value).length === 0) return null

  const preferredMessages = ["message", "summary", "result", "output", "description"]
  for (const key of preferredMessages) {
    const text = formatPrimitive(value[key])
    if (text) {
      return { summary: text, bullets: [] }
    }
  }

  const bullets: string[] = []
  for (const [key, raw] of Object.entries(value)) {
    const text = formatPrimitive(raw)
    if (text) bullets.push(`${humanizeKey(key)}: ${text}`)
    else if (raw && typeof raw === "object" && !Array.isArray(raw)) {
      const nested = summarizeStepPayload(raw as Record<string, unknown>)
      if (nested?.summary) bullets.push(`${humanizeKey(key)}: ${nested.summary}`)
    } else if (Array.isArray(raw) && raw.length === 0) {
      bullets.push(`${humanizeKey(key)}: none`)
    }
  }

  if (bullets.length === 0) {
    const keys = Object.keys(value)
    if (keys.length === 1 && Object.keys(value[keys[0]] as object ?? {}).length === 0) {
      return { summary: "No input was passed into this step.", bullets: [] }
    }
    return { summary: "Step data was recorded.", bullets: [] }
  }

  if (bullets.length === 1) {
    return { summary: bullets[0], bullets: [] }
  }

  return {
    summary: bullets[0],
    bullets: bullets.slice(1, 4),
  }
}

export function humanizeLogLine(line: string): string {
  const trimmed = line.trim()
  if (!trimmed) return trimmed
  const withoutPrefix = trimmed.replace(/^ERROR:\s*/i, "")
  const translated = summarizeStepError(withoutPrefix)
  return translated?.title ?? withoutPrefix
}

/**
 * API / DB `logs` may be string[], a single JSON string, or a parsed object
 * (execution engine writes one JSON blob). Never assume `.map` works.
 */
export function normalizeStepLogs(logs: unknown): string[] {
  if (logs == null) return []
  if (Array.isArray(logs)) {
    return logs
      .map((item) => {
        if (typeof item === "string") return item
        if (item == null) return ""
        try {
          return typeof item === "object" ? JSON.stringify(item) : String(item)
        } catch {
          return String(item)
        }
      })
      .filter((line) => line.trim().length > 0)
  }
  if (typeof logs === "string") {
    const trimmed = logs.trim()
    return trimmed ? [trimmed] : []
  }
  if (typeof logs === "object") {
    try {
      return [JSON.stringify(logs)]
    } catch {
      return []
    }
  }
  return [String(logs)]
}

export function humanizeConnectorAction(action: string | undefined): string | null {
  if (!action) return null
  const [vendor, ...rest] = action.split(".")
  if (!vendor || rest.length === 0) return titleCase(action.replace(/\./g, " "))
  return `${titleCase(vendor)} · ${titleCase(rest.join(" "))}`
}
