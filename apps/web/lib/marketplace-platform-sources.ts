/**
 * Knowledge-base platform sources (FRED, NVD, CISA, …) for Marketplace pack UX.
 * These stay off the Connectors hub; Marketplace is where tenants see them
 * under category "Knowledge Base".
 */

import {
  CONNECTOR_CATALOG,
  isConnectorsHubHidden,
  lookupCatalogEntry,
  type CatalogConnectorEntry,
} from "@/lib/connectors"
import type { MarketplaceConnectorChecklistItem } from "@/types/api"

/** Pack slug → gravitre-managed sources staged/activated with that pack. */
export const PACK_PLATFORM_SOURCE_TYPES: Record<string, readonly string[]> = {
  "executive-intelligence-pack": ["fred", "sec_edgar", "world_bank", "oecd", "opencorporates"],
  "msp-intelligence-pack": ["nvd", "cisa_kev"],
}

export type PlatformSourceStatus = "active" | "managed" | "pending_license"

export type PlatformSourceItem = {
  connectorType: string
  label: string
  description: string
  status: PlatformSourceStatus
  statusLabel: string
}

export function isPlatformSourceType(connectorType: string): boolean {
  return isConnectorsHubHidden(connectorType)
}

/** Split checklist into platform sources vs tenant apps (OAuth/API keys). */
export function partitionConnectorChecklist(items: MarketplaceConnectorChecklistItem[]): {
  platform: MarketplaceConnectorChecklistItem[]
  apps: MarketplaceConnectorChecklistItem[]
} {
  const platform: MarketplaceConnectorChecklistItem[] = []
  const apps: MarketplaceConnectorChecklistItem[] = []
  for (const item of items) {
    if (isPlatformSourceType(item.connectorType)) platform.push(item)
    else apps.push(item)
  }
  return { platform, apps }
}

function catalogLabel(vendorKey: string): string {
  const entry = lookupCatalogEntry(vendorKey)
  return entry?.type ?? vendorKey.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase())
}

function catalogDescription(vendorKey: string): string {
  return lookupCatalogEntry(vendorKey)?.description ?? "Gravitre-managed intelligence source"
}

function resolveStatus(
  vendorKey: string,
  checklistItem: MarketplaceConnectorChecklistItem | undefined,
  installed: boolean,
): PlatformSourceStatus {
  const entry = lookupCatalogEntry(vendorKey)
  if (entry?.activationBlocked) return "pending_license"
  if (checklistItem?.connected || checklistItem?.ready || installed) return "active"
  return "managed"
}

function statusLabel(status: PlatformSourceStatus): string {
  if (status === "active") return "Active"
  if (status === "pending_license") return "Pending license"
  return "Managed by Gravitre"
}

/**
 * Build the Platform sources list for a marketplace pack.
 * Prefers pack-known gravitre vendors; falls back to checklist platform items.
 */
export function resolvePlatformSources(args: {
  packSlug?: string | null
  checklist?: MarketplaceConnectorChecklistItem[] | null
  installed?: boolean
}): PlatformSourceItem[] {
  const checklist = args.checklist ?? []
  const byType = new Map(
    checklist.map((item) => [String(item.connectorType || "").toLowerCase(), item] as const),
  )
  const installed = Boolean(args.installed)
  const slug = String(args.packSlug || "").trim().toLowerCase()
  const fromPack = slug ? PACK_PLATFORM_SOURCE_TYPES[slug] : undefined

  let types: string[]
  if (fromPack?.length) {
    types = [...fromPack]
  } else {
    types = checklist.filter((item) => isPlatformSourceType(item.connectorType)).map((item) =>
      String(item.connectorType).toLowerCase(),
    )
  }

  const seen = new Set<string>()
  const out: PlatformSourceItem[] = []
  for (const raw of types) {
    const key = String(raw || "").trim().toLowerCase()
    if (!key || seen.has(key)) continue
    seen.add(key)
    const checklistItem = byType.get(key)
    const status = resolveStatus(key, checklistItem, installed)
    out.push({
      connectorType: key,
      label: checklistItem?.label?.trim() || catalogLabel(key),
      description: catalogDescription(key),
      status,
      statusLabel: statusLabel(status),
    })
  }
  return out
}

/** Catalog entries used only for platform-source discovery tests / docs. */
export function listGravitreManagedCatalogEntries(): CatalogConnectorEntry[] {
  return CONNECTOR_CATALOG.filter(
    (entry) => entry.authMode === "gravitre_managed" || entry.credentialModel === "platform_only",
  )
}
