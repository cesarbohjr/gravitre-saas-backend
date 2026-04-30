"use client"

import { motion } from "framer-motion"
import { Button } from "@/components/ui/button"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip"
import Link from "next/link"
import { Icon, StatusIcon, type IconName } from "@/lib/icons"
import { AlertTriangle } from "lucide-react"

interface WorkflowNode {
  id: string
  type: "source" | "agent" | "task" | "connector" | "approval"
  name: string
  status?: "success" | "running" | "failed" | "pending"
}

interface ConnectorDependency {
  name: string
  vendor: string
  status: "connected" | "disconnected" | "error"
  lastSync?: string
}

interface WorkflowCardProps {
  id: string
  name: string
  description: string
  status: "active" | "paused" | "draft" | "error"
  environment: "production" | "staging"
  lastRun: string
  successRate: string
  runCount: number
  nodes?: WorkflowNode[]
  isRunning?: boolean
  connectorDependencies?: ConnectorDependency[]
  onClick?: () => void
  onEdit?: () => void
  onViewRuns?: () => void
  onDuplicate?: () => void
  onDelete?: () => void
  onToggleStatus?: () => void
}

const nodeIconMap: Record<string, IconName> = {
  source: "data",
  agent: "agents",
  task: "execution",
  connector: "apps",
  approval: "approvals",
}

const nodeColors: Record<string, string> = {
  source: "bg-emerald-500/15 text-emerald-400 border-emerald-500/25",
  agent: "bg-blue-500/15 text-blue-400 border-blue-500/25",
  task: "bg-amber-500/15 text-amber-400 border-amber-500/25",
  connector: "bg-violet-500/15 text-violet-400 border-violet-500/25",
  approval: "bg-rose-500/15 text-rose-400 border-rose-500/25",
}

const statusConfig = {
  active: { color: "bg-emerald-500", label: "Active", ring: "ring-emerald-500/30" },
  paused: { color: "bg-amber-500", label: "Paused", ring: "ring-amber-500/30" },
  draft: { color: "bg-zinc-500", label: "Draft", ring: "ring-zinc-500/30" },
  error: { color: "bg-red-500", label: "Error", ring: "ring-red-500/30" },
}

// Mini workflow diagram showing node connections
function WorkflowDiagram({ nodes }: { nodes: WorkflowNode[] }) {
  if (!nodes || nodes.length === 0) return null

  return (
    <TooltipProvider delayDuration={200}>
      <div className="flex items-center gap-1 py-3">
        {nodes.map((node, index) => {
          const iconName = nodeIconMap[node.type] || "execution"
          const colors = nodeColors[node.type] || nodeColors.task
          const isLast = index === nodes.length - 1

          return (
            <div key={node.id} className="flex items-center">
              {/* Node */}
              <Tooltip>
                <TooltipTrigger asChild>
                  <motion.div
                    initial={{ scale: 0.8, opacity: 0 }}
                    animate={{ scale: 1, opacity: 1 }}
                    transition={{ delay: index * 0.05 }}
                    className={`
                      relative flex h-8 w-8 items-center justify-center rounded-lg border cursor-help
                      ${colors}
                      ${node.status === "running" ? "animate-pulse" : ""}
                    `}
                  >
                    <Icon name={iconName} size="sm" />
                    
                    {/* Status indicator */}
                    {node.status && (
                      <div className={`
                        absolute -bottom-0.5 -right-0.5 h-2.5 w-2.5 rounded-full border-2 border-card
                        ${node.status === "success" ? "bg-emerald-500" : ""}
                        ${node.status === "running" ? "bg-blue-500 animate-pulse" : ""}
                        ${node.status === "failed" ? "bg-red-500" : ""}
                        ${node.status === "pending" ? "bg-zinc-500" : ""}
                      `} />
                    )}
                  </motion.div>
                </TooltipTrigger>
                <TooltipContent side="top" className="text-xs">
                  <span className="font-medium">{node.name}</span>
                  {node.status && (
                    <span className="ml-1 text-muted-foreground capitalize">({node.status})</span>
                  )}
                </TooltipContent>
              </Tooltip>

              {/* Connector line */}
              {!isLast && (
                <motion.div
                  initial={{ scaleX: 0 }}
                  animate={{ scaleX: 1 }}
                  transition={{ delay: index * 0.05 + 0.1 }}
                  className="relative h-[2px] w-4 bg-border origin-left"
                >
                  <div className="absolute inset-0 bg-gradient-to-r from-blue-500/0 via-blue-500/50 to-blue-500/0 animate-shimmer" />
                </motion.div>
              )}
            </div>
          )
        })}
      </div>
    </TooltipProvider>
  )
}

