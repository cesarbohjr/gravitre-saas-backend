"use client"

import { useState, useCallback, useEffect } from "react"
import { use } from "react"
import useSWR from "swr"
import Link from "next/link"
import { AppShell } from "@/components/gravitre/app-shell"
import { StatusBadge } from "@/components/gravitre/status-badge"
import { EnvironmentBadge } from "@/components/gravitre/environment-badge"
import { ModelSelector, ModelInheritanceChain } from "@/components/gravitre/model-selector"
import { VendorLogo } from "@/components/gravitre/vendor-logo"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import {
  ArrowLeft,
  Plus,
  Play,
  Save,
  Settings,
  Bot,
  Zap,
  Database,
  Plug,
  FileText,
  Shield,
  ChevronRight,
  X,
  GripVertical,
  Trash2,
  Copy,
  MoreHorizontal,
  Search,
  Workflow,
  ArrowRight,
  CheckCircle,
  AlertTriangle,
} from "lucide-react"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import { fetcher } from "@/lib/fetcher"

// Node types
type NodeType = "agent" | "task" | "connector" | "tool" | "source" | "approval"

interface WorkflowNode {
  id: string
  type: NodeType
  name: string
  description?: string
  config: Record<string, unknown>
  position: { x: number; y: number }
  connections: string[]
}

interface Connection {
  id: string
  from: string
  to: string
}

// Mock workflow data
type WorkflowMeta = {
  id: string
  name: string
  description: string
  status: "active" | "paused" | "draft" | "error"
  environment: "production" | "staging"
  version: string
}

const workflowMeta: WorkflowMeta = {
  id: "wf-001",
  name: "Customer Data Pipeline",
  description: "End-to-end customer data sync with validation and enrichment",
  status: "draft",
  environment: "staging",
  version: "v1.2.0",
}

// Mock nodes for the canvas
const initialNodes: WorkflowNode[] = [
  {
    id: "node-1",
    type: "source",
    name: "Salesforce CRM",
    description: "Pull customer records",
    config: { connector: "salesforce", table: "contacts" },
    position: { x: 100, y: 150 },
    connections: ["node-2"],
  },
  {
    id: "node-2",
    type: "agent",
    name: "Data Validator",
    description: "Validate and clean records",
    config: { model: "gpt-4-turbo", temperature: 0.3 },
    position: { x: 350, y: 150 },
    connections: ["node-3"],
  },
  {
    id: "node-3",
    type: "task",
    name: "Enrich with metadata",
    description: "Add company info and scoring",
    config: { instruction: "Enrich customer records with company data" },
    position: { x: 600, y: 100 },
    connections: ["node-4"],
  },
  {
    id: "node-4",
    type: "approval",
    name: "Quality Gate",
    description: "Review before production",
    config: { approvers: ["admin"], autoApprove: false },
    position: { x: 600, y: 250 },
    connections: ["node-5"],
  },
  {
    id: "node-5",
    type: "connector",
    name: "PostgreSQL",
    description: "Write to data warehouse",
    config: { connector: "postgresql", schema: "customers" },
    position: { x: 850, y: 150 },
    connections: [],
  },
]

function mapBackendNodeType(type: string | null | undefined): NodeType {
  if (type === "agent" || type === "task" || type === "connector" || type === "tool" || type === "source" || type === "approval") {
    return type
  }
  return "task"
}

function mapBuilderNodes(
  nodes: Array<Record<string, unknown>> | undefined,
  edges: Array<Record<string, unknown>> | undefined
): WorkflowNode[] {
  if (!nodes || nodes.length === 0) return initialNodes
  const outgoing: Record<string, string[]> = {}
  for (const edge of edges ?? []) {
    const from = String(edge.from_node_id ?? edge.fromNodeId ?? "")
    const to = String(edge.to_node_id ?? edge.toNodeId ?? "")
    if (!from || !to) continue
    outgoing[from] = [...(outgoing[from] ?? []), to]
  }
  return nodes.map((node, index) => {
    const nodeId = String(node.id ?? `node-${index}`)
    const position = (node.position as Record<string, unknown> | undefined) ?? {}
    return {
      id: nodeId,
      type: mapBackendNodeType(String(node.type ?? node.node_type ?? "task")),
      name: String(node.name ?? node.title ?? `Node ${index + 1}`),
      description: String(node.description ?? node.instruction ?? ""),
      config: (node.config as Record<string, unknown> | undefined) ?? {},
      position: {
        x: Number(position.x ?? node.position_x ?? 0),
        y: Number(position.y ?? node.position_y ?? 0),
      },
      connections: outgoing[nodeId] ?? [],
    }
  })
}

