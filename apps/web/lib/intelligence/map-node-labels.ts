/**
 * Map satellite label helpers — truncate + soft dedupe for spatial graph.
 * Does not invent product claims; only shortens/collapses display strings.
 */

const DEFAULT_MAX = 42

/** Soft fingerprint: stem before step/detail suffixes so near-duplicate alerts collapse. */
export function mapLabelFingerprint(label: string): string {
  const normalized = label
    .toLowerCase()
    .replace(/\s+/g, " ")
    .trim()
    // Drop trailing connector/step detail that varies across duplicate alerts
    .replace(/\b(hubspot|salesforce|gmail|outlook|slack|pipedrive)\b.*$/i, "")
    .replace(/\bat\s+step\b.*$/i, "")
    .replace(/\bin\s+\d+\s+hours?\b/gi, "in N hours")
    .replace(/\d+/g, "#")
    .replace(/[^a-z#\s:]/g, "")
    .replace(/\s+/g, " ")
    .trim()
  // Prefer statement head (before first colon+long tail) when present
  const head = normalized.split(":")[0]?.trim() ?? normalized
  return (head.length >= 12 ? head : normalized).slice(0, 64)
}

export function truncateMapLabel(label: string, max = DEFAULT_MAX): string {
  const trimmed = label.replace(/\s+/g, " ").trim()
  if (trimmed.length <= max) return trimmed
  const slice = trimmed.slice(0, max - 1)
  const breakAt = Math.max(slice.lastIndexOf(" "), slice.lastIndexOf(":"))
  const base = breakAt >= Math.floor(max * 0.45) ? slice.slice(0, breakAt) : slice
  return `${base.trimEnd()}…`
}

/**
 * Keep highest-emphasis / first node per fingerprint. Preserves order.
 */
export function dedupeMapNodesByLabel<T extends { label: string; emphasis?: number }>(
  nodes: T[],
  max = 6,
): T[] {
  const best = new Map<string, T>()
  const order: string[] = []
  for (const node of nodes) {
    const key = mapLabelFingerprint(node.label)
    const existing = best.get(key)
    if (!existing) {
      best.set(key, node)
      order.push(key)
      continue
    }
    if ((node.emphasis ?? 0) > (existing.emphasis ?? 0)) {
      best.set(key, node)
    }
  }
  return order
    .map((key) => best.get(key)!)
    .slice(0, max)
}