// Generate mock connector dependencies based on nodes
function getConnectorDependencies(nodes: WorkflowNode[]): ConnectorDependency[] {
  const connectorNodes = nodes.filter(n => n.type === "connector" || n.type === "source")
  const vendorMap: Record<string, ConnectorDependency> = {
    "Salesforce": { name: "Salesforce", vendor: "salesforce", status: "connected", lastSync: "2 min ago" },
    "PostgreSQL": { name: "PostgreSQL", vendor: "postgresql", status: "connected", lastSync: "Just now" },
    "Slack": { name: "Slack", vendor: "slack", status: "connected", lastSync: "5 min ago" },
    "HubSpot": { name: "HubSpot", vendor: "hubspot", status: "disconnected" },
    "Stripe": { name: "Stripe", vendor: "stripe", status: "connected", lastSync: "1 min ago" },
    "SendGrid": { name: "SendGrid", vendor: "sendgrid", status: "connected", lastSync: "10 min ago" },
    "S3 Bucket": { name: "AWS S3", vendor: "aws", status: "connected", lastSync: "Just now" },
    "Snowflake": { name: "Snowflake", vendor: "snowflake", status: "connected", lastSync: "3 min ago" },
    "QuickBooks": { name: "QuickBooks", vendor: "quickbooks", status: "error" },
  }
  
  return connectorNodes
    .map(n => vendorMap[n.name])
    .filter((dep): dep is ConnectorDependency => !!dep)
}

