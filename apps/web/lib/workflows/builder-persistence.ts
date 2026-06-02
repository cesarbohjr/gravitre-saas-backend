/**
 * STA-19: Map workflow builder canvas ↔ API builder graph (GET/PUT /api/workflows/{id}/builder).
 */
import { workflowsApi } from "@/lib/api"

type NodeType = "agent" | "task" | "connector" | "tool" | "source" | "approval" | "decision" | "council"

export interface WorkflowMeta {
  id: string
  name: string
  description?: string
  status: "draft" | "active" | "paused" | "archived"
  environment?: "development" | "staging" | "production"
  version?: string
}

export interface ExecuteResponse {
  run_id: string
  status: "pending" | "running" | "completed" | "failed"
}

const UUID_RE =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i

export function isPersistableWorkflowId(id: string): boolean {
  return UUID_RE.test(id)
}

export interface CanvasWorkflowNode {
  id: string
  type: NodeType
  name: string
  description?: string
  config: Record<string, unknown>
  position: { x: number; y: number }
  connections: string[]
  state?: string
  vendor?: string
  selectedAction?: string
  dataLabel?: string
  decisionConfig?: Record<string, unknown>
  outputPaths?: Array<Record<string, unknown>>
  councilConfig?: Record<string, unknown>
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
      type: (String(node.node_type ?? node.type ?? "task") as NodeType),
      name: String(node.name ?? node.title ?? "Node"),
      description: (node.description as string) || (node.instruction as string),
      config,
      position: { x: Number(position.x ?? 0), y: Number(position.y ?? 0) },
      connections: edgeTargets(apiEdges, id),
      state: "idle",
      vendor: (config.vendor as string) || (node.systemName as string),
      decisionConfig: metadata.decisionConfig as CanvasWorkflowNode["decisionConfig"],
      outputPaths: metadata.outputPaths as CanvasWorkflowNode["outputPaths"],
      councilConfig: metadata.councilConfig as CanvasWorkflowNode["councilConfig"],
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
  const response = await apiFetch(apiUrl(`/api/workflows/${workflowId}/builder`))
  if (!response.ok) {
    const body = await response.json().catch(() => ({}))
    throw new Error(
      (body as { detail?: string }).detail || `Failed to load workflow builder (${response.status})`
    )
  }
  const graph = (await response.json()) as BuilderGraphResponse
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
  meta?: { name?: string; description?: string }
): Promise<{ success: boolean; stepCount: number }> {
  if (!isPersistableWorkflowId(workflowId)) {
    throw new Error("Cannot save non-UUID workflow. Create a real workflow first.")
  }
  const payload = { ...canvasToSavePayload(nodes), ...meta }
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
