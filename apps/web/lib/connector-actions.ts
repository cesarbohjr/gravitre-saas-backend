/**
 * Connector action catalog types — v1 read, v2 write, v3 advanced, v4 orchestration + demo workflows.
 * Data served by GET /api/connectors/catalog/actions
 */

export type ActionTier = "v1" | "v2" | "v3" | "v4"
export type ActionKind = "read" | "write" | "advanced"

export interface ConnectorActionDefinition {
  id: string
  tool: string
  name: string
  description: string
  tier: ActionTier
  kind: ActionKind
  scopes: string[]
  apiReference?: string | null
  idempotent?: boolean
  destructive?: boolean
  requiresApproval?: boolean
  implemented: boolean
  /** True when invoke_tool + chat ToolRegistry expose this action to Gravitre chat. */
  chatExecutable?: boolean
}

export interface ConnectorActionTier {
  label: string
  description: string
  actions: ConnectorActionDefinition[]
}

export interface DemoWorkflowStep {
  id: string
  name: string
  type: string
  description?: string
  action?: string
  config?: Record<string, unknown>
}

export interface DemoWorkflowDefinition {
  id: string
  vendor: string
  name: string
  description: string
  department: string
  riskLevel: "low" | "medium" | "high"
  requiresApproval: boolean
  successCriteria: string[]
  steps: DemoWorkflowStep[]
}

export interface VendorActionCatalog {
  vendor: string
  displayName: string
  category: string
  apiDocsUrl: string
  shipped: boolean
  tiers: {
    v1: ConnectorActionTier
    v2: ConnectorActionTier
    v3: ConnectorActionTier
    v4?: ConnectorActionTier
  }
  readTools: string[]
  demoWorkflows: DemoWorkflowDefinition[]
}

export interface ConnectorActionCatalogResponse {
  vendors: VendorActionCatalog[]
  vendorCount: number
  tierLabels: Record<ActionTier, string>
}

/** Read-only v1 actions for a vendor catalog entry. */
export function readActions(catalog: VendorActionCatalog): ConnectorActionDefinition[] {
  return catalog.tiers.v1.actions
}

/** All tool keys across v1–v4. */
export function allToolKeys(catalog: VendorActionCatalog): string[] {
  const tiers = [
    ...catalog.tiers.v1.actions,
    ...catalog.tiers.v2.actions,
    ...catalog.tiers.v3.actions,
    ...(catalog.tiers.v4?.actions ?? []),
  ]
  return tiers.map((a) => a.tool)
}

/** Implemented tools only. */
export function implementedTools(catalog: VendorActionCatalog): string[] {
  const tiers = [
    ...catalog.tiers.v1.actions,
    ...catalog.tiers.v2.actions,
    ...catalog.tiers.v3.actions,
    ...(catalog.tiers.v4?.actions ?? []),
  ]
  return allToolKeys(catalog).filter((tool) => {
    const action = tiers.find((a) => a.tool === tool)
    return action?.implemented === true
  })
}
