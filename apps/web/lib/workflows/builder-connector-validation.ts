import { allActions, type VendorActionCatalog } from "@/lib/connector-actions"

/** Mirrors backend ACTIVE_CONNECTOR_STATUSES (backend/app/connectors/constants.py). */
export const USABLE_CONNECTOR_STATUSES: ReadonlySet<string> = new Set(["active", "connected", "syncing", "healthy"])

export function isUsableConnectorStatus(status: unknown): boolean {
  return USABLE_CONNECTOR_STATUSES.has(String(status ?? "").toLowerCase())
}

export interface ConnectorValidationNode {
  id: string
  name: string
  type: string
  vendor?: string
  selectedAction?: string
}

export interface ConnectorValidationIssue {
  nodeId: string
  nodeName: string
  severity: "error" | "warning"
  message: string
}

export interface ConnectorValidationContext {
  /** Vendors with a usable org connection; null while the connector list is unknown. */
  connectedVendors: ReadonlySet<string> | null
  /** Implemented canonical ActionSpec ids and tool keys per vendor; null until the catalog loads. */
  catalogActions: ReadonlyMap<string, ReadonlySet<string>> | null
  /** Legacy local action list, consulted only when the catalog has no entry for the vendor. */
  isLegacyActionImplemented?: (vendor: string, actionId: string) => boolean
}

export function connectedVendorSet(
  connectors: ReadonlyArray<{ vendor?: string | null; type?: string | null; status?: unknown }> | null | undefined,
): ReadonlySet<string> | null {
  if (!connectors) return null
  const vendors = new Set<string>()
  for (const connector of connectors) {
    const vendor = connector.vendor || connector.type
    if (vendor && isUsableConnectorStatus(connector.status)) vendors.add(vendor)
  }
  return vendors
}

export function catalogActionIndex(
  catalog: { vendors?: VendorActionCatalog[] } | null | undefined,
): ReadonlyMap<string, ReadonlySet<string>> | null {
  if (!catalog?.vendors) return null
  const index = new Map<string, Set<string>>()
  for (const vendor of catalog.vendors) {
    const keys = new Set<string>()
    for (const action of allActions(vendor)) {
      if (action.implemented === false) continue
      keys.add(action.id)
      if (action.tool) keys.add(action.tool)
    }
    index.set(vendor.vendor, keys)
  }
  return index
}

function isActionAvailable(vendor: string, actionId: string, ctx: ConnectorValidationContext): boolean {
  const vendorActions = ctx.catalogActions?.get(vendor)
  if (vendorActions) {
    return vendorActions.has(actionId) || vendorActions.has(`${vendor}.${actionId}`)
  }
  return ctx.isLegacyActionImplemented?.(vendor, actionId) ?? false
}

/** Pre-save/publish validation so a connector step never silently compiles to a no-op. */
export function getConnectorValidationIssues(
  nodes: ReadonlyArray<ConnectorValidationNode>,
  ctx: ConnectorValidationContext,
): ConnectorValidationIssue[] {
  const issues: ConnectorValidationIssue[] = []
  for (const node of nodes) {
    if (node.type !== "connector") continue
    if (!node.vendor) {
      issues.push({
        nodeId: node.id,
        nodeName: node.name,
        severity: "error",
        message: "No connector selected — pick a connector & action.",
      })
      continue
    }
    if (ctx.connectedVendors && !ctx.connectedVendors.has(node.vendor)) {
      issues.push({
        nodeId: node.id,
        nodeName: node.name,
        severity: "error",
        message: `${node.vendor} is not connected — connect it before publishing.`,
      })
    }
    if (!node.selectedAction) {
      issues.push({
        nodeId: node.id,
        nodeName: node.name,
        severity: "error",
        message: "No action selected — this step would not run.",
      })
    } else if (!isActionAvailable(node.vendor, node.selectedAction, ctx)) {
      issues.push({
        nodeId: node.id,
        nodeName: node.name,
        severity: "error",
        message: `Action "${node.selectedAction}" is not available for ${node.vendor}.`,
      })
    }
  }
  return issues
}
