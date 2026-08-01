/**
 * STA-19: Map workflow builder canvas ↔ API builder graph (GET/PUT /api/workflows/{id}/builder).
 */
import { workflowsApi } from "@/lib/api"
import type { WorkflowDryRunResponse } from "@/types/api"
import {
  connectorConfigWithBind,
  resolveConnectorBind,
} from "@/lib/workflows/builder-connector-bind"

export type CanvasNodeType =
  | "agent"
  | "task"
  | "connector"
  | "tool"
  | "source"
  | "approval"
  | "decision"
  | "council"
  | "if"
  | "switch"
  | "merge"
  | "loop"

export type NodeState =
  | "idle"
  | "running"
  | "success"
  | "error"
  | "waiting"
  | "evaluating"
  | "debating"
  | "consensus"
  | "escalated"

export interface DecisionPath {
  id: string
  label: string
  condition?: string
  targetNodeId?: string
  isDefault?: boolean
}

export interface DecisionConfig {
  objective?: string
  strategy?: "rule-based" | "ai-assisted" | "hybrid"
  inputSources?: string[]
  conditions?: string
  outputPaths?: DecisionPath[]
  reasoning?: {
    summary: string
    confidence: number
    factors: string[]
    chosenPath: string
    rejectedPaths?: string[]
  }
}

export interface CouncilAgent {
  id: string
  name: string
  role: string
  expertise: string
  confidenceStyle: "cautious" | "fast" | "analytical" | "creative"
  dataSources?: string[]
  position?: string
  confidence?: number
  reasoning?: string
  evidenceUsed?: string[]
}

export interface DebateContribution {
  agentId: string
  position: string
  confidence: number
  reasoning: string
  evidenceUsed: string[]
  timestamp: Date
}

export interface CouncilConfig {
  objective?: string
  participatingAgents?: CouncilAgent[]
  debateMode?: "consensus" | "majority" | "lead-decides" | "human-approval" | "risk-escalation"
  evidenceSources?: string[]
  outputOptions?: { id: string; label: string; description?: string }[]
  debate?: {
    contributions: DebateContribution[]
    disagreements?: { agentIds: string[]; topic: string }[]
    timeline: { step: string; status: "pending" | "active" | "complete" }[]
  }
  finalDecision?: {
    recommendation: string
    method: "consensus" | "majority" | "lead-decides" | "human-approval" | "risk-escalation"
    confidence: number
    keyReasons: string[]
    dissentingOpinions?: { agentId: string; opinion: string }[]
    executedAction?: string
  }
}

export interface CanvasWorkflowNode {
  id: string
  type: CanvasNodeType
  name: string
  description?: string
  config: Record<string, unknown>
  position: { x: number; y: number }
  connections: string[]
  state?: NodeState
  vendor?: string
  selectedAction?: string
  dataLabel?: string
  decisionConfig?: DecisionConfig
  outputPaths?: DecisionPath[]
  councilConfig?: CouncilConfig
  /** Populated during live run polling when a step fails. */
  stepError?: string
}

export interface WorkflowMeta {
  id: string
  name: string
  description?: string
  status: "draft" | "active" | "paused" | "archived"
  environment?: "development" | "staging" | "production"
  version?: string
  created_at?: string
  updated_at?: string
}

export interface BuilderGraphResponse {
  workflow_id: string
  name?: string
  description?: string
  status?: string
  nodes: Array<Record<string, unknown>>
  edges: Array<Record<string, unknown>>
}

export interface BuilderSaveResponse extends BuilderGraphResponse {
  step_count?: number
}

export interface ExecuteResponse {
  run_id: string
  status:
    | "pending"
    | "running"
    | "completed"
    | "failed"
    | "cancelled"
    | "pending_approval"
    | "awaiting_approval"
  errors?: string[]
  steps?: {
    node_id: string
    status: "pending" | "running" | "completed" | "failed"
    started_at?: string
    completed_at?: string
    error?: string
  }[]
}

const UUID_RE =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i

/** Align with backend definition_resolver legacy node type mapping. */
const LEGACY_NODE_TYPE_MAP: Record<string, CanvasNodeType> = {
  trigger: "source",
  action: "tool",
  end: "task",
  human_approval: "approval",
  parallel: "task",
  delay: "task",
  // Marketplace / pack steps compile as invoke_tool — surface as connector nodes.
  invoke_tool: "connector",
  tool_invoke: "connector",
}

const CANVAS_NODE_TYPES = new Set<CanvasNodeType>([
  "agent",
  "task",
  "connector",
  "tool",
  "source",
  "approval",
  "decision",
  "council",
  "if",
  "switch",
  "merge",
  "loop",
])

