"use client"

import { useState } from "react"
import useSWR from "swr"
import { motion, AnimatePresence } from "framer-motion"
import { AppShell } from "@/components/gravitre/app-shell"
import { EnvironmentBadge } from "@/components/gravitre/environment-badge"
import { Button } from "@/components/ui/button"
import { cn } from "@/lib/utils"
import { 
  Check, 
  X, 
  Clock, 
  Shield, 
  User, 
  Workflow, 
  RefreshCw, 
  AlertCircle,
  Sparkles,
  ChevronRight,
  Eye,
  Zap,
  AlertTriangle,
  CheckCircle2,
  XCircle,
  ArrowRight,
  Bot
} from "lucide-react"

const fetcher = (url: string) => fetch(url).then((res) => res.json())

interface Approval {
  id: string
  title: string
  description: string
  type: "workflow" | "connector" | "config" | "access"
  environment: "production" | "staging"
  requestedBy: string
  requestedAt: string
  priority: "high" | "medium" | "low"
  status: "pending" | "approved" | "rejected"
  aiRecommendation?: {
    action: "approve" | "reject" | "review"
    confidence: number
    reason: string
  }
  context: {
    entity: string
    action: string
    impact?: string
  }
}

const fallbackApprovals: Approval[] = [
  {
    id: "apr-001",
    title: "Retry failed sync-customers workflow",
    description: "Request to retry the failed workflow run that encountered a connection timeout",
    type: "workflow",
    environment: "production",
    requestedBy: "AI Operator",
    requestedAt: "5 minutes ago",
    priority: "high",
    status: "pending",
    aiRecommendation: {
      action: "approve",
      confidence: 94,
      reason: "Previous failure was due to transient network issue. Retry is safe.",
    },
    context: {
      entity: "sync-customers-1234",
      action: "Retry workflow execution",
      impact: "Will process 1,247 pending records",
    },
  },
  {
    id: "apr-002",
    title: "Update Salesforce connector credentials",
    description: "OAuth token refresh required due to security policy rotation",
    type: "connector",
    environment: "production",
    requestedBy: "System",
    requestedAt: "15 minutes ago",
    priority: "high",
    status: "pending",
    aiRecommendation: {
      action: "approve",
      confidence: 98,
      reason: "Routine credential rotation. New tokens validated.",
    },
    context: {
      entity: "salesforce-api",
      action: "Update OAuth credentials",
      impact: "3 workflows depend on this connector",
    },
  },
  {
    id: "apr-003",
    title: "Enable new workflow in production",
    description: "Promote invoice-processing workflow from staging to production",
    type: "workflow",
    environment: "production",
    requestedBy: "john.doe@company.com",
    requestedAt: "1 hour ago",
    priority: "medium",
    status: "pending",
    aiRecommendation: {
      action: "review",
      confidence: 72,
      reason: "Workflow passed staging tests but has not been reviewed by ops team.",
    },
    context: {
      entity: "invoice-processing",
      action: "Deploy to production",
      impact: "New workflow, will process incoming invoices",
    },
  },
  {
    id: "apr-004",
    title: "Grant admin access for new team member",
    description: "Request to add Sarah Chen as an admin user",
    type: "access",
    environment: "production",
    requestedBy: "mike.johnson@company.com",
    requestedAt: "2 hours ago",
    priority: "medium",
    status: "pending",
    context: {
      entity: "sarah.chen@company.com",
      action: "Grant admin role",
      impact: "Full system access",
    },
  },
  {
    id: "apr-005",
    title: "Modify data retention policy",
    description: "Change retention period from 90 days to 180 days",
    type: "config",
    environment: "staging",
    requestedBy: "compliance@company.com",
    requestedAt: "3 hours ago",
    priority: "low",
    status: "pending",
    context: {
      entity: "data-retention-policy",
      action: "Update retention period",
      impact: "Affects all data sources",
    },
  },
]

