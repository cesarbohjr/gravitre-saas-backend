import type {
  ActionKind,
  ActionTier,
  ConnectorActionCatalogResponse,
  ConnectorActionDefinition,
  VendorActionCatalog,
} from "@/lib/connector-actions"

export type CapabilityAutonomyLabel =
  | "READ ONLY"
  | "ACT WITH APPROVAL"
  | "ACT WITHIN POLICY"

export interface CapabilityGovernance {
  writeRequiresApprovalByDefault?: boolean
  noHitlPolicyMeans?: CapabilityAutonomyLabel
  effectiveAutonomyLabel?: CapabilityAutonomyLabel
  unattendedWriteAuthorized?: boolean
  reason?: string | null
  hitlMatchedPolicyId?: string | null
  trustLevel?: string | null
}

export interface CapabilityAction {
  tool: string
  vendor: string
  name: string
  tier: string
  kind: string
  access: "read" | "write"
  requires_approval: boolean
  destructive: boolean
  implemented: boolean
  verification_mode?: string | null
  compensating_action?: string | null
  catalogRequiresWriteApproval?: boolean
  runtimeRequiresUserApproval?: boolean
  runtimeApprovalNote?: string
  readiness?: string
  provenance?: string
}

export interface CapabilityCatalogConnector {
  vendor: string
  display_name: string
  category: string
  shipped: boolean
  action_count: number
  implemented_read_count: number
  implemented_write_count: number
  provenance?: string
}

export interface CapabilitySnapshot {
  orgId: string
  environment: string
  mutation: false
  governance: CapabilityGovernance
  connectedVendors: string[]
  actions: CapabilityAction[]
  catalogConnectors: CapabilityCatalogConnector[]
  orgConnectors: Array<{
    id?: string | null
    orgId?: string | null
    vendor?: string | null
    name?: string | null
    status?: string | null
    environment?: string | null
    usable?: boolean
    readiness?: string
  }>
  agents: Array<Record<string, unknown>>
  workflowPrimitives: Array<{ step_type: string; execute_allowed: boolean }>
  verification: {
    write_verification_modes?: Record<string, number>
    implemented_writes_accepted_async_only?: string[]
    run_outcome_verification?: string[]
  }
  evidence: Record<string, string[]>
  unavailable?: Record<string, string>
}

function normalizedTier(value: string, access: "read" | "write"): ActionTier {
  if (value === "v1" || value === "v2" || value === "v3" || value === "v4") return value
  return access === "read" ? "v1" : "v2"
}

function normalizedKind(action: CapabilityAction): ActionKind {
  if (action.kind === "advanced") return "advanced"
  return action.access === "write" ? "write" : "read"
}

export function capabilityActionToConnectorAction(
  action: CapabilityAction,
): ConnectorActionDefinition {
  const prefix = `${action.vendor}.`
  const id = action.tool.startsWith(prefix) ? action.tool.slice(prefix.length) : action.tool
  return {
    id,
    tool: action.tool,
    name: action.name,
    description: action.name,
    tier: normalizedTier(action.tier, action.access),
    kind: normalizedKind(action),
    scopes: [],
    destructive: action.destructive,
    requiresApproval:
      action.runtimeRequiresUserApproval ??
      action.catalogRequiresWriteApproval ??
      action.requires_approval,
    implemented: action.implemented,
    chatExecutable: action.implemented,
  }
}

/**
 * Compatibility view for existing workflow/configuration UI.
 * Capability truth comes exclusively from GET /api/capabilities; this adapter
 * only preserves the existing frontend catalog shape while those surfaces are
 * migrated incrementally.
 */
export function capabilitySnapshotToActionCatalog(
  snapshot: CapabilitySnapshot,
): ConnectorActionCatalogResponse {
  const actionsByVendor = new Map<string, CapabilityAction[]>()
  for (const action of snapshot.actions ?? []) {
    const rows = actionsByVendor.get(action.vendor) ?? []
    rows.push(action)
    actionsByVendor.set(action.vendor, rows)
  }

  const vendors: VendorActionCatalog[] = (snapshot.catalogConnectors ?? []).map((connector) => {
    const canonical = actionsByVendor.get(connector.vendor) ?? []
    const definitions = canonical.map(capabilityActionToConnectorAction)
    const byTier = (tier: ActionTier) => definitions.filter((action) => action.tier === tier)
    return {
      vendor: connector.vendor,
      displayName: connector.display_name,
      category: connector.category,
      apiDocsUrl: "",
      shipped: connector.shipped,
      tiers: {
        v1: { label: "Read", description: "Read actions", actions: byTier("v1") },
        v2: { label: "Write", description: "Write actions", actions: byTier("v2") },
        v3: { label: "Advanced", description: "Advanced actions", actions: byTier("v3") },
        v4: { label: "Orchestration", description: "Orchestration actions", actions: byTier("v4") },
      },
      readTools: canonical.filter((action) => action.access === "read").map((action) => action.tool),
      demoWorkflows: [],
    }
  })

  return {
    vendors,
    vendorCount: vendors.length,
    tierLabels: {
      v1: "Read",
      v2: "Write",
      v3: "Advanced",
      v4: "Orchestration",
    },
  }
}

/**
 * Fail closed. No identity or no explicit auto_run is ACT WITH APPROVAL.
 * ACT WITHIN POLICY is available only when the stored identity is autonomous,
 * WRITE has an explicit auto_run override, and no covering HITL policy matched.
 */
export function deriveAutonomyLabel(
  trustLevel?: string | null,
  overrides?: Record<string, string> | null,
  governance?: CapabilityGovernance | null,
): CapabilityAutonomyLabel {
  if (trustLevel === "read_only") return "READ ONLY"

  const writeOverride = overrides?.write
  const explicitlyAuto =
    trustLevel === "autonomous" &&
    writeOverride === "auto_run" &&
    !governance?.hitlMatchedPolicyId

  if (explicitlyAuto) return "ACT WITHIN POLICY"
  return "ACT WITH APPROVAL"
}