export function normalizeCanvasNodeType(rawType: unknown): CanvasNodeType {
  const normalized = String(rawType ?? "task").trim().toLowerCase()
  const mapped = LEGACY_NODE_TYPE_MAP[normalized] ?? normalized
  return CANVAS_NODE_TYPES.has(mapped as CanvasNodeType) ? (mapped as CanvasNodeType) : "task"
}

export function isPersistableWorkflowId(id: string): boolean {
  return UUID_RE.test(id)
}

function edgeTargets(edges: Array<Record<string, unknown>>, nodeId: string): string[] {
  return edges
    .filter((e) => String(e.from_node_id ?? e.fromNodeId) === nodeId)
    .map((e) => String(e.to_node_id ?? e.toNodeId))
}

function resolveNodePosition(node: Record<string, unknown>): { x: number; y: number } {
  const rawPosition = node.position
  const position =
    rawPosition && typeof rawPosition === "object"
      ? (rawPosition as { x?: number; y?: number })
      : null
  const xFromPosition =
    position && typeof position.x === "number" && Number.isFinite(position.x) ? position.x : null
  const yFromPosition =
    position && typeof position.y === "number" && Number.isFinite(position.y) ? position.y : null
  const xFromColumn = Number(node.position_x)
  const yFromColumn = Number(node.position_y)
  return {
    x: xFromPosition ?? (Number.isFinite(xFromColumn) ? xFromColumn : 0),
    y: yFromPosition ?? (Number.isFinite(yFromColumn) ? yFromColumn : 0),
  }
}

function autoLayoutCanvasNodes(nodes: CanvasWorkflowNode[]): CanvasWorkflowNode[] {
  if (nodes.length === 0) return nodes
  const allAtOrigin = nodes.every((node) => node.position.x === 0 && node.position.y === 0)
  if (!allAtOrigin) return nodes
  return nodes.map((node, index) => ({
    ...node,
    position: {
      x: 120 + (index % 3) * 280,
      y: 120 + Math.floor(index / 3) * 200,
    },
  }))
}

export function apiGraphToCanvasNodes(
  apiNodes: Array<Record<string, unknown>>,
  apiEdges: Array<Record<string, unknown>>
): CanvasWorkflowNode[] {
  const nodes = apiNodes.map((node) => {
    const id = String(node.id)
    const metadata = (node.metadata as Record<string, unknown>) || {}
    const rawConfig = (node.config as Record<string, unknown>) || {}
    const sourceId = node.source_id as string | undefined
    const metaAgentId =
      (metadata.agent_id as string | undefined) || (metadata.agentId as string | undefined)
    const config: Record<string, unknown> = {
      ...rawConfig,
      ...(sourceId && !rawConfig.source_id ? { source_id: sourceId } : {}),
      ...(metaAgentId && !rawConfig.agent_id && !rawConfig.agentId
        ? { agent_id: metaAgentId, agentId: metaAgentId }
        : {}),
      ...(metadata.task && !rawConfig.task ? { task: metadata.task } : {}),
    }
    const position = resolveNodePosition(node)
    const nodeType = normalizeCanvasNodeType(node.node_type ?? node.type)
    // Pack installs store requires_connector + config.action on invoke_tool steps.
    const requiresConnector =
      (node.requires_connector as string | undefined) ||
      (metadata.requires_connector as string | undefined) ||
      (config.requires_connector as string | undefined) ||
      (config.connector as string | undefined)
    const bind =
      nodeType === "connector" || Boolean(requiresConnector) || Boolean(config.action)
        ? resolveConnectorBind({
            vendor:
              (config.vendor as string) ||
              requiresConnector ||
              (node.systemName as string),
            selectedAction:
              (config.selected_action as string) || (config.selectedAction as string),
            config,
          })
        : null
    const resolvedType: CanvasNodeType =
      nodeType === "task" && bind?.vendor ? "connector" : nodeType
    const mergedConfig = bind ? connectorConfigWithBind(config, bind) : config
    const description =
      (node.description as string) ||
      (node.instruction as string) ||
      (metadata.task as string) ||
      (mergedConfig.task as string) ||
      (mergedConfig.instruction as string)
    return {
      id,
      type: resolvedType,
      name: String(node.name ?? node.title ?? "Node"),
      description,
      config: mergedConfig,
      position,
      connections: edgeTargets(apiEdges, id),
      state: "idle" as const,
      vendor: bind?.vendor || (mergedConfig.vendor as string) || (node.systemName as string),
      selectedAction:
        bind?.selectedAction ||
        (mergedConfig.selected_action as string) ||
        (mergedConfig.selectedAction as string),
      dataLabel: (mergedConfig.data_label as string) || (mergedConfig.dataLabel as string),
      decisionConfig: (metadata.decisionConfig ?? mergedConfig.decisionConfig) as DecisionConfig | undefined,
      outputPaths: (metadata.outputPaths ?? mergedConfig.outputPaths) as DecisionPath[] | undefined,
      councilConfig: (metadata.councilConfig ?? mergedConfig.councilConfig) as CouncilConfig | undefined,
    }
  })
  return autoLayoutCanvasNodes(nodes)
}