const typeIcons = {
  workflow: Workflow,
  connector: Shield,
  config: AlertTriangle,
  access: User,
}

const priorityConfig = {
  high: { color: "border-l-red-500", bg: "bg-red-500/5", badge: "bg-red-500/10 text-red-400" },
  medium: { color: "border-l-amber-500", bg: "bg-amber-500/5", badge: "bg-amber-500/10 text-amber-400" },
  low: { color: "border-l-zinc-500", bg: "bg-transparent", badge: "bg-zinc-500/10 text-zinc-400" },
}

// Decision Card Component
function DecisionCard({ 
  approval, 
  isSelected,
  onSelect,
  onApprove, 
  onReject 
}: { 
  approval: Approval
  isSelected: boolean
  onSelect: () => void
  onApprove: (id: string) => void
  onReject: (id: string) => void
}) {
  const TypeIcon = typeIcons[approval.type]
  const config = priorityConfig[approval.priority]

  return (
    <motion.div
      layout
      initial={{ opacity: 0, x: -20 }}
      animate={{ opacity: 1, x: 0 }}
      className={cn(
        "relative rounded-lg border-l-4 transition-all cursor-pointer",
        config.color,
        isSelected 
          ? "bg-card border border-primary/30 shadow-lg" 
          : "bg-card/50 border border-border hover:bg-card hover:border-border"
      )}
      onClick={onSelect}
    >
      <div className="p-4">
        {/* Header */}
        <div className="flex items-start gap-3 mb-3">
          <div className={cn(
            "flex h-10 w-10 shrink-0 items-center justify-center rounded-lg",
            approval.priority === "high" ? "bg-red-500/10" : "bg-secondary"
          )}>
            <TypeIcon className={cn(
              "h-5 w-5",
              approval.priority === "high" ? "text-red-400" : "text-muted-foreground"
            )} />
          </div>
          <div className="flex-1 min-w-0">
            <h3 className="text-sm font-medium text-foreground mb-1 line-clamp-1">
              {approval.title}
            </h3>
            <p className="text-xs text-muted-foreground line-clamp-2">
              {approval.description}
            </p>
          </div>
          <ChevronRight className={cn(
            "h-4 w-4 text-muted-foreground transition-transform shrink-0",
            isSelected && "rotate-90"
          )} />
        </div>

        {/* Badges row */}
        <div className="flex items-center gap-2 mb-3 flex-wrap">
          <EnvironmentBadge environment={approval.environment} />
          <span className={cn("px-2 py-0.5 rounded text-[10px] font-medium uppercase", config.badge)}>
            {approval.priority}
          </span>
          <span className="px-2 py-0.5 rounded text-[10px] font-medium bg-secondary text-muted-foreground">
            {approval.type}
          </span>
        </div>

        {/* AI Recommendation - prominent */}
        {approval.aiRecommendation && (
          <div className={cn(
            "rounded-lg p-3 mb-3 border",
            approval.aiRecommendation.action === "approve" && "bg-emerald-500/5 border-emerald-500/20",
            approval.aiRecommendation.action === "reject" && "bg-red-500/5 border-red-500/20",
            approval.aiRecommendation.action === "review" && "bg-amber-500/5 border-amber-500/20"
          )}>
            <div className="flex items-center gap-2 mb-1">
              <Sparkles className={cn(
                "h-3.5 w-3.5",
                approval.aiRecommendation.action === "approve" && "text-emerald-400",
                approval.aiRecommendation.action === "reject" && "text-red-400",
                approval.aiRecommendation.action === "review" && "text-amber-400"
              )} />
              <span className={cn(
                "text-xs font-medium",
                approval.aiRecommendation.action === "approve" && "text-emerald-400",
                approval.aiRecommendation.action === "reject" && "text-red-400",
                approval.aiRecommendation.action === "review" && "text-amber-400"
              )}>
                AI recommends: {approval.aiRecommendation.action}
                <span className="text-muted-foreground font-normal ml-1">
                  ({approval.aiRecommendation.confidence}% confidence)
                </span>
              </span>
            </div>
            <p className="text-[11px] text-muted-foreground">
              {approval.aiRecommendation.reason}
            </p>
          </div>
        )}

        {/* Context */}
        <div className="text-xs text-muted-foreground mb-3">
          <span>Requested by </span>
          <span className="text-foreground">{approval.requestedBy}</span>
          <span className="mx-1">&middot;</span>
          <span>{approval.requestedAt}</span>
        </div>

        {/* Quick Actions */}
        <div className="flex items-center gap-2">
          <Button 
            variant="outline" 
            size="sm" 
            className="h-8 gap-1.5 text-xs flex-1 hover:bg-red-500/10 hover:text-red-400 hover:border-red-500/30"
            onClick={(e) => {
              e.stopPropagation()
              onReject(approval.id)
            }}
          >
            <X className="h-3.5 w-3.5" />
            Reject
          </Button>
          <Button 
            size="sm" 
            className="h-8 gap-1.5 text-xs flex-1"
            onClick={(e) => {
              e.stopPropagation()
              onApprove(approval.id)
            }}
          >
            <Check className="h-3.5 w-3.5" />
            Approve
          </Button>
        </div>
      </div>
    </motion.div>
  )
}

