import { inferAgentDepartment } from "@/lib/agent-display"
import type { SearchHistoryItem } from "@/types/api"

export type SearchSuggestionChip = {
  id: string
  label: string
}

type OrgContextSnapshot = {
  counts?: { agents?: number; workflows?: number; connectors?: number }
  agents?: Array<{ id: string; name: string }>
  connectors?: Array<{ id: string; name: string; type?: string }>
}

const FALLBACK_LABELS = [
  "failed runs in production today",
  "connectors with sync errors",
  "workflows using HubSpot",
  "agents active in finance",
] as const

const VENDOR_LABELS: Record<string, string> = {
  hubspot: "HubSpot",
  salesforce: "Salesforce",
  google_analytics: "Google Analytics",
  "google analytics": "Google Analytics",
  quickbooks: "QuickBooks",
  slack: "Slack",
}

function formatVendorName(raw: string): string {
  const key = raw.replace(/_/g, " ").trim().toLowerCase()
  if (VENDOR_LABELS[key]) return VENDOR_LABELS[key]
  return raw
    .replace(/_/g, " ")
    .split(/\s+/)
    .filter(Boolean)
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1).toLowerCase())
    .join(" ")
}

function pickFeaturedConnector(
  connectors: Array<{ id: string; name: string; type?: string }>,
) {
  const priority = ["hubspot", "salesforce", "google_analytics", "slack", "quickbooks"]
  for (const needle of priority) {
    const match = connectors.find((connector) => {
      const haystack = `${connector.type ?? ""} ${connector.name ?? ""}`.toLowerCase()
      return haystack.includes(needle.replace(/_/g, " "))
    })
    if (match) return match
  }
  return connectors[0] ?? null
}

export function buildFallbackSearchChips(): SearchSuggestionChip[] {
  return FALLBACK_LABELS.map((label, index) => ({
    id: `fallback-${index}`,
    label,
  }))
}

export function buildOrgSearchChips(
  org: OrgContextSnapshot | undefined,
  history: SearchHistoryItem[],
): SearchSuggestionChip[] {
  if (!org) return buildFallbackSearchChips()

  const chips: SearchSuggestionChip[] = [
    { id: "failed-runs", label: "failed runs in production today" },
  ]

  if ((org.counts?.connectors ?? org.connectors?.length ?? 0) > 0) {
    chips.push({ id: "connector-sync", label: "connectors with sync errors" })
  }

  const featuredConnector = pickFeaturedConnector(org.connectors ?? [])
  if (featuredConnector) {
    const vendor = formatVendorName(featuredConnector.type || featuredConnector.name || "connector")
    chips.push({
      id: `workflows-${featuredConnector.id}`,
      label: `workflows using ${vendor}`,
    })
  }

  const agents = org.agents ?? []
  if (agents.length > 0) {
    const featuredAgent =
      agents.find((agent) => inferAgentDepartment(agent.name) !== "Operations") ?? agents[0]
    const department = inferAgentDepartment(featuredAgent.name).toLowerCase()
    chips.push({
      id: `agents-${featuredAgent.id}`,
      label: `agents active in ${department}`,
    })
  }

  const recentQuery = history.find((entry) => entry.query.trim())?.query.trim()
  if (recentQuery) {
    const duplicate = chips.some(
      (chip) => chip.label.toLowerCase() === recentQuery.toLowerCase(),
    )
    if (!duplicate) {
      if (chips.length >= 4) {
        chips[chips.length - 1] = { id: `recent-search`, label: recentQuery }
      } else {
        chips.push({ id: "recent-search", label: recentQuery })
      }
    }
  }

  return chips.slice(0, 4)
}

const FALLBACK_SEARCH_PLACEHOLDERS = [
  "Search agents, workflows, connectors...",
  "Try: failed runs in production",
  "Try: agents active in marketing",
] as const

export function buildFallbackSearchPlaceholders(): string[] {
  return [...FALLBACK_SEARCH_PLACEHOLDERS]
}

/** Rotating search input placeholders (Search 3.1). */
export function buildSearchPlaceholders(
  org: OrgContextSnapshot | undefined,
  history: SearchHistoryItem[],
): string[] {
  const primary = "Search agents, workflows, connectors..."
  if (!org) return buildFallbackSearchPlaceholders()

  const tryLines = buildOrgSearchChips(org, history)
    .slice(0, 3)
    .map((chip) => `Try: ${chip.label}`)

  const placeholders = [primary, ...tryLines]
  if (placeholders.length >= 2) return placeholders

  return buildFallbackSearchPlaceholders()
}
