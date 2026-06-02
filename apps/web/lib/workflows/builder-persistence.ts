// Workflow Builder Persistence Layer
// Maps between canvas nodes and API payloads for save/load/execute

import { workflowsApi, type Workflow, type WorkflowNode as ApiWorkflowNode, type WorkflowEdge } from "@/lib/api"

// Canvas node shape used by the builder
export interface CanvasWorkflowNode {
  id: string
  type: "agent" | "task" | "connector" | "tool" | "source" | "approval" | "decision" | "council"
  name: string
  description?: string
  config: Record<string, unknown>
  position: { x: number; y: number }
  connections: string[] // target node ids
  state?: "idle" | "running" | "success" | "error" | "waiting" | "evaluating" | "debating" | "consensus" | "escalated"
  vendor?: string
  selectedAction?: string
  dataLabel?: string
  decisionConfig?: {
    objective?: string
    strategy?: "rule-based" | "ai-assisted" | "hybrid"
    inputSources?: string[]
    conditions?: string
    outputPaths?: { id: string; label: string; condition?: string; targetNodeId?: string; isDefault?: boolean }[]
    reasoning?: {
      summary: string
      confidence: number
      factors: string[]
      chosenPath: string
      rejectedPaths?: string[]
    }
  }
  outputPaths?: { id: string; label: string; condition?: string; targetNodeId?: string; isDefault?: boolean }[]
  councilConfig?: Record<string, unknown>
  metadata?: Record<string, unknown>
}

// Workflow metadata from API
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

// Builder graph response from API
export interface BuilderGraphResponse {
  workflow_id: string
  name: string
  description?: string
  status: "draft" | "active" | "paused" | "archived"
  nodes: ApiWorkflowNode[]
  edges: WorkflowEdge[]
}

// Execute response
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

/**
 * Check if ID is a persistable UUID (real workflow from backend)
 */
export function isPersistableWorkflowId(id: string): boolean {
  const uuidRegex = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i
  return uuidRegex.test(id)
}

/**
 * Convert API nodes/edges to canvas nodes with connections array
 */
export function apiGraphToCanvasNodes(
  apiNodes: ApiWorkflowNode[],
  apiEdges: WorkflowEdge[]
): CanvasWorkflowNode[] {
  // Build edge lookup: source_node_id -> target_node_ids[]
  const edgeMap = new Map<string, string[]>()
  for (const edge of apiEdges) {
    const targets = edgeMap.get(edge.source_node_id) || []
    targets.push(edge.target_node_id)
    edgeMap.set(edge.source_node_id, targets)
  }

  return apiNodes.map((apiNode) => {
    const nodeType = (apiNode.node_type || apiNode.type || "task") as CanvasWorkflowNode["type"]
    const position = apiNode.position || { x: apiNode.position_x || 0, y: apiNode.position_y || 0 }
    
    return {
      id: apiNode.id,
      type: nodeType,
      name: apiNode.title || apiNode.name || "Untitled",
      description: apiNode.description,
      config: apiNode.config || {},
      position: { x: position.x, y: position.y },
      connections: edgeMap.get(apiNode.id) || [],
      state: "idle",
      vendor: apiNode.metadata?.vendor as string | undefined,
      selectedAction: apiNode.metadata?.selected_action as string | undefined,
      dataLabel: apiNode.metadata?.data_label as string | undefined,
      decisionConfig: apiNode.metadata?.decisionConfig as CanvasWorkflowNode["decisionConfig"],
      outputPaths: apiNode.metadata?.outputPaths as CanvasWorkflowNode["outputPaths"],
      councilConfig: apiNode.metadata?.councilConfig as Record<string, unknown>,
      metadata: apiNode.metadata,
    }
  })
}

/**
 * Convert canvas nodes to API save payload (nodes + edges derived from connections)
 */
export function canvasToSavePayload(nodes: CanvasWorkflowNode[]): {
  nodes: Partial<ApiWorkflowNode>[]
  edges: Partial<WorkflowEdge>[]
} {
  const apiNodes: Partial<ApiWorkflowNode>[] = nodes.map((node) => ({
    id: node.id,
    node_type: node.type,
    title: node.name,
    description: node.description,
    config: node.config,
    position: node.position,
    position_x: node.position.x,
    position_y: node.position.y,
    metadata: {
      vendor: node.vendor,
      selected_action: node.selectedAction,
      data_label: node.dataLabel,
      decisionConfig: node.decisionConfig,
      outputPaths: node.outputPaths,
      councilConfig: node.councilConfig,
      ...node.metadata,
    },
  }))

  // Derive edges from node connections
  const apiEdges: Partial<WorkflowEdge>[] = []
  for (const node of nodes) {
    for (const targetId of node.connections) {
      apiEdges.push({
        source_node_id: node.id,
        target_node_id: targetId,
      })
    }
  }

  return { nodes: apiNodes, edges: apiEdges }
}

