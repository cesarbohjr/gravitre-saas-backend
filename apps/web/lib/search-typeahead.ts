import type { SearchHistoryItem } from "@/types/api"

export type SearchTypeaheadKind = "agent" | "workflow" | "connector" | "history" | "search"

export type SearchTypeaheadItem = {
  id: string
  label: string
  subtitle?: string
  kind: SearchTypeaheadKind
  href?: string
  searchQuery?: string
  score: number
}

type OrgContextSnapshot = {
  agents?: Array<{ id: string; name: string }>
  workflows?: Array<{ id: string; name: string }>
  connectors?: Array<{ id: string; name: string; type?: string }>
}

function matchScore(label: string, query: string): number {
  const haystack = label.trim().toLowerCase()
  const needle = query.trim().toLowerCase()
  if (!needle || !haystack) return 0
  if (haystack === needle) return 100
  if (haystack.startsWith(needle)) return 85
  const words = haystack.split(/\s+/).filter(Boolean)
  if (words.some((word) => word.startsWith(needle))) return 70
  if (haystack.includes(needle)) return 55
  return 0
}

function pushEntityMatches(
  items: SearchTypeaheadItem[],
  query: string,
  entities: Array<{ id: string; name: string; type?: string }>,
  kind: Exclude<SearchTypeaheadKind, "history" | "search">,
  hrefPrefix: string,
  subtitleFor?: (entity: { id: string; name: string; type?: string }) => string | undefined,
) {
  for (const entity of entities) {
    const name = entity.name?.trim()
    if (!name) continue
    const score = matchScore(name, query)
    if (score <= 0) continue
    items.push({
      id: `${kind}-${entity.id}`,
      label: name,
      subtitle: subtitleFor?.(entity) ?? kind.charAt(0).toUpperCase() + kind.slice(1),
      kind,
      href: `${hrefPrefix}/${entity.id}`,
      score,
    })
  }
}

export function buildSearchTypeaheadItems(
  query: string,
  org: OrgContextSnapshot | undefined,
  history: SearchHistoryItem[],
  limit = 8,
): SearchTypeaheadItem[] {
  const trimmed = query.trim()
  if (trimmed.length < 1) return []

  const items: SearchTypeaheadItem[] = []

  if (org) {
    pushEntityMatches(items, trimmed, org.agents ?? [], "agent", "/agents")
    pushEntityMatches(items, trimmed, org.workflows ?? [], "workflow", "/workflows")
    pushEntityMatches(
      items,
      trimmed,
      org.connectors ?? [],
      "connector",
      "/connectors",
      (entity) => entity.type?.replace(/_/g, " ") ?? "Connector",
    )
  }

  for (const entry of history) {
    const historyQuery = entry.query?.trim()
    if (!historyQuery) continue
    const score = matchScore(historyQuery, trimmed)
    if (score <= 0) continue
    items.push({
      id: `history-${entry.id}`,
      label: historyQuery,
      subtitle: "Recent search",
      kind: "history",
      searchQuery: historyQuery,
      score: score + 5,
    })
  }

  items.sort((a, b) => b.score - a.score || a.label.localeCompare(b.label))

  const deduped: SearchTypeaheadItem[] = []
  const seen = new Set<string>()
  for (const item of items) {
    const key = item.href ?? item.searchQuery ?? item.label
    if (seen.has(key)) continue
    seen.add(key)
    deduped.push(item)
    if (deduped.length >= limit) break
  }

  if (trimmed.length >= 2) {
    deduped.push({
      id: "semantic-search",
      label: `Search for "${trimmed}"`,
      subtitle: "Semantic search",
      kind: "search",
      searchQuery: trimmed,
      score: -1,
    })
  }

  return deduped
}