// Library items
const agentLibrary = [
  { id: "agent-1", name: "Data Validator", description: "Validates and cleans data" },
  { id: "agent-2", name: "Content Writer", description: "Generates content" },
  { id: "agent-3", name: "Research Analyst", description: "Analyzes and summarizes" },
  { id: "agent-4", name: "Code Reviewer", description: "Reviews code quality" },
]

const connectorLibrary = [
  { id: "conn-1", name: "Salesforce", vendor: "salesforce" },
  { id: "conn-2", name: "HubSpot", vendor: "hubspot" },
  { id: "conn-3", name: "Slack", vendor: "slack" },
  { id: "conn-4", name: "Microsoft 365", vendor: "microsoft" },
  { id: "conn-5", name: "PostgreSQL", vendor: "postgresql" },
  { id: "conn-6", name: "Stripe", vendor: "stripe" },
]

const sourceLibrary = [
  { id: "src-1", name: "CRM Records", type: "database" },
  { id: "src-2", name: "Internal Docs", type: "documents" },
  { id: "src-3", name: "API Endpoints", type: "api" },
]

const toolLibrary = [
  { id: "tool-1", name: "SQL Query", description: "Execute SQL" },
  { id: "tool-2", name: "Webhook", description: "HTTP calls" },
  { id: "tool-3", name: "Excel Export", description: "Spreadsheet" },
]

// Node type configs
const nodeTypeConfig: Record<NodeType, { icon: typeof Bot; color: string; label: string }> = {
  agent: { icon: Bot, color: "bg-info/20 border-info/40 text-info", label: "Agent" },
  task: { icon: FileText, color: "bg-success/20 border-success/40 text-success", label: "Task" },
  connector: { icon: Plug, color: "bg-warning/20 border-warning/40 text-warning", label: "Connector" },
  tool: { icon: Zap, color: "bg-chart-4/20 border-chart-4/40 text-chart-4", label: "Tool" },
  source: { icon: Database, color: "bg-muted border-border text-muted-foreground", label: "Source" },
  approval: { icon: Shield, color: "bg-destructive/20 border-destructive/40 text-destructive", label: "Approval" },
}