// Detail Panel Component
function DetailPanel({ approval, onApprove, onReject }: { 
  approval: Approval | null
  onApprove: (id: string) => void
  onReject: (id: string) => void
}) {
  if (!approval) {
    return (
      <div className="flex flex-col items-center justify-center h-full text-center p-8">
        <div className="flex h-16 w-16 items-center justify-center rounded-full bg-secondary mb-4">
          <Eye className="h-8 w-8 text-muted-foreground" />
        </div>
        <p className="text-sm text-muted-foreground">Select a request to view details</p>
      </div>
    )
  }

  const TypeIcon = typeIcons[approval.type]
  const config = priorityConfig[approval.priority]

  return (
    <motion.div
      key={approval.id}
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      className="h-full flex flex-col"
    >
      {/* Header */}
      <div className={cn("p-4 sm:p-6 border-b border-border", config.bg)}>
        <div className="flex items-start gap-3 sm:gap-4">
          <div className={cn(
            "flex h-10 w-10 sm:h-12 sm:w-12 shrink-0 items-center justify-center rounded-lg sm:rounded-xl",
            approval.priority === "high" ? "bg-red-500/20" : "bg-secondary"
          )}>
            <TypeIcon className={cn(
              "h-5 w-5 sm:h-6 sm:w-6",
              approval.priority === "high" ? "text-red-400" : "text-muted-foreground"
            )} />
          </div>
          <div className="flex-1 min-w-0">
            <h2 className="text-base sm:text-lg font-semibold text-foreground mb-1">
              {approval.title}
            </h2>
            <p className="text-xs sm:text-sm text-muted-foreground">
              {approval.description}
            </p>
          </div>
        </div>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-auto p-4 sm:p-6 space-y-4 sm:space-y-6">
        {/* AI Recommendation */}
        {approval.aiRecommendation && (
          <div className={cn(
            "rounded-xl p-4 border",
            approval.aiRecommendation.action === "approve" && "bg-emerald-500/5 border-emerald-500/20",
            approval.aiRecommendation.action === "reject" && "bg-red-500/5 border-red-500/20",
            approval.aiRecommendation.action === "review" && "bg-amber-500/5 border-amber-500/20"
          )}>
            <div className="flex items-center gap-3 mb-3">
              <div className={cn(
                "flex h-10 w-10 items-center justify-center rounded-lg",
                approval.aiRecommendation.action === "approve" && "bg-emerald-500/20",
                approval.aiRecommendation.action === "reject" && "bg-red-500/20",
                approval.aiRecommendation.action === "review" && "bg-amber-500/20"
              )}>
                <Bot className={cn(
                  "h-5 w-5",
                  approval.aiRecommendation.action === "approve" && "text-emerald-400",
                  approval.aiRecommendation.action === "reject" && "text-red-400",
                  approval.aiRecommendation.action === "review" && "text-amber-400"
                )} />
              </div>
              <div>
                <p className={cn(
                  "text-sm font-medium",
                  approval.aiRecommendation.action === "approve" && "text-emerald-400",
                  approval.aiRecommendation.action === "reject" && "text-red-400",
                  approval.aiRecommendation.action === "review" && "text-amber-400"
                )}>
                  AI Recommendation: {approval.aiRecommendation.action.charAt(0).toUpperCase() + approval.aiRecommendation.action.slice(1)}
                </p>
                <p className="text-xs text-muted-foreground">
                  {approval.aiRecommendation.confidence}% confidence
                </p>
              </div>
            </div>
            <p className="text-sm text-foreground">
              {approval.aiRecommendation.reason}
            </p>
          </div>
        )}

        {/* Context Details */}
        <div>
          <h3 className="text-xs font-medium text-muted-foreground uppercase tracking-wide mb-3">
            Request Details
          </h3>
          <div className="space-y-3">
            <div className="flex items-center justify-between py-2 border-b border-border/50">
              <span className="text-sm text-muted-foreground">Entity</span>
              <span className="text-sm font-medium text-foreground font-mono">{approval.context.entity}</span>
            </div>
            <div className="flex items-center justify-between py-2 border-b border-border/50">
              <span className="text-sm text-muted-foreground">Action</span>
              <span className="text-sm font-medium text-foreground">{approval.context.action}</span>
            </div>
            {approval.context.impact && (
              <div className="flex items-center justify-between py-2 border-b border-border/50">
                <span className="text-sm text-muted-foreground">Impact</span>
                <span className="text-sm font-medium text-foreground">{approval.context.impact}</span>
              </div>
            )}
            <div className="flex items-center justify-between py-2 border-b border-border/50">
              <span className="text-sm text-muted-foreground">Environment</span>
              <EnvironmentBadge environment={approval.environment} />
            </div>
            <div className="flex items-center justify-between py-2">
              <span className="text-sm text-muted-foreground">Requested by</span>
              <span className="text-sm font-medium text-foreground">{approval.requestedBy}</span>
            </div>
          </div>
        </div>
      </div>

      {/* Footer Actions */}
      <div className="p-6 border-t border-border bg-card/50">
        <div className="flex items-center gap-3">
          <Button 
            variant="outline" 
            size="lg" 
            className="flex-1 gap-2 h-11 hover:bg-red-500/10 hover:text-red-400 hover:border-red-500/30"
            onClick={() => onReject(approval.id)}
          >
            <XCircle className="h-4 w-4" />
            Reject
          </Button>
          <Button 
            size="lg" 
            className="flex-1 gap-2 h-11"
            onClick={() => onApprove(approval.id)}
          >
            <CheckCircle2 className="h-4 w-4" />
            Approve
          </Button>
        </div>
      </div>
    </motion.div>
  )
}

