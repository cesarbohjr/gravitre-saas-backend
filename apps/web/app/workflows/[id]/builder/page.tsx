"use client"

// Workflow Builder - Main canvas for creating and editing workflows
// Includes: Agent, Task, Connector, Tool, Source, Approval, Decision, and Council node types
import { useState, useCallback, useEffect, useRef, useMemo, use } from "react"
import Link from "next/link"
import { AppShell } from "@/components/gravitre/app-shell"
import { StatusBadge } from "@/components/gravitre/status-badge"
import { EnvironmentBadge } from "@/components/gravitre/environment-badge"
import { ModelSelector, ModelInheritanceChain } from "@/components/gravitre/model-selector"
import { ConnectorIcon } from "@/components/gravitre/connector-icon"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
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
  ChevronDown,
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
  Loader2,
  Lightbulb,
  Clock,
  PanelRightOpen,
  Sparkles,
  CircleDot,
  Activity,
  Link2,
  LayoutGrid,
  GitBranch,
  Brain,
  MessageSquare,
  ThumbsUp,
  ThumbsDown,
  RotateCcw,
  History,
  Target,
  Gauge,
  FileSearch,
  Users,
} from "lucide-react"
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet"
import { cn } from "@/lib/utils"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { Label } from "@/components/ui/label"
import { Switch } from "@/components/ui/switch"
import { Textarea } from "@/components/ui/textarea"
import { toast } from "sonner"

// Node types
type NodeType = "agent" | "task" | "connector" | "tool" | "source" | "approval" | "decision" | "council"
type NodeState = "idle" | "running" | "success" | "error" | "waiting" | "evaluating" | "debating" | "consensus" | "escalated"
type DecisionStrategy = "rule-based" | "ai-assisted" | "hybrid"
type DebateMode = "consensus" | "majority" | "lead-decides" | "human-approval" | "risk-escalation"

