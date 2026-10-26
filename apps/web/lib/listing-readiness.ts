/**
 * The readiness footer every Marketplace card shares (UIRefresh-System):
 * one dot, one line of status and one action, decided from what the catalog
 * API reports for this workspace. Nothing here is guessed: a listing whose
 * setup requirements are not reported says so instead of claiming it is ready.
 */
import type { MarketplaceAssetSummary, MarketplaceConnectorChecklistItem } from "@/types/api"
import { assetRequiresPurchase, formatAssetPrice } from "@/components/marketplace/marketplace-asset-commerce"

export type ReadinessState = "installed" | "connect" | "review" | "purchase" | "ready" | "unknown"

/** What the footer button does. The page decides how each one is carried out. */
export type ReadinessAction =
  | { kind: "open"; label: "Open" }
  | { kind: "connect"; label: "Connect"; href: string }
  | { kind: "review"; label: "Review" }
  | { kind: "install"; label: string }
  | { kind: "details"; label: "Details" }

export type ListingReadiness = {
  state: ReadinessState
  /** "Ready to install", "Needs HubSpot", "Needs Apollo search API", "Installed". */
  label: string
  /** Longer reason for a tooltip, when the API gave one. */
  detail?: string
  action: ReadinessAction
}

function missingRequired(asset: MarketplaceAssetSummary): MarketplaceConnectorChecklistItem[] {
  return (asset.connectorChecklist ?? []).filter((item) => item.required && !item.connected)
}

function needsLabel(missing: MarketplaceConnectorChecklistItem[]): string {
  if (missing.length === 1) return `Needs ${missing[0].label || missing[0].connectorType}`
  return `Needs ${missing.length} apps`
}

/** Where Connect goes: the API's connect path for the first missing app, else the Connectors page. */
export function connectHref(item: MarketplaceConnectorChecklistItem | undefined): string {
  const path = item?.connectPath || item?.action_url
  // "/connectors" is the schema default; a typed link opens the right app's connect flow.
  if (path && path.startsWith("/") && path !== "/connectors") return path
  return item ? `/connectors?connect=${encodeURIComponent(item.connectorType)}` : "/connectors"
}

export function listingReadiness(asset: MarketplaceAssetSummary, { canInstall }: { canInstall: boolean }): ListingReadiness {
  const isConnector = asset.assetType === "connector_config"
  if (asset.installed) {
    return { state: "installed", label: isConnector ? "Connected" : "Installed", action: { kind: "open", label: "Open" } }
  }

  const missing = missingRequired(asset)
  if (missing.length > 0) {
    return {
      state: "connect",
      label: needsLabel(missing),
      detail: missing.map((item) => item.label || item.connectorType).join(", "),
      action: { kind: "connect", label: "Connect", href: connectHref(missing[0]) },
    }
  }

  const limited = (asset.connectorChecklist ?? []).find((item) => item.discoveryLimitation || item.warning)
  if (limited) {
    const name = limited.label || limited.connectorType
    return {
      state: "review",
      label: limited.discoveryLimitation ? `Needs ${name} search API` : `Review ${name} access`,
      detail: limited.discoveryLimitation || limited.warning || undefined,
      action: { kind: "review", label: "Review" },
    }
  }
  const manual = asset.manualSetupRequired?.[0]
  if (manual) {
    return {
      state: "review",
      label: `Needs manual ${manual.connector} setup`,
      detail: manual.reason,
      action: { kind: "review", label: "Review" },
    }
  }
  if ((asset.installReadyErrors?.length ?? 0) > 0) {
    return {
      state: "review",
      label: "Setup needs review",
      detail: asset.installReadyErrors?.[0]?.message,
      action: { kind: "review", label: "Review" },
    }
  }

  if (!asset.connectorChecklist) {
    return { state: "unknown", label: "Setup not reported", action: { kind: "details", label: "Details" } }
  }

  if (assetRequiresPurchase(asset)) {
    return {
      state: "purchase",
      label: `Paid · ${formatAssetPrice(asset)}`,
      action: canInstall ? { kind: "install", label: "Buy" } : { kind: "details", label: "Details" },
    }
  }

  return {
    state: "ready",
    label: "Ready to install",
    action: canInstall ? { kind: "install", label: "Install" } : { kind: "details", label: "Details" },
  }
}

/** Readiness filter buckets for the catalog toolbar. */
export const READINESS_FILTERS = [
  { id: "all", label: "Any readiness" },
  { id: "ready", label: "Ready to install" },
  { id: "connect", label: "Needs an app" },
  { id: "review", label: "Needs review" },
  { id: "installed", label: "Installed" },
] as const

export type ReadinessFilter = (typeof READINESS_FILTERS)[number]["id"]

export function matchesReadiness(readiness: ListingReadiness, filter: ReadinessFilter): boolean {
  if (filter === "all") return true
  if (filter === "ready") return readiness.state === "ready" || readiness.state === "purchase"
  return readiness.state === filter
}
