/**
 * STA-19: Map workflow builder canvas ↔ API builder graph (GET/PUT /api/workflows/{id}/builder).
 */
import { workflowsApi } from "@/lib/api"

export type CanvasNodeType =
  | "agent"
  | "task"
  | "connector"
  | "tool"
  | "source"
  | "approval"
  | "decision"
  | "council"

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
  status: "pending" | "running" | "completed" | "failed"
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

export function isPersistableWorkflowId(id: string): boolean {
  return UUID_RE.test(id)
}

function edgeTargets(edges: Array<Record<string, unknown>>, nodeId: string): string[] {
  return edges
    .filter((e) => String(e.from_node_id ?? e.fromNodeId) === nodeId)
    .map((e) => String(e.to_node_id ?? e.toNodeId))
}

export function apiGraphToCanvasNodes(
  apiNodes: Array<Record<string, unknown>>,
  apiEdges: Array<Record<string, unknown>>
): CanvasWorkflowNode[] {
  return apiNodes.map((node) => {
    const id = String(node.id)
    const metadata = (node.metadata as Record<string, unknown>) || {}
    const config = (node.config as Record<string, unknown>) || {}
    const position =
      (node.position as { x?: number; y?: number }) ||
      ({ x: Number(node.position_x ?? 0), y: Number(node.position_y ?? 0) })
    return {
      id,
      type: String(node.node_type ?? node.type ?? "task") as CanvasNodeType,
      name: String(node.name ?? node.title ?? "Node"),
      description: (node.description as string) || (node.instruction as string),
      config,
      position: { x: Number(position.x ?? 0), y: Number(position.y ?? 0) },
      connections: edgeTargets(apiEdges, id),
      state: "idle",
      vendor: (config.vendor as string) || (node.systemName as string),
      selectedAction: (config.selected_action as string) || (config.selectedAction as string),
      dataLabel: (config.data_label as string) || (config.dataLabel as string),
      decisionConfig: (metadata.decisionConfig ?? config.decisionConfig) as DecisionConfig | undefined,
      outputPaths: (metadata.outputPaths ?? config.outputPaths) as DecisionPath[] | undefined,
      councilConfig: (metadata.councilConfig ?? config.councilConfig) as CouncilConfig | undefined,
    }
  })
}

export function canvasToSavePayload(nodes: CanvasWorkflowNode[]) {
  const edges: Array<{ fromNodeId: string; toNodeId: string }> = []
  for (const node of nodes) {
    for (const target of node.connections) {
      edges.push({ fromNodeId: node.id, toNodeId: target })
    }
  }
  return {
    nodes: nodes.map((node) => ({
      id: node.id,
      type: node.type,
      name: node.name,
      description: node.description,
      config: node.config,
      position: node.position,
      metadata: {
        ...(node.decisionConfig ? { decisionConfig: node.decisionConfig } : {}),
        ...(node.outputPaths ? { outputPaths: node.outputPaths } : {}),
        ...(node.councilConfig ? { councilConfig: node.councilConfig } : {}),
        ...(node.config?.agent_id ? { agent_id: node.config.agent_id } : {}),
        ...(node.config?.next_agent_id ? { next_agent_id: node.config.next_agent_id } : {}),
        ...(node.config?.task ? { task: node.config.task } : {}),
      },
    })),
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
  const run = await workflowsApi.execute({
    workflow_id: workflowId,
    parameters: parameters ?? {},
  })
  return {
    run_id: run.id,
    status: run.status as ExecuteResponse["status"],
  }
}