// Agent role for council
interface CouncilAgent {
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

// Council debate contribution
interface DebateContribution {
  agentId: string
  position: string
  confidence: number
  reasoning: string
  evidenceUsed: string[]
  timestamp: Date
}

// Council configuration
interface CouncilConfig {
  objective?: string
  participatingAgents?: CouncilAgent[]
  debateMode?: DebateMode
  evidenceSources?: string[]
  outputOptions?: { id: string; label: string; description?: string }[]
  debate?: {
    contributions: DebateContribution[]
    disagreements?: { agentIds: string[]; topic: string }[]
    timeline: { step: string; status: "pending" | "active" | "complete" }[]
  }
  finalDecision?: {
    recommendation: string
    method: DebateMode
    confidence: number
    keyReasons: string[]
    dissentingOpinions?: { agentId: string; opinion: string }[]
    executedAction?: string
  }
}

interface DecisionPath {
  id: string
  label: string
  condition?: string
  targetNodeId?: string
  isDefault?: boolean
}

interface DecisionConfig {
  objective?: string
  strategy?: DecisionStrategy
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

interface WorkflowNode {
  id: string
  type: NodeType
  name: string
  description?: string
  config: Record<string, unknown>
  position: { x: number; y: number }
  connections: string[]
  state?: NodeState
  vendor?: string
  selectedAction?: string
  dataLabel?: string
  // Decision node specific
  decisionConfig?: DecisionConfig
  outputPaths?: DecisionPath[]
  // Council node specific
  councilConfig?: CouncilConfig
}

interface Connection {
  id: string
  from: string
  to: string
}

// Mock workflow data
const workflowMeta = {
  id: "wf-001",
  name: "Customer Data Pipeline",
  description: "End-to-end customer data sync with validation and enrichment",
  status: "draft" as const,
  environment: "staging" as const,
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
    state: "idle",
    vendor: "salesforce",
    selectedAction: "fetch_records",
    dataLabel: "customer_records",
  },
  {
    id: "node-2",
    type: "agent",
    name: "Data Validator",
    description: "Validate and clean records",
    config: { model: "gpt-4-turbo", temperature: 0.3 },
    position: { x: 350, y: 150 },
    connections: ["node-3"],
    state: "idle",
    dataLabel: "validated_data",
  },
  {
    id: "node-3",
    type: "task",
    name: "Enrich with metadata",
    description: "Add company info and scoring",
    config: { instruction: "Enrich customer records with company data" },
    position: { x: 600, y: 100 },
    connections: ["node-4"],
    state: "idle",
    dataLabel: "enriched_records",
  },
  {
    id: "node-4",
    type: "approval",
    name: "Quality Gate",
    description: "Review before production",
    config: { approvers: ["admin"], autoApprove: false },
    position: { x: 600, y: 250 },
    connections: ["node-5"],
    state: "idle",
    dataLabel: "approved_batch",
  },
  {
    id: "node-5",
    type: "connector",
    name: "PostgreSQL",
    description: "Write to data warehouse",
    config: { connector: "postgresql", schema: "customers" },
    position: { x: 850, y: 150 },
    connections: [],
    state: "idle",
    vendor: "postgresql",
    selectedAction: "insert",
    dataLabel: "sync_complete",
  },
]

// Library items
const agentLibrary = [
  { id: "agent-1", name: "Data Validator", description: "Validates and cleans data" },
  { id: "agent-2", name: "Content Writer", description: "Generates content" },
  { id: "agent-3", name: "Research Analyst", description: "Analyzes and summarizes" },
  { id: "agent-4", name: "Code Reviewer", description: "Reviews code quality" },
]

// Connector actions with dynamic form fields
const connectorActions: Record<string, { actions: Array<{ id: string; name: string; method: string; type: string; fields: Array<{ name: string; type: string; required: boolean; placeholder?: string; options?: string[] }> }> }> = {
  salesforce: {
    actions: [
      { id: "fetch_records", name: "Fetch Records", method: "GET", type: "Read", fields: [
        { name: "object", type: "select", required: true, options: ["Account", "Contact", "Lead", "Opportunity", "Case"] },
        { name: "filter", type: "text", required: false, placeholder: "WHERE clause (optional)" },
        { name: "limit", type: "number", required: false, placeholder: "100" },
      ]},
      { id: "create_lead", name: "Create Lead", method: "POST", type: "Write", fields: [
        { name: "firstName", type: "text", required: true, placeholder: "First name" },
        { name: "lastName", type: "text", required: true, placeholder: "Last name" },
        { name: "email", type: "email", required: true, placeholder: "Email address" },
        { name: "company", type: "text", required: true, placeholder: "Company name" },
        { name: "status", type: "select", required: false, options: ["Open", "Working", "Qualified", "Unqualified"] },
      ]},
      { id: "update_contact", name: "Update Contact", method: "PATCH", type: "Write", fields: [
        { name: "contactId", type: "text", required: true, placeholder: "Contact ID" },
        { name: "fields", type: "textarea", required: true, placeholder: '{"Email": "new@email.com"}' },
      ]},
      { id: "query_object", name: "Query Object", method: "GET", type: "Read", fields: [
        { name: "soql", type: "textarea", required: true, placeholder: "SELECT Id, Name FROM Account WHERE..." },
      ]},
    ]
  },
  stripe: {
    actions: [
      { id: "create_payment", name: "Create Payment Intent", method: "POST", type: "Write", fields: [
        { name: "amount", type: "number", required: true, placeholder: "Amount in cents" },
        { name: "currency", type: "select", required: true, options: ["usd", "eur", "gbp", "jpy"] },
        { name: "description", type: "text", required: false, placeholder: "Payment description" },
      ]},
      { id: "retrieve_customer", name: "Retrieve Customer", method: "GET", type: "Read", fields: [
        { name: "customerId", type: "text", required: true, placeholder: "cus_xxx" },
      ]},
      { id: "create_invoice", name: "Create Invoice", method: "POST", type: "Write", fields: [
        { name: "customerId", type: "text", required: true, placeholder: "Customer ID" },
        { name: "autoAdvance", type: "checkbox", required: false },
        { name: "dueDate", type: "date", required: false },
      ]},
    ]
  },
  slack: {
    actions: [
      { id: "send_message", name: "Send Message", method: "POST", type: "Write", fields: [
        { name: "channel", type: "text", required: true, placeholder: "#general or @user" },
        { name: "text", type: "textarea", required: true, placeholder: "Message content..." },
        { name: "threadTs", type: "text", required: false, placeholder: "Thread timestamp (optional)" },
      ]},
      { id: "post_channel", name: "Post to Channel", method: "POST", type: "Write", fields: [
        { name: "channel", type: "select", required: true, options: ["#general", "#engineering", "#sales", "#support"] },
        { name: "blocks", type: "textarea", required: false, placeholder: "Block Kit JSON (optional)" },
      ]},
      { id: "trigger_notification", name: "Trigger Notification", method: "POST", type: "Webhook", fields: [
        { name: "webhookUrl", type: "text", required: true, placeholder: "Webhook URL" },
        { name: "payload", type: "textarea", required: true, placeholder: '{"text": "Alert!"}' },
      ]},
    ]
  },
  hubspot: {
    actions: [
      { id: "create_contact", name: "Create Contact", method: "POST", type: "Write", fields: [
        { name: "email", type: "email", required: true, placeholder: "Email address" },
        { name: "firstname", type: "text", required: false, placeholder: "First name" },
        { name: "lastname", type: "text", required: false, placeholder: "Last name" },
        { name: "company", type: "text", required: false, placeholder: "Company" },
      ]},
      { id: "get_deal", name: "Get Deal", method: "GET", type: "Read", fields: [
        { name: "dealId", type: "text", required: true, placeholder: "Deal ID" },
      ]},
      { id: "update_deal", name: "Update Deal Stage", method: "PATCH", type: "Write", fields: [
        { name: "dealId", type: "text", required: true, placeholder: "Deal ID" },
        { name: "stage", type: "select", required: true, options: ["appointmentscheduled", "qualifiedtobuy", "presentationscheduled", "decisionmakerboughtin", "contractsent", "closedwon", "closedlost"] },
      ]},
    ]
  },
  postgresql: {
    actions: [
      { id: "query", name: "Execute Query", method: "GET", type: "Read", fields: [
        { name: "sql", type: "textarea", required: true, placeholder: "SELECT * FROM users WHERE..." },
        { name: "params", type: "textarea", required: false, placeholder: '["param1", "param2"]' },
      ]},
      { id: "insert", name: "Insert Records", method: "POST", type: "Write", fields: [
        { name: "table", type: "text", required: true, placeholder: "Table name" },
        { name: "data", type: "textarea", required: true, placeholder: '[{"name": "John", "email": "john@example.com"}]' },
      ]},
      { id: "update", name: "Update Records", method: "PATCH", type: "Write", fields: [
        { name: "table", type: "text", required: true, placeholder: "Table name" },
        { name: "set", type: "textarea", required: true, placeholder: '{"status": "active"}' },
        { name: "where", type: "text", required: true, placeholder: "id = 123" },
      ]},
    ]
  },
  microsoft: {
    actions: [
      { id: "send_email", name: "Send Email", method: "POST", type: "Write", fields: [
        { name: "to", type: "email", required: true, placeholder: "Recipient email" },
        { name: "subject", type: "text", required: true, placeholder: "Email subject" },
        { name: "body", type: "textarea", required: true, placeholder: "Email body (HTML supported)" },
      ]},
      { id: "create_event", name: "Create Calendar Event", method: "POST", type: "Write", fields: [
        { name: "subject", type: "text", required: true, placeholder: "Event title" },
        { name: "start", type: "datetime-local", required: true },
        { name: "end", type: "datetime-local", required: true },
        { name: "attendees", type: "text", required: false, placeholder: "Comma-separated emails" },
      ]},
    ]
  },
}

const connectorLibrary = [
  { id: "conn-1", name: "Salesforce", vendor: "salesforce", status: "connected" },
  { id: "conn-2", name: "HubSpot", vendor: "hubspot", status: "connected" },
  { id: "conn-3", name: "Slack", vendor: "slack", status: "connected" },
  { id: "conn-4", name: "Microsoft 365", vendor: "microsoft", status: "disconnected" },
  { id: "conn-5", name: "PostgreSQL", vendor: "postgresql", status: "connected" },
  { id: "conn-6", name: "Stripe", vendor: "stripe", status: "connected" },
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
  decision: { icon: GitBranch, color: "bg-violet-500/20 border-violet-500/40 text-violet-400", label: "Decision" },
  council: { icon: Users, color: "bg-amber-500/20 border-amber-500/40 text-amber-400", label: "Agent Council" },
  }

// Node state visual config
const nodeStateConfig: Record<NodeState, { border: string; bg: string; animation: string }> = {
  idle: { border: "", bg: "", animation: "" },
  running: { border: "border-blue-500 shadow-[0_0_15px_rgba(59,130,246,0.4)]", bg: "bg-blue-500/5", animation: "animate-pulse" },
  success: { border: "border-emerald-500 shadow-[0_0_10px_rgba(16,185,129,0.3)]", bg: "bg-emerald-500/5", animation: "" },
  error: { border: "border-red-500 shadow-[0_0_12px_rgba(239,68,68,0.4)]", bg: "bg-red-500/5", animation: "animate-shake" },
waiting: { border: "border-amber-500/50", bg: "bg-amber-500/5", animation: "opacity-60" },
  evaluating: { border: "border-violet-500 shadow-[0_0_20px_rgba(139,92,246,0.5)]", bg: "bg-violet-500/10", animation: "animate-pulse" },
  debating: { border: "border-amber-500 shadow-[0_0_20px_rgba(245,158,11,0.5)]", bg: "bg-amber-500/10", animation: "animate-pulse" },
  consensus: { border: "border-emerald-500 shadow-[0_0_15px_rgba(16,185,129,0.4)]", bg: "bg-emerald-500/10", animation: "" },
  escalated: { border: "border-red-500 shadow-[0_0_15px_rgba(239,68,68,0.4)]", bg: "bg-red-500/10", animation: "" },
  }

// Canvas Node Component
function CanvasNode({
  node,
  isSelected,
  isConnectTarget,
  onSelect,
  onDelete,
  onDrag,
  onShowDetails,
  onConnectionDragStart,
  onConnectionDrop,
  isDraggingConnection,
  }: {
  node: WorkflowNode
  isSelected: boolean
  isConnectTarget: boolean
  onSelect: () => void
  onDelete: () => void
  onDrag: (position: { x: number; y: number }) => void
  onShowDetails: () => void
  onConnectionDragStart?: (nodeId: string, e: React.MouseEvent) => void
  onConnectionDrop?: (nodeId: string) => void
  isDraggingConnection?: boolean
  }) {
  const config = nodeTypeConfig[node.type]
  const Icon = config.icon
  const [isDragging, setIsDragging] = useState(false)
  const [isMouseDown, setIsMouseDown] = useState(false)
  const [isHovered, setIsHovered] = useState(false)
  const dragStartRef = useRef({ x: 0, y: 0, nodeX: 0, nodeY: 0 })
  const hasDraggedRef = useRef(false)
  
  const stateConfig = nodeStateConfig[node.state || "idle"]

  const handleMouseDown = (e: React.MouseEvent) => {
    e.preventDefault()
    e.stopPropagation()
    setIsMouseDown(true)
    hasDraggedRef.current = false
    dragStartRef.current = {
      x: e.clientX,
      y: e.clientY,
      nodeX: node.position.x,
      nodeY: node.position.y,
    }
  }

  const handleDoubleClick = (e: React.MouseEvent) => {
    e.preventDefault()
    e.stopPropagation()
    onShowDetails()
  }

  useEffect(() => {
    if (!isMouseDown) return

    const handleGlobalMouseMove = (e: MouseEvent) => {
      const dx = e.clientX - dragStartRef.current.x
      const dy = e.clientY - dragStartRef.current.y
      
      // Only count as drag if moved more than 5 pixels
      if (Math.abs(dx) > 5 || Math.abs(dy) > 5) {
        hasDraggedRef.current = true
        setIsDragging(true)
        const newX = Math.max(0, dragStartRef.current.nodeX + dx)
        const newY = Math.max(0, dragStartRef.current.nodeY + dy)
        onDrag({ x: newX, y: newY })
      }
    }

    const handleGlobalMouseUp = () => {
      if (!hasDraggedRef.current) {
        // This was a click, not a drag - trigger select
        onSelect()
      }
      setIsDragging(false)
      setIsMouseDown(false)
      hasDraggedRef.current = false
    }

    window.addEventListener("mousemove", handleGlobalMouseMove)
    window.addEventListener("mouseup", handleGlobalMouseUp)

    return () => {
      window.removeEventListener("mousemove", handleGlobalMouseMove)
      window.removeEventListener("mouseup", handleGlobalMouseUp)
    }
  }, [isMouseDown, onDrag, onSelect, node.id])

  return (
    <div
      className={cn(
        "absolute cursor-pointer transition-all duration-150",
        isSelected ? "z-20" : "z-10",
        isDragging && "cursor-grabbing z-30",
        stateConfig.animation
      )}
      style={{ left: node.position.x, top: node.position.y }}
      onMouseDown={handleMouseDown}
      onDoubleClick={handleDoubleClick}
      onMouseEnter={() => setIsHovered(true)}
      onMouseLeave={() => setIsHovered(false)}
    >
      <div
        className={cn(
          "group relative w-56 rounded-lg border bg-card p-3 shadow-lg transition-all duration-300",
          isSelected ? "border-info ring-2 ring-info/30" : "border-border hover:border-muted-foreground/50",
          stateConfig.border,
          stateConfig.bg,
          isHovered && "shadow-xl translate-y-[-2px]"
        )}
      >
        {/* Running indicator glow */}
        {node.state === "running" && (
          <div className="absolute inset-0 rounded-lg bg-blue-500/10 animate-pulse pointer-events-none" />
        )}

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

        {/* State indicator badge */}
        {node.state && node.state !== "idle" && (
          <div className={cn(
            "absolute -top-2 left-4 px-2 py-0.5 rounded-full text-[9px] font-semibold uppercase tracking-wide",
            node.state === "running" && "bg-blue-500 text-white",
            node.state === "success" && "bg-emerald-500 text-white",
            node.state === "error" && "bg-red-500 text-white",
            node.state === "waiting" && "bg-amber-500 text-white"
          )}>
            {node.state === "running" && <Loader2 className="h-2.5 w-2.5 inline mr-1 animate-spin" />}
            {node.state}
          </div>
        )}

        {/* Node header */}
        <div className="flex items-start gap-2.5 mb-2">
          <div className={cn(
            "flex h-8 w-8 shrink-0 items-center justify-center rounded-md border transition-all",
            config.color,
            node.state === "running" && "animate-pulse"
          )}>
{node.vendor ? (
  <ConnectorIcon vendor={node.vendor} size="xs" showStatusIndicator={false} />
  ) : (
  <Icon className="h-4 w-4" />
  )}
          </div>
          <div className="flex-1 min-w-0">
            <p className="text-sm font-medium text-foreground truncate">{node.name}</p>
            <div className="flex items-center gap-1.5">
              <p className="text-[10px] text-muted-foreground">{config.label}</p>
              {node.selectedAction && (
                <>
                  <span className="text-muted-foreground/30">|</span>
                  <p className="text-[10px] text-blue-400">
                    {connectorActions[node.vendor || ""]?.actions.find(a => a.id === node.selectedAction)?.name || node.selectedAction}
                  </p>
                </>
              )}
            </div>
          </div>
        </div>

        {/* Description */}
        {node.description && (
          <p className="text-xs text-muted-foreground line-clamp-2 mb-2">{node.description}</p>
        )}

        {/* API Context - subtle metadata */}
        {node.vendor && node.selectedAction && (
          <div className="flex items-center gap-2 mb-2 text-[9px] text-muted-foreground/70">
            {(() => {
              const action = connectorActions[node.vendor]?.actions.find(a => a.id === node.selectedAction)
              if (!action) return null
              return (
                <>
                  <span className={cn(
                    "px-1.5 py-0.5 rounded font-mono",
                    action.method === "GET" && "bg-emerald-500/10 text-emerald-400",
                    action.method === "POST" && "bg-blue-500/10 text-blue-400",
                    action.method === "PATCH" && "bg-amber-500/10 text-amber-400"
                  )}>
                    {action.method}
                  </span>
                  <span className="text-muted-foreground/50">|</span>
                  <span>{action.type}</span>
                </>
              )
            })()}
          </div>
        )}

        {/* Connection indicator */}
        {node.connections.length > 0 && (
          <div className="flex items-center gap-1 text-[10px] text-muted-foreground">
            <ArrowRight className="h-3 w-3" />
            <span>{node.connections.length} connection{node.connections.length > 1 ? "s" : ""}</span>
          </div>
        )}

{/* Connection handles - all 4 sides - Drag from these to connect */}
  {/* Left handle */}
  <div
  onMouseDown={(e) => onConnectionDragStart?.(node.id, e)}
  onMouseUp={() => isDraggingConnection && onConnectionDrop?.(node.id)}
  className={`absolute left-0 top-1/2 -translate-x-1/2 -translate-y-1/2 h-4 w-4 rounded-full border-2 transition-all duration-200 cursor-crosshair z-10 ${
  isDraggingConnection
  ? "border-emerald-400 bg-emerald-400 shadow-[0_0_12px_rgba(52,211,153,0.6)] scale-125"
  : isSelected
  ? "border-info bg-info/60 hover:scale-125 hover:shadow-[0_0_10px_rgba(59,130,246,0.5)]"
  : "border-muted-foreground/40 bg-card hover:border-info hover:bg-info/50 hover:scale-125"
  }`}
  title="Drag to connect"
  />
  {/* Right handle */}
  <div
  onMouseDown={(e) => onConnectionDragStart?.(node.id, e)}
  onMouseUp={() => isDraggingConnection && onConnectionDrop?.(node.id)}
  className={`absolute right-0 top-1/2 translate-x-1/2 -translate-y-1/2 h-4 w-4 rounded-full border-2 transition-all duration-200 cursor-crosshair z-10 ${
  isDraggingConnection
  ? "border-emerald-400 bg-emerald-400 shadow-[0_0_12px_rgba(52,211,153,0.6)] scale-125"
  : isSelected
  ? "border-info bg-info/60 hover:scale-125 hover:shadow-[0_0_10px_rgba(59,130,246,0.5)]"
  : "border-muted-foreground/40 bg-card hover:border-info hover:bg-info/50 hover:scale-125"
  }`}
  title="Drag to connect"
  />
  {/* Top handle */}
  <div
  onMouseDown={(e) => onConnectionDragStart?.(node.id, e)}
  onMouseUp={() => isDraggingConnection && onConnectionDrop?.(node.id)}
  className={`absolute top-0 left-1/2 -translate-x-1/2 -translate-y-1/2 h-4 w-4 rounded-full border-2 transition-all duration-200 cursor-crosshair z-10 ${
  isDraggingConnection
  ? "border-emerald-400 bg-emerald-400 shadow-[0_0_12px_rgba(52,211,153,0.6)] scale-125"
  : isSelected
  ? "border-info bg-info/60 hover:scale-125 hover:shadow-[0_0_10px_rgba(59,130,246,0.5)]"
  : "border-muted-foreground/40 bg-card hover:border-info hover:bg-info/50 hover:scale-125"
  }`}
  title="Drag to connect"
  />
  {/* Bottom handle */}
  <div
  onMouseDown={(e) => onConnectionDragStart?.(node.id, e)}
  onMouseUp={() => isDraggingConnection && onConnectionDrop?.(node.id)}
  className={`absolute bottom-0 left-1/2 -translate-x-1/2 translate-y-1/2 h-4 w-4 rounded-full border-2 transition-all duration-200 cursor-crosshair z-10 ${
  isDraggingConnection
  ? "border-emerald-400 bg-emerald-400 shadow-[0_0_12px_rgba(52,211,153,0.6)] scale-125"
  : isSelected
  ? "border-info bg-info/60 hover:scale-125 hover:shadow-[0_0_10px_rgba(59,130,246,0.5)]"
  : "border-muted-foreground/40 bg-card hover:border-info hover:bg-info/50 hover:scale-125"
  }`}
  title="Drag to connect"
  />
      </div>
    </div>
  )
}

// Diamond-shaped Decision Node Component
function DecisionNode({
  node,
  isSelected,
  isConnectTarget,
  onSelect,
  onDelete,
  onDrag,
  onShowDetails,
  onConnectionDragStart,
  onConnectionDrop,
  isDraggingConnection,
  }: {
  node: WorkflowNode
  isSelected: boolean
  isConnectTarget: boolean
  onSelect: () => void
  onDelete: () => void
  onDrag: (position: { x: number; y: number }) => void
  onShowDetails: () => void
  onConnectionDragStart?: (nodeId: string, e: React.MouseEvent) => void
  onConnectionDrop?: (nodeId: string) => void
  isDraggingConnection?: boolean
  }) {
  const [isDragging, setIsDragging] = useState(false)
  const [isMouseDown, setIsMouseDown] = useState(false)
  const [isHovered, setIsHovered] = useState(false)
  const dragStartRef = useRef({ x: 0, y: 0, nodeX: 0, nodeY: 0 })
  const hasDraggedRef = useRef(false)
  
  const stateConfig = nodeStateConfig[node.state || "idle"]
  const isEvaluating = node.state === "evaluating" || node.state === "running"
  const hasReasoning = node.decisionConfig?.reasoning

  const handleMouseDown = (e: React.MouseEvent) => {
    e.preventDefault()
    e.stopPropagation()
    setIsMouseDown(true)
    hasDraggedRef.current = false
    dragStartRef.current = {
      x: e.clientX,
      y: e.clientY,
      nodeX: node.position.x,
      nodeY: node.position.y,
    }
  }

  const handleDoubleClick = (e: React.MouseEvent) => {
    e.preventDefault()
    e.stopPropagation()
    onShowDetails()
  }

  useEffect(() => {
    if (!isMouseDown) return

    const handleGlobalMouseMove = (e: MouseEvent) => {
      const dx = e.clientX - dragStartRef.current.x
      const dy = e.clientY - dragStartRef.current.y
      
      if (Math.abs(dx) > 5 || Math.abs(dy) > 5) {
        hasDraggedRef.current = true
        setIsDragging(true)
        const newX = Math.max(0, dragStartRef.current.nodeX + dx)
        const newY = Math.max(0, dragStartRef.current.nodeY + dy)
        onDrag({ x: newX, y: newY })
      }
    }

    const handleGlobalMouseUp = () => {
      if (!hasDraggedRef.current) {
        onSelect()
      }
      setIsDragging(false)
      setIsMouseDown(false)
      hasDraggedRef.current = false
    }

    window.addEventListener("mousemove", handleGlobalMouseMove)
    window.addEventListener("mouseup", handleGlobalMouseUp)

    return () => {
      window.removeEventListener("mousemove", handleGlobalMouseMove)
      window.removeEventListener("mouseup", handleGlobalMouseUp)
    }
  }, [isMouseDown, onDrag, onSelect, node.id])

  return (
    <div
      className={cn(
        "absolute cursor-pointer transition-all duration-150",
        isSelected ? "z-20" : "z-10",
        isDragging && "cursor-grabbing z-30",
        stateConfig.animation
      )}
      style={{ left: node.position.x, top: node.position.y }}
      onMouseDown={handleMouseDown}
      onDoubleClick={handleDoubleClick}
      onMouseEnter={() => setIsHovered(true)}
      onMouseLeave={() => setIsHovered(false)}
    >
      {/* Diamond shape container */}
      <div className="relative w-48 flex flex-col items-center">
        {/* Evaluating/Running indicator */}
        {isEvaluating && (
          <div className="absolute -top-8 left-1/2 -translate-x-1/2 flex items-center gap-1.5 px-2 py-1 rounded-full bg-violet-500/20 border border-violet-500/40">
            <Loader2 className="h-3 w-3 text-violet-400 animate-spin" />
            <span className="text-[10px] font-medium text-violet-400">Evaluating...</span>
          </div>
        )}

        {/* AI Reasoning badge */}
        {hasReasoning && !isEvaluating && (
          <div className="absolute -top-8 left-1/2 -translate-x-1/2 flex items-center gap-1.5 px-2 py-1 rounded-full bg-emerald-500/20 border border-emerald-500/40">
            <Brain className="h-3 w-3 text-emerald-400" />
            <span className="text-[10px] font-medium text-emerald-400">
              {node.decisionConfig?.reasoning?.confidence}% confidence
            </span>
          </div>
        )}
        
        {/* Diamond shape */}
        <div
          className={cn(
            "relative w-32 h-32 transform rotate-45 rounded-lg border-2 transition-all duration-300",
            isSelected 
              ? "border-violet-500 shadow-[0_0_25px_rgba(139,92,246,0.4)]" 
              : "border-violet-500/40 hover:border-violet-500/60",
            stateConfig.border || "",
            stateConfig.bg || "bg-card",
            isEvaluating && "shadow-[0_0_30px_rgba(139,92,246,0.6)]",
            isHovered && !isDragging && "shadow-[0_0_20px_rgba(139,92,246,0.3)] scale-105"
          )}
        >
          {/* Animated glow ring when evaluating */}
          {isEvaluating && (
            <div className="absolute inset-0 rounded-lg animate-ping bg-violet-500/20" />
          )}
          
          {/* Inner content - counter-rotate to be upright */}
          <div className="absolute inset-0 flex flex-col items-center justify-center -rotate-45">
            <div className={cn(
              "flex h-10 w-10 items-center justify-center rounded-lg transition-all",
              isEvaluating 
                ? "bg-violet-500/30 text-violet-300" 
                : "bg-violet-500/20 text-violet-400"
            )}>
              <GitBranch className={cn(
                "h-5 w-5",
                isEvaluating && "animate-pulse"
              )} />
            </div>
          </div>

          {/* Delete button */}
          <button
            onClick={(e) => {
              e.stopPropagation()
              onDelete()
            }}
            className="absolute -right-3 -top-3 -rotate-45 h-5 w-5 rounded-full bg-destructive text-destructive-foreground opacity-0 group-hover:opacity-100 hover:opacity-100 transition-opacity flex items-center justify-center z-10"
          >
            <X className="h-3 w-3" />
          </button>

{/* Connection handles - on diamond corners - Drag to connect */}
  {/* Top corner */}
  <div
  onMouseDown={(e) => onConnectionDragStart?.(node.id, e)}
  onMouseUp={() => isDraggingConnection && onConnectionDrop?.(node.id)}
  className={cn(
  "absolute -top-1.5 left-1/2 -translate-x-1/2 h-4 w-4 rounded-full border-2 transition-all duration-200 cursor-crosshair z-10",
  isDraggingConnection
  ? "border-emerald-400 bg-emerald-400 shadow-[0_0_12px_rgba(52,211,153,0.6)] scale-125"
  : isSelected
  ? "border-violet-400 bg-violet-400/60 hover:scale-125"
  : "border-violet-400/40 bg-card hover:border-violet-400 hover:bg-violet-400/50 hover:scale-125"
  )}
  title="Drag to connect"
  />
  {/* Right corner */}
  <div
  onMouseDown={(e) => onConnectionDragStart?.(node.id, e)}
  onMouseUp={() => isDraggingConnection && onConnectionDrop?.(node.id)}
  className={cn(
  "absolute top-1/2 -right-1.5 -translate-y-1/2 h-4 w-4 rounded-full border-2 transition-all duration-200 cursor-crosshair z-10",
  isDraggingConnection
  ? "border-emerald-400 bg-emerald-400 shadow-[0_0_12px_rgba(52,211,153,0.6)] scale-125"
  : isSelected
  ? "border-violet-400 bg-violet-400/60 hover:scale-125"
  : "border-violet-400/40 bg-card hover:border-violet-400 hover:bg-violet-400/50 hover:scale-125"
  )}
  title="Drag to connect"
  />
  {/* Bottom corner */}
  <div
  onMouseDown={(e) => onConnectionDragStart?.(node.id, e)}
  onMouseUp={() => isDraggingConnection && onConnectionDrop?.(node.id)}
  className={cn(
  "absolute -bottom-1.5 left-1/2 -translate-x-1/2 h-4 w-4 rounded-full border-2 transition-all duration-200 cursor-crosshair z-10",
  isDraggingConnection
  ? "border-emerald-400 bg-emerald-400 shadow-[0_0_12px_rgba(52,211,153,0.6)] scale-125"
  : isSelected
  ? "border-violet-400 bg-violet-400/60 hover:scale-125"
  : "border-violet-400/40 bg-card hover:border-violet-400 hover:bg-violet-400/50 hover:scale-125"
  )}
  title="Drag to connect"
  />
  {/* Left corner */}
  <div
  onMouseDown={(e) => onConnectionDragStart?.(node.id, e)}
  onMouseUp={() => isDraggingConnection && onConnectionDrop?.(node.id)}
  className={cn(
  "absolute top-1/2 -left-1.5 -translate-y-1/2 h-4 w-4 rounded-full border-2 transition-all duration-200 cursor-crosshair z-10",
  isDraggingConnection
  ? "border-emerald-400 bg-emerald-400 shadow-[0_0_12px_rgba(52,211,153,0.6)] scale-125"
  : isSelected
  ? "border-violet-400 bg-violet-400/60 hover:scale-125"
  : "border-violet-400/40 bg-card hover:border-violet-400 hover:bg-violet-400/50 hover:scale-125"
  )}
  title="Drag to connect"
  />
        </div>

        {/* Node label below diamond */}
        <div className="mt-4 text-center max-w-[180px]">
          <p className="text-sm font-medium text-foreground truncate">{node.name}</p>
          <p className="text-[10px] text-violet-400 flex items-center justify-center gap-1">
            <GitBranch className="h-3 w-3" />
            Decision Node
          </p>
          {node.description && (
            <p className="text-[10px] text-muted-foreground mt-0.5 line-clamp-1">{node.description}</p>
          )}
        </div>

        {/* Output paths indicators */}
        {node.outputPaths && node.outputPaths.length > 0 && (
          <div className="mt-2 flex flex-wrap gap-1 justify-center max-w-[180px]">
            {node.outputPaths.map((path, idx) => (
              <span
                key={path.id}
                className={cn(
                  "px-1.5 py-0.5 rounded text-[9px] font-medium border",
                  node.decisionConfig?.reasoning?.chosenPath === path.id
                    ? "bg-emerald-500/20 border-emerald-500/40 text-emerald-400"
                    : "bg-muted/50 border-border text-muted-foreground"
                )}
              >
                {path.label}
              </span>
            ))}
          </div>
        )}
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
  <ConnectorIcon vendor={vendor} size="sm" showStatusIndicator={false} />
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

// AI Reasoning Panel - Expandable component showing decision reasoning
function AIReasoningPanel({
  reasoning,
  isExpanded,
  onToggle,
  onFeedback,
}: {
  reasoning: DecisionConfig["reasoning"]
  isExpanded: boolean
  onToggle: () => void
  onFeedback?: (correct: boolean) => void
}) {
  if (!reasoning) return null

  return (
    <div className={cn(
      "rounded-lg border transition-all duration-300",
      "bg-gradient-to-br from-emerald-500/5 to-violet-500/5",
      "border-emerald-500/20"
    )}>
      {/* Header - always visible */}
      <button
        onClick={onToggle}
        className="w-full flex items-center justify-between p-3 hover:bg-white/5 transition-colors"
      >
        <div className="flex items-center gap-2">
          <div className="flex h-7 w-7 items-center justify-center rounded-lg bg-emerald-500/20">
            <Brain className="h-4 w-4 text-emerald-400" />
          </div>
          <div className="text-left">
            <p className="text-xs font-medium text-emerald-400">AI Decision Made</p>
            <p className="text-[10px] text-muted-foreground">
              {reasoning.confidence}% confidence
            </p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <div className="px-2 py-0.5 rounded-full bg-emerald-500/20 text-[10px] font-medium text-emerald-400">
            {reasoning.chosenPath}
          </div>
          <ChevronDown className={cn(
            "h-4 w-4 text-muted-foreground transition-transform",
            isExpanded && "rotate-180"
          )} />
        </div>
      </button>

      {/* Expanded content */}
      {isExpanded && (
        <div className="px-3 pb-3 space-y-3 border-t border-emerald-500/10">
          {/* Summary */}
          <div className="pt-3">
            <p className="text-xs text-muted-foreground">{reasoning.summary}</p>
          </div>

          {/* Confidence meter */}
          <div>
            <div className="flex items-center justify-between mb-1">
              <span className="text-[10px] text-muted-foreground uppercase tracking-wide">Confidence</span>
              <span className="text-xs font-mono text-emerald-400">{reasoning.confidence}%</span>
            </div>
            <div className="h-1.5 bg-muted rounded-full overflow-hidden">
              <div 
                className="h-full bg-gradient-to-r from-emerald-500 to-emerald-400 transition-all"
                style={{ width: `${reasoning.confidence}%` }}
              />
            </div>
          </div>

          {/* Key factors */}
          <div>
            <p className="text-[10px] text-muted-foreground uppercase tracking-wide mb-2">Key Factors</p>
            <div className="space-y-1.5">
              {reasoning.factors?.map((factor, i) => (
                <div key={i} className="flex items-start gap-2 text-xs">
                  <CheckCircle className="h-3.5 w-3.5 text-emerald-400 mt-0.5 shrink-0" />
                  <span className="text-foreground">{factor}</span>
                </div>
              ))}
            </div>
          </div>

          {/* Rejected paths */}
          {reasoning.rejectedPaths && reasoning.rejectedPaths.length > 0 && (
            <div>
              <p className="text-[10px] text-muted-foreground uppercase tracking-wide mb-2">Alternatives Considered</p>
              <div className="flex flex-wrap gap-1.5">
                {reasoning.rejectedPaths.map((path, i) => (
                  <span
                    key={i}
                    className="px-2 py-0.5 rounded text-[10px] bg-muted/50 text-muted-foreground line-through"
                  >
                    {path}
                  </span>
                ))}
              </div>
            </div>
          )}

          {/* Feedback buttons */}
          {onFeedback && (
            <div className="flex items-center gap-2 pt-2 border-t border-border/50">
              <span className="text-[10px] text-muted-foreground">Was this correct?</span>
              <div className="flex gap-1 ml-auto">
                <button
                  onClick={() => onFeedback(true)}
                  className="flex items-center gap-1 px-2 py-1 rounded text-[10px] bg-emerald-500/10 text-emerald-400 hover:bg-emerald-500/20 transition-colors"
                >
                  <ThumbsUp className="h-3 w-3" />
                  Yes
                </button>
                <button
                  onClick={() => onFeedback(false)}
                  className="flex items-center gap-1 px-2 py-1 rounded text-[10px] bg-destructive/10 text-destructive hover:bg-destructive/20 transition-colors"
                >
                  <ThumbsDown className="h-3 w-3" />
                  No
                </button>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  )
}

// Decision Summary Toast - Shows decision result notification
function DecisionSummaryToast({
  nodeName,
  chosenPath,
  confidence,
  onClose,
}: {
  nodeName: string
  chosenPath: string
  confidence: number
  onClose: () => void
}) {
  return (
    <div className="fixed bottom-4 right-4 z-50 animate-in slide-in-from-bottom-2 fade-in">
      <div className="flex items-start gap-3 p-4 rounded-lg bg-card border border-emerald-500/30 shadow-lg max-w-sm">
        <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-emerald-500/20 shrink-0">
          <Brain className="h-4 w-4 text-emerald-400" />
        </div>
        <div className="flex-1 min-w-0">
          <p className="text-sm font-medium text-foreground">AI Decision Complete</p>
          <p className="text-xs text-muted-foreground mt-0.5">
            <span className="text-emerald-400 font-medium">{nodeName}</span> selected{" "}
            <span className="text-foreground font-medium">{chosenPath}</span>
          </p>
          <div className="flex items-center gap-2 mt-2">
            <div className="flex-1 h-1 bg-muted rounded-full overflow-hidden">
              <div 
                className="h-full bg-emerald-500"
                style={{ width: `${confidence}%` }}
              />
            </div>
            <span className="text-[10px] text-emerald-400 font-mono">{confidence}%</span>
          </div>
        </div>
        <button
          onClick={onClose}
          className="p-1 text-muted-foreground hover:text-foreground transition-colors"
        >
          <X className="h-4 w-4" />
        </button>
      </div>
    </div>
  )
}

// Dynamic Form Field Component
function DynamicFormField({
  field,
  value,
  onChange,
}: {
  field: { name: string; type: string; required: boolean; placeholder?: string; options?: string[] }
  value: string
  onChange: (value: string) => void
}) {
  const labelClass = "text-xs font-medium text-muted-foreground mb-1.5 block"
  const inputClass = "w-full h-9 rounded-md border border-border bg-secondary px-3 text-sm focus:outline-none focus:ring-1 focus:ring-ring"
  
  return (
    <div>
      <label className={labelClass}>
        {field.name.replace(/([A-Z])/g, ' $1').replace(/^./, s => s.toUpperCase())}
        {field.required && <span className="text-red-500 ml-0.5">*</span>}
      </label>
      
      {field.type === "select" && field.options && (
        <select
          value={value}
          onChange={(e) => onChange(e.target.value)}
          className={inputClass}
        >
          <option value="">Select...</option>
          {field.options.map((opt) => (
            <option key={opt} value={opt}>{opt}</option>
          ))}
        </select>
      )}
      
      {field.type === "textarea" && (
        <textarea
          value={value}
          onChange={(e) => onChange(e.target.value)}
          placeholder={field.placeholder}
          className="w-full h-24 rounded-md border border-border bg-secondary px-3 py-2 text-sm font-mono resize-none focus:outline-none focus:ring-1 focus:ring-ring"
        />
      )}
      
      {field.type === "checkbox" && (
        <div className="flex items-center gap-2">
          <input
            type="checkbox"
            checked={value === "true"}
            onChange={(e) => onChange(e.target.checked ? "true" : "false")}
            className="rounded border-border"
          />
          <span className="text-sm text-muted-foreground">{field.placeholder || "Enable"}</span>
        </div>
      )}
      
      {["text", "email", "number", "date", "datetime-local"].includes(field.type) && (
        <Input
          type={field.type}
          value={value}
          onChange={(e) => onChange(e.target.value)}
          placeholder={field.placeholder}
          className="h-9 text-sm bg-secondary border-border"
        />
      )}
      
      {field.placeholder && field.type !== "checkbox" && (
        <p className="text-[10px] text-muted-foreground mt-1">{field.placeholder}</p>
      )}
    </div>
  )
}

// Agent Council Node Component - Multi-agent collaboration
function AgentCouncilNode({
  node,
  isSelected,
  isConnectTarget,
  onSelect,
  onDelete,
  onDrag,
  onShowDetails,
  onViewDebate,
  onConnectionDragStart,
  onConnectionDrop,
  isDraggingConnection,
  }: {
  node: WorkflowNode
  isSelected: boolean
  isConnectTarget: boolean
  onSelect: () => void
  onDelete: () => void
  onDrag: (position: { x: number; y: number }) => void
  onShowDetails: () => void
  onViewDebate?: () => void
  onConnectionDragStart?: (nodeId: string, e: React.MouseEvent) => void
  onConnectionDrop?: (nodeId: string) => void
  isDraggingConnection?: boolean
  }) {
  const [isDragging, setIsDragging] = useState(false)
  const [isMouseDown, setIsMouseDown] = useState(false)
  const [isHovered, setIsHovered] = useState(false)
  const dragStartRef = useRef({ x: 0, y: 0, nodeX: 0, nodeY: 0 })
  const hasDraggedRef = useRef(false)
  
  const agents = node.councilConfig?.participatingAgents || []
  const isDebating = node.state === "debating"
  const hasConsensus = node.state === "consensus"
  const isEscalated = node.state === "escalated"
  
  const stateColors = {
    idle: { ring: "border-amber-500/30", bg: "bg-amber-500/5", glow: "" },
    debating: { ring: "border-amber-400 animate-pulse", bg: "bg-amber-500/10", glow: "shadow-[0_0_30px_rgba(245,158,11,0.3)]" },
    consensus: { ring: "border-emerald-500", bg: "bg-emerald-500/10", glow: "shadow-[0_0_20px_rgba(16,185,129,0.3)]" },
    escalated: { ring: "border-red-500", bg: "bg-red-500/10", glow: "shadow-[0_0_20px_rgba(239,68,68,0.3)]" },
    running: { ring: "border-blue-500 animate-pulse", bg: "bg-blue-500/10", glow: "shadow-[0_0_20px_rgba(59,130,246,0.3)]" },
    success: { ring: "border-emerald-500", bg: "bg-emerald-500/10", glow: "" },
    error: { ring: "border-red-500", bg: "bg-red-500/10", glow: "" },
    waiting: { ring: "border-amber-500/50", bg: "bg-amber-500/5", glow: "" },
    evaluating: { ring: "border-violet-500", bg: "bg-violet-500/10", glow: "" },
  }
  const stateConfig = stateColors[node.state || "idle"]
  
  const handleMouseDown = (e: React.MouseEvent) => {
    e.preventDefault()
    e.stopPropagation()
    setIsMouseDown(true)
    hasDraggedRef.current = false
    dragStartRef.current = {
      x: e.clientX,
      y: e.clientY,
      nodeX: node.position.x,
      nodeY: node.position.y,
    }
  }
  
  const handleDoubleClick = (e: React.MouseEvent) => {
    e.preventDefault()
    e.stopPropagation()
    onShowDetails()
  }
  
  useEffect(() => {
    if (!isMouseDown) return
    
    const handleGlobalMouseMove = (e: MouseEvent) => {
      const dx = e.clientX - dragStartRef.current.x
      const dy = e.clientY - dragStartRef.current.y
      
      if (Math.abs(dx) > 5 || Math.abs(dy) > 5) {
        hasDraggedRef.current = true
        setIsDragging(true)
        const newX = Math.max(0, dragStartRef.current.nodeX + dx)
        const newY = Math.max(0, dragStartRef.current.nodeY + dy)
        onDrag({ x: newX, y: newY })
      }
    }
    
    const handleGlobalMouseUp = () => {
      if (!hasDraggedRef.current) {
        onSelect()
      }
      setIsDragging(false)
      setIsMouseDown(false)
      hasDraggedRef.current = false
    }
    
    window.addEventListener("mousemove", handleGlobalMouseMove)
    window.addEventListener("mouseup", handleGlobalMouseUp)
    
    return () => {
      window.removeEventListener("mousemove", handleGlobalMouseMove)
      window.removeEventListener("mouseup", handleGlobalMouseUp)
    }
  }, [isMouseDown, onDrag, onSelect, node.id])
  
  // Agent avatar colors based on role
  const getAgentColor = (index: number) => {
    const colors = [
      "bg-blue-500", "bg-emerald-500", "bg-violet-500", "bg-amber-500",
      "bg-rose-500", "bg-cyan-500", "bg-indigo-500", "bg-pink-500"
    ]
    return colors[index % colors.length]
  }
  
  return (
    <div
      className={cn(
        "absolute cursor-pointer transition-all duration-150 group",
        isSelected ? "z-20" : "z-10",
        isDragging && "cursor-grabbing z-30"
      )}
      style={{ left: node.position.x, top: node.position.y }}
      onMouseDown={handleMouseDown}
      onDoubleClick={handleDoubleClick}
      onMouseEnter={() => setIsHovered(true)}
      onMouseLeave={() => setIsHovered(false)}
    >
      {/* Circular council container */}
      <div className={cn(
        "relative w-48 h-48 rounded-full border-2 transition-all duration-300",
        stateConfig.ring,
        stateConfig.bg,
        stateConfig.glow,
        isSelected && "ring-2 ring-amber-400/50 ring-offset-2 ring-offset-background"
      )}>
        {/* Orbital ring animation */}
        <div className={cn(
          "absolute inset-2 rounded-full border border-dashed border-amber-500/30",
          isDebating && "animate-spin"
        )} style={{ animationDuration: "8s" }} />
        
        {/* Center icon */}
        <div className="absolute inset-0 flex items-center justify-center">
          <div className={cn(
            "w-16 h-16 rounded-full flex items-center justify-center",
            "bg-gradient-to-br from-amber-500/20 to-orange-500/20 border border-amber-500/40"
          )}>
            <Users className="h-8 w-8 text-amber-400" />
          </div>
        </div>
        
        {/* Agent avatars in orbital positions */}
        {agents.slice(0, 6).map((agent, index) => {
          const angle = (index * 360 / Math.min(agents.length, 6)) - 90
          const radius = 70
          const x = Math.cos(angle * Math.PI / 180) * radius
          const y = Math.sin(angle * Math.PI / 180) * radius
          
          return (
            <div
              key={agent.id}
              className={cn(
                "absolute w-10 h-10 rounded-full flex items-center justify-center text-xs font-bold text-white transition-all duration-300",
                getAgentColor(index),
                isDebating && "animate-pulse"
              )}
              style={{
                left: `calc(50% + ${x}px - 20px)`,
                top: `calc(50% + ${y}px - 20px)`,
              }}
              title={`${agent.name} - ${agent.role}`}
            >
              {agent.name.charAt(0)}
            </div>
          )
        })}
        
        {/* Connection handles */}
        {/* Top */}
        <div
          onMouseDown={(e) => onConnectionDragStart?.(node.id, e)}
          onMouseUp={() => isDraggingConnection && onConnectionDrop?.(node.id)}
          className={cn(
            "absolute top-0 left-1/2 -translate-x-1/2 -translate-y-1/2 h-4 w-4 rounded-full border-2 transition-all duration-200 cursor-crosshair z-10",
            isDraggingConnection
              ? "border-emerald-400 bg-emerald-400 shadow-[0_0_12px_rgba(52,211,153,0.6)] scale-125"
              : isSelected
              ? "border-amber-400 bg-amber-400/60 hover:scale-125"
              : "border-amber-400/40 bg-card hover:border-amber-400 hover:bg-amber-400/50 hover:scale-125"
          )}
          title="Drag to connect"
        />
        {/* Right */}
        <div
          onMouseDown={(e) => onConnectionDragStart?.(node.id, e)}
          onMouseUp={() => isDraggingConnection && onConnectionDrop?.(node.id)}
          className={cn(
            "absolute right-0 top-1/2 translate-x-1/2 -translate-y-1/2 h-4 w-4 rounded-full border-2 transition-all duration-200 cursor-crosshair z-10",
            isDraggingConnection
              ? "border-emerald-400 bg-emerald-400 shadow-[0_0_12px_rgba(52,211,153,0.6)] scale-125"
              : isSelected
              ? "border-amber-400 bg-amber-400/60 hover:scale-125"
              : "border-amber-400/40 bg-card hover:border-amber-400 hover:bg-amber-400/50 hover:scale-125"
          )}
          title="Drag to connect"
        />
        {/* Bottom */}
        <div
          onMouseDown={(e) => onConnectionDragStart?.(node.id, e)}
          onMouseUp={() => isDraggingConnection && onConnectionDrop?.(node.id)}
          className={cn(
            "absolute bottom-0 left-1/2 -translate-x-1/2 translate-y-1/2 h-4 w-4 rounded-full border-2 transition-all duration-200 cursor-crosshair z-10",
            isDraggingConnection
              ? "border-emerald-400 bg-emerald-400 shadow-[0_0_12px_rgba(52,211,153,0.6)] scale-125"
              : isSelected
              ? "border-amber-400 bg-amber-400/60 hover:scale-125"
              : "border-amber-400/40 bg-card hover:border-amber-400 hover:bg-amber-400/50 hover:scale-125"
          )}
          title="Drag to connect"
        />
        {/* Left */}
        <div
          onMouseDown={(e) => onConnectionDragStart?.(node.id, e)}
          onMouseUp={() => isDraggingConnection && onConnectionDrop?.(node.id)}
          className={cn(
            "absolute left-0 top-1/2 -translate-x-1/2 -translate-y-1/2 h-4 w-4 rounded-full border-2 transition-all duration-200 cursor-crosshair z-10",
            isDraggingConnection
              ? "border-emerald-400 bg-emerald-400 shadow-[0_0_12px_rgba(52,211,153,0.6)] scale-125"
              : isSelected
              ? "border-amber-400 bg-amber-400/60 hover:scale-125"
              : "border-amber-400/40 bg-card hover:border-amber-400 hover:bg-amber-400/50 hover:scale-125"
          )}
          title="Drag to connect"
        />
        
        {/* Delete button on hover */}
        {isHovered && (
          <button
            onClick={(e) => {
              e.stopPropagation()
              onDelete()
            }}
            className="absolute -top-2 -right-2 h-6 w-6 rounded-full bg-destructive text-destructive-foreground flex items-center justify-center hover:bg-destructive/90 transition-colors z-20"
          >
            <X className="h-3 w-3" />
          </button>
        )}
      </div>
      
      {/* Node label below */}
      <div className="mt-2 text-center max-w-48">
        <div className="font-medium text-sm text-foreground">{node.name}</div>
        <div className="flex items-center justify-center gap-1 mt-0.5">
          <Users className="h-3 w-3 text-amber-500" />
          <span className="text-xs text-amber-500">Agent Council</span>
        </div>
        {node.description && (
          <div className="text-xs text-muted-foreground mt-0.5 line-clamp-1">{node.description}</div>
        )}
        {/* State indicator */}
        {isDebating && (
          <Badge variant="outline" className="mt-1 text-[10px] bg-amber-500/10 text-amber-400 border-amber-500/30">
            Council evaluating...
          </Badge>
        )}
        {hasConsensus && (
          <Badge variant="outline" className="mt-1 text-[10px] bg-emerald-500/10 text-emerald-400 border-emerald-500/30">
            Consensus reached
          </Badge>
        )}
        {isEscalated && (
          <Badge variant="outline" className="mt-1 text-[10px] bg-red-500/10 text-red-400 border-red-500/30">
            Escalated to human
          </Badge>
        )}
{/* Agent count and View Debate button */}
  <div className="flex items-center justify-center gap-2 mt-1.5">
    {agents.length > 0 && (
      <span className="text-[10px] text-muted-foreground">{agents.length} agents</span>
    )}
    {(isDebating || hasConsensus || isEscalated) && onViewDebate && (
      <button
        onClick={(e) => {
          e.stopPropagation()
          onViewDebate()
        }}
        className="flex items-center gap-1 text-[10px] text-amber-400 hover:text-amber-300 bg-amber-500/10 px-2 py-0.5 rounded-full hover:bg-amber-500/20 transition-colors"
      >
        <MessageSquare className="h-3 w-3" />
        View Debate
      </button>
    )}
  </div>
      </div>
    </div>
  )
}

// Multi-Agent Debate View Dialog
function DebateViewDialog({
  open,
  onOpenChange,
  node,
  onAcceptDecision,
  onOverrideDecision,
  onRequestMoreEvidence,
}: {
  open: boolean
  onOpenChange: (open: boolean) => void
  node: WorkflowNode | null
  onAcceptDecision?: () => void
  onOverrideDecision?: () => void
  onRequestMoreEvidence?: () => void
}) {
  if (!node || node.type !== "council") return null

  const agents = node.councilConfig?.participatingAgents || []
  const debate = node.councilConfig?.debate
  const finalDecision = node.councilConfig?.finalDecision
  const isDebating = node.state === "debating"
  const hasConsensus = node.state === "consensus"

  // Mock debate data if not present
  const contributions = debate?.contributions || agents.map((agent, idx) => ({
    agentId: agent.id,
    position: idx === 0 ? "Approve" : idx === 1 ? "Request more data" : "Approve with conditions",
    confidence: 70 + Math.random() * 25,
    reasoning: `Based on the available evidence, I recommend this action because...`,
    evidenceUsed: ["CRM data", "Previous node outputs"],
    timestamp: new Date(),
  }))

  const disagreements = debate?.disagreements || (agents.length > 2 ? [{
    agentIds: [agents[0]?.id, agents[1]?.id].filter(Boolean) as string[],
    topic: "Data completeness requirement"
  }] : [])

  const timeline = debate?.timeline || [
    { step: "Gathering evidence", status: "complete" as const },
    { step: "Agents reviewing", status: "complete" as const },
    { step: "Submitting positions", status: isDebating ? "active" as const : "complete" as const },
    { step: "Resolving conflicts", status: hasConsensus ? "complete" as const : "pending" as const },
    { step: "Final recommendation", status: hasConsensus ? "complete" as const : "pending" as const },
  ]

  const getAgentById = (id: string) => agents.find(a => a.id === id)
  const getAgentColor = (index: number) => {
    const colors = ["bg-blue-500", "bg-emerald-500", "bg-violet-500", "bg-amber-500", "bg-rose-500", "bg-cyan-500"]
    return colors[index % colors.length]
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-3xl max-h-[85vh] overflow-hidden flex flex-col">
        <DialogHeader>
          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-full bg-amber-500/20">
              <Users className="h-5 w-5 text-amber-400" />
            </div>
            <div>
              <DialogTitle className="text-lg">{node.name}</DialogTitle>
              <DialogDescription className="text-sm">
                {isDebating ? "Council is evaluating..." : hasConsensus ? "Consensus reached" : "Multi-agent debate view"}
              </DialogDescription>
            </div>
            {isDebating && (
              <Badge variant="outline" className="ml-auto bg-amber-500/10 text-amber-400 border-amber-500/30 animate-pulse">
                Debating...
              </Badge>
            )}
            {hasConsensus && (
              <Badge variant="outline" className="ml-auto bg-emerald-500/10 text-emerald-400 border-emerald-500/30">
                Consensus
              </Badge>
            )}
          </div>
        </DialogHeader>

        <div className="flex-1 overflow-y-auto space-y-6 py-4">
          {/* Debate Timeline */}
          <div className="px-1">
            <h4 className="text-xs font-medium text-muted-foreground uppercase tracking-wide mb-3">Debate Timeline</h4>
            <div className="flex items-center gap-2">
              {timeline.map((step, idx) => (
                <div key={idx} className="flex items-center gap-2 flex-1">
                  <div className={cn(
                    "flex items-center justify-center h-6 w-6 rounded-full text-[10px] font-medium",
                    step.status === "complete" && "bg-emerald-500 text-white",
                    step.status === "active" && "bg-amber-500 text-white animate-pulse",
                    step.status === "pending" && "bg-secondary text-muted-foreground"
                  )}>
                    {step.status === "complete" ? <CheckCircle className="h-3.5 w-3.5" /> : idx + 1}
                  </div>
                  <span className={cn(
                    "text-[10px] truncate",
                    step.status === "complete" && "text-emerald-400",
                    step.status === "active" && "text-amber-400",
                    step.status === "pending" && "text-muted-foreground"
                  )}>
                    {step.step}
                  </span>
                  {idx < timeline.length - 1 && (
                    <div className={cn(
                      "flex-1 h-0.5 rounded",
                      step.status === "complete" ? "bg-emerald-500/50" : "bg-border"
                    )} />
                  )}
                </div>
              ))}
            </div>
          </div>

          {/* Agent Contributions */}
          <div>
            <h4 className="text-xs font-medium text-muted-foreground uppercase tracking-wide mb-3">Agent Contributions</h4>
            <div className="grid gap-3">
              {contributions.map((contribution, idx) => {
                const agent = getAgentById(contribution.agentId) || agents[idx]
                if (!agent) return null
                return (
                  <div key={contribution.agentId} className="p-4 rounded-lg bg-secondary/30 border border-border">
                    <div className="flex items-start gap-3">
                      <div className={cn(
                        "h-10 w-10 rounded-full flex items-center justify-center text-sm font-bold text-white",
                        getAgentColor(idx)
                      )}>
                        {agent.name.charAt(0)}
                      </div>
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2 mb-1">
                          <span className="font-medium text-sm text-foreground">{agent.name}</span>
                          <Badge variant="outline" className="text-[9px] py-0 h-4">{agent.role}</Badge>
                          <Badge 
                            variant="outline" 
                            className={cn(
                              "ml-auto text-[10px]",
                              contribution.position.toLowerCase().includes("approve") 
                                ? "bg-emerald-500/10 text-emerald-400 border-emerald-500/30"
                                : contribution.position.toLowerCase().includes("reject")
                                ? "bg-red-500/10 text-red-400 border-red-500/30"
                                : "bg-amber-500/10 text-amber-400 border-amber-500/30"
                            )}
                          >
                            {contribution.position}
                          </Badge>
                        </div>
                        <p className="text-xs text-muted-foreground mb-2">{contribution.reasoning}</p>
                        <div className="flex items-center gap-3">
                          <div className="flex items-center gap-1.5">
                            <Gauge className="h-3 w-3 text-muted-foreground" />
                            <span className="text-[10px] text-muted-foreground">
                              {Math.round(contribution.confidence)}% confident
                            </span>
                          </div>
                          <div className="flex items-center gap-1">
                            <Database className="h-3 w-3 text-muted-foreground" />
                            <span className="text-[10px] text-muted-foreground">
                              {contribution.evidenceUsed?.join(", ")}
                            </span>
                          </div>
                        </div>
                      </div>
                    </div>
                  </div>
                )
              })}
            </div>
          </div>

          {/* Disagreements */}
          {disagreements.length > 0 && (
            <div>
              <h4 className="text-xs font-medium text-muted-foreground uppercase tracking-wide mb-3 flex items-center gap-2">
                <AlertTriangle className="h-3.5 w-3.5 text-amber-400" />
                Disagreements Detected
              </h4>
              <div className="space-y-2">
                {disagreements.map((disagreement, idx) => {
                  const conflictingAgents = disagreement.agentIds.map(id => getAgentById(id)).filter(Boolean)
                  return (
                    <div key={idx} className="p-3 rounded-lg bg-amber-500/5 border border-amber-500/20">
                      <div className="flex items-center gap-2 mb-1">
                        {conflictingAgents.map((agent, agentIdx) => (
                          <span key={agent?.id} className="text-xs font-medium text-foreground">
                            {agent?.name}{agentIdx < conflictingAgents.length - 1 && " vs "}
                          </span>
                        ))}
                      </div>
                      <p className="text-xs text-amber-400">{disagreement.topic}</p>
                    </div>
                  )
                })}
              </div>
            </div>
          )}

          {/* Final Decision Summary */}
          {finalDecision && (
            <div className="p-4 rounded-lg bg-emerald-500/5 border border-emerald-500/30">
              <div className="flex items-center gap-2 mb-3">
                <CheckCircle className="h-5 w-5 text-emerald-400" />
                <h4 className="font-medium text-foreground">Final Decision</h4>
                <Badge variant="outline" className="ml-auto bg-emerald-500/10 text-emerald-400 border-emerald-500/30">
                  {finalDecision.confidence}% confidence
                </Badge>
              </div>
              <div className="text-lg font-semibold text-foreground mb-2">
                {finalDecision.recommendation}
              </div>
              <p className="text-sm text-muted-foreground mb-3">
                Method: {finalDecision.method?.replace("-", " ")}
              </p>
              {finalDecision.keyReasons && (
                <div className="space-y-1 mb-3">
                  {finalDecision.keyReasons.map((reason, i) => (
                    <div key={i} className="flex items-center gap-2 text-sm text-foreground">
                      <CheckCircle className="h-3.5 w-3.5 text-emerald-400 shrink-0" />
                      {reason}
                    </div>
                  ))}
                </div>
              )}
              {finalDecision.dissentingOpinions && finalDecision.dissentingOpinions.length > 0 && (
                <div className="pt-3 border-t border-amber-500/20">
                  <p className="text-xs text-amber-400 uppercase tracking-wide mb-2">Dissenting opinions:</p>
                  {finalDecision.dissentingOpinions.map((dissent, i) => {
                    const agent = getAgentById(dissent.agentId)
                    return (
                      <div key={i} className="text-sm text-muted-foreground">
                        <span className="font-medium">{agent?.name || "Agent"}:</span> {dissent.opinion}
                      </div>
                    )
                  })}
                </div>
              )}
            </div>
          )}
        </div>

        {/* Action buttons */}
        {(hasConsensus || finalDecision) && (
          <div className="flex items-center gap-2 pt-4 border-t border-border">
            <Button 
              variant="default" 
              className="flex-1 gap-2 bg-emerald-600 hover:bg-emerald-700"
              onClick={onAcceptDecision}
            >
              <CheckCircle className="h-4 w-4" />
              Accept Recommendation
            </Button>
            <Button 
              variant="outline" 
              className="gap-2"
              onClick={onOverrideDecision}
            >
              <RotateCcw className="h-4 w-4" />
              Override
            </Button>
            <Button 
              variant="outline" 
              className="gap-2"
              onClick={onRequestMoreEvidence}
            >
              <FileSearch className="h-4 w-4" />
              More Evidence
            </Button>
          </div>
        )}
      </DialogContent>
    </Dialog>
  )
}

// Config Panel - Sheet-based with connector intelligence
function ConfigPanel({
  node,
  onClose,
  onUpdate,
}: {
  node: WorkflowNode | null
  onClose: () => void
  onUpdate: (updates: Partial<WorkflowNode>) => void
}) {
  const [formValues, setFormValues] = useState<Record<string, string>>({})
  
  useEffect(() => {
    // Reset form values when node changes
    setFormValues({})
  }, [node?.id])
  
  if (!node) return null

  const config = nodeTypeConfig[node.type]
  const Icon = config.icon
  
  // Get available actions for this node's vendor
  const availableActions = node.vendor ? connectorActions[node.vendor]?.actions || [] : []
  const selectedAction = availableActions.find(a => a.id === node.selectedAction)
  
  // Get connector status
  const connectorStatus = connectorLibrary.find(c => c.vendor === node.vendor)?.status || "disconnected"

  return (
    <Sheet open={!!node} onOpenChange={() => onClose()}>
      <SheetContent className="w-[400px] sm:w-[540px] overflow-y-auto px-6">
        <SheetHeader className="pb-4 border-b border-border mb-4">
          <div className="flex items-center gap-3">
            <div className={cn(
              "flex h-10 w-10 items-center justify-center rounded-lg border",
              config.color
            )}>
{node.vendor ? (
  <ConnectorIcon vendor={node.vendor} size="sm" showStatusIndicator={false} />
  ) : (
  <Icon className="h-5 w-5" />
  )}
            </div>
            <div>
              <SheetTitle className="text-left">{node.name}</SheetTitle>
              <SheetDescription className="text-left">
                {config.label} Configuration
              </SheetDescription>
            </div>
          </div>
        </SheetHeader>

        <div className="space-y-6">
          {/* Node Type Badge */}
          <div className="flex items-center gap-2 p-3 rounded-lg bg-secondary/50 border border-border">
            <div className={cn("h-2 w-2 rounded-full", 
              node.type === "source" && "bg-muted-foreground",
              node.type === "agent" && "bg-blue-500",
              node.type === "connector" && "bg-amber-500",
              node.type === "tool" && "bg-violet-500",
node.type === "approval" && "bg-red-500",
  node.type === "task" && "bg-emerald-500",
  node.type === "decision" && "bg-violet-500"
            )} />
            <span className="text-sm font-medium">{config.label}</span>
            {node.vendor && (
              <>
                <span className="text-muted-foreground/50">|</span>
                <span className="text-sm text-muted-foreground capitalize">{node.vendor}</span>
                <div className={cn(
                  "ml-auto flex items-center gap-1.5 text-xs px-2 py-0.5 rounded-full",
                  connectorStatus === "connected" 
                    ? "bg-emerald-500/10 text-emerald-500" 
                    : "bg-amber-500/10 text-amber-500"
                )}>
                  <div className={cn(
                    "h-1.5 w-1.5 rounded-full",
                    connectorStatus === "connected" ? "bg-emerald-500" : "bg-amber-500"
                  )} />
                  {connectorStatus}
                </div>
              </>
            )}
          </div>

          {/* Basic Info */}
          <div className="space-y-4">
            <div>
              <label className="text-xs font-medium text-muted-foreground uppercase tracking-wide mb-1.5 block">
                Name
              </label>
              <Input
                value={node.name}
                onChange={(e) => onUpdate({ name: e.target.value })}
                className="h-9 text-sm bg-secondary border-border"
              />
            </div>

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

            <div>
              <label className="text-xs font-medium text-muted-foreground uppercase tracking-wide mb-1.5 block">
                Data Label
              </label>
              <Input
                value={node.dataLabel || ""}
                onChange={(e) => onUpdate({ dataLabel: e.target.value })}
                className="h-9 text-sm bg-secondary border-border font-mono"
                placeholder="e.g., customer_data, validated_records"
              />
              <p className="text-[10px] text-muted-foreground mt-1">
                Label shown on the connection line for this output
              </p>
            </div>
          </div>

          {/* Action Selector for Connectors/Sources */}
          {node.vendor && availableActions.length > 0 && (
            <div className="space-y-4 pt-4 border-t border-border">
              <div className="flex items-center justify-between">
                <h4 className="text-sm font-medium text-foreground">Action Configuration</h4>
                {selectedAction && (
                  <div className="flex items-center gap-2">
                    <span className={cn(
                      "px-2 py-0.5 rounded text-xs font-mono",
                      selectedAction.method === "GET" && "bg-emerald-500/10 text-emerald-400",
                      selectedAction.method === "POST" && "bg-blue-500/10 text-blue-400",
                      selectedAction.method === "PATCH" && "bg-amber-500/10 text-amber-400"
                    )}>
                      {selectedAction.method}
                    </span>
                    <span className="text-xs text-muted-foreground">{selectedAction.type}</span>
                  </div>
                )}
              </div>

              <div>
                <label className="text-xs font-medium text-muted-foreground uppercase tracking-wide mb-1.5 block">
                  Select Action
                </label>
                <select
                  value={node.selectedAction || ""}
                  onChange={(e) => onUpdate({ selectedAction: e.target.value })}
                  className="w-full h-9 rounded-md border border-border bg-secondary px-3 text-sm focus:outline-none focus:ring-1 focus:ring-ring"
                >
                  <option value="">Select an action...</option>
                  {availableActions.map((action) => (
                    <option key={action.id} value={action.id}>
                      {action.name} ({action.method})
                    </option>
                  ))}
                </select>
              </div>

              {/* Dynamic Form Fields */}
              {selectedAction && (
                <div className="space-y-4 p-4 rounded-lg bg-muted/30 border border-border">
                  <div className="flex items-center gap-2 mb-2">
                    <Sparkles className="h-4 w-4 text-blue-400" />
                    <span className="text-sm font-medium">Action Parameters</span>
                  </div>
                  {selectedAction.fields.map((field) => (
                    <DynamicFormField
                      key={field.name}
                      field={field}
                      value={formValues[field.name] || ""}
                      onChange={(value) => setFormValues(prev => ({ ...prev, [field.name]: value }))}
                    />
                  ))}
                </div>
              )}

              {/* API Context Display */}
              {selectedAction && (
                <div className="flex items-center gap-4 p-3 rounded-lg bg-muted/20 border border-border text-xs text-muted-foreground">
                  <div className="flex items-center gap-1.5">
                    <Activity className="h-3.5 w-3.5" />
                    <span>Method: {selectedAction.method}</span>
                  </div>
                  <div className="flex items-center gap-1.5">
                    <Link2 className="h-3.5 w-3.5" />
                    <span>Type: {selectedAction.type}</span>
                  </div>
                  {connectorStatus === "connected" && (
                    <div className="flex items-center gap-1.5 text-emerald-400">
                      <CircleDot className="h-3.5 w-3.5" />
                      <span>Ready</span>
                    </div>
                  )}
                </div>
              )}
            </div>
          )}

          {/* Type-specific config */}
          {node.type === "agent" && (
            <div className="space-y-4 pt-4 border-t border-border">
              <h4 className="text-sm font-medium text-foreground">Agent Settings</h4>
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
                <div className="mt-2">
                  <ModelInheritanceChain
                    workspaceModel="auto"
                    agentModel="balanced"
                    taskModel={String(node.config.model || "")}
                  />
                </div>
              </div>
            </div>
          )}

          {node.type === "task" && (
            <div className="space-y-4 pt-4 border-t border-border">
              <h4 className="text-sm font-medium text-foreground">Task Settings</h4>
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
            </div>
          )}

{node.type === "approval" && (
  <div className="space-y-4 pt-4 border-t border-border">
  <h4 className="text-sm font-medium text-foreground">Approval Settings</h4>
  <div>
  <label className="text-xs font-medium text-muted-foreground uppercase tracking-wide mb-1.5 block">
  Approvers
  </label>
  <Input
  placeholder="admin@company.com"
  className="h-9 text-sm bg-secondary border-border"
  />
  </div>
  <div className="flex items-center justify-between p-3 rounded-lg bg-secondary/50">
  <label className="text-sm text-foreground">Auto-approve in staging</label>
  <Switch />
  </div>
  <div className="flex items-center gap-2 p-3 rounded-lg bg-warning/10 border border-warning/20">
  <AlertTriangle className="h-4 w-4 text-warning" />
  <span className="text-sm text-warning">Requires admin approval</span>
  </div>
  </div>
  )}

  {/* Decision Node Configuration */}
  {node.type === "decision" && (
  <div className="space-y-5 pt-4 border-t border-violet-500/20">
    {/* Header */}
    <div className="flex items-center gap-2">
      <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-violet-500/20">
        <GitBranch className="h-4 w-4 text-violet-400" />
      </div>
      <div>
        <h4 className="text-sm font-medium text-foreground">Decision Configuration</h4>
        <p className="text-[10px] text-muted-foreground">Configure AI-powered branching logic</p>
      </div>
    </div>

    {/* Decision Objective */}
    <div>
      <label className="text-xs font-medium text-muted-foreground uppercase tracking-wide mb-1.5 block">
        Decision Objective
      </label>
      <Textarea
        value={node.decisionConfig?.objective || ""}
        onChange={(e) => onUpdate({ 
          decisionConfig: { ...node.decisionConfig, objective: e.target.value } 
        })}
        placeholder="What should the AI decide? e.g., 'Determine if lead is high value'"
        className="h-20 text-sm bg-secondary border-border resize-none"
      />
    </div>

    {/* Decision Strategy */}
    <div>
      <label className="text-xs font-medium text-muted-foreground uppercase tracking-wide mb-1.5 block">
        Decision Strategy
      </label>
      <div className="grid grid-cols-3 gap-2">
        {(["rule-based", "ai-assisted", "hybrid"] as const).map((strategy) => (
          <button
            key={strategy}
            onClick={() => onUpdate({ 
              decisionConfig: { ...node.decisionConfig, strategy } 
            })}
            className={cn(
              "p-2.5 rounded-lg border text-center transition-all",
              node.decisionConfig?.strategy === strategy
                ? "border-violet-500 bg-violet-500/10 text-violet-400"
                : "border-border bg-secondary/50 text-muted-foreground hover:border-muted-foreground"
            )}
          >
            <div className="text-xs font-medium capitalize">{strategy.replace("-", " ")}</div>
            <div className="text-[9px] mt-0.5 opacity-70">
              {strategy === "rule-based" && "If/else logic"}
              {strategy === "ai-assisted" && "LLM reasoning"}
              {strategy === "hybrid" && "Rules + AI"}
            </div>
          </button>
        ))}
      </div>
    </div>

    {/* Input Data Sources */}
    <div>
      <label className="text-xs font-medium text-muted-foreground uppercase tracking-wide mb-1.5 block">
        Input Data Sources
      </label>
      <div className="space-y-1.5">
        {["Previous node outputs", "CRM data", "Engagement metrics", "Enriched data"].map((source) => (
          <label key={source} className="flex items-center gap-2 p-2 rounded-md bg-secondary/30 hover:bg-secondary/50 cursor-pointer">
            <input
              type="checkbox"
              checked={node.decisionConfig?.inputSources?.includes(source) || false}
              onChange={(e) => {
                const current = node.decisionConfig?.inputSources || []
                const updated = e.target.checked 
                  ? [...current, source]
                  : current.filter(s => s !== source)
                onUpdate({ decisionConfig: { ...node.decisionConfig, inputSources: updated } })
              }}
              className="rounded border-border"
            />
            <span className="text-sm text-foreground">{source}</span>
          </label>
        ))}
      </div>
    </div>

    {/* Conditions (for rule-based) */}
    {node.decisionConfig?.strategy === "rule-based" && (
      <div>
        <label className="text-xs font-medium text-muted-foreground uppercase tracking-wide mb-1.5 block">
          Conditions
        </label>
        <Textarea
          value={node.decisionConfig?.conditions || ""}
          onChange={(e) => onUpdate({ 
            decisionConfig: { ...node.decisionConfig, conditions: e.target.value } 
          })}
          placeholder="If score > 80 → High Value&#10;If score 40-80 → Medium Value&#10;Else → Low Value"
          className="h-24 text-sm bg-secondary border-border resize-none font-mono"
        />
      </div>
    )}

    {/* AI Instructions (for ai-assisted/hybrid) */}
    {(node.decisionConfig?.strategy === "ai-assisted" || node.decisionConfig?.strategy === "hybrid") && (
      <div>
        <label className="text-xs font-medium text-muted-foreground uppercase tracking-wide mb-1.5 block">
          AI Instructions
        </label>
        <Textarea
          value={node.decisionConfig?.conditions || ""}
          onChange={(e) => onUpdate({ 
            decisionConfig: { ...node.decisionConfig, conditions: e.target.value } 
          })}
          placeholder="Choose the best next action based on customer intent, engagement history, and available data signals..."
          className="h-24 text-sm bg-secondary border-border resize-none"
        />
      </div>
    )}

    {/* Output Paths */}
    <div>
      <div className="flex items-center justify-between mb-1.5">
        <label className="text-xs font-medium text-muted-foreground uppercase tracking-wide">
          Output Paths
        </label>
        <button
          onClick={() => {
            const paths = node.outputPaths || []
            const newPath: DecisionPath = {
              id: `path-${Date.now()}`,
              label: `Path ${paths.length + 1}`,
            }
            onUpdate({ outputPaths: [...paths, newPath] })
          }}
          className="flex items-center gap-1 text-[10px] text-violet-400 hover:text-violet-300"
        >
          <Plus className="h-3 w-3" />
          Add path
        </button>
      </div>
      <div className="space-y-2">
        {(node.outputPaths || []).map((path, idx) => (
          <div key={path.id} className="flex items-center gap-2 p-2 rounded-lg bg-secondary/30 border border-border">
            <div className={cn(
              "h-2 w-2 rounded-full",
              idx === 0 && "bg-emerald-500",
              idx === 1 && "bg-blue-500",
              idx === 2 && "bg-amber-500",
              idx >= 3 && "bg-muted-foreground"
            )} />
            <Input
              value={path.label}
              onChange={(e) => {
                const updated = [...(node.outputPaths || [])]
                updated[idx] = { ...path, label: e.target.value }
                onUpdate({ outputPaths: updated })
              }}
              className="h-7 text-xs bg-secondary border-border flex-1"
              placeholder="Path label"
            />
            <Input
              value={path.condition || ""}
              onChange={(e) => {
                const updated = [...(node.outputPaths || [])]
                updated[idx] = { ...path, condition: e.target.value }
                onUpdate({ outputPaths: updated })
              }}
              className="h-7 text-xs bg-secondary border-border flex-1 font-mono"
              placeholder="Condition"
            />
            {path.isDefault && (
              <span className="text-[9px] text-muted-foreground px-1.5 py-0.5 bg-muted rounded">Default</span>
            )}
            <button
              onClick={() => {
                const updated = (node.outputPaths || []).filter(p => p.id !== path.id)
                onUpdate({ outputPaths: updated })
              }}
              className="p-1 text-muted-foreground hover:text-destructive"
            >
              <X className="h-3 w-3" />
            </button>
          </div>
        ))}
      </div>
    </div>

    {/* AI Reasoning Display (if available) */}
    {node.decisionConfig?.reasoning && (
      <div className="p-3 rounded-lg bg-emerald-500/5 border border-emerald-500/20">
        <div className="flex items-center gap-2 mb-2">
          <Brain className="h-4 w-4 text-emerald-400" />
          <span className="text-xs font-medium text-emerald-400">AI Reasoning</span>
          <span className="ml-auto text-[10px] text-emerald-400 bg-emerald-500/20 px-1.5 py-0.5 rounded">
            {node.decisionConfig.reasoning.confidence}% confidence
          </span>
        </div>
        <p className="text-xs text-muted-foreground mb-2">
          {node.decisionConfig.reasoning.summary}
        </p>
        <div className="space-y-1">
          <p className="text-[10px] text-muted-foreground uppercase tracking-wide">Key factors:</p>
          {node.decisionConfig.reasoning.factors?.map((factor, i) => (
            <div key={i} className="flex items-center gap-1.5 text-xs text-foreground">
              <CheckCircle className="h-3 w-3 text-emerald-400" />
              {factor}
            </div>
          ))}
        </div>
        <div className="mt-2 pt-2 border-t border-emerald-500/20">
          <span className="text-[10px] text-emerald-400">
            Selected: {node.decisionConfig.reasoning.chosenPath}
          </span>
        </div>
      </div>
    )}
  </div>
  )}

  {/* Agent Council Configuration */}
  {node.type === "council" && (
  <div className="space-y-5 pt-4 border-t border-amber-500/20">
    {/* Header */}
    <div className="flex items-center gap-2">
      <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-amber-500/20">
        <Users className="h-4 w-4 text-amber-400" />
      </div>
      <div>
        <h4 className="text-sm font-medium text-foreground">Council Configuration</h4>
        <p className="text-[10px] text-muted-foreground">Configure multi-agent collaboration</p>
      </div>
    </div>

    {/* Council Objective */}
    <div>
      <label className="text-xs font-medium text-muted-foreground uppercase tracking-wide mb-1.5 block">
        Council Objective
      </label>
      <Textarea
        value={node.councilConfig?.objective || ""}
        onChange={(e) => onUpdate({
          councilConfig: { ...node.councilConfig, objective: e.target.value }
        })}
        placeholder="What should this group of agents decide? e.g., 'Choose best follow-up strategy for this lead'"
        className="h-20 text-sm bg-secondary border-border resize-none"
      />
    </div>

    {/* Participating Agents */}
    <div>
      <div className="flex items-center justify-between mb-1.5">
        <label className="text-xs font-medium text-muted-foreground uppercase tracking-wide">
          Participating Agents
        </label>
        <span className="text-[10px] text-amber-400">
          {node.councilConfig?.participatingAgents?.length || 0} selected
        </span>
      </div>
      <div className="space-y-2">
        {[
          { id: "analyst", name: "Research Analyst", role: "Data analysis & insights", style: "analytical" },
          { id: "validator", name: "Data Validator", role: "Quality & accuracy", style: "cautious" },
          { id: "compliance", name: "Compliance Reviewer", role: "Risk & policy", style: "cautious" },
          { id: "content", name: "Content Writer", role: "Communication", style: "creative" },
          { id: "sales", name: "Sales Strategist", role: "Revenue & engagement", style: "fast" },
          { id: "finance", name: "Finance Reviewer", role: "Cost & ROI", style: "analytical" },
          { id: "support", name: "Customer Support", role: "Customer satisfaction", style: "cautious" },
          { id: "legal", name: "Legal/Risk Reviewer", role: "Compliance & risk", style: "cautious" },
        ].map((agent) => {
          const isSelected = node.councilConfig?.participatingAgents?.some(a => a.id === agent.id) || false
          return (
            <label 
              key={agent.id} 
              className={cn(
                "flex items-center gap-3 p-2.5 rounded-lg border cursor-pointer transition-all",
                isSelected 
                  ? "border-amber-500/50 bg-amber-500/10" 
                  : "border-border bg-secondary/30 hover:bg-secondary/50"
              )}
            >
              <input
                type="checkbox"
                checked={isSelected}
                onChange={(e) => {
                  const current = node.councilConfig?.participatingAgents || []
                  const updated = e.target.checked
                    ? [...current, { 
                        id: agent.id, 
                        name: agent.name, 
                        role: agent.role, 
                        expertise: agent.role,
                        confidenceStyle: agent.style as "cautious" | "fast" | "analytical" | "creative"
                      }]
                    : current.filter(a => a.id !== agent.id)
                  onUpdate({ councilConfig: { ...node.councilConfig, participatingAgents: updated } })
                }}
                className="rounded border-border"
              />
              <div className="flex-1">
                <div className="flex items-center gap-2">
                  <span className="text-sm font-medium text-foreground">{agent.name}</span>
                  <Badge variant="outline" className="text-[9px] py-0 h-4">
                    {agent.style}
                  </Badge>
                </div>
                <span className="text-xs text-muted-foreground">{agent.role}</span>
              </div>
            </label>
          )
        })}
      </div>
    </div>

    {/* Debate Mode */}
    <div>
      <label className="text-xs font-medium text-muted-foreground uppercase tracking-wide mb-1.5 block">
        Debate Mode
      </label>
      <div className="grid grid-cols-2 gap-2">
        {([
          { id: "consensus", label: "Consensus Required", desc: "All must agree" },
          { id: "majority", label: "Majority Vote", desc: "Most votes wins" },
          { id: "lead-decides", label: "Lead Agent Decides", desc: "One agent leads" },
          { id: "human-approval", label: "Human Approval", desc: "User must confirm" },
        ] as const).map((mode) => (
          <button
            key={mode.id}
            onClick={() => onUpdate({
              councilConfig: { ...node.councilConfig, debateMode: mode.id }
            })}
            className={cn(
              "p-2.5 rounded-lg border text-left transition-all",
              node.councilConfig?.debateMode === mode.id
                ? "border-amber-500 bg-amber-500/10"
                : "border-border bg-secondary/50 hover:border-muted-foreground"
            )}
          >
            <div className="text-xs font-medium text-foreground">{mode.label}</div>
            <div className="text-[10px] text-muted-foreground">{mode.desc}</div>
          </button>
        ))}
      </div>
    </div>

    {/* Evidence Sources */}
    <div>
      <label className="text-xs font-medium text-muted-foreground uppercase tracking-wide mb-1.5 block">
        Evidence Sources
      </label>
      <div className="space-y-1.5">
        {["Previous node outputs", "CRM data", "Billing data", "Support tickets", "Knowledge base", "Documents"].map((source) => (
          <label key={source} className="flex items-center gap-2 p-2 rounded-md bg-secondary/30 hover:bg-secondary/50 cursor-pointer">
            <input
              type="checkbox"
              checked={node.councilConfig?.evidenceSources?.includes(source) || false}
              onChange={(e) => {
                const current = node.councilConfig?.evidenceSources || []
                const updated = e.target.checked
                  ? [...current, source]
                  : current.filter(s => s !== source)
                onUpdate({ councilConfig: { ...node.councilConfig, evidenceSources: updated } })
              }}
              className="rounded border-border"
            />
            <span className="text-sm text-foreground">{source}</span>
          </label>
        ))}
      </div>
    </div>

    {/* Output Options */}
    <div>
      <div className="flex items-center justify-between mb-1.5">
        <label className="text-xs font-medium text-muted-foreground uppercase tracking-wide">
          Output Options
        </label>
        <button
          onClick={() => {
            const options = node.councilConfig?.outputOptions || []
            const newOption = {
              id: `option-${Date.now()}`,
              label: `Option ${options.length + 1}`,
            }
            onUpdate({ councilConfig: { ...node.councilConfig, outputOptions: [...options, newOption] } })
          }}
          className="flex items-center gap-1 text-[10px] text-amber-400 hover:text-amber-300"
        >
          <Plus className="h-3 w-3" />
          Add option
        </button>
      </div>
      <div className="space-y-2">
        {(node.councilConfig?.outputOptions || []).map((option, idx) => (
          <div key={option.id} className="flex items-center gap-2 p-2 rounded-lg bg-secondary/30 border border-border">
            <div className={cn(
              "h-2 w-2 rounded-full",
              idx === 0 && "bg-emerald-500",
              idx === 1 && "bg-red-500",
              idx === 2 && "bg-amber-500",
              idx >= 3 && "bg-muted-foreground"
            )} />
            <Input
              value={option.label}
              onChange={(e) => {
                const updated = [...(node.councilConfig?.outputOptions || [])]
                updated[idx] = { ...option, label: e.target.value }
                onUpdate({ councilConfig: { ...node.councilConfig, outputOptions: updated } })
              }}
              className="h-7 text-xs bg-secondary border-border flex-1"
              placeholder="Option label"
            />
            <button
              onClick={() => {
                const updated = (node.councilConfig?.outputOptions || []).filter(o => o.id !== option.id)
                onUpdate({ councilConfig: { ...node.councilConfig, outputOptions: updated } })
              }}
              className="p-1 text-muted-foreground hover:text-destructive"
            >
              <X className="h-3 w-3" />
            </button>
          </div>
        ))}
      </div>
    </div>

    {/* Final Decision Display (if available) */}
    {node.councilConfig?.finalDecision && (
      <div className="p-3 rounded-lg bg-emerald-500/5 border border-emerald-500/20">
        <div className="flex items-center gap-2 mb-2">
          <CheckCircle className="h-4 w-4 text-emerald-400" />
          <span className="text-xs font-medium text-emerald-400">Council Decision</span>
          <span className="ml-auto text-[10px] text-emerald-400 bg-emerald-500/20 px-1.5 py-0.5 rounded">
            {node.councilConfig.finalDecision.confidence}% confidence
          </span>
        </div>
        <div className="text-sm font-medium text-foreground mb-1">
          {node.councilConfig.finalDecision.recommendation}
        </div>
        <p className="text-xs text-muted-foreground mb-2">
          Method: {node.councilConfig.finalDecision.method?.replace("-", " ")}
        </p>
        {node.councilConfig.finalDecision.keyReasons && (
          <div className="space-y-1">
            <p className="text-[10px] text-muted-foreground uppercase tracking-wide">Key reasons:</p>
            {node.councilConfig.finalDecision.keyReasons.map((reason, i) => (
              <div key={i} className="flex items-center gap-1.5 text-xs text-foreground">
                <CheckCircle className="h-3 w-3 text-emerald-400" />
                {reason}
              </div>
            ))}
          </div>
        )}
        {node.councilConfig.finalDecision.dissentingOpinions && node.councilConfig.finalDecision.dissentingOpinions.length > 0 && (
          <div className="mt-2 pt-2 border-t border-amber-500/20">
            <p className="text-[10px] text-amber-400 uppercase tracking-wide mb-1">Dissenting opinions:</p>
            {node.councilConfig.finalDecision.dissentingOpinions.map((dissent, i) => (
              <div key={i} className="text-xs text-muted-foreground">
                {dissent.opinion}
              </div>
            ))}
          </div>
        )}
      </div>
    )}
  </div>
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
        </div>

        {/* Footer actions */}
        <div className="mt-6 pt-4 border-t border-border flex items-center gap-2">
          <Button variant="outline" size="sm" className="h-9 gap-1.5 flex-1">
            <Copy className="h-3.5 w-3.5" />
            Duplicate
          </Button>
          <Button variant="outline" size="sm" className="h-9 gap-1.5 text-destructive hover:text-destructive flex-1">
            <Trash2 className="h-3.5 w-3.5" />
            Delete
          </Button>
        </div>
      </SheetContent>
    </Sheet>
  )
}

export default function WorkflowBuilderPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params)
  const [nodes, setNodes] = useState<WorkflowNode[]>(initialNodes)
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null)
  const [activeLibrary, setActiveLibrary] = useState<"agents" | "connectors" | "sources" | "tools" | "decisions">("agents")
  const [searchQuery, setSearchQuery] = useState("")
  const [libraryPanelOpen, setLibraryPanelOpen] = useState(false)
  const libraryPanelTimerRef = useRef<NodeJS.Timeout | null>(null)
  
  // Dialog state for connect/disconnect confirmation
  const [dialogOpen, setDialogOpen] = useState(false)
  const [dialogType, setDialogType] = useState<"connect" | "disconnect">("connect")
  const [pendingConnection, setPendingConnection] = useState<{ from: string; to: string } | null>(null)
  
  // Drag-to-connect state
  const [isDraggingConnection, setIsDraggingConnection] = useState(false)
  const [dragSourceNodeId, setDragSourceNodeId] = useState<string | null>(null)
  const [dragMousePosition, setDragMousePosition] = useState<{ x: number; y: number } | null>(null)
  const canvasRef = useRef<HTMLDivElement>(null)
  
  // Settings dialog state
  const [settingsOpen, setSettingsOpen] = useState(false)
  
  // Debate view dialog state
  const [debateDialogOpen, setDebateDialogOpen] = useState(false)
  const [debateNodeId, setDebateNodeId] = useState<string | null>(null)
  const debateNode = nodes.find(n => n.id === debateNodeId) || null
  
  // Saving and running state
  const [isSaving, setIsSaving] = useState(false)
  const [isRunning, setIsRunning] = useState(false)
  
  // Execution mode state
  const [isExecuting, setIsExecuting] = useState(false)
  const [executionStep, setExecutionStep] = useState(0)
  const [executionStartTime, setExecutionStartTime] = useState<number | null>(null)
  const [executionElapsed, setExecutionElapsed] = useState(0)
  const [executionStatus, setExecutionStatus] = useState<"idle" | "running" | "completed" | "error">("idle")
  const [executionError, setExecutionError] = useState<string | null>(null)
  
  // Elapsed time timer
  useEffect(() => {
    let interval: NodeJS.Timeout
    if (isExecuting && executionStartTime) {
      interval = setInterval(() => {
        setExecutionElapsed(Math.floor((Date.now() - executionStartTime) / 1000))
      }, 100)
    }
    return () => clearInterval(interval)
  }, [isExecuting, executionStartTime])
  
  // Smart suggestions state (moved after addNode definition)
  const [dismissedSuggestions, setDismissedSuggestions] = useState<string[]>([])

  // Get selected node object
  const selectedNode = nodes.find((n) => n.id === selectedNodeId) || null

  // Check if two nodes are connected (in either direction)
  const areNodesConnected = useCallback((nodeA: string, nodeB: string) => {
    const nodeAData = nodes.find((n) => n.id === nodeA)
    const nodeBData = nodes.find((n) => n.id === nodeB)
    if (!nodeAData || !nodeBData) return false
    return nodeAData.connections.includes(nodeB) || nodeBData.connections.includes(nodeA)
  }, [nodes])

  // Handle node click - implements the click-to-select-then-click-to-connect pattern
// Simplified click - just select/deselect nodes
  const handleNodeClick = useCallback((clickedNodeId: string) => {
    if (selectedNodeId === clickedNodeId) {
      setSelectedNodeId(null)
    } else {
      setSelectedNodeId(clickedNodeId)
    }
  }, [selectedNodeId])

  // Handle connection handle drag start
  const handleConnectionDragStart = useCallback((nodeId: string, e: React.MouseEvent) => {
    e.stopPropagation()
    setIsDraggingConnection(true)
    setDragSourceNodeId(nodeId)
    const rect = canvasRef.current?.getBoundingClientRect()
    if (rect) {
      setDragMousePosition({ x: e.clientX - rect.left, y: e.clientY - rect.top })
    }
  }, [])

  // Handle mouse move during connection drag
  const handleConnectionDragMove = useCallback((e: React.MouseEvent) => {
    if (!isDraggingConnection) return
    const rect = canvasRef.current?.getBoundingClientRect()
    if (rect) {
      setDragMousePosition({ x: e.clientX - rect.left, y: e.clientY - rect.top })
    }
  }, [isDraggingConnection])

  // Handle drop on node to create connection
  const handleConnectionDrop = useCallback((targetNodeId: string) => {
    if (!isDraggingConnection || !dragSourceNodeId || dragSourceNodeId === targetNodeId) {
      setIsDraggingConnection(false)
      setDragSourceNodeId(null)
      setDragMousePosition(null)
      return
    }
    
    // Check if already connected
    const alreadyConnected = areNodesConnected(dragSourceNodeId, targetNodeId)
    if (!alreadyConnected) {
      // Create connection
      setNodes((prev) =>
        prev.map((n) =>
          n.id === dragSourceNodeId
            ? { ...n, connections: [...n.connections, targetNodeId] }
            : n
        )
      )
      toast.success("Nodes connected", {
        description: `Connection created successfully`
      })
    }
    
    setIsDraggingConnection(false)
    setDragSourceNodeId(null)
    setDragMousePosition(null)
  }, [isDraggingConnection, dragSourceNodeId, areNodesConnected])

  // Handle mouse up anywhere to cancel drag
  const handleConnectionDragEnd = useCallback(() => {
    if (isDraggingConnection) {
      setIsDraggingConnection(false)
      setDragSourceNodeId(null)
      setDragMousePosition(null)
    }
  }, [isDraggingConnection])

  // Handle dialog confirmation
  const handleDialogConfirm = useCallback(() => {
    if (!pendingConnection) return
    
    const { from, to } = pendingConnection
    
    if (dialogType === "connect") {
      // Create connection from -> to
      setNodes((prev) =>
        prev.map((n) =>
          n.id === from
            ? { ...n, connections: [...n.connections, to] }
            : n
        )
      )
      toast.success("Nodes connected")
    } else {
      // Remove connection (check both directions)
      setNodes((prev) =>
        prev.map((n) => {
          if (n.id === from && n.connections.includes(to)) {
            return { ...n, connections: n.connections.filter((c) => c !== to) }
          }
          if (n.id === to && n.connections.includes(from)) {
            return { ...n, connections: n.connections.filter((c) => c !== from) }
          }
          return n
        })
      )
      toast.success("Nodes disconnected")
    }
    
    // Clear state
    setDialogOpen(false)
    setPendingConnection(null)
    setSelectedNodeId(null)
  }, [dialogType, pendingConnection])

  // Handle dialog cancel
  const handleDialogCancel = useCallback(() => {
    setDialogOpen(false)
    setPendingConnection(null)
    setSelectedNodeId(null)
    toast("Connection cancelled")
  }, [])

  // Handle canvas click - deselect
  const handleCanvasClick = useCallback(() => {
    setSelectedNodeId(null)
  }, [])

  // Handle showing node details (double-click)
  const handleShowDetails = useCallback((nodeId: string) => {
    setSelectedNodeId(nodeId)
  }, [])

  const handleDeleteNode = useCallback((nodeId: string) => {
    // Also remove any connections to this node
    setNodes((prev) => {
      const updated = prev
        .filter((n) => n.id !== nodeId)
        .map((n) => ({
          ...n,
          connections: n.connections.filter((c) => c !== nodeId),
        }))
      return updated
    })
    if (selectedNodeId === nodeId) {
      setSelectedNodeId(null)
    }
  }, [selectedNodeId])

  const handleUpdateNode = useCallback((updates: Partial<WorkflowNode>) => {
    if (!selectedNodeId) return
    setNodes((prev) =>
      prev.map((n) => (n.id === selectedNodeId ? { ...n, ...updates } : n))
    )
  }, [selectedNodeId])

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
    setSelectedNodeId(newNode.id)
  }, [])

  // Generate smart suggestions based on current workflow state
  const smartSuggestions = useMemo(() => {
    const suggestions: Array<{ id: string; text: string; action: () => void; icon: typeof Lightbulb }> = []
    
    // Check if workflow has approval step
    const hasApproval = nodes.some(n => n.type === "approval")
    if (!hasApproval && nodes.length >= 2) {
      suggestions.push({
        id: "add-approval",
        text: "Add approval step before production?",
        action: () => addNode("approval", "Quality Gate", "Review before production"),
        icon: Shield,
      })
    }
    
    // Check if there's a Slack notification
    const hasSlackNotification = nodes.some(n => n.vendor === "slack")
    if (!hasSlackNotification && nodes.length >= 3) {
      suggestions.push({
        id: "add-slack",
        text: "Add Slack notification step?",
        action: () => {
          const newNode: WorkflowNode = {
            id: `node-${Date.now()}`,
            type: "connector",
            name: "Slack Notification",
            description: "Send completion notification",
            config: {},
            position: { x: Math.max(...nodes.map(n => n.position.x)) + 100, y: 200 },
            connections: [],
            vendor: "slack",
            selectedAction: "send_message",
          }
          setNodes((prev) => [...prev, newNode])
        },
        icon: Zap,
      })
    }
    
// Check if there's data validation
  const hasValidation = nodes.some(n => n.name.toLowerCase().includes("valid") || n.type === "agent")
  if (!hasValidation && nodes.length >= 1 && nodes.some(n => n.type === "source" || n.type === "connector")) {
  suggestions.push({
  id: "add-validation",
  text: "Add data validation step?",
  action: () => {
    const newNode: WorkflowNode = {
      id: `node-${Date.now()}`,
      type: "agent",
      name: "Data Validator",
      description: "Validate and clean data",
      config: {},
      position: { x: Math.max(...nodes.map(n => n.position.x)) + 100, y: 150 },
      connections: [],
    }
    setNodes((prev) => [...prev, newNode])
    setSelectedNodeId(newNode.id)
  },
  icon: Bot,
  })
  }
  
  // Check if there's a decision node after data processing
  const hasDecision = nodes.some(n => n.type === "decision")
  const hasDataProcessing = nodes.some(n => n.type === "agent" || n.type === "task")
  if (!hasDecision && hasDataProcessing && nodes.length >= 2) {
  suggestions.push({
  id: "add-decision",
  text: "Add decision node for dynamic routing?",
  action: () => {
    const newNode: WorkflowNode = {
      id: `node-${Date.now()}`,
      type: "decision",
      name: "Route Decision",
      description: "AI-powered routing based on data",
      config: {},
      position: { x: Math.max(...nodes.map(n => n.position.x)) + 100, y: 150 },
      connections: [],
      decisionConfig: {
        objective: "Route to the appropriate next step based on data",
        strategy: "ai-assisted",
      },
      outputPaths: [
        { id: "path-a", label: "Primary Path" },
        { id: "path-b", label: "Alternate Path" },
      ],
    }
    setNodes((prev) => [...prev, newNode])
    setSelectedNodeId(newNode.id)
  },
  icon: GitBranch,
  })
  }

  // Suggest adding branching after lead scoring or data enrichment
  const hasLeadScoring = nodes.some(n => 
    n.name.toLowerCase().includes("score") || 
    n.name.toLowerCase().includes("lead") ||
    n.name.toLowerCase().includes("enrich")
  )
  if (hasLeadScoring && !hasDecision) {
  suggestions.push({
  id: "add-lead-routing",
  text: "Add lead quality routing?",
  action: () => {
    const newNode: WorkflowNode = {
      id: `node-${Date.now()}`,
      type: "decision",
      name: "Evaluate Lead Quality",
      description: "Route leads based on quality score",
      config: {},
      position: { x: Math.max(...nodes.map(n => n.position.x)) + 100, y: 150 },
      connections: [],
      decisionConfig: {
        objective: "Determine if lead is high value based on engagement and profile",
        strategy: "ai-assisted",
        inputSources: ["Previous node outputs", "CRM data"],
      },
      outputPaths: [
        { id: "high", label: "High Value", condition: "score > 80" },
        { id: "medium", label: "Medium Value", condition: "score 40-80" },
        { id: "low", label: "Low Value", condition: "score < 40", isDefault: true },
      ],
    }
    setNodes((prev) => [...prev, newNode])
    setSelectedNodeId(newNode.id)
  },
  icon: Target,
  })
  }
  
  return suggestions.filter(s => !dismissedSuggestions.includes(s.id))
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [nodes, dismissedSuggestions])
  
  const dismissSuggestion = useCallback((id: string) => {
    setDismissedSuggestions(prev => [...prev, id])
  }, [])

  // Handle save workflow
  const handleSave = useCallback(() => {
    setIsSaving(true)
    // Simulate save operation
    setTimeout(() => {
      setIsSaving(false)
      toast.success("Workflow saved successfully")
    }, 800)
  }, [])

  // Handle run workflow with execution simulation
const handleRun = useCallback(async () => {
  setIsRunning(true)
  setIsExecuting(true)
  setExecutionStatus("running")
  setExecutionStartTime(Date.now())
  setExecutionStep(0)
  setExecutionError(null)
  
  // Get ordered nodes for execution (simple ordering by x position)
  const orderedNodes = [...nodes].sort((a, b) => a.position.x - b.position.x)
  
  // Simulate execution through each node
  for (let i = 0; i < orderedNodes.length; i++) {
    const currentNode = orderedNodes[i]
    setExecutionStep(i + 1)
    
    // Special handling for decision nodes - show evaluating state
    if (currentNode.type === "decision") {
      // Set to evaluating state with pulsing animation
      setNodes((prev) =>
        prev.map((n) =>
          n.id === currentNode.id
            ? { ...n, state: "evaluating" as NodeState }
            : n
        )
      )
      
      // Longer evaluation time for decision nodes (1.5-3 seconds)
      const evaluationTime = 1500 + Math.random() * 1500
      await new Promise((resolve) => setTimeout(resolve, evaluationTime))
      
      // Simulate AI decision reasoning
      const outputPaths = currentNode.outputPaths || [
        { id: "default", label: "Default Path" }
      ]
      const randomPathIndex = Math.floor(Math.random() * outputPaths.length)
      const chosenPath = outputPaths[randomPathIndex]
      const confidence = Math.floor(75 + Math.random() * 25) // 75-100%
      
      // Generate reasoning
      const reasoning: DecisionConfig["reasoning"] = {
        summary: `Based on analysis of input data, the AI determined that "${chosenPath.label}" is the optimal path forward.`,
        confidence,
        chosenPath: chosenPath.label,
        factors: [
          "High engagement signals detected",
          "Data quality score above threshold",
          "Pattern matches historical successes"
        ],
        rejectedPaths: outputPaths
          .filter(p => p.id !== chosenPath.id)
          .map(p => p.label)
      }
      
      // Update node with reasoning and set to success
      setNodes((prev) =>
        prev.map((n) =>
          n.id === currentNode.id
            ? { 
                ...n, 
                state: "success" as NodeState,
                decisionConfig: {
                  ...n.decisionConfig,
                  reasoning
                }
              }
            : n
        )
      )
      
      // Show decision toast
      toast.success(`AI Decision: ${chosenPath.label}`, {
        description: `${currentNode.name} completed with ${confidence}% confidence`,
        icon: <Brain className="h-4 w-4 text-emerald-400" />,
      })
      
    } else {
      // Standard node execution
      setNodes((prev) =>
        prev.map((n) =>
          n.id === currentNode.id
            ? { ...n, state: "running" as NodeState }
            : n
        )
      )
      
      // Simulate processing time (0.8-2 seconds per node)
      const processingTime = 800 + Math.random() * 1200
      await new Promise((resolve) => setTimeout(resolve, processingTime))
      
      // Simulate random error (5% chance) for demo - skip for now
      // const hasError = Math.random() < 0.05
      const hasError = false
      
      if (hasError) {
        setNodes((prev) =>
          prev.map((n) =>
            n.id === currentNode.id
              ? { ...n, state: "error" as NodeState }
              : n
          )
        )
        setExecutionStatus("error")
        setExecutionError(`${currentNode.name} failed: API key invalid`)
        setIsRunning(false)
        toast.error("Workflow execution failed", {
          description: `Error at step: ${currentNode.name}`,
        })
        return
      }
      
      // Set current node to success
      setNodes((prev) =>
        prev.map((n) =>
          n.id === currentNode.id
            ? { ...n, state: "success" as NodeState }
            : n
        )
      )
    }
  }
  
  // Execution completed
  setIsExecuting(false)
  setIsRunning(false)
  setExecutionStatus("completed")
  
  toast.success("Workflow completed successfully", {
    description: `Executed ${orderedNodes.length} steps in ${((Date.now() - (executionStartTime || Date.now())) / 1000).toFixed(1)}s`,
  })
  }, [nodes, executionStartTime])
  
  // Reset execution state
  const handleResetExecution = useCallback(() => {
    setIsExecuting(false)
    setExecutionStep(0)
    setExecutionStatus("idle")
    setExecutionError(null)
    setExecutionElapsed(0)
    setExecutionStartTime(null)
    
// Reset all node states to idle and clear decision reasoning
  setNodes((prev) =>
  prev.map((n) => ({ 
    ...n, 
    state: "idle" as NodeState,
    decisionConfig: n.decisionConfig ? { ...n.decisionConfig, reasoning: undefined } : undefined
  }))
    )
  }, [])

  // Handle opening the library panel with auto-close
  const openLibraryPanel = useCallback(() => {
    // Clear any existing timer
    if (libraryPanelTimerRef.current) {
      clearTimeout(libraryPanelTimerRef.current)
    }
    setLibraryPanelOpen(true)
    // Auto-close after 5 seconds (giving user time to browse)
    libraryPanelTimerRef.current = setTimeout(() => {
      setLibraryPanelOpen(false)
    }, 5000)
  }, [])

  const closeLibraryPanel = useCallback(() => {
    if (libraryPanelTimerRef.current) {
      clearTimeout(libraryPanelTimerRef.current)
    }
    setLibraryPanelOpen(false)
  }, [])

  // Keep panel open while hovering/interacting
  const resetPanelTimer = useCallback(() => {
    if (libraryPanelTimerRef.current) {
      clearTimeout(libraryPanelTimerRef.current)
    }
    libraryPanelTimerRef.current = setTimeout(() => {
      setLibraryPanelOpen(false)
    }, 5000)
  }, [])

  // Cleanup timer on unmount
  useEffect(() => {
    return () => {
      if (libraryPanelTimerRef.current) {
        clearTimeout(libraryPanelTimerRef.current)
      }
    }
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
                href="/workflows"
                className="text-muted-foreground hover:text-foreground transition-colors shrink-0"
                title="Back to Workflows"
              >
                <ArrowLeft className="h-4 w-4" />
              </Link>
              <DropdownMenu>
                <DropdownMenuTrigger asChild>
                  <button 
                    className="hidden sm:flex items-center gap-2 min-w-0 hover:text-foreground transition-colors group"
                    title="Switch workflow"
                  >
                    <Workflow className="h-4 w-4 text-muted-foreground shrink-0" />
                    <span className="text-sm font-medium text-foreground truncate">{workflowMeta.name}</span>
                    <ChevronDown className="h-3 w-3 text-muted-foreground group-hover:text-foreground transition-colors" />
                  </button>
                </DropdownMenuTrigger>
                <DropdownMenuContent align="start" className="w-64">
                  <div className="px-2 py-1.5 text-xs font-medium text-muted-foreground">Recent Workflows</div>
                  <DropdownMenuSeparator />
                  <DropdownMenuItem asChild>
                    <Link href="/workflows/1/builder" className="flex items-center gap-2">
                      <Workflow className="h-3.5 w-3.5 text-muted-foreground" />
                      <span className="truncate">sync-customers</span>
                      <EnvironmentBadge environment="production" className="ml-auto scale-90" />
                    </Link>
                  </DropdownMenuItem>
                  <DropdownMenuItem asChild>
                    <Link href="/workflows/2/builder" className="flex items-center gap-2">
                      <Workflow className="h-3.5 w-3.5 text-muted-foreground" />
                      <span className="truncate">etl-main-pipeline</span>
                      <EnvironmentBadge environment="production" className="ml-auto scale-90" />
                    </Link>
                  </DropdownMenuItem>
                  <DropdownMenuItem asChild>
                    <Link href="/workflows/3/builder" className="flex items-center gap-2">
                      <Workflow className="h-3.5 w-3.5 text-muted-foreground" />
                      <span className="truncate">invoice-processing</span>
                      <EnvironmentBadge environment="staging" className="ml-auto scale-90" />
                    </Link>
                  </DropdownMenuItem>
                  <DropdownMenuSeparator />
                  <DropdownMenuItem asChild>
                    <Link href="/workflows" className="flex items-center gap-2 text-info">
                      <LayoutGrid className="h-3.5 w-3.5" />
                      <span>View All Workflows</span>
                    </Link>
                  </DropdownMenuItem>
                  <DropdownMenuItem asChild>
                    <Link href="/workflows/new/builder" className="flex items-center gap-2 text-success">
                      <Plus className="h-3.5 w-3.5" />
                      <span>Create New Workflow</span>
                    </Link>
                  </DropdownMenuItem>
                </DropdownMenuContent>
              </DropdownMenu>
              <StatusBadge variant="muted">{workflowMeta.status}</StatusBadge>
              <EnvironmentBadge environment={workflowMeta.environment} />
              <span className="hidden md:inline text-xs text-muted-foreground">{workflowMeta.version}</span>
            </div>
            <div className="flex items-center gap-1 md:gap-2 shrink-0">
              <Button 
                variant="outline" 
                size="sm" 
                className="h-8 gap-2"
                onClick={() => setSettingsOpen(true)}
              >
                <Settings className="h-3.5 w-3.5" />
                <span className="hidden sm:inline">Settings</span>
              </Button>
              <Button 
                variant="outline" 
                size="sm" 
                className="h-8 gap-2"
                onClick={handleSave}
                disabled={isSaving}
              >
                {isSaving ? (
                  <Loader2 className="h-3.5 w-3.5 animate-spin" />
                ) : (
                  <Save className="h-3.5 w-3.5" />
                )}
                <span className="hidden sm:inline">{isSaving ? "Saving..." : "Save"}</span>
              </Button>
              <Button 
                size="sm" 
                className="h-8 gap-2"
                onClick={handleRun}
                disabled={isRunning}
              >
                {isRunning ? (
                  <Loader2 className="h-3.5 w-3.5 animate-spin" />
                ) : (
                  <Play className="h-3.5 w-3.5" />
                )}
                <span className="hidden sm:inline">{isRunning ? "Starting..." : "Run"}</span>
              </Button>
            </div>
          </div>
        </div>

        {/* Main content */}
        <div className="flex flex-1 min-h-0 flex-col md:flex-row">
          {/* Left library panel - conditionally shown */}
          {libraryPanelOpen && (
          <div 
            className="w-full md:w-64 border-b md:border-b-0 md:border-r border-border bg-card flex flex-col max-h-[40vh] md:max-h-none overflow-hidden relative animate-in slide-in-from-left-2 duration-200"
            onMouseEnter={resetPanelTimer}
            onClick={resetPanelTimer}
          >
            {/* Close button */}
            <button
              onClick={closeLibraryPanel}
              className="absolute top-2 right-2 z-10 p-1 rounded-md hover:bg-secondary text-muted-foreground hover:text-foreground transition-colors"
            >
              <X className="h-4 w-4" />
            </button>
{/* Library tabs */}
  <div className="flex border-b border-border overflow-x-auto">
  {(["agents", "connectors", "sources", "tools", "decisions"] as const).map((tab) => (
  <button
  key={tab}
  onClick={() => setActiveLibrary(tab)}
  className={`px-2.5 py-2.5 text-[10px] font-medium uppercase tracking-wide transition-colors whitespace-nowrap shrink-0 ${
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

              {activeLibrary === "decisions" && (
                <div className="space-y-0.5">
                  {/* Pre-built decision templates */}
                  <LibraryItem
                    name="Evaluate Lead Quality"
                    description="Score and route leads"
                    icon={Target}
                    onAdd={() => {
                      const newNode: WorkflowNode = {
                        id: `node-${Date.now()}`,
                        type: "decision",
                        name: "Evaluate Lead Quality",
                        description: "Determine if lead is high value",
                        config: {},
                        position: { x: 300 + Math.random() * 100, y: 150 + Math.random() * 100 },
                        connections: [],
                        decisionConfig: {
                          objective: "Determine if lead is high value based on engagement and profile",
                          strategy: "ai-assisted",
                          inputSources: ["CRM data", "Engagement metrics"],
                        },
                        outputPaths: [
                          { id: "high", label: "High Value", condition: "score > 80" },
                          { id: "medium", label: "Medium Value", condition: "score 40-80" },
                          { id: "low", label: "Low Value", condition: "score < 40", isDefault: true },
                        ],
                      }
                      setNodes((prev) => [...prev, newNode])
                      setSelectedNodeId(newNode.id)
                    }}
                  />
                  <LibraryItem
                    name="Choose Next Action"
                    description="AI selects best action"
                    icon={Brain}
                    onAdd={() => {
                      const newNode: WorkflowNode = {
                        id: `node-${Date.now()}`,
                        type: "decision",
                        name: "Choose Next Action",
                        description: "Select the best next step based on context",
                        config: {},
                        position: { x: 300 + Math.random() * 100, y: 150 + Math.random() * 100 },
                        connections: [],
                        decisionConfig: {
                          objective: "Choose the best next action based on available data",
                          strategy: "ai-assisted",
                        },
                        outputPaths: [
                          { id: "action-a", label: "Action A" },
                          { id: "action-b", label: "Action B" },
                          { id: "fallback", label: "Fallback", isDefault: true },
                        ],
                      }
                      setNodes((prev) => [...prev, newNode])
                      setSelectedNodeId(newNode.id)
                    }}
                  />
                  <LibraryItem
                    name="Route Customer Request"
                    description="Direct to right team"
                    icon={GitBranch}
                    onAdd={() => {
                      const newNode: WorkflowNode = {
                        id: `node-${Date.now()}`,
                        type: "decision",
                        name: "Route Customer Request",
                        description: "Route to appropriate team based on request type",
                        config: {},
                        position: { x: 300 + Math.random() * 100, y: 150 + Math.random() * 100 },
                        connections: [],
                        decisionConfig: {
                          objective: "Determine the correct team to handle this request",
                          strategy: "hybrid",
                        },
                        outputPaths: [
                          { id: "sales", label: "Sales Team" },
                          { id: "support", label: "Support Team" },
                          { id: "billing", label: "Billing Team" },
                          { id: "other", label: "General", isDefault: true },
                        ],
                      }
                      setNodes((prev) => [...prev, newNode])
                      setSelectedNodeId(newNode.id)
                    }}
                  />
                  <LibraryItem
                    name="Select Best Channel"
                    description="Choose communication channel"
                    icon={Gauge}
                    onAdd={() => {
                      const newNode: WorkflowNode = {
                        id: `node-${Date.now()}`,
                        type: "decision",
                        name: "Select Best Channel",
                        description: "Choose optimal outreach channel",
                        config: {},
                        position: { x: 300 + Math.random() * 100, y: 150 + Math.random() * 100 },
                        connections: [],
                        decisionConfig: {
                          objective: "Select the best channel for customer outreach",
                          strategy: "rule-based",
                        },
                        outputPaths: [
                          { id: "email", label: "Email" },
                          { id: "sms", label: "SMS" },
                          { id: "call", label: "Phone Call" },
                        ],
                      }
                      setNodes((prev) => [...prev, newNode])
                      setSelectedNodeId(newNode.id)
                    }}
                  />
                  
                  {/* Custom decision node */}
                  <button
                    className="w-full flex items-center gap-2 p-2 mt-2 rounded-md border border-dashed border-violet-500/30 hover:border-violet-500/50 hover:bg-violet-500/5 transition-colors"
                    onClick={() => {
                      const newNode: WorkflowNode = {
                        id: `node-${Date.now()}`,
                        type: "decision",
                        name: "Custom Decision",
                        description: "Configure custom branching logic",
                        config: {},
                        position: { x: 300 + Math.random() * 100, y: 150 + Math.random() * 100 },
                        connections: [],
                        decisionConfig: {
                          strategy: "ai-assisted",
                        },
                        outputPaths: [
                          { id: "path-a", label: "Path A" },
                          { id: "path-b", label: "Path B" },
                        ],
                      }
                      setNodes((prev) => [...prev, newNode])
                      setSelectedNodeId(newNode.id)
                    }}
                  >
                    <GitBranch className="h-3.5 w-3.5 text-violet-400" />
                    <span className="text-xs text-violet-400">Create custom decision</span>
                  </button>
                </div>
              )}
            </div>

{/* Quick add */}
  <div className="border-t border-border p-3">
  <p className="text-[10px] text-muted-foreground uppercase tracking-wide mb-2">Quick Add</p>
  <div className="grid grid-cols-5 gap-1">
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
  onClick={() => {
  const newNode: WorkflowNode = {
  id: `node-${Date.now()}`,
  type: "decision",
  name: "New Decision",
  description: "Configure branching logic",
  config: {},
  position: { x: 300 + Math.random() * 100, y: 150 + Math.random() * 100 },
  connections: [],
  decisionConfig: { strategy: "ai-assisted" },
  outputPaths: [
  { id: "path-a", label: "Path A" },
  { id: "path-b", label: "Path B" },
  ],
  }
  setNodes((prev) => [...prev, newNode])
  setSelectedNodeId(newNode.id)
  }}
  className="flex flex-col items-center gap-1 p-2 rounded-md hover:bg-violet-500/10 transition-colors"
  >
  <GitBranch className="h-4 w-4 text-violet-400" />
  <span className="text-[10px] text-violet-400">Decision</span>
  </button>
<button
  onClick={() => {
    try {
      const defaultAgents = [
        { id: "agent-1", name: "Analyst", role: "Research Analyst", expertise: "Data analysis", confidenceStyle: "analytical" as const },
        { id: "agent-2", name: "Reviewer", role: "Compliance Reviewer", expertise: "Risk assessment", confidenceStyle: "cautious" as const },
        { id: "agent-3", name: "Strategist", role: "Sales Strategist", expertise: "Customer engagement", confidenceStyle: "fast" as const },
      ]
      const newNode: WorkflowNode = {
        id: `node-${Date.now()}`,
        type: "council",
        name: "Agent Council",
        description: "Multi-agent decision making",
        config: {},
        position: { x: 300 + Math.random() * 100, y: 150 + Math.random() * 100 },
        connections: [],
        councilConfig: {
          participatingAgents: defaultAgents,
          debateMode: "consensus",
          outputOptions: [
            { id: "approve", label: "Approve" },
            { id: "reject", label: "Reject" },
            { id: "escalate", label: "Escalate to Human" },
          ],
        },
      }
      setNodes((prev) => [...prev, newNode])
      setSelectedNodeId(newNode.id)
    } catch (err) {
      console.error("[v0] Error creating council node:", err)
    }
  }}
  className="flex flex-col items-center gap-1 p-2 rounded-md hover:bg-amber-500/10 transition-colors"
>
  <Users className="h-4 w-4 text-amber-400" />
  <span className="text-[10px] text-amber-400">Council</span>
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
          )}

          {/* Canvas */}
          <div 
            ref={canvasRef}
            className={cn(
              "flex-1 relative overflow-hidden bg-background",
              isDraggingConnection && "cursor-crosshair"
            )}
            onClick={handleCanvasClick}
            onMouseMove={handleConnectionDragMove}
            onMouseUp={handleConnectionDragEnd}
            onMouseLeave={handleConnectionDragEnd}
          >
            {/* Enhanced grid background with subtle gradient */}
            <div className="absolute inset-0">
              {/* Radial gradient overlay for depth */}
              <div 
                className="absolute inset-0 pointer-events-none"
                style={{
                  background: "radial-gradient(ellipse at center, transparent 0%, hsl(var(--background)) 70%)",
                }}
              />
              {/* Subtle animated gradient orbs */}
              <div 
                className="absolute top-1/4 right-1/4 w-96 h-96 rounded-full pointer-events-none opacity-[0.03]"
                style={{
                  background: "radial-gradient(circle, hsl(var(--info)) 0%, transparent 70%)",
                  animation: "pulse 8s ease-in-out infinite",
                }}
              />
              <div 
                className="absolute bottom-1/4 left-1/4 w-72 h-72 rounded-full pointer-events-none opacity-[0.02]"
                style={{
                  background: "radial-gradient(circle, hsl(var(--success)) 0%, transparent 70%)",
                  animation: "pulse 10s ease-in-out infinite 2s",
                }}
              />
              {/* Grid pattern */}
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
            </div>

            {/* Connections - render as one SVG for all lines */}
            <svg 
              className="absolute inset-0" 
              style={{ overflow: "visible", width: "100%", height: "100%", zIndex: 5, pointerEvents: "none" }}
            >
              {/* SVG Definitions for gradients and filters */}
              <defs>
                <linearGradient id="connectionGradient" x1="0%" y1="0%" x2="100%" y2="0%">
                  <stop offset="0%" stopColor="#3b82f6" stopOpacity="0.5" />
                  <stop offset="50%" stopColor="#06b6d4" stopOpacity="1" />
                  <stop offset="100%" stopColor="#3b82f6" stopOpacity="0.5" />
                </linearGradient>
                <linearGradient id="connectionGradientActive" x1="0%" y1="0%" x2="100%" y2="0%">
                  <stop offset="0%" stopColor="#10b981" stopOpacity="0.7" />
                  <stop offset="50%" stopColor="#06b6d4" stopOpacity="1" />
                  <stop offset="100%" stopColor="#10b981" stopOpacity="0.7" />
                </linearGradient>
                {/* Decision node gradients - violet themed */}
                <linearGradient id="decisionGradient" x1="0%" y1="0%" x2="100%" y2="0%">
                  <stop offset="0%" stopColor="#8b5cf6" stopOpacity="0.6" />
                  <stop offset="50%" stopColor="#a78bfa" stopOpacity="1" />
                  <stop offset="100%" stopColor="#8b5cf6" stopOpacity="0.6" />
                </linearGradient>
                <linearGradient id="decisionGradientActive" x1="0%" y1="0%" x2="100%" y2="0%">
                  <stop offset="0%" stopColor="#10b981" stopOpacity="0.8" />
                  <stop offset="50%" stopColor="#22c55e" stopOpacity="1" />
                  <stop offset="100%" stopColor="#10b981" stopOpacity="0.8" />
                </linearGradient>
                <linearGradient id="decisionGradientDimmed" x1="0%" y1="0%" x2="100%" y2="0%">
                  <stop offset="0%" stopColor="#6b7280" stopOpacity="0.2" />
                  <stop offset="50%" stopColor="#6b7280" stopOpacity="0.3" />
                  <stop offset="100%" stopColor="#6b7280" stopOpacity="0.2" />
                </linearGradient>
                <filter id="glow" x="-50%" y="-50%" width="200%" height="200%">
                  <feGaussianBlur stdDeviation="3" result="coloredBlur"/>
                  <feMerge>
                    <feMergeNode in="coloredBlur"/>
                    <feMergeNode in="SourceGraphic"/>
                  </feMerge>
                </filter>
                <filter id="decisionGlow" x="-50%" y="-50%" width="200%" height="200%">
                  <feGaussianBlur stdDeviation="4" result="coloredBlur"/>
                  <feMerge>
                    <feMergeNode in="coloredBlur"/>
                    <feMergeNode in="SourceGraphic"/>
                  </feMerge>
                </filter>
              </defs>
              
              {connections.map((conn, i) => {
                const nodeWidth = conn.from.type === "decision" ? 128 : 224
                const nodeHeight = conn.from.type === "decision" ? 128 : 80
                const toNodeWidth = conn.to.type === "decision" ? 128 : 224
                const toNodeHeight = conn.to.type === "decision" ? 128 : 80
                
                // Check if this is a decision node connection
                const isDecisionSource = conn.from.type === "decision"
                const isDecisionTarget = conn.to.type === "decision"
                
                // For decision nodes, find the path index to offset connections
                const pathIndex = isDecisionSource 
                  ? conn.from.connections.indexOf(conn.to.id)
                  : 0
                const totalPaths = isDecisionSource 
                  ? conn.from.connections.length 
                  : 1
                
                // Check if this path is the "chosen" path based on reasoning
                const chosenPathId = conn.from.decisionConfig?.reasoning?.chosenPath
                const outputPath = conn.from.outputPaths?.find(p => 
                  conn.from.connections[conn.from.outputPaths?.findIndex(op => op.id === p.id) || 0] === conn.to.id
                )
                const isChosenPath = chosenPathId && outputPath?.id === chosenPathId
                const isDimmedPath = isDecisionSource && chosenPathId && !isChosenPath
                
                // Calculate center positions
                const fromCenterX = conn.from.position.x + nodeWidth / 2
                const fromCenterY = conn.from.position.y + nodeHeight / 2
                const toCenterX = conn.to.position.x + toNodeWidth / 2
                const toCenterY = conn.to.position.y + toNodeHeight / 2
                
                // Determine connection direction based on relative position
                const dx = toCenterX - fromCenterX
                const dy = toCenterY - fromCenterY
                const isHorizontal = Math.abs(dx) > Math.abs(dy)
                
                // Get state-based coloring
                const fromState = conn.from.state || "idle"
                const isActive = fromState === "running" || fromState === "success" || fromState === "evaluating"
                const isEvaluating = fromState === "evaluating"
                
                // Use decision-specific colors for decision nodes
                let strokeColor: string
                let dotColor: string
                if (isDimmedPath) {
                  strokeColor = "url(#decisionGradientDimmed)"
                  dotColor = "#6b7280"
                } else if (isDecisionSource) {
                  strokeColor = isChosenPath ? "url(#decisionGradientActive)" : "url(#decisionGradient)"
                  dotColor = isChosenPath ? "#10b981" : "#8b5cf6"
                } else {
                  strokeColor = isActive ? "url(#connectionGradientActive)" : "url(#connectionGradient)"
                  dotColor = isActive ? "#10b981" : "#3b82f6"
                }
                const animationDuration = isActive ? "1.5s" : "3s"
                
                let fromX: number, fromY: number, toX: number, toY: number
                let pathD: string
                
                // For decision nodes, offset multiple output paths
                const pathYOffset = isDecisionSource && totalPaths > 1 
                  ? (pathIndex - (totalPaths - 1) / 2) * 25 
                  : 0
                
                if (isHorizontal) {
                  // Horizontal connection (left-right)
                  if (dx > 0) {
                    // To is to the right of From
                    if (isDecisionSource) {
                      // Decision node uses diamond shape - exit from right corner
                      fromX = conn.from.position.x + nodeWidth + 10
                      fromY = conn.from.position.y + nodeHeight / 2 + pathYOffset
                    } else {
                      fromX = conn.from.position.x + nodeWidth + 7
                      fromY = conn.from.position.y + nodeHeight / 2
                    }
                    if (isDecisionTarget) {
                      toX = conn.to.position.x - 10
                      toY = conn.to.position.y + toNodeHeight / 2
                    } else {
                      toX = conn.to.position.x - 7
                      toY = conn.to.position.y + toNodeHeight / 2
                    }
                  } else {
                    // To is to the left of From
                    if (isDecisionSource) {
                      fromX = conn.from.position.x - 10
                      fromY = conn.from.position.y + nodeHeight / 2 + pathYOffset
                    } else {
                      fromX = conn.from.position.x - 7
                      fromY = conn.from.position.y + nodeHeight / 2
                    }
                    if (isDecisionTarget) {
                      toX = conn.to.position.x + toNodeWidth + 10
                      toY = conn.to.position.y + toNodeHeight / 2
                    } else {
                      toX = conn.to.position.x + toNodeWidth + 7
                      toY = conn.to.position.y + toNodeHeight / 2
                    }
                  }
                  const controlOffset = Math.max(Math.abs(toX - fromX) * 0.4, 50)
                  const ctrl1X = dx > 0 ? fromX + controlOffset : fromX - controlOffset
                  const ctrl2X = dx > 0 ? toX - controlOffset : toX + controlOffset
                  pathD = `M ${fromX} ${fromY} C ${ctrl1X} ${fromY}, ${ctrl2X} ${toY}, ${toX} ${toY}`
                } else {
                  // Vertical connection (top-bottom)
                  if (dy > 0) {
                    // To is below From
                    if (isDecisionSource) {
                      fromX = conn.from.position.x + nodeWidth / 2 + pathYOffset
                      fromY = conn.from.position.y + nodeHeight + 10
                    } else {
                      fromX = conn.from.position.x + nodeWidth / 2
                      fromY = conn.from.position.y + nodeHeight + 7
                    }
                    if (isDecisionTarget) {
                      toX = conn.to.position.x + toNodeWidth / 2
                      toY = conn.to.position.y - 10
                    } else {
                      toX = conn.to.position.x + toNodeWidth / 2
                      toY = conn.to.position.y - 7
                    }
                  } else {
                    // To is above From
                    if (isDecisionSource) {
                      fromX = conn.from.position.x + nodeWidth / 2 + pathYOffset
                      fromY = conn.from.position.y - 10
                    } else {
                      fromX = conn.from.position.x + nodeWidth / 2
                      fromY = conn.from.position.y - 7
                    }
                    if (isDecisionTarget) {
                      toX = conn.to.position.x + toNodeWidth / 2
                      toY = conn.to.position.y + toNodeHeight + 10
                    } else {
                      toX = conn.to.position.x + toNodeWidth / 2
                      toY = conn.to.position.y + toNodeHeight + 7
                    }
                  }
                  const controlOffset = Math.max(Math.abs(toY - fromY) * 0.4, 50)
                  const ctrl1Y = dy > 0 ? fromY + controlOffset : fromY - controlOffset
                  const ctrl2Y = dy > 0 ? toY - controlOffset : toY + controlOffset
                  pathD = `M ${fromX} ${fromY} C ${fromX} ${ctrl1Y}, ${toX} ${ctrl2Y}, ${toX} ${toY}`
                }
                
                // Calculate label position (midpoint of the curve)
                const labelX = (fromX + toX) / 2
                const labelY = (fromY + toY) / 2 - 12
                
                // For decision nodes, show the path label instead of data label
                const decisionPathLabel = isDecisionSource && conn.from.outputPaths?.[pathIndex]?.label
                const dataLabel = decisionPathLabel || conn.from.dataLabel
                
                // Handler to disconnect this connection
                const handleDisconnect = () => {
                  setNodes(prev => prev.map(n => 
                    n.id === conn.from.id 
                      ? { ...n, connections: n.connections.filter(c => c !== conn.to.id) }
                      : n
                  ))
                  toast.info("Connection removed", {
                    description: `Disconnected ${conn.from.name} from ${conn.to.name}`
                  })
                }

                return (
                  <g key={i} className={cn("connection-group group", isDimmedPath && "opacity-30")}>
{/* Invisible wider hit area for clicking */}
  <path
  d={pathD}
  stroke="transparent"
  strokeWidth="20"
  fill="none"
  style={{ cursor: "pointer", pointerEvents: "all" }}
  onClick={(e) => {
    e.stopPropagation()
    handleDisconnect()
  }}
  />
                    {/* Glow effect - wider and softer */}
                    <path
                      d={pathD}
                      stroke={dotColor}
                      strokeWidth={isDecisionSource && isChosenPath ? "10" : "8"}
                      fill="none"
                      opacity={isChosenPath ? "0.3" : isActive ? "0.2" : "0.1"}
                      filter={isChosenPath ? "url(#decisionGlow)" : isActive ? "url(#glow)" : undefined}
                    />
                    {/* Main line with gradient */}
                    <path
                      d={pathD}
                      stroke={strokeColor}
                      strokeWidth={isDecisionSource ? "3" : "2.5"}
                      fill="none"
                      opacity={isDimmedPath ? "0.4" : "0.9"}
                      strokeLinecap="round"
                      strokeDasharray={isEvaluating && isDecisionSource ? "8 4" : undefined}
                    >
                      {isEvaluating && isDecisionSource && (
                        <animate
                          attributeName="stroke-dashoffset"
                          from="0"
                          to="24"
                          dur="0.8s"
                          repeatCount="indefinite"
                        />
                      )}
                    </path>
                    {/* Multiple animated data flow particles - skip for dimmed paths */}
                    {!isDimmedPath && (
                      <>
                        <circle r={isChosenPath ? "5" : "4"} fill={dotColor} filter={isDecisionSource ? "url(#decisionGlow)" : "url(#glow)"}>
                          <animateMotion dur={animationDuration} repeatCount="indefinite" path={pathD} />
                        </circle>
                        <circle r="2.5" fill={dotColor} opacity="0.6">
                          <animateMotion dur={animationDuration} repeatCount="indefinite" path={pathD} begin="0.5s" />
                        </circle>
                        <circle r="2" fill={dotColor} opacity="0.4">
                          <animateMotion dur={animationDuration} repeatCount="indefinite" path={pathD} begin="1s" />
                        </circle>
                      </>
                    )}
                    {/* Connection endpoint dots with glow */}
                    <circle cx={fromX} cy={fromY} r={isDecisionSource ? "6" : "5"} fill={dotColor} opacity={isDimmedPath ? "0.4" : "0.9"} />
                    <circle cx={toX} cy={toY} r="5" fill={dotColor} opacity={isDimmedPath ? "0.4" : "0.9"} />
                    <circle cx={fromX} cy={fromY} r="3" fill="white" opacity={isDimmedPath ? "0.2" : "0.5"} />
                    <circle cx={toX} cy={toY} r="3" fill="white" opacity={isDimmedPath ? "0.2" : "0.5"} />
                    
{/* Disconnect button - always visible and clickable */}
  <g 
    className="disconnect-btn" 
    style={{ pointerEvents: "all", cursor: "pointer" }}
    onClick={(e) => {
      e.stopPropagation()
      e.preventDefault()
      handleDisconnect()
    }}
  >
    {/* Visible button background */}
    <circle
      cx={labelX}
      cy={labelY}
      r="12"
      fill="#374151"
      stroke="#6b7280"
      strokeWidth="2"
    />
    {/* X icon */}
    <line 
      x1={labelX - 4} 
      y1={labelY - 4} 
      x2={labelX + 4} 
      y2={labelY + 4} 
      stroke="#d1d5db" 
      strokeWidth="2.5" 
      strokeLinecap="round" 
    />
    <line 
      x1={labelX + 4} 
      y1={labelY - 4} 
      x2={labelX - 4} 
      y2={labelY + 4} 
      stroke="#d1d5db" 
      strokeWidth="2.5" 
      strokeLinecap="round" 
    />
  </g>

  {/* Data label on connection - shown below disconnect button on hover */}
  {dataLabel && (
  <g className="data-label opacity-0 group-hover:opacity-100 transition-opacity duration-200">
  <rect
  x={labelX - 50}
  y={labelY + 18}
  width={100}
  height={20}
  rx="6"
  fill="#1a1a2e"
  stroke={isDecisionSource ? "#8b5cf6" : "#3b82f6"}
  strokeWidth="1"
  opacity="0.95"
  />
  <text
  x={labelX}
  y={labelY + 32}
  textAnchor="middle"
  fill={isDecisionSource ? "#a78bfa" : "#60a5fa"}
  fontSize="10"
  fontFamily="ui-monospace, monospace"
  fontWeight="500"
  >
  {dataLabel.length > 12 ? dataLabel.slice(0, 12) + "..." : dataLabel}
  </text>
  </g>
  )}
                  </g>
                )
              })}
            </svg>

{/* Nodes */}
  {nodes.map((node) => (
  node.type === "decision" ? (
  <DecisionNode
  key={node.id}
  node={node}
  isSelected={selectedNodeId === node.id}
  isConnectTarget={isDraggingConnection && dragSourceNodeId !== node.id}
  onSelect={() => handleNodeClick(node.id)}
  onDelete={() => handleDeleteNode(node.id)}
  onDrag={(position) => handleDragNode(node.id, position)}
  onShowDetails={() => handleShowDetails(node.id)}
  onConnectionDragStart={handleConnectionDragStart}
  onConnectionDrop={handleConnectionDrop}
  isDraggingConnection={isDraggingConnection}
  />
  ) : node.type === "council" ? (
  <AgentCouncilNode
  key={node.id}
  node={node}
  isSelected={selectedNodeId === node.id}
  isConnectTarget={isDraggingConnection && dragSourceNodeId !== node.id}
  onSelect={() => handleNodeClick(node.id)}
  onDelete={() => handleDeleteNode(node.id)}
  onDrag={(position) => handleDragNode(node.id, position)}
  onShowDetails={() => {
    // For council nodes, show both config panel AND debate view button
    handleShowDetails(node.id)
  }}
  onViewDebate={() => {
    setDebateNodeId(node.id)
    setDebateDialogOpen(true)
  }}
  onConnectionDragStart={handleConnectionDragStart}
  onConnectionDrop={handleConnectionDrop}
  isDraggingConnection={isDraggingConnection}
  />
  ) : (
  <CanvasNode
      key={node.id}
      node={node}
      isSelected={selectedNodeId === node.id}
      isConnectTarget={isDraggingConnection && dragSourceNodeId !== node.id}
      onSelect={() => handleNodeClick(node.id)}
      onDelete={() => handleDeleteNode(node.id)}
      onDrag={(position) => handleDragNode(node.id, position)}
      onShowDetails={() => handleShowDetails(node.id)}
      onConnectionDragStart={handleConnectionDragStart}
      onConnectionDrop={handleConnectionDrop}
      isDraggingConnection={isDraggingConnection}
    />
  )
  ))}

{/* Drag-to-connect line visual */}
  {isDraggingConnection && dragSourceNodeId && dragMousePosition && (() => {
    const sourceNode = nodes.find(n => n.id === dragSourceNodeId)
    if (!sourceNode) return null
    const nodeWidth = sourceNode.type === "decision" ? 128 : 224
    const nodeHeight = sourceNode.type === "decision" ? 128 : 80
    const startX = sourceNode.position.x + nodeWidth / 2
    const startY = sourceNode.position.y + nodeHeight / 2
    return (
      <svg 
        className="absolute inset-0 pointer-events-none" 
        style={{ overflow: "visible", width: "100%", height: "100%", zIndex: 100 }}
      >
        <defs>
          <linearGradient id="dragLineGradient" x1="0%" y1="0%" x2="100%" y2="0%">
            <stop offset="0%" stopColor="#10b981" stopOpacity="1" />
            <stop offset="100%" stopColor="#34d399" stopOpacity="0.5" />
          </linearGradient>
        </defs>
        {/* Glow effect */}
        <line
          x1={startX}
          y1={startY}
          x2={dragMousePosition.x}
          y2={dragMousePosition.y}
          stroke="#10b981"
          strokeWidth="6"
          opacity="0.3"
          strokeLinecap="round"
        />
        {/* Main line */}
        <line
          x1={startX}
          y1={startY}
          x2={dragMousePosition.x}
          y2={dragMousePosition.y}
          stroke="url(#dragLineGradient)"
          strokeWidth="3"
          strokeLinecap="round"
          strokeDasharray="8 4"
        >
          <animate
            attributeName="stroke-dashoffset"
            from="0"
            to="-24"
            dur="0.5s"
            repeatCount="indefinite"
          />
        </line>
        {/* Start point */}
        <circle cx={startX} cy={startY} r="6" fill="#10b981" />
        <circle cx={startX} cy={startY} r="3" fill="white" opacity="0.6" />
        {/* End point (cursor) */}
        <circle cx={dragMousePosition.x} cy={dragMousePosition.y} r="8" fill="#10b981" opacity="0.3" />
        <circle cx={dragMousePosition.x} cy={dragMousePosition.y} r="4" fill="#10b981" />
      </svg>
    )
  })()}

  {/* Drag-to-connect indicator */}
  {isDraggingConnection && (
  <div className="absolute top-4 left-1/2 -translate-x-1/2 flex items-center gap-2 bg-emerald-500/10 border border-emerald-500/30 text-emerald-400 rounded-full px-4 py-2 shadow-lg z-50">
  <div className="h-2 w-2 rounded-full bg-emerald-400 animate-pulse" />
  <span className="text-sm font-medium">Drop on a node to connect</span>
  </div>
  )}

            {/* Execution HUD - floating overlay */}
            {(isExecuting || executionStatus !== "idle") && (
              <div className="absolute top-4 left-1/2 -translate-x-1/2 z-50">
                <div className={cn(
                  "flex items-center gap-4 px-5 py-3 rounded-xl border shadow-lg backdrop-blur-sm",
                  executionStatus === "running" && "bg-blue-500/10 border-blue-500/30",
                  executionStatus === "completed" && "bg-emerald-500/10 border-emerald-500/30",
                  executionStatus === "error" && "bg-red-500/10 border-red-500/30"
                )}>
                  {/* Status indicator */}
                  <div className="flex items-center gap-2">
                    {executionStatus === "running" && (
                      <>
                        <Loader2 className="h-5 w-5 text-blue-400 animate-spin" />
                        <span className="text-sm font-medium text-blue-400">Running workflow...</span>
                      </>
                    )}
                    {executionStatus === "completed" && (
                      <>
                        <CheckCircle className="h-5 w-5 text-emerald-400" />
                        <span className="text-sm font-medium text-emerald-400">Completed</span>
                      </>
                    )}
                    {executionStatus === "error" && (
                      <>
                        <AlertTriangle className="h-5 w-5 text-red-400" />
                        <span className="text-sm font-medium text-red-400">Failed</span>
                      </>
                    )}
                  </div>
                  
                  <div className="w-px h-6 bg-border" />
                  
                  {/* Progress */}
                  <div className="flex items-center gap-3">
                    <div className="text-sm text-muted-foreground">
                      Step <span className="font-mono text-foreground">{executionStep}</span>
                      <span className="text-muted-foreground/50">/</span>
                      <span className="font-mono">{nodes.length}</span>
                    </div>
                    
                    {/* Progress bar */}
                    <div className="w-24 h-1.5 rounded-full bg-muted overflow-hidden">
                      <div 
                        className={cn(
                          "h-full rounded-full transition-all duration-300",
                          executionStatus === "running" && "bg-blue-500",
                          executionStatus === "completed" && "bg-emerald-500",
                          executionStatus === "error" && "bg-red-500"
                        )}
                        style={{ width: `${(executionStep / nodes.length) * 100}%` }}
                      />
                    </div>
                  </div>
                  
                  <div className="w-px h-6 bg-border" />
                  
                  {/* Time elapsed */}
                  <div className="flex items-center gap-2 text-sm text-muted-foreground">
                    <Clock className="h-3.5 w-3.5" />
                    <span className="font-mono">{executionElapsed}s</span>
                  </div>
                  
                  {/* Error message */}
                  {executionError && (
                    <>
                      <div className="w-px h-6 bg-border" />
                      <span className="text-xs text-red-400 max-w-[200px] truncate">{executionError}</span>
                    </>
                  )}
                  
                  {/* Close/Reset button */}
                  {executionStatus !== "running" && (
                    <button
                      onClick={handleResetExecution}
                      className="ml-2 p-1 rounded-md hover:bg-secondary/50 text-muted-foreground hover:text-foreground transition-colors"
                    >
                      <X className="h-4 w-4" />
                    </button>
                  )}
                </div>
              </div>
            )}

            {/* Canvas toolbar */}
            <div className="absolute bottom-4 left-1/2 -translate-x-1/2 flex items-center gap-1 bg-card border border-border rounded-lg p-1 shadow-lg">
              <Button 
                variant="ghost" 
                size="sm" 
                className="h-8 w-8 p-0"
                onClick={openLibraryPanel}
                title="Add node"
              >
                <Plus className="h-4 w-4" />
              </Button>
              <div className="w-px h-6 bg-border" />
              <Button variant="ghost" size="sm" className="h-8 px-3 gap-1.5 text-xs">
                <CheckCircle className="h-3.5 w-3.5 text-success" />
                {nodes.length} nodes
              </Button>
              <div className="w-px h-6 bg-border" />
              <Link href={`/workflows/${id}`}>
                <Button variant="ghost" size="sm" className="h-8 px-3 gap-1.5 text-xs">
                  Preview
                  <ChevronRight className="h-3.5 w-3.5" />
                </Button>
              </Link>
            </div>

            {/* Floating add button when library is closed */}
            {!libraryPanelOpen && (
              <Button
                onClick={openLibraryPanel}
                size="sm"
                className="absolute top-4 left-4 h-9 w-9 p-0 rounded-full shadow-lg"
                title="Add node"
              >
                <Plus className="h-4 w-4" />
              </Button>
            )}

            {/* Smart Suggestions - contextual AI-like hints */}
            {smartSuggestions.length > 0 && !isExecuting && !selectedNodeId && (
              <div className="absolute bottom-20 right-4 space-y-2 z-40 max-w-xs">
                {smartSuggestions.slice(0, 2).map((suggestion) => (
                  <div
                    key={suggestion.id}
                    className="group flex items-center gap-3 p-3 rounded-xl bg-card/90 backdrop-blur-sm border border-border shadow-lg hover:shadow-xl hover:border-info/30 transition-all animate-in slide-in-from-right-5 duration-300"
                  >
                    <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-info/10 text-info">
                      <Lightbulb className="h-4 w-4" />
                    </div>
                    <div className="flex-1 min-w-0">
                      <p className="text-sm text-foreground">{suggestion.text}</p>
                    </div>
                    <div className="flex items-center gap-1 shrink-0">
                      <button
                        onClick={() => {
                          suggestion.action()
                          dismissSuggestion(suggestion.id)
                          toast.success("Step added to workflow")
                        }}
                        className="p-1.5 rounded-md bg-info/10 text-info hover:bg-info/20 transition-colors"
                      >
                        <Plus className="h-3.5 w-3.5" />
                      </button>
                      <button
                        onClick={() => dismissSuggestion(suggestion.id)}
                        className="p-1.5 rounded-md text-muted-foreground hover:text-foreground hover:bg-secondary transition-colors"
                      >
                        <X className="h-3.5 w-3.5" />
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Right config panel */}
<ConfigPanel
  node={selectedNode}
  onClose={() => setSelectedNodeId(null)}
  onUpdate={handleUpdateNode}
  />

  {/* Debate View Dialog */}
  <DebateViewDialog
    open={debateDialogOpen}
    onOpenChange={setDebateDialogOpen}
    node={debateNode}
    onAcceptDecision={() => {
      if (debateNode) {
        handleUpdateNode({
          state: "success",
          councilConfig: {
            ...debateNode.councilConfig,
            finalDecision: {
              recommendation: debateNode.councilConfig?.finalDecision?.recommendation ?? "Decision accepted",
              method: debateNode.councilConfig?.finalDecision?.method ?? "consensus",
              confidence: debateNode.councilConfig?.finalDecision?.confidence ?? 100,
              keyReasons: debateNode.councilConfig?.finalDecision?.keyReasons ?? [],
              dissentingOpinions: debateNode.councilConfig?.finalDecision?.dissentingOpinions,
              executedAction: debateNode.councilConfig?.finalDecision?.recommendation
            }
          }
        })
        toast.success("Decision accepted", {
          description: "The council recommendation has been executed"
        })
      }
      setDebateDialogOpen(false)
    }}
    onOverrideDecision={() => {
      toast.info("Override requested", {
        description: "Please select a different action"
      })
    }}
    onRequestMoreEvidence={() => {
      if (debateNode) {
        handleUpdateNode({ state: "debating" })
        toast.info("Requesting more evidence", {
          description: "Agents are gathering additional data..."
        })
      }
    }}
  />
  </div>
  </div>
  
  {/* Connect/Disconnect Confirmation Dialog */}
      <AlertDialog open={dialogOpen} onOpenChange={setDialogOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>
              {dialogType === "connect" ? "Connect these nodes?" : "Disconnect these nodes?"}
            </AlertDialogTitle>
            <AlertDialogDescription>
              {dialogType === "connect"
                ? "This will create a connection between the selected nodes. Data will flow from the first node to the second."
                : "This will remove the connection between these nodes."}
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel onClick={handleDialogCancel}>No</AlertDialogCancel>
            <AlertDialogAction onClick={handleDialogConfirm}>Yes</AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      {/* Settings Dialog */}
      <Dialog open={settingsOpen} onOpenChange={setSettingsOpen}>
        <DialogContent className="sm:max-w-lg">
          <DialogHeader>
            <DialogTitle>Workflow Settings</DialogTitle>
            <DialogDescription>
              Configure settings for this workflow.
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-6 py-4">
            {/* Workflow Name */}
            <div className="space-y-2">
              <Label htmlFor="workflow-name">Workflow Name</Label>
              <Input 
                id="workflow-name" 
                defaultValue={workflowMeta.name}
                placeholder="Enter workflow name"
              />
            </div>

            {/* Description */}
            <div className="space-y-2">
              <Label htmlFor="workflow-description">Description</Label>
              <Textarea 
                id="workflow-description" 
                defaultValue="Automatically syncs customer data from Salesforce"
                placeholder="Enter workflow description"
                rows={3}
              />
            </div>

            {/* Schedule */}
            <div className="space-y-2">
              <Label htmlFor="workflow-schedule">Schedule</Label>
              <Input 
                id="workflow-schedule" 
                defaultValue="Every 15 minutes"
                placeholder="e.g., Every hour, Daily at 9am"
              />
            </div>

            {/* Toggles */}
            <div className="space-y-4">
              <div className="flex items-center justify-between">
                <div className="space-y-0.5">
                  <Label>Enable Notifications</Label>
                  <p className="text-xs text-muted-foreground">Get notified when workflow fails</p>
                </div>
                <Switch defaultChecked />
              </div>
              
              <div className="flex items-center justify-between">
                <div className="space-y-0.5">
                  <Label>Auto-retry on Failure</Label>
                  <p className="text-xs text-muted-foreground">Automatically retry failed steps</p>
                </div>
                <Switch defaultChecked />
              </div>

              <div className="flex items-center justify-between">
                <div className="space-y-0.5">
                  <Label>Require Approval</Label>
                  <p className="text-xs text-muted-foreground">Require manual approval before execution</p>
                </div>
                <Switch />
              </div>
            </div>
          </div>
          <div className="flex justify-end gap-2">
            <Button variant="outline" onClick={() => setSettingsOpen(false)}>
              Cancel
            </Button>
            <Button onClick={() => {
              setSettingsOpen(false)
              toast.success("Settings saved")
            }}>
              Save Settings
            </Button>
          </div>
        </DialogContent>
      </Dialog>
    </AppShell>
  )
}