/**
 * Load workflow builder graph from API
 */
export async function loadBuilderGraph(workflowId: string): Promise<{
  meta: WorkflowMeta
  nodes: CanvasWorkflowNode[]
} | null> {
  if (!isPersistableWorkflowId(workflowId)) {
    return null // Non-UUID ids use local demo data
  }

  try {
    // Fetch workflow metadata
    const workflow = await workflowsApi.get(workflowId)
    
    // Fetch nodes and edges
    const [nodesResponse, edgesResponse] = await Promise.all([
      workflowsApi.nodes.list(workflowId),
      workflowsApi.edges.list(workflowId),
    ])

    const nodes = Array.isArray(nodesResponse) ? nodesResponse : (nodesResponse as { nodes: ApiWorkflowNode[] }).nodes || []
    const edges = Array.isArray(edgesResponse) ? edgesResponse : (edgesResponse as { edges: WorkflowEdge[] }).edges || []

    const canvasNodes = apiGraphToCanvasNodes(nodes, edges)

    return {
      meta: {
        id: workflow.id,
        name: workflow.name,
        description: workflow.description,
        status: workflow.status as WorkflowMeta["status"],
        environment: workflow.environment as WorkflowMeta["environment"],
        version: workflow.active_version_id ? `v${workflow.active_version_id}` : undefined,
        created_at: workflow.created_at,
        updated_at: workflow.updated_at,
      },
      nodes: canvasNodes,
    }
  } catch (error) {
    console.error("[builder-persistence] Failed to load workflow:", error)
    throw error
  }
}

/**
 * Save workflow builder graph to API
 */
export async function saveBuilderGraph(
  workflowId: string,
  nodes: CanvasWorkflowNode[],
  options?: { name?: string; description?: string }
): Promise<{ success: boolean; stepCount: number }> {
  if (!isPersistableWorkflowId(workflowId)) {
    throw new Error("Cannot save non-UUID workflow. Create a real workflow first.")
  }

  try {
    const { nodes: apiNodes, edges: apiEdges } = canvasToSavePayload(nodes)

    // Update workflow metadata if provided
    if (options?.name || options?.description) {
      await workflowsApi.update(workflowId, {
        name: options.name,
        description: options.description,
      })
    }

    // Clear existing nodes and edges, then recreate
    // This is a simple approach - a more sophisticated one would diff and patch
    const existingNodes = await workflowsApi.nodes.list(workflowId)
    const existingNodesList = Array.isArray(existingNodes) ? existingNodes : (existingNodes as { nodes: ApiWorkflowNode[] }).nodes || []
    
    const existingEdges = await workflowsApi.edges.list(workflowId)
    const existingEdgesList = Array.isArray(existingEdges) ? existingEdges : (existingEdges as { edges: WorkflowEdge[] }).edges || []

    // Delete existing edges first (to avoid FK issues)
    await Promise.all(existingEdgesList.map((e) => workflowsApi.edges.delete(workflowId, e.id)))
    
    // Delete existing nodes
    await Promise.all(existingNodesList.map((n) => workflowsApi.nodes.delete(workflowId, n.id)))

    // Create new nodes
    for (const node of apiNodes) {
      await workflowsApi.nodes.create(workflowId, node as Parameters<typeof workflowsApi.nodes.create>[1])
    }

    // Create new edges
    for (const edge of apiEdges) {
      await workflowsApi.edges.create(workflowId, edge as Parameters<typeof workflowsApi.edges.create>[1])
    }

    return { success: true, stepCount: nodes.length }
  } catch (error) {
    console.error("[builder-persistence] Failed to save workflow:", error)
    throw error
  }
}

/**
 * Execute workflow via API
 */
export async function executeWorkflow(
  workflowId: string,
  parameters?: Record<string, unknown>
): Promise<ExecuteResponse> {
  if (!isPersistableWorkflowId(workflowId)) {
    throw new Error("Cannot execute non-UUID workflow. Create a real workflow first.")
  }

  try {
    const response = await workflowsApi.execute({
      workflow_id: workflowId,
      parameters,
    })

    return {
      run_id: response.id,
      status: response.status as ExecuteResponse["status"],
      steps: [], // Will be populated by polling if needed
    }
  } catch (error) {
    console.error("[builder-persistence] Failed to execute workflow:", error)
    throw error
  }
}