export function WorkflowCard({
  id,
  name,
  description,
  status,
  environment,
  lastRun,
  successRate,
  runCount,
  nodes = [],
  isRunning = false,
  connectorDependencies,
  onClick,
  onEdit,
  onViewRuns,
  onDuplicate,
  onDelete,
  onToggleStatus,
}: WorkflowCardProps) {
  const statusConf = statusConfig[status]
  
  // Use provided dependencies or generate from nodes
  const dependencies = connectorDependencies || getConnectorDependencies(nodes)
  const hasDisconnected = dependencies.some(d => d.status === "disconnected" || d.status === "error")

  return (
    <motion.div
      initial={{ opacity: 0, y: 20, scale: 0.98 }}
      animate={{ opacity: 1, y: 0, scale: 1 }}
      whileHover={{ 
        y: -4, 
        scale: 1.01,
        transition: { duration: 0.15, ease: [0.2, 0, 0, 1] }
      }}
      whileTap={{ scale: 0.99 }}
      transition={{ duration: 0.25, ease: [0.4, 0, 0.2, 1] }}
      className="group relative"
    >
      <Link href={`/workflows/${id}`}>
        <div className={`
          relative rounded-xl border bg-card p-4 transition-all duration-200 cursor-pointer
          hover:border-blue-500/30 hover:shadow-xl hover:shadow-blue-500/10
          ${isRunning ? "border-blue-500/30 shadow-[0_0_25px_rgba(59,130,246,0.15)]" : "border-border hover:shadow-lg hover:shadow-black/5"}
        `}>
          {/* Ambient glow for running workflows */}
          {isRunning && (
            <div className="absolute inset-0 rounded-xl bg-gradient-to-br from-blue-500/[0.03] to-transparent pointer-events-none" />
          )}

          {/* Header */}
          <div className="flex items-start justify-between mb-3">
            <div className="flex items-center gap-3">
              {/* Status indicator */}
              <div className="relative flex h-3 w-3 items-center justify-center">
                <div className={`h-2 w-2 rounded-full ${statusConf.color}`} />
                {status === "active" && (
                  <div className={`absolute inset-0 rounded-full ${statusConf.color} animate-ping opacity-75`} />
                )}
              </div>
              
              <div>
                <h3 className="text-sm font-medium text-foreground group-hover:text-blue-400 transition-colors">
                  {name}
                </h3>
                <p className="text-xs text-muted-foreground mt-0.5 line-clamp-1">
                  {description}
                </p>
              </div>
            </div>

            {/* Environment badge */}
            <div className={`
              flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-medium uppercase tracking-wide
              ${environment === "production" 
                ? "bg-emerald-500/10 text-emerald-400 ring-1 ring-emerald-500/20" 
                : "bg-amber-500/10 text-amber-400 ring-1 ring-amber-500/20"
              }
            `}>
              <Icon 
                name={environment === "production" ? "production" : "staging"} 
                size="xs" 
              />
              {environment === "production" ? "PROD" : "STG"}
            </div>
          </div>

          {/* Workflow diagram */}
          <WorkflowDiagram nodes={nodes} />

          {/* Connector Dependencies Warning */}
          {hasDisconnected && (
            <div className="flex items-center gap-2 px-3 py-2 rounded-lg bg-amber-500/10 border border-amber-500/20 mb-3">
              <AlertTriangle className="h-3.5 w-3.5 text-amber-500 shrink-0" />
              <span className="text-xs text-amber-500">
                Depends on {dependencies.filter(d => d.status !== "connected").map(d => d.name).join(", ")} (disconnected)
              </span>
            </div>
          )}

          {/* Connected Systems Mini-Icons */}
          {dependencies.length > 0 && !hasDisconnected && (
            <div className="flex items-center gap-2 mb-3">
              <span className="text-[10px] text-muted-foreground uppercase tracking-wide">Systems:</span>
              <div className="flex items-center gap-1">
                {dependencies.slice(0, 4).map((dep, i) => (
                  <Tooltip key={i}>
                    <TooltipTrigger asChild>
                      <div className={`
                        flex h-5 w-5 items-center justify-center rounded-md text-[10px] font-medium
                        ${dep.status === "connected" ? "bg-emerald-500/10 text-emerald-400 border border-emerald-500/20" : "bg-amber-500/10 text-amber-400 border border-amber-500/20"}
                      `}>
                        {dep.name.charAt(0)}
                      </div>
                    </TooltipTrigger>
                    <TooltipContent side="top" className="text-xs">
                      <div className="font-medium">{dep.name}</div>
                      {dep.lastSync && <div className="text-muted-foreground">Last sync: {dep.lastSync}</div>}
                    </TooltipContent>
                  </Tooltip>
                ))}
                {dependencies.length > 4 && (
                  <span className="text-[10px] text-muted-foreground">+{dependencies.length - 4}</span>
                )}
              </div>
            </div>
          )}

          {/* Metrics bar */}
          <div className="flex items-center justify-between pt-3 border-t border-border/50">
            <div className="flex items-center gap-4">
              {/* Success rate */}
              <div className="flex items-center gap-1.5">
                <Icon name="chartLine" size="xs" className="text-emerald-400" />
                <span className="text-xs text-muted-foreground">{successRate}</span>
              </div>
              
              {/* Run count */}
              <div className="flex items-center gap-1.5">
                <Icon name="activity" size="xs" className="text-muted-foreground" />
                <span className="text-xs text-muted-foreground">{runCount.toLocaleString()} runs</span>
              </div>
            </div>

            {/* Last run */}
            <div className="flex items-center gap-1.5 text-xs text-muted-foreground">
              <Icon name="pending" size="xs" />
              <span>{lastRun}</span>
            </div>
          </div>
        </div>
      </Link>

      {/* Quick actions - shown on hover */}
      <div className="absolute top-3 right-12 opacity-0 group-hover:opacity-100 transition-opacity flex items-center gap-1">
        <TooltipProvider delayDuration={200}>
          <Tooltip>
            <TooltipTrigger asChild>
              <Button 
                variant="ghost" 
                size="sm" 
                className="h-7 w-7 p-0 bg-card/80 backdrop-blur-sm border border-border hover:bg-secondary hover:border-muted-foreground/50"
                onClick={(e) => {
                  e.preventDefault()
                  e.stopPropagation()
                  onToggleStatus?.()
                }}
              >
                <Icon name={status === "active" ? "pause" : "run"} size="xs" />
              </Button>
            </TooltipTrigger>
            <TooltipContent side="top" className="text-xs">
              {status === "active" ? "Pause" : "Resume"}
            </TooltipContent>
          </Tooltip>
        </TooltipProvider>
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button 
              variant="ghost" 
              size="sm" 
              className="h-7 w-7 p-0 bg-card/80 backdrop-blur-sm border border-border hover:bg-secondary hover:border-muted-foreground/50"
              onClick={(e) => {
                e.preventDefault()
                e.stopPropagation()
              }}
            >
              <Icon name="more" size="xs" />
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end">
            <DropdownMenuItem onClick={(e) => { e.stopPropagation(); onEdit?.(); }} className="gap-2">
              <Icon name="edit" size="sm" />
              Edit
            </DropdownMenuItem>
            <DropdownMenuItem onClick={(e) => { e.stopPropagation(); onViewRuns?.(); }} className="gap-2">
              <Icon name="view" size="sm" />
              View runs
            </DropdownMenuItem>
            <DropdownMenuItem onClick={(e) => { e.stopPropagation(); onDuplicate?.(); }} className="gap-2">
              <Icon name="duplicate" size="sm" />
              Duplicate
            </DropdownMenuItem>
            <DropdownMenuSeparator />
            <DropdownMenuItem 
              className="text-destructive gap-2"
              onClick={(e) => { e.stopPropagation(); onDelete?.(); }}
            >
              <Icon name="delete" size="sm" />
              Delete
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      </div>
    </motion.div>
  )
}

// Grid container for workflow cards
export function WorkflowGrid({ children }: { children: React.ReactNode }) {
  return (
    <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
      {children}
    </div>
  )
}
