/** Copied from apps/web/lib/assignment-signals.ts, which imports web-only types. */
const VERBS = new Set([
  "list",
  "search",
  "get",
  "create",
  "update",
  "delete",
  "add",
  "remove",
  "send",
  "find",
  "enrich",
  "fetch",
  "sync",
  "read",
  "write",
  "post",
  "upsert",
  "lookup",
  "query",
  "export",
  "import",
  "match",
])

function capitalize(text: string): string {
  return text ? text.charAt(0).toUpperCase() + text.slice(1) : text
}

/** "apollo.organizations.search" → "Search organizations"; "apollo.lists.list" → "List Apollo lists". */
export function humanizeToolName(id: string): string {
  const parts = id
    .trim()
    .split(/[._:/\s-]+/)
    .map((part) => part.toLowerCase())
    .filter(Boolean)
  if (parts.length === 0) return "Tool call"
  if (parts.length === 1) return capitalize(parts[0])
  const [provider, ...rest] = parts
  const last = rest[rest.length - 1]
  if (rest.length >= 2 && VERBS.has(last)) {
    const noun = rest.slice(0, -1).join(" ")
    const nounRoot = noun.replace(/s$/, "")
    if (nounRoot === last) return `${capitalize(last)} ${capitalize(provider)} ${noun}`
    return `${capitalize(last)} ${noun}`
  }
  if (VERBS.has(rest[0])) return capitalize(rest.join(" "))
  return capitalize(rest.join(" "))
}