// Canvas Node Component
function CanvasNode({
  node,
  isSelected,
  isConnecting,
  isConnectingSource,
  onSelect,
  onDelete,
  onDrag,
  onStartConnection,
  onEndConnection,
}: {
  node: WorkflowNode
  isSelected: boolean
  isConnecting: boolean
  isConnectingSource: boolean
  onSelect: () => void
  onDelete: () => void
  onDrag: (position: { x: number; y: number }) => void
  onStartConnection: () => void
  onEndConnection: () => void
}) {
  const config = nodeTypeConfig[node.type]
  const Icon = config.icon
  const [isDragging, setIsDragging] = useState(false)
  const [dragOffset, setDragOffset] = useState({ x: 0, y: 0 })

  const handleMouseDown = (e: React.MouseEvent) => {
    e.preventDefault()
    setIsDragging(true)
    setDragOffset({
      x: e.clientX - node.position.x,
      y: e.clientY - node.position.y,
    })
  }

  const handleDoubleClick = (e: React.MouseEvent) => {
    e.preventDefault()
    e.stopPropagation()
    onSelect()
  }

  useEffect(() => {
    if (!isDragging) return

    const handleMouseMove = (e: MouseEvent) => {
      const newX = Math.max(0, e.clientX - dragOffset.x)
      const newY = Math.max(0, e.clientY - dragOffset.y)
      onDrag({ x: newX, y: newY })
    }

    const handleMouseUp = () => {
      setIsDragging(false)
    }

    window.addEventListener("mousemove", handleMouseMove)
    window.addEventListener("mouseup", handleMouseUp)

    return () => {
      window.removeEventListener("mousemove", handleMouseMove)
      window.removeEventListener("mouseup", handleMouseUp)
    }
  }, [isDragging, dragOffset, onDrag])

  return (
    <div
      className={`absolute cursor-grab transition-shadow duration-150 ${isSelected ? "z-10" : "z-0"} ${isDragging ? "cursor-grabbing z-20" : ""}`}
      style={{ left: node.position.x, top: node.position.y }}
      onMouseDown={handleMouseDown}
      onDoubleClick={handleDoubleClick}
    >
      <div
        className={`
          group relative w-56 rounded-lg border bg-card p-3 shadow-lg
          ${isSelected ? "border-info ring-2 ring-info/30" : "border-border hover:border-muted-foreground/50"}
        `}
      >
        {/* Drag handle */}
        <div className="absolute -left-2 top-1/2 -translate-y-1/2 opacity-0 group-hover:opacity-100 transition-opacity">
          <GripVertical className="h-4 w-4 text-muted-foreground" />
        </div>

        {/* Delete button */}
        <button
          onClick={(e) => {
            e.stopPropagation()
            onDelete()
          }}
          className="absolute -right-2 -top-2 h-5 w-5 rounded-full bg-destructive text-destructive-foreground opacity-0 group-hover:opacity-100 transition-opacity flex items-center justify-center"
        >
          <X className="h-3 w-3" />
        </button>

        {/* Node header */}
        <div className="flex items-start gap-2.5 mb-2">
          <div className={`flex h-8 w-8 shrink-0 items-center justify-center rounded-md border ${config.color}`}>
            <Icon className="h-4 w-4" />
          </div>
          <div className="flex-1 min-w-0">
            <p className="text-sm font-medium text-foreground truncate">{node.name}</p>
            <p className="text-[10px] text-muted-foreground">{config.label}</p>
          </div>
        </div>

        {/* Description */}
        {node.description && (
          <p className="text-xs text-muted-foreground line-clamp-2 mb-2">{node.description}</p>
        )}

        {/* Connection indicator */}
        {node.connections.length > 0 && (
          <div className="flex items-center gap-1 text-[10px] text-muted-foreground">
            <ArrowRight className="h-3 w-3" />
            <span>{node.connections.length} connection{node.connections.length > 1 ? "s" : ""}</span>
          </div>
        )}

        {/* Connection points - Input (left) */}
        <button
          onClick={(e) => {
            e.stopPropagation()
            if (isConnecting && !isConnectingSource) {
              onEndConnection()
            }
          }}
          onMouseEnter={(e) => {
            if (isConnecting && !isConnectingSource) {
              e.currentTarget.classList.add("scale-150")
            }
          }}
          onMouseLeave={(e) => {
            e.currentTarget.classList.remove("scale-150")
          }}
          className={`absolute left-0 top-1/2 -translate-x-1/2 -translate-y-1/2 h-3.5 w-3.5 rounded-full border-2 transition-all duration-200 ${
            isConnecting && !isConnectingSource
              ? "border-info bg-info shadow-[0_0_12px_rgba(59,130,246,0.6)] cursor-pointer animate-pulse"
              : "border-muted-foreground/30 bg-card opacity-0 group-hover:opacity-100 hover:border-info hover:bg-info/20 hover:scale-125"
          }`}
        />
        {/* Connection points - Output (right) - Blue dot */}
        <button
          onMouseDown={(e) => {
            e.stopPropagation()
            e.preventDefault()
            if (!isConnecting) {
              onStartConnection()
            }
          }}
          className={`absolute right-0 top-1/2 translate-x-1/2 -translate-y-1/2 h-3.5 w-3.5 rounded-full border-2 transition-all duration-200 cursor-pointer ${
            isConnectingSource
              ? "border-info bg-info scale-150 shadow-[0_0_16px_rgba(59,130,246,0.8)]"
              : "border-info bg-info/80 shadow-[0_0_8px_rgba(59,130,246,0.4)] hover:scale-125 hover:shadow-[0_0_12px_rgba(59,130,246,0.6)]"
          }`}
        />
      </div>
    </div>
  )
}

// Library Panel Item
function LibraryItem({
  name,
  description,
  icon: Icon,
  vendor,
  onAdd,
}: {
  name: string
  description?: string
  icon?: typeof Bot
  vendor?: string
  onAdd: () => void
}) {
  return (
    <button
      onClick={onAdd}
      className="w-full flex items-center gap-2.5 p-2 rounded-md hover:bg-secondary/50 transition-colors text-left group"
    >
      {vendor ? (
        <VendorLogo vendor={vendor} size="sm" />
      ) : Icon ? (
        <div className="flex h-6 w-6 shrink-0 items-center justify-center rounded bg-muted">
          <Icon className="h-3.5 w-3.5 text-muted-foreground" />
        </div>
      ) : null}
      <div className="flex-1 min-w-0">
        <p className="text-xs font-medium text-foreground truncate">{name}</p>
        {description && <p className="text-[10px] text-muted-foreground truncate">{description}</p>}
      </div>
      <Plus className="h-3.5 w-3.5 text-muted-foreground opacity-0 group-hover:opacity-100 transition-opacity" />
    </button>
  )
}

