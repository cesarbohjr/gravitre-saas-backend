/**
 * Settings > AI models: chat entity matching (Memory) policy at
 * /api/settings/memory-entity-embeddings ({ enabled, connectors }, where an
 * empty connectors list means every connected app), and the app chips built
 * from the workspace's real connectors.
 */
import { connectorVendorKey, formatVendorLabel } from "@/lib/connectors"

export interface MemoryPolicy {
  enabled: boolean
  connectors: string[]
}

export interface AppChip {
  id: string
  name: string
  /** Saved in the policy but no longer connected. */
  stale?: boolean
}

export const MEMORY_KEY = "/api/settings/memory-entity-embeddings"
export const CONNECTORS_KEY = "/api/connectors"

const CONNECTED = new Set(["active", "connected", "syncing", "healthy"])

/** One chip per connected app (by vendor key), plus saved picks that are not connected any more. */
export function appChips(
  connectors: Array<{ vendor?: string; type?: string; status?: string }> | undefined,
  saved: string[] = [],
): AppChip[] {
  const chips = new Map<string, AppChip>()
  for (const connector of connectors ?? []) {
    const raw = String(connector.vendor || connector.type || "").trim()
    if (!raw || !CONNECTED.has(String(connector.status || "").toLowerCase())) continue
    const id = connectorVendorKey(raw)
    if (!chips.has(id)) chips.set(id, { id, name: formatVendorLabel(id) })
  }
  const live = [...chips.values()].sort((a, b) => a.name.localeCompare(b.name))
  const stale = saved
    .map((id) => id.toLowerCase())
    .filter((id) => !chips.has(id))
    .map((id) => ({ id, name: formatVendorLabel(id), stale: true }))
  return [...live, ...stale]
}

export function scopeText(chips: AppChip[], selected: string[]): string {
  const picked = chips.filter((chip) => selected.includes(chip.id)).map((chip) => chip.name)
  return picked.length ? `Applies to ${picked.join(", ")} only.` : "Applies to every connected app."
}

export function samePolicy(a: MemoryPolicy, b: MemoryPolicy): boolean {
  const left = [...a.connectors].sort().join(",")
  const right = [...b.connectors].sort().join(",")
  return a.enabled === b.enabled && left === right
}
