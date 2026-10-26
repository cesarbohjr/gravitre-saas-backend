/**
 * The short facts a Marketplace card shows next to its kind and department
 * chips ("Uses HubSpot", "1 agent · 2 workflows"). Built only from what the
 * catalog reports; when a fact is missing the chip is left out.
 */
import type { MarketplaceAssetSummary } from "@/types/api"
import { identityDepartmentFor } from "@/lib/listing-identity"

const NOUN: Record<string, [string, string]> = {
  ai_agent: ["agent", "agents"],
  workflow: ["workflow", "workflows"],
  play: ["play", "plays"],
  knowledge_pack: ["knowledge pack", "knowledge packs"],
  dataset_pack: ["dataset", "datasets"],
  connector_config: ["connector", "connectors"],
  department_pack: ["pack", "packs"],
  outcome_pack: ["pack", "packs"],
  dashboard_pack: ["dashboard", "dashboards"],
  capability_package: ["skill", "skills"],
}

/** Counts of what a pack installs, in catalog order: [{ noun: "agent", count: 1 }, ...]. */
export function packContents(asset: Pick<MarketplaceAssetSummary, "packItems">): Array<{ type: string; count: number; label: string }> {
  const counts = new Map<string, number>()
  for (const item of asset.packItems ?? []) {
    const type = item.child?.assetType
    if (type) counts.set(type, (counts.get(type) ?? 0) + 1)
  }
  return Array.from(counts.entries()).map(([type, count]) => {
    const [one, many] = NOUN[type] ?? [type.replace(/_/g, " "), `${type.replace(/_/g, " ")}s`]
    return { type, count, label: `${count} ${count === 1 ? one : many}` }
  })
}

/** "1 agent, 2 workflows and 3 knowledge packs", for sentences. */
export function packContentsSentence(asset: Pick<MarketplaceAssetSummary, "packItems">): string | null {
  const parts = packContents(asset).map((part) => part.label)
  if (parts.length === 0) return null
  if (parts.length === 1) return parts[0]
  return `${parts.slice(0, -1).join(", ")} and ${parts[parts.length - 1]}`
}

export function appsUsed(asset: Pick<MarketplaceAssetSummary, "connectorChecklist">): string | null {
  const apps = asset.connectorChecklist
  if (!apps) return null
  if (apps.length === 0) return "No apps needed"
  if (apps.length <= 2) return `Uses ${apps.map((item) => item.label || item.connectorType).join(", ")}`
  return `Uses ${apps.length} apps`
}

/** The third chip on a card. */
export function listingMeta(asset: MarketplaceAssetSummary): string | null {
  const contents = packContents(asset)
  if (contents.length > 0) return contents.map((part) => part.label).join(" · ")
  return appsUsed(asset)
}

/** Install toast copy: "1 agent, 2 workflows and 3 knowledge packs are ready in Support." */
export function installedDescription(asset: MarketplaceAssetSummary): string {
  const dept = asset.department ? identityDepartmentFor(asset.department).label : null
  const contents = packContentsSentence(asset)
  if (contents) {
    const plural = packContents(asset).reduce((sum, part) => sum + part.count, 0) > 1
    return `${contents} ${plural ? "are" : "is"} ready${dept ? ` in ${dept}` : ""}.`
  }
  return dept ? `It is ready in ${dept}.` : "It is ready in your workspace."
}
