/**
 * Client-side framing helper for governed write badges on the canvas.
 *
 * Classification SoT remains backend catalog_write_authority — this mirrors the
 * same suffix last-resort used when no catalog row is present, plus HTTP method
 * heuristics from the local connector action catalog. Badge is visual framing only.
 */

const WRITE_SUFFIXES = [
  ".create",
  ".update",
  ".delete",
  ".upsert",
  ".send",
  ".post",
  ".patch",
  ".put",
  ".remove",
  ".archive",
  ".enroll",
  ".write",
  ".publish",
  ".invite",
  ".assign",
  ".move",
  ".merge",
  ".postmessage",
  ".chat.postmessage",
] as const

export type WriteAuthorityKind = "write" | "read" | "unknown"

export function actionKeyLooksLikeWrite(actionKey: string | null | undefined): boolean {
  const key = (actionKey || "").trim().toLowerCase()
  if (!key) return false
  return WRITE_SUFFIXES.some((suffix) => key.endsWith(suffix) || key.includes(suffix))
}

export function classifyCanvasNodeWriteAuthority(opts: {
  type?: string
  vendor?: string
  selectedAction?: string
  compiledActionKey?: string | null
  httpMethod?: string | null
}): WriteAuthorityKind {
  const type = (opts.type || "").toLowerCase()
  if (type === "approval") return "write"
  if (type === "connector" || type === "tool") {
    const key = opts.compiledActionKey || (opts.vendor && opts.selectedAction
      ? `${opts.vendor}.${opts.selectedAction}`
      : null)
    if (actionKeyLooksLikeWrite(key)) return "write"
    const method = (opts.httpMethod || "").toUpperCase()
    if (method && method !== "GET" && method !== "HEAD" && method !== "OPTIONS") {
      return "write"
    }
    if (key) return "read"
  }
  return "unknown"
}