// Config Panel
function ConfigPanel({
  node,
  onClose,
  onUpdate,
}: {
  node: WorkflowNode | null
  onClose: () => void
  onUpdate: (updates: Partial<WorkflowNode>) => void
}) {
  if (!node) return null

  const config = nodeTypeConfig[node.type]
  const Icon = config.icon

  return (
    <div className="hidden md:flex w-80 border-l border-border bg-card flex-col">
      {/* Header */}
      <div className="flex items-center justify-between border-b border-border p-4">
        <div className="flex items-center gap-2">
          <div className={`flex h-7 w-7 items-center justify-center rounded-md border ${config.color}`}>
            <Icon className="h-3.5 w-3.5" />
          </div>
          <span className="text-sm font-medium text-foreground">{config.label} Configuration</span>
        </div>
        <button onClick={onClose} className="text-muted-foreground hover:text-foreground">
          <X className="h-4 w-4" />
        </button>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto p-4">
        <div className="space-y-4">
          {/* Name */}
          <div>
            <label className="text-xs font-medium text-muted-foreground uppercase tracking-wide mb-1.5 block">
              Name
            </label>
            <Input
              value={node.name}
              onChange={(e) => onUpdate({ name: e.target.value })}
              className="h-8 text-sm bg-secondary border-border"
            />
          </div>

          {/* Description */}
          <div>
            <label className="text-xs font-medium text-muted-foreground uppercase tracking-wide mb-1.5 block">
              Description
            </label>
            <textarea
              value={node.description || ""}
              onChange={(e) => onUpdate({ description: e.target.value })}
              className="w-full h-20 rounded-md border border-border bg-secondary px-3 py-2 text-sm resize-none focus:outline-none focus:ring-1 focus:ring-ring"
              placeholder="Describe what this step does..."
            />
          </div>

          {/* Type-specific config */}
          {node.type === "agent" && (
            <>
              <div>
                <label className="text-xs font-medium text-muted-foreground uppercase tracking-wide mb-1.5 block">
                  Model
                </label>
                <ModelSelector
                  value={String(node.config.model || "auto")}
                  onChange={(model) => onUpdate({ config: { ...node.config, model } })}
                  inheritedFrom="agent"
                  onResetToDefault={() => onUpdate({ config: { ...node.config, model: "auto" } })}
                  showAdvanced
                  size="sm"
                />
                {/* Inheritance chain */}
                <div className="mt-2">
                  <ModelInheritanceChain
                    workspaceModel="auto"
                    agentModel="balanced"
                    taskModel={String(node.config.model || "")}
                  />
                </div>
              </div>
            </>
          )}

          {node.type === "task" && (
            <>
              <div>
                <label className="text-xs font-medium text-muted-foreground uppercase tracking-wide mb-1.5 block">
                  Instructions
                </label>
                <textarea
                  className="w-full h-32 rounded-md border border-border bg-secondary px-3 py-2 text-sm resize-none focus:outline-none focus:ring-1 focus:ring-ring font-mono"
                  placeholder="Enter task instructions for the agent..."
                  defaultValue={String(node.config.instruction || "")}
                />
              </div>
              <div>
                <label className="text-xs font-medium text-muted-foreground uppercase tracking-wide mb-1.5 block">
                  Model Override
                </label>
                <p className="text-[10px] text-muted-foreground mb-1.5">
                  Optionally override the agent&apos;s default model for this step
                </p>
                <ModelSelector
                  value={String(node.config.model || "auto")}
                  onChange={(model) => onUpdate({ config: { ...node.config, model } })}
                  inheritedFrom="agent"
                  onResetToDefault={() => onUpdate({ config: { ...node.config, model: "auto" } })}
                  size="sm"
                />
              </div>
            </>
          )}

          {node.type === "connector" && (
            <>
              <div>
                <label className="text-xs font-medium text-muted-foreground uppercase tracking-wide mb-1.5 block">
                  Connection
                </label>
                <select className="w-full h-8 rounded-md border border-border bg-secondary px-3 text-sm focus:outline-none focus:ring-1 focus:ring-ring">
                  <option value="salesforce-prod">Salesforce (Production)</option>
                  <option value="hubspot-main">HubSpot (Main)</option>
                  <option value="postgres-dw">PostgreSQL (Data Warehouse)</option>
                </select>
              </div>
              <div>
                <label className="text-xs font-medium text-muted-foreground uppercase tracking-wide mb-1.5 block">
                  Schema / Table
                </label>
                <Input
                  placeholder="e.g., customers.contacts"
                  className="h-8 text-sm bg-secondary border-border font-mono"
                />
              </div>
            </>
          )}

          {node.type === "approval" && (
            <>
              <div>
                <label className="text-xs font-medium text-muted-foreground uppercase tracking-wide mb-1.5 block">
                  Approvers
                </label>
                <Input
                  placeholder="admin@company.com"
                  className="h-8 text-sm bg-secondary border-border"
                />
              </div>
              <div className="flex items-center justify-between">
                <label className="text-xs font-medium text-muted-foreground">Auto-approve in staging</label>
                <input type="checkbox" className="rounded border-border" />
              </div>
            </>
          )}

          {/* Environment */}
          <div className="pt-4 border-t border-border">
            <label className="text-xs font-medium text-muted-foreground uppercase tracking-wide mb-1.5 block">
              Environment
            </label>
            <div className="flex items-center gap-2">
              <EnvironmentBadge environment="staging" />
              <span className="text-xs text-muted-foreground">Inherited from workflow</span>
            </div>
          </div>

          {/* Admin marker */}
          {node.type === "approval" && (
            <div className="flex items-center gap-2 p-2 rounded-md bg-warning/10 border border-warning/20">
              <AlertTriangle className="h-3.5 w-3.5 text-warning" />
              <span className="text-xs text-warning">Requires admin approval</span>
            </div>
          )}
        </div>
      </div>

      {/* Footer actions */}
      <div className="border-t border-border p-4 flex items-center gap-2">
        <Button variant="outline" size="sm" className="h-8 gap-1.5 flex-1">
          <Copy className="h-3.5 w-3.5" />
          Duplicate
        </Button>
        <Button variant="outline" size="sm" className="h-8 gap-1.5 text-destructive hover:text-destructive flex-1">
          <Trash2 className="h-3.5 w-3.5" />
          Delete
        </Button>
      </div>
    </div>
  )
}