export default function ApprovalsPage() {
  const [selectedId, setSelectedId] = useState<string | null>(null)
  
  const { data, error, isLoading, mutate } = useSWR<{ approvals: Approval[] }>("/api/approvals", fetcher, {
    fallbackData: { approvals: fallbackApprovals },
    revalidateOnFocus: false,
  })

  const approvals = data?.approvals ?? fallbackApprovals
  const pendingApprovals = approvals.filter(a => a.status === "pending")
  const selectedApproval = approvals.find(a => a.id === selectedId) || null

  // Stats
  const highPriorityCount = pendingApprovals.filter(a => a.priority === "high").length
  const aiRecommendedCount = pendingApprovals.filter(a => a.aiRecommendation?.action === "approve").length

  const handleApprove = async (id: string) => {
    await fetch(`/api/approvals/${id}/approve`, { method: "POST" })
    mutate()
    setSelectedId(null)
  }

  const handleReject = async (id: string) => {
    await fetch(`/api/approvals/${id}/reject`, { method: "POST" })
    mutate()
    setSelectedId(null)
  }

  return (
    <AppShell title="Approvals">
      <div className="flex flex-col lg:flex-row h-full">
        {/* Left: Queue */}
        <div className="w-full lg:w-[420px] flex-shrink-0 lg:border-r border-border flex flex-col">
          {/* Header */}
          <div className="flex-shrink-0 p-3 sm:p-4 border-b border-border">
            <div className="flex items-center justify-between mb-3 sm:mb-4">
              <div>
                <h1 className="text-base sm:text-lg font-semibold text-foreground">Decision Queue</h1>
                <p className="text-xs text-muted-foreground mt-0.5">
                  {pendingApprovals.length} pending request{pendingApprovals.length !== 1 ? "s" : ""}
                </p>
              </div>
              <Button 
                variant="outline" 
                size="sm" 
                className="h-9 sm:h-8 w-9 sm:w-auto gap-2" 
                onClick={() => mutate()}
              >
                <RefreshCw className={`h-3.5 w-3.5 ${isLoading ? "animate-spin" : ""}`} />
              </Button>
            </div>

            {/* Quick stats */}
            <div className="flex items-center gap-2 flex-wrap">
              {highPriorityCount > 0 && (
                <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-lg bg-red-500/10 border border-red-500/20">
                  <AlertTriangle className="h-3 w-3 text-red-400" />
                  <span className="text-xs font-medium text-red-400">{highPriorityCount} urgent</span>
                </div>
              )}
              {aiRecommendedCount > 0 && (
                <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-lg bg-emerald-500/10 border border-emerald-500/20">
                  <Sparkles className="h-3 w-3 text-emerald-400" />
                  <span className="text-xs font-medium text-emerald-400">{aiRecommendedCount} AI-approved</span>
                </div>
              )}
            </div>
          </div>

          {/* Error banner */}
          {error && (
            <div className="mx-4 mt-4 flex items-center gap-2 rounded-lg border border-destructive/50 bg-destructive/10 px-3 py-2 text-xs text-destructive">
              <AlertCircle className="h-3.5 w-3.5" />
              Failed to load. Showing cached data.
            </div>
          )}

          {/* Queue list */}
          <div className="flex-1 overflow-auto p-3 sm:p-4 space-y-3">
            <AnimatePresence>
              {pendingApprovals.map((approval) => (
                <DecisionCard
                  key={approval.id}
                  approval={approval}
                  isSelected={selectedId === approval.id}
                  onSelect={() => setSelectedId(approval.id)}
                  onApprove={handleApprove}
                  onReject={handleReject}
                />
              ))}
            </AnimatePresence>

            {pendingApprovals.length === 0 && (
              <div className="flex flex-col items-center justify-center py-12 text-center">
                <div className="flex h-12 w-12 items-center justify-center rounded-full bg-emerald-500/10 mb-3">
                  <CheckCircle2 className="h-6 w-6 text-emerald-400" />
                </div>
                <p className="text-sm font-medium text-foreground">All caught up!</p>
                <p className="text-xs text-muted-foreground mt-1">No pending approvals</p>
              </div>
            )}
          </div>
        </div>

        {/* Right: Detail Panel - Hidden on mobile unless item selected */}
        <div className={`flex-1 bg-card/30 border-t lg:border-t-0 border-border ${!selectedApproval ? 'hidden lg:block' : ''}`}>
          <DetailPanel 
            approval={selectedApproval} 
            onApprove={handleApprove}
            onReject={handleReject}
          />
        </div>
      </div>
    </AppShell>
  )
}
