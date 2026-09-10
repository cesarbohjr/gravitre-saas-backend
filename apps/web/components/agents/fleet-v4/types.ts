/**
 * Agents 4.0 — canonical types for identity + fleet views.
 * Prototype-first; intended to become production after visual approval.
 */

export type AgentIdentityColorId =
  | "green"
  | "cyan"
  | "violet"
  | "blue"
  | "teal"
  | "amber"
  | "rose"

export type AgentRoleIconId =
  | "sales"
  | "support"
  | "finance"
  | "ops"
  | "research"
  | "analytics"
  | "reliability"
  | "security"
  | "recruiting"
  | "marketing"
  | "knowledge"
  | "workflow"
  | "data"
  | "general"

/** Configuration state — separate from runtime. */
export type AgentConfigState = "enabled" | "paused" | "disabled"

/** Runtime state — never recolors the identity tile. */
export type AgentRuntimeState =
  | "available"
  | "idle"
  | "thinking"
  | "retrieving"
  | "planning"
  | "executing"
  | "waiting_approval"
  | "delegating"
  | "completed"
  | "failed"
  | "blocked"
  | "offline"

export type AgentFleetView = "team" | "list" | "graph"

export type AgentDepartmentId =
  | "sales"
  | "customer_success"
  | "finance"
  | "operations"
  | "engineering"
  | "marketing"
  | "security"
  | "general"

export type AgentRelationKind =
  | "delegates_to"
  | "collaborates_with"
  | "invoked_by_workflow"
  | "uses_connector"
  | "escalates_to"
  | "parent_of"

export interface FleetAgent {
  id: string
  name: string
  role: string
  department: AgentDepartmentId
  departmentLabel: string
  icon: AgentRoleIconId
  identityColor: AgentIdentityColorId
  configState: AgentConfigState
  runtimeState: AgentRuntimeState
  currentActivity: string | null
  tasksToday: number
  successRate: number | null
  model: string
  lastActiveLabel: string
  tools: string[]
  workflows: string[]
  /** Display names from API connectedSystems — used for uses_connector edges. */
  connectedSystems?: string[]
  workflowCount?: number
  parentAgentId?: string | null
}

export interface FleetEdge {
  id: string
  source: string
  target: string
  kind: AgentRelationKind
  label: string
  /** Highlight during an active multi-agent run */
  active?: boolean
}

/** Non-agent graph nodes (connectors, workflows). */
export interface FleetGraphExtraNode {
  id: string
  kind: "connector" | "workflow"
  label: string
}

export type IdentitySize = "sm" | "md" | "lg"
export type IdentityVariant = "row" | "card" | "graph" | "picker"