export function canvasToSavePayload(nodes: CanvasWorkflowNode[]) {
  const edges: Array<{ fromNodeId: string; toNodeId: string }> = []
  for (const node of nodes) {
    for (const target of node.connections) {
      edges.push({ fromNodeId: node.id, toNodeId: target })
    }
  }
  return {
    nodes: nodes.map((node) => {
      const bind =
        node.type === "connector"
          ? resolveConnectorBind({
              vendor: node.vendor,
              selectedAction: node.selectedAction,
              config: node.config,
            })
          : null
      const config = bind ? connectorConfigWithBind(node.config, bind) : node.config
      return {
        id: node.id,
        type: node.type,
        name: node.name,
        description: node.description,
        config,
        position: node.position,
        ...(node.type === "source" && config?.source_id
          ? { source_id: String(config.source_id) }
          : {}),
        metadata: {
          ...(node.decisionConfig ? { decisionConfig: node.decisionConfig } : {}),
          ...(node.outputPaths ? { outputPaths: node.outputPaths } : {}),
          ...(node.councilConfig ? { councilConfig: node.councilConfig } : {}),
          ...(config?.agent_id ? { agent_id: config.agent_id } : {}),
          ...(config?.next_agent_id ? { next_agent_id: config.next_agent_id } : {}),
          ...(config?.task ? { task: config.task } : {}),
          ...(bind?.vendor ? { vendor: bind.vendor } : {}),
          ...(bind?.selectedAction ? { selectedAction: bind.selectedAction } : {}),
          ...(bind?.action ? { action: bind.action } : {}),
        },
      }
    }),
    edges,
  }
}

export async function loadBuilderGraph(
  workflowId: string
): Promise<{ meta: WorkflowMeta; nodes: CanvasWorkflowNode[] } | null> {
  if (!isPersistableWorkflowId(workflowId)) {
    return null
  }
  const graph = (await workflowsApi.getBuilder(workflowId)) as unknown as BuilderGraphResponse
  return {
    meta: {
      id: workflowId,
      name: graph.name || "Workflow",
      description: graph.description,
      status: (graph.status as WorkflowMeta["status"]) || "draft",
    },
    nodes: apiGraphToCanvasNodes(graph.nodes, graph.edges),
  }
}

export async function saveBuilderGraph(
  workflowId: string,
  nodes: CanvasWorkflowNode[],
  options?: { name?: string; description?: string }
): Promise<{ success: boolean; stepCount: number }> {
  if (!isPersistableWorkflowId(workflowId)) {
    throw new Error("Cannot save non-UUID workflow. Create a real workflow first.")
  }
  const payload = { ...canvasToSavePayload(nodes), ...options }
  const saved = (await workflowsApi.saveBuilder(workflowId, payload)) as BuilderSaveResponse
  return {
    success: true,
    stepCount: saved.step_count ?? nodes.length,
  }
}

export async function executeWorkflow(
  workflowId: string,
  parameters?: Record<string, unknown>
): Promise<ExecuteResponse> {
  if (!isPersistableWorkflowId(workflowId)) {
    throw new Error("Cannot execute non-UUID workflow. Create a real workflow first.")
  }
  const response = await workflowsApi.execute({
    workflow_id: workflowId,
    parameters: { source: "canvas", ...(parameters ?? {}) },
  })
  const runId = response.run_id || response.id
  if (!runId) {
    throw new Error("Execute response missing run_id")
  }
  return {
    run_id: runId,
    status: response.status as ExecuteResponse["status"],
    errors: Array.isArray(response.errors)
      ? response.errors.map((item) => String(item))
      : [],
    steps: (response.steps ?? []).map((step) => ({
      node_id: String(step.nodeId ?? step.node_id ?? step.step_id ?? step.stepId ?? ""),
      status: String(step.status ?? "pending") as "pending" | "running" | "completed" | "failed",
      started_at: (step.started_at as string | undefined) ?? (step.startedAt as string | undefined),
      completed_at: (step.completed_at as string | undefined) ?? (step.completedAt as string | undefined),
      error: (step.error_message as string | undefined) ?? (step.errorMessage as string | undefined),
    })),
  }
}

export async function previewWorkflow(
  workflowId: string,
  parameters?: Record<string, unknown>
): Promise<WorkflowDryRunResponse> {
  if (!isPersistableWorkflowId(workflowId)) {
    throw new Error("Cannot preview non-UUID workflow. Create a real workflow first.")
  }
  return workflowsApi.dryRun({
    workflow_id: workflowId,
    parameters: parameters ?? {},
  })
}