export default function WorkflowBuilderPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params)
  const { data } = useSWR<{ workflow?: Record<string, unknown>; nodes?: Array<Record<string, unknown>>; edges?: Array<Record<string, unknown>> }>(
    `/api/workflows/${id}`,
    fetcher,
    { revalidateOnFocus: false }
  )
  const [nodes, setNodes] = useState<WorkflowNode[]>(initialNodes)
  const [workflowMetaState, setWorkflowMetaState] = useState<WorkflowMeta>(workflowMeta)
  const [selectedNode, setSelectedNode] = useState<WorkflowNode | null>(null)
  const [activeLibrary, setActiveLibrary] = useState<"agents" | "connectors" | "sources" | "tools">("agents")
  const [searchQuery, setSearchQuery] = useState("")
  const [connectingFrom, setConnectingFrom] = useState<string | null>(null)
  const [mousePos, setMousePos] = useState({ x: 0, y: 0 })

  useEffect(() => {
    if (!data) return
    setNodes(mapBuilderNodes(data.nodes, data.edges))
    if (data.workflow) {
      setWorkflowMetaState((prev) => ({
        ...prev,
        id: String(data.workflow?.id ?? prev.id),
        name: String(data.workflow?.name ?? prev.name),
        description: String(data.workflow?.description ?? prev.description),
        status: String(data.workflow?.status ?? prev.status) as WorkflowMeta["status"],
        environment: data.workflow?.environment === "production" ? "production" : "staging",
        version: String(data.workflow?.version ?? prev.version),
      }))
    }
  }, [data])

  const handleSaveWorkflow = async () => {
    await fetch(`/api/workflows/${id}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        name: workflowMetaState.name,
        description: workflowMetaState.description,
        status: workflowMetaState.status,
        definition: {
          nodes: nodes.map((node) => ({
            id: node.id,
            type: node.type,
            name: node.name,
            description: node.description,
            config: node.config,
            position: node.position,
          })),
          edges: connections.map((connection) => ({
            from: connection.from.id,
            to: connection.to.id,
          })),
          config: {},
        },
      }),
    })
  }

  const handleSelectNode = useCallback((node: WorkflowNode) => {
    setSelectedNode(node)
  }, [])

  const handleDeleteNode = useCallback((nodeId: string) => {
    setNodes((prev) => prev.filter((n) => n.id !== nodeId))
    if (selectedNode?.id === nodeId) {
      setSelectedNode(null)
    }
  }, [selectedNode])

  const handleUpdateNode = useCallback((updates: Partial<WorkflowNode>) => {
    if (!selectedNode) return
    setNodes((prev) =>
      prev.map((n) => (n.id === selectedNode.id ? { ...n, ...updates } : n))
    )
    setSelectedNode((prev) => (prev ? { ...prev, ...updates } : null))
  }, [selectedNode])

  const handleDragNode = useCallback((nodeId: string, position: { x: number; y: number }) => {
    setNodes((prev) =>
      prev.map((n) => (n.id === nodeId ? { ...n, position } : n))
    )
  }, [])

  const addNode = useCallback((type: NodeType, name: string, description?: string) => {
    const newNode: WorkflowNode = {
      id: `node-${Date.now()}`,
      type,
      name,
      description,
      config: {},
      position: { x: 200 + Math.random() * 200, y: 100 + Math.random() * 200 },
      connections: [],
    }
    setNodes((prev) => [...prev, newNode])
    setSelectedNode(newNode)
  }, [])

  const handleStartConnection = useCallback((nodeId: string) => {
    setConnectingFrom(nodeId)
  }, [])

  const handleEndConnection = useCallback((toNodeId: string) => {
    if (connectingFrom && connectingFrom !== toNodeId) {
      // Check if connection already exists
      const fromNode = nodes.find((n) => n.id === connectingFrom)
      if (fromNode && !fromNode.connections.includes(toNodeId)) {
        setNodes((prev) =>
          prev.map((n) =>
            n.id === connectingFrom
              ? { ...n, connections: [...n.connections, toNodeId] }
              : n
          )
        )
      }
    }
    setConnectingFrom(null)
  }, [connectingFrom, nodes])

  const handleCancelConnection = useCallback(() => {
    setConnectingFrom(null)
  }, [])

  const handleRemoveConnection = useCallback((fromId: string, toId: string) => {
    setNodes((prev) =>
      prev.map((n) =>
        n.id === fromId
          ? { ...n, connections: n.connections.filter((c) => c !== toId) }
          : n
      )
    )
  }, [])

  // Calculate connections
  const connections: { from: WorkflowNode; to: WorkflowNode }[] = []
  nodes.forEach((node) => {
    node.connections.forEach((connId) => {
      const toNode = nodes.find((n) => n.id === connId)
      if (toNode) {
        connections.push({ from: node, to: toNode })
      }
    })
  })

  return (
    <AppShell>
      <div className="flex h-full flex-col">
        {/* Top toolbar */}
        <div className="flex-shrink-0 border-b border-border bg-card px-3 md:px-4 py-2 md:py-3">
          <div className="flex items-center justify-between gap-2">
            <div className="flex items-center gap-2 md:gap-3 min-w-0">
              <Link
                href={`/workflows/${id}`}
                className="text-muted-foreground hover:text-foreground transition-colors shrink-0"
              >
                <ArrowLeft className="h-4 w-4" />
              </Link>
              <div className="hidden sm:flex items-center gap-2 min-w-0">
                <Workflow className="h-4 w-4 text-muted-foreground shrink-0" />
                <span className="text-sm font-medium text-foreground truncate">{workflowMetaState.name}</span>
              </div>
              <StatusBadge variant="muted">{workflowMetaState.status}</StatusBadge>
              <EnvironmentBadge environment={workflowMetaState.environment} />
              <span className="hidden md:inline text-xs text-muted-foreground">{workflowMetaState.version}</span>
            </div>
            <div className="flex items-center gap-1 md:gap-2 shrink-0">
              <Button variant="outline" size="sm" className="h-8 gap-2">
                <Settings className="h-3.5 w-3.5" />
                <span className="hidden sm:inline">Settings</span>
              </Button>
              <Button variant="outline" size="sm" className="h-8 gap-2" onClick={handleSaveWorkflow}>
                <Save className="h-3.5 w-3.5" />
                <span className="hidden sm:inline">Save</span>
              </Button>
              <Button size="sm" className="h-8 gap-2">
                <Play className="h-3.5 w-3.5" />
                <span className="hidden sm:inline">Run</span>
              </Button>
            </div>
          </div>
        </div>

        {/* Main content */}
        <div className="flex flex-1 min-h-0 flex-col md:flex-row">
          {/* Left library panel - collapsible on mobile */}
          <div className="w-full md:w-64 border-b md:border-b-0 md:border-r border-border bg-card flex flex-col max-h-[40vh] md:max-h-none overflow-hidden">
            {/* Library tabs */}
            <div className="flex border-b border-border">
              {(["agents", "connectors", "sources", "tools"] as const).map((tab) => (
                <button
                  key={tab}
                  onClick={() => setActiveLibrary(tab)}
                  className={`flex-1 py-2.5 text-[11px] font-medium uppercase tracking-wide transition-colors ${
                    activeLibrary === tab
                      ? "text-foreground border-b-2 border-foreground"
                      : "text-muted-foreground hover:text-foreground"
                  }`}
                >
                  {tab}
                </button>
              ))}
            </div>

            {/* Search */}
            <div className="p-3 border-b border-border">
              <div className="relative">
                <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-muted-foreground" />
                <Input
                  placeholder="Search..."
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  className="h-8 pl-8 text-xs bg-secondary border-border"
                />
              </div>
            </div>

            {/* Library items */}
            <div className="flex-1 overflow-y-auto p-2">
              {activeLibrary === "agents" && (
                <div className="space-y-0.5">
                  {agentLibrary.map((agent) => (
                    <LibraryItem
                      key={agent.id}
                      name={agent.name}
                      description={agent.description}
                      icon={Bot}
                      onAdd={() => addNode("agent", agent.name, agent.description)}
                    />
                  ))}
                  <button
                    className="w-full flex items-center gap-2 p-2 mt-2 rounded-md border border-dashed border-border hover:border-muted-foreground transition-colors"
                    onClick={() => addNode("agent", "New Agent", "Custom agent")}
                  >
                    <Plus className="h-3.5 w-3.5 text-muted-foreground" />
                    <span className="text-xs text-muted-foreground">Create custom agent</span>
                  </button>
                </div>
              )}

              {activeLibrary === "connectors" && (
                <div className="space-y-0.5">
                  {connectorLibrary.map((conn) => (
                    <LibraryItem
                      key={conn.id}
                      name={conn.name}
                      vendor={conn.vendor}
                      onAdd={() => addNode("connector", conn.name)}
                    />
                  ))}
                </div>
              )}

              {activeLibrary === "sources" && (
                <div className="space-y-0.5">
                  {sourceLibrary.map((src) => (
                    <LibraryItem
                      key={src.id}
                      name={src.name}
                      description={src.type}
                      icon={Database}
                      onAdd={() => addNode("source", src.name, src.type)}
                    />
                  ))}
                </div>
              )}

              {activeLibrary === "tools" && (
                <div className="space-y-0.5">
                  {toolLibrary.map((tool) => (
                    <LibraryItem
                      key={tool.id}
                      name={tool.name}
                      description={tool.description}
                      icon={Zap}
                      onAdd={() => addNode("tool", tool.name, tool.description)}
                    />
                  ))}
                  <button
                    className="w-full flex items-center gap-2 p-2 mt-2 rounded-md border border-dashed border-border hover:border-muted-foreground transition-colors"
                    onClick={() => addNode("approval", "Approval Gate", "Require approval")}
                  >
                    <Shield className="h-3.5 w-3.5 text-muted-foreground" />
                    <span className="text-xs text-muted-foreground">Add approval gate</span>
                  </button>
                </div>
              )}
            </div>

            {/* Quick add */}
            <div className="border-t border-border p-3">
              <p className="text-[10px] text-muted-foreground uppercase tracking-wide mb-2">Quick Add</p>
              <div className="grid grid-cols-3 gap-1.5">
                <button
                  onClick={() => addNode("agent", "New Agent")}
                  className="flex flex-col items-center gap-1 p-2 rounded-md hover:bg-secondary/50 transition-colors"
                >
                  <Bot className="h-4 w-4 text-info" />
                  <span className="text-[10px] text-muted-foreground">Agent</span>
                </button>
                <button
                  onClick={() => addNode("task", "New Task")}
                  className="flex flex-col items-center gap-1 p-2 rounded-md hover:bg-secondary/50 transition-colors"
                >
                  <FileText className="h-4 w-4 text-success" />
                  <span className="text-[10px] text-muted-foreground">Task</span>
                </button>
                <button
                  onClick={() => addNode("approval", "Gate")}
                  className="flex flex-col items-center gap-1 p-2 rounded-md hover:bg-secondary/50 transition-colors"
                >
                  <Shield className="h-4 w-4 text-destructive" />
                  <span className="text-[10px] text-muted-foreground">Gate</span>
                </button>
              </div>
            </div>
          </div>

          {/* Canvas */}
          <div 
            className="flex-1 relative overflow-hidden bg-background"
            onClick={() => connectingFrom && handleCancelConnection()}
            onMouseMove={(e) => {
              if (connectingFrom) {
                const rect = e.currentTarget.getBoundingClientRect()
                setMousePos({ x: e.clientX - rect.left, y: e.clientY - rect.top })
              }
            }}
          >
            {/* Grid background */}
            <div
              className="absolute inset-0 opacity-[0.03]"
              style={{
                backgroundImage: `
                  linear-gradient(hsl(var(--foreground)) 1px, transparent 1px),
                  linear-gradient(90deg, hsl(var(--foreground)) 1px, transparent 1px)
                `,
                backgroundSize: "40px 40px",
              }}
            />

            {/* Connections - render as one SVG for all lines */}
            <svg 
              className="absolute inset-0 pointer-events-none" 
              style={{ overflow: "visible", width: "100%", height: "100%", zIndex: 5 }}
            >
              {connections.map((conn, i) => {
                const nodeWidth = 224
                const nodeHeight = 80
                const fromX = conn.from.position.x + nodeWidth
                const fromY = conn.from.position.y + nodeHeight / 2
                const toX = conn.to.position.x
                const toY = conn.to.position.y + nodeHeight / 2
                const dx = Math.abs(toX - fromX)
                const controlOffset = Math.min(dx * 0.5, 100)
                const pathD = `M ${fromX} ${fromY} C ${fromX + controlOffset} ${fromY}, ${toX - controlOffset} ${toY}, ${toX} ${toY}`
                
                return (
                  <g key={i}>
                    {/* Glow effect */}
                    <path
                      d={pathD}
                      stroke="#3b82f6"
                      strokeWidth="8"
                      fill="none"
                      opacity="0.2"
                    />
                    {/* Main line */}
                    <path
                      d={pathD}
                      stroke="#3b82f6"
                      strokeWidth="2.5"
                      fill="none"
                      opacity="0.9"
                    />
                    {/* Animated data flow dot */}
                    <circle r="4" fill="#3b82f6">
                      <animateMotion dur="2s" repeatCount="indefinite" path={pathD} />
                    </circle>
                    {/* Arrow head */}
                    <polygon
                      points={`${toX},${toY} ${toX - 10},${toY - 5} ${toX - 10},${toY + 5}`}
                      fill="#3b82f6"
                      opacity="0.9"
                    />
                    {/* Connection dots */}
                    <circle cx={fromX} cy={fromY} r="5" fill="#3b82f6" />
                    <circle cx={toX} cy={toY} r="5" fill="#3b82f6" />
                  </g>
                )
              })}
            </svg>

            {/* Temporary connection line while dragging */}
            {connectingFrom && (
              <svg className="absolute inset-0 pointer-events-none z-50" style={{ overflow: "visible" }}>
                {(() => {
                  const fromNode = nodes.find((n) => n.id === connectingFrom)
                  if (!fromNode) return null
                  const fromX = fromNode.position.x + 224
                  const fromY = fromNode.position.y + 40
                  const toX = mousePos.x
                  const toY = mousePos.y
                  const dx = Math.abs(toX - fromX)
                  const controlOffset = Math.min(dx * 0.5, 100)
                  const pathD = `M ${fromX} ${fromY} C ${fromX + controlOffset} ${fromY}, ${toX - controlOffset} ${toY}, ${toX} ${toY}`
                  return (
                    <>
                      {/* Glow */}
                      <path
                        d={pathD}
                        stroke="hsl(var(--info))"
                        strokeWidth="8"
                        fill="none"
                        opacity="0.2"
                      />
                      {/* Main dashed line */}
                      <path
                        d={pathD}
                        stroke="hsl(var(--info))"
                        strokeWidth="2.5"
                        fill="none"
                        strokeDasharray="8 4"
                        className="animate-pulse"
                      />
                      {/* Source dot */}
                      <circle cx={fromX} cy={fromY} r="5" fill="hsl(var(--info))" className="animate-pulse" />
                      {/* Target cursor */}
                      <circle cx={toX} cy={toY} r="8" fill="hsl(var(--info))" opacity="0.3" />
                      <circle cx={toX} cy={toY} r="4" fill="hsl(var(--info))" />
                    </>
                  )
                })()}
              </svg>
            )}

            {/* Nodes */}
            {nodes.map((node) => (
              <CanvasNode
                key={node.id}
                node={node}
                isSelected={selectedNode?.id === node.id}
                isConnecting={connectingFrom !== null}
                isConnectingSource={connectingFrom === node.id}
                onSelect={() => handleSelectNode(node)}
                onDelete={() => handleDeleteNode(node.id)}
                onDrag={(position) => handleDragNode(node.id, position)}
                onStartConnection={() => handleStartConnection(node.id)}
                onEndConnection={() => handleEndConnection(node.id)}
              />
            ))}

            {/* Connection mode indicator */}
            {connectingFrom && (
              <div className="absolute top-4 left-1/2 -translate-x-1/2 flex items-center gap-2 bg-info/10 border border-info/30 text-info rounded-full px-4 py-2 shadow-lg z-50">
                <div className="h-2 w-2 rounded-full bg-info animate-pulse" />
                <span className="text-sm font-medium">Click on a node input to connect</span>
                <button 
                  onClick={() => setConnectingFrom(null)}
                  className="ml-2 text-info/70 hover:text-info"
                >
                  <X className="h-4 w-4" />
                </button>
              </div>
            )}

            {/* Canvas toolbar */}
            <div className="absolute bottom-4 left-1/2 -translate-x-1/2 flex items-center gap-1 bg-card border border-border rounded-lg p-1 shadow-lg">
              <Button variant="ghost" size="sm" className="h-8 w-8 p-0">
                <Plus className="h-4 w-4" />
              </Button>
              <div className="w-px h-6 bg-border" />
              <Button variant="ghost" size="sm" className="h-8 px-3 gap-1.5 text-xs">
                <CheckCircle className="h-3.5 w-3.5 text-success" />
                {nodes.length} nodes
              </Button>
              <div className="w-px h-6 bg-border" />
              <Button variant="ghost" size="sm" className="h-8 px-3 gap-1.5 text-xs">
                Preview
                <ChevronRight className="h-3.5 w-3.5" />
              </Button>
            </div>
          </div>

          {/* Right config panel */}
          <ConfigPanel
            node={selectedNode}
            onClose={() => setSelectedNode(null)}
            onUpdate={handleUpdateNode}
          />
        </div>
      </div>
    </AppShell>
  )
}
