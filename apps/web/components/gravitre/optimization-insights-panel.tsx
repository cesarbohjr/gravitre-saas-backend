"use client"

import { useState } from "react"
import { motion, AnimatePresence } from "framer-motion"
import {
  TrendingUp,
  TrendingDown,
  AlertTriangle,
  CheckCircle,
  Clock,
  Zap,
  Shield,
  Target,
  ChevronRight,
  ChevronDown,
  Lightbulb,
  BarChart3,
  ArrowRight,
  Sparkles,
  Activity,
  RefreshCw,
  Eye,
  ThumbsUp,
  ThumbsDown,
  HelpCircle,
  X,
  GitBranch,
  FlaskConical,
  History,
} from "lucide-react"
import { cn } from "@/lib/utils"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Progress } from "@/components/ui/progress"
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  ResponsiveContainer,
  Area,
  AreaChart,
} from "recharts"

// Types
interface ScoreDimension {
  name: string
  score: number
  trend: "up" | "down" | "stable"
  icon: typeof Activity
}

interface OptimizationRecommendation {
  id: string
  title: string
  issue: string
  evidence: string[]
  suggestedChange: string
  estimatedImpact: string
  confidence: number
  riskLevel: "low" | "medium" | "high"
  category: "performance" | "reliability" | "cost" | "quality"
  affectedNodes?: string[]
}

interface WorkflowVersion {
  id: string
  version: number
  createdAt: Date
  createdBy: string
  changes: string[]
  healthScore: number
  status: "active" | "testing" | "archived"
}

// Mock data
const mockScoreHistory = [
  { date: "Mon", score: 74 },
  { date: "Tue", score: 76 },
  { date: "Wed", score: 75 },
  { date: "Thu", score: 79 },
  { date: "Fri", score: 82 },
  { date: "Sat", score: 81 },
  { date: "Sun", score: 82 },
]

const mockDimensions: ScoreDimension[] = [
  { name: "Reliability", score: 94, trend: "up", icon: Shield },
  { name: "Speed", score: 78, trend: "up", icon: Zap },
  { name: "Cost Efficiency", score: 85, trend: "stable", icon: TrendingUp },
  { name: "Override Rate", score: 72, trend: "down", icon: RefreshCw },
  { name: "Goal Completion", score: 88, trend: "up", icon: Target },
  { name: "Decision Accuracy", score: 79, trend: "stable", icon: CheckCircle },
]

const mockRecommendations: OptimizationRecommendation[] = [
  {
    id: "opt-1",
    title: "Move Data Validation Earlier",
    issue: "Invalid records are causing downstream HubSpot sync failures in 28% of runs.",
    evidence: [
      "42 failed runs caused by malformed CRM records",
      "Average 2.3 retries per failed sync",
      "Validation errors detected at step 5 of 7",
    ],
    suggestedChange: "Add validation step before CRM enrichment to catch invalid records early.",
    estimatedImpact: "Reduce failed runs by 18-24%",
    confidence: 87,
    riskLevel: "low",
    category: "reliability",
    affectedNodes: ["Data Enrichment", "HubSpot Sync"],
  },
  {
    id: "opt-2",
    title: "Remove Redundant Approval Step",
    issue: "Manager approval adds 2.4 days average delay for low-value leads.",
    evidence: [
      "98% approval rate for leads under $5K",
      "Average wait time: 2.4 days",
      "No rejections in past 60 days for this segment",
    ],
    suggestedChange: "Auto-approve leads under $5K threshold, require approval only for high-value.",
    estimatedImpact: "Reduce processing time by 2+ days",
    confidence: 91,
    riskLevel: "medium",
    category: "performance",
    affectedNodes: ["Manager Approval Gate"],
  },
  {
    id: "opt-3",
    title: "Add Slack Notification on Completion",
    issue: "Sales team missing follow-up windows for qualified leads.",
    evidence: [
      "31% higher conversion when contacted within 10 min",
      "Average current response time: 47 minutes",
      "Slack integration available but unused",
    ],
    suggestedChange: "Add instant Slack notification to sales channel when lead is qualified.",
    estimatedImpact: "Improve follow-up rate by 31%",
    confidence: 78,
    riskLevel: "low",
    category: "quality",
  },
]

const mockVersions: WorkflowVersion[] = [
  {
    id: "v3",
    version: 3,
    createdAt: new Date(Date.now() - 2 * 24 * 60 * 60 * 1000),
    createdBy: "AI Optimization",
    changes: ["Added early validation step", "Optimized connector sequence"],
    healthScore: 82,
    status: "active",
  },
  {
    id: "v2",
    version: 2,
    createdAt: new Date(Date.now() - 7 * 24 * 60 * 60 * 1000),
    createdBy: "John Smith",
    changes: ["Added HubSpot sync", "Configured approval gate"],
    healthScore: 76,
    status: "archived",
  },
  {
    id: "v1",
    version: 1,
    createdAt: new Date(Date.now() - 14 * 24 * 60 * 60 * 1000),
    createdBy: "John Smith",
    changes: ["Initial workflow creation"],
    healthScore: 68,
    status: "archived",
  },
]

// Health Score Ring Component
function HealthScoreRing({ score, size = 120 }: { score: number; size?: number }) {
  const strokeWidth = 8
  const radius = (size - strokeWidth) / 2
  const circumference = radius * 2 * Math.PI
  const offset = circumference - (score / 100) * circumference
  
  const getScoreColor = (s: number) => {
    if (s >= 80) return { stroke: "#10b981", bg: "rgba(16, 185, 129, 0.1)" }
    if (s >= 60) return { stroke: "#f59e0b", bg: "rgba(245, 158, 11, 0.1)" }
    return { stroke: "#ef4444", bg: "rgba(239, 68, 68, 0.1)" }
  }
  
  const colors = getScoreColor(score)
  
  return (
    <div className="relative" style={{ width: size, height: size }}>
      <svg width={size} height={size} className="transform -rotate-90">
        {/* Background ring */}
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          fill="none"
          stroke="currentColor"
          strokeWidth={strokeWidth}
          className="text-secondary"
        />
        {/* Progress ring */}
        <motion.circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          fill="none"
          stroke={colors.stroke}
          strokeWidth={strokeWidth}
          strokeLinecap="round"
          strokeDasharray={circumference}
          initial={{ strokeDashoffset: circumference }}
          animate={{ strokeDashoffset: offset }}
          transition={{ duration: 1, ease: "easeOut" }}
        />
      </svg>
      <div className="absolute inset-0 flex flex-col items-center justify-center">
        <motion.span
          className="text-3xl font-bold text-foreground"
          initial={{ opacity: 0, scale: 0.5 }}
          animate={{ opacity: 1, scale: 1 }}
          transition={{ delay: 0.5 }}
        >
          {score}
        </motion.span>
        <span className="text-xs text-muted-foreground">/ 100</span>
      </div>
    </div>
  )
}

// Recommendation Card Component
function RecommendationCard({
  recommendation,
  onPreview,
  onApply,
  onDismiss,
  onExplain,
}: {
  recommendation: OptimizationRecommendation
  onPreview: () => void
  onApply: () => void
  onDismiss: () => void
  onExplain: () => void
}) {
  const [expanded, setExpanded] = useState(false)
  
  const riskColors = {
    low: "bg-emerald-500/10 text-emerald-400 border-emerald-500/30",
    medium: "bg-amber-500/10 text-amber-400 border-amber-500/30",
    high: "bg-red-500/10 text-red-400 border-red-500/30",
  }
  
  const categoryColors = {
    performance: "text-blue-400",
    reliability: "text-emerald-400",
    cost: "text-violet-400",
    quality: "text-amber-400",
  }
  
  return (
    <motion.div
      layout
      className="p-4 rounded-xl bg-secondary/30 border border-border hover:border-primary/30 transition-colors"
    >
      <div className="flex items-start gap-3">
        <div className={cn(
          "flex h-10 w-10 shrink-0 items-center justify-center rounded-lg",
          "bg-gradient-to-br from-primary/20 to-primary/5 border border-primary/20"
        )}>
          <Lightbulb className="h-5 w-5 text-primary" />
        </div>
        
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-1">
            <h4 className="font-medium text-sm text-foreground">{recommendation.title}</h4>
            <Badge variant="outline" className={cn("text-[10px]", riskColors[recommendation.riskLevel])}>
              {recommendation.riskLevel} risk
            </Badge>
          </div>
          
          <p className="text-xs text-muted-foreground mb-2">{recommendation.issue}</p>
          
          <div className="flex items-center gap-4 text-[10px] text-muted-foreground mb-3">
            <span className="flex items-center gap-1">
              <TrendingUp className={cn("h-3 w-3", categoryColors[recommendation.category])} />
              {recommendation.estimatedImpact}
            </span>
            <span className="flex items-center gap-1">
              <Activity className="h-3 w-3" />
              {recommendation.confidence}% confidence
            </span>
          </div>
          
          <AnimatePresence>
            {expanded && (
              <motion.div
                initial={{ height: 0, opacity: 0 }}
                animate={{ height: "auto", opacity: 1 }}
                exit={{ height: 0, opacity: 0 }}
                className="overflow-hidden"
              >
                <div className="pt-3 border-t border-border space-y-3">
                  <div>
                    <p className="text-[10px] uppercase tracking-wide text-muted-foreground mb-1">Evidence</p>
                    <ul className="space-y-1">
                      {recommendation.evidence.map((item, i) => (
                        <li key={i} className="flex items-start gap-2 text-xs text-foreground">
                          <CheckCircle className="h-3 w-3 text-emerald-400 mt-0.5 shrink-0" />
                          {item}
                        </li>
                      ))}
                    </ul>
                  </div>
                  
                  <div>
                    <p className="text-[10px] uppercase tracking-wide text-muted-foreground mb-1">Suggested Change</p>
                    <p className="text-xs text-foreground">{recommendation.suggestedChange}</p>
                  </div>
                  
                  {recommendation.affectedNodes && (
                    <div>
                      <p className="text-[10px] uppercase tracking-wide text-muted-foreground mb-1">Affected Steps</p>
                      <div className="flex flex-wrap gap-1">
                        {recommendation.affectedNodes.map((node) => (
                          <Badge key={node} variant="outline" className="text-[10px]">
                            {node}
                          </Badge>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              </motion.div>
            )}
          </AnimatePresence>
          
          <div className="flex items-center gap-2 mt-3">
            <Button size="sm" variant="default" className="h-7 text-xs gap-1" onClick={onPreview}>
              <Eye className="h-3 w-3" />
              Preview
            </Button>
            <Button size="sm" variant="outline" className="h-7 text-xs gap-1" onClick={onApply}>
              <CheckCircle className="h-3 w-3" />
              Apply
            </Button>
            <Button size="sm" variant="ghost" className="h-7 text-xs gap-1" onClick={onExplain}>
              <HelpCircle className="h-3 w-3" />
              Why?
            </Button>
            <Button size="sm" variant="ghost" className="h-7 text-xs text-muted-foreground" onClick={onDismiss}>
              <X className="h-3 w-3" />
            </Button>
            <Button
              size="sm"
              variant="ghost"
              className="h-7 text-xs ml-auto"
              onClick={() => setExpanded(!expanded)}
            >
              {expanded ? "Less" : "More"}
              <ChevronDown className={cn("h-3 w-3 ml-1 transition-transform", expanded && "rotate-180")} />
            </Button>
          </div>
        </div>
      </div>
    </motion.div>
  )
}

// Preview Optimization Dialog
function PreviewOptimizationDialog({
  open,
  onOpenChange,
  recommendation,
  onApply,
  onSaveAsNew,
}: {
  open: boolean
  onOpenChange: (open: boolean) => void
  recommendation: OptimizationRecommendation | null
  onApply: () => void
  onSaveAsNew: () => void
}) {
  if (!recommendation) return null
  
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-2xl">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <Eye className="h-5 w-5 text-primary" />
            Preview Optimization
          </DialogTitle>
          <DialogDescription>
            Review the proposed changes before applying them to your workflow.
          </DialogDescription>
        </DialogHeader>
        
        <div className="space-y-6 py-4">
          {/* Change summary */}
          <div className="p-4 rounded-lg bg-primary/5 border border-primary/20">
            <h4 className="font-medium text-sm text-foreground mb-2">{recommendation.title}</h4>
            <p className="text-xs text-muted-foreground">{recommendation.suggestedChange}</p>
          </div>
          
          {/* Before/After comparison */}
          <div className="grid grid-cols-2 gap-4">
            <div className="p-4 rounded-lg bg-secondary/50 border border-border">
              <div className="flex items-center gap-2 mb-3">
                <div className="h-2 w-2 rounded-full bg-muted-foreground" />
                <span className="text-xs font-medium text-muted-foreground uppercase tracking-wide">Current</span>
              </div>
              <div className="space-y-2">
                <div className="flex items-center gap-2 p-2 rounded bg-secondary/50 text-xs">
                  <div className="h-6 w-6 rounded bg-blue-500/20 flex items-center justify-center">
                    <span className="text-[10px] text-blue-400">1</span>
                  </div>
                  Data Enrichment
                </div>
                <div className="flex items-center gap-2 p-2 rounded bg-secondary/50 text-xs">
                  <div className="h-6 w-6 rounded bg-blue-500/20 flex items-center justify-center">
                    <span className="text-[10px] text-blue-400">2</span>
                  </div>
                  HubSpot Sync
                </div>
                <div className="flex items-center gap-2 p-2 rounded bg-red-500/10 border border-red-500/20 text-xs text-red-400">
                  <AlertTriangle className="h-4 w-4" />
                  28% failure rate
                </div>
              </div>
            </div>
            
            <div className="p-4 rounded-lg bg-emerald-500/5 border border-emerald-500/20">
              <div className="flex items-center gap-2 mb-3">
                <div className="h-2 w-2 rounded-full bg-emerald-400" />
                <span className="text-xs font-medium text-emerald-400 uppercase tracking-wide">Proposed</span>
              </div>
              <div className="space-y-2">
                <div className="flex items-center gap-2 p-2 rounded bg-emerald-500/10 border border-emerald-500/20 text-xs">
                  <div className="h-6 w-6 rounded bg-emerald-500/20 flex items-center justify-center">
                    <Sparkles className="h-3 w-3 text-emerald-400" />
                  </div>
                  <span className="text-emerald-400">Data Validation</span>
                  <Badge className="ml-auto text-[9px] bg-emerald-500/20 text-emerald-400">NEW</Badge>
                </div>
                <div className="flex items-center gap-2 p-2 rounded bg-secondary/50 text-xs">
                  <div className="h-6 w-6 rounded bg-blue-500/20 flex items-center justify-center">
                    <span className="text-[10px] text-blue-400">2</span>
                  </div>
                  Data Enrichment
                </div>
                <div className="flex items-center gap-2 p-2 rounded bg-secondary/50 text-xs">
                  <div className="h-6 w-6 rounded bg-blue-500/20 flex items-center justify-center">
                    <span className="text-[10px] text-blue-400">3</span>
                  </div>
                  HubSpot Sync
                </div>
              </div>
            </div>
          </div>
          
          {/* Expected impact */}
          <div className="p-4 rounded-lg bg-secondary/30 border border-border">
            <h4 className="text-xs font-medium text-muted-foreground uppercase tracking-wide mb-3">Expected Impact</h4>
            <div className="grid grid-cols-3 gap-4">
              <div className="text-center">
                <div className="text-2xl font-bold text-emerald-400">-24%</div>
                <div className="text-[10px] text-muted-foreground">Failed Runs</div>
              </div>
              <div className="text-center">
                <div className="text-2xl font-bold text-blue-400">+6</div>
                <div className="text-[10px] text-muted-foreground">Health Score</div>
              </div>
              <div className="text-center">
                <div className="text-2xl font-bold text-amber-400">87%</div>
                <div className="text-[10px] text-muted-foreground">Confidence</div>
              </div>
            </div>
          </div>
        </div>
        
        <div className="flex items-center gap-2 pt-4 border-t border-border">
          <Button variant="default" className="flex-1 gap-2" onClick={onApply}>
            <CheckCircle className="h-4 w-4" />
            Apply Optimization
          </Button>
          <Button variant="outline" className="gap-2" onClick={onSaveAsNew}>
            <GitBranch className="h-4 w-4" />
            Save as New Version
          </Button>
          <Button variant="ghost" onClick={() => onOpenChange(false)}>
            Cancel
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  )
}

// AI Explanation Dialog
function AIExplanationDialog({
  open,
  onOpenChange,
  recommendation,
}: {
  open: boolean
  onOpenChange: (open: boolean) => void
  recommendation: OptimizationRecommendation | null
}) {
  if (!recommendation) return null
  
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-lg">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <Sparkles className="h-5 w-5 text-violet-400" />
            AI Explanation
          </DialogTitle>
          <DialogDescription>
            Understanding why Gravitre recommends this optimization.
          </DialogDescription>
        </DialogHeader>
        
        <div className="space-y-4 py-4">
          <div>
            <h4 className="text-xs font-medium text-muted-foreground uppercase tracking-wide mb-2">Why this recommendation?</h4>
            <p className="text-sm text-foreground">
              Gravitre analyzed 847 workflow runs over the past 30 days and identified a pattern: 
              {recommendation.issue.toLowerCase()} This optimization addresses the root cause by {recommendation.suggestedChange.toLowerCase()}
            </p>
          </div>
          
          <div>
            <h4 className="text-xs font-medium text-muted-foreground uppercase tracking-wide mb-2">Supporting Evidence</h4>
            <ul className="space-y-2">
              {recommendation.evidence.map((item, i) => (
                <li key={i} className="flex items-start gap-2 text-sm text-foreground">
                  <CheckCircle className="h-4 w-4 text-emerald-400 mt-0.5 shrink-0" />
                  {item}
                </li>
              ))}
            </ul>
          </div>
          
          <div>
            <h4 className="text-xs font-medium text-muted-foreground uppercase tracking-wide mb-2">What could go wrong?</h4>
            <ul className="space-y-2">
              <li className="flex items-start gap-2 text-sm text-muted-foreground">
                <AlertTriangle className="h-4 w-4 text-amber-400 mt-0.5 shrink-0" />
                Additional validation step may slightly increase processing time (+0.3s avg)
              </li>
              <li className="flex items-start gap-2 text-sm text-muted-foreground">
                <AlertTriangle className="h-4 w-4 text-amber-400 mt-0.5 shrink-0" />
                Some edge cases may be flagged as invalid when they are actually valid
              </li>
            </ul>
          </div>
          
          <div className="p-3 rounded-lg bg-violet-500/5 border border-violet-500/20">
            <div className="flex items-center gap-2 mb-1">
              <Activity className="h-4 w-4 text-violet-400" />
              <span className="text-xs font-medium text-violet-400">Confidence Level: {recommendation.confidence}%</span>
            </div>
            <p className="text-xs text-muted-foreground">
              This recommendation is based on strong evidence from recent workflow executions. 
              Similar optimizations have shown positive results in comparable workflows.
            </p>
          </div>
        </div>
        
        <div className="flex items-center gap-2 pt-4 border-t border-border">
          <span className="text-xs text-muted-foreground">Was this helpful?</span>
          <Button variant="ghost" size="sm" className="h-7">
            <ThumbsUp className="h-3 w-3" />
          </Button>
          <Button variant="ghost" size="sm" className="h-7">
            <ThumbsDown className="h-3 w-3" />
          </Button>
          <Button variant="outline" className="ml-auto" onClick={() => onOpenChange(false)}>
            Close
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  )
}

// Main Component
export function OptimizationInsightsPanel({
  workflowId,
  workflowName,
  className,
}: {
  workflowId?: string
  workflowName?: string
  className?: string
}) {
  const [activeTab, setActiveTab] = useState<"insights" | "versions" | "testing">("insights")
  const [selectedRecommendation, setSelectedRecommendation] = useState<OptimizationRecommendation | null>(null)
  const [previewOpen, setPreviewOpen] = useState(false)
  const [explainOpen, setExplainOpen] = useState(false)
  const [isCollapsed, setIsCollapsed] = useState(false)
  
  const healthScore = 82
  
  return (
    <TooltipProvider>
      <div className={cn("rounded-xl border border-border bg-card overflow-hidden", className)}>
        {/* Header */}
        <div 
          className="flex items-center justify-between p-4 border-b border-border cursor-pointer hover:bg-secondary/30 transition-colors"
          onClick={() => setIsCollapsed(!isCollapsed)}
        >
          <div className="flex items-center gap-3">
            <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-gradient-to-br from-violet-500/20 to-purple-500/20 border border-violet-500/30">
              <Sparkles className="h-4 w-4 text-violet-400" />
            </div>
            <div>
              <h3 className="font-semibold text-sm text-foreground">Optimization Insights</h3>
              <p className="text-xs text-muted-foreground">
                {mockRecommendations.length} recommendations available
              </p>
            </div>
          </div>
          <div className="flex items-center gap-3">
            <div className="flex items-center gap-2">
              <span className="text-xs text-muted-foreground">Health:</span>
              <span className={cn(
                "text-sm font-bold",
                healthScore >= 80 ? "text-emerald-400" : healthScore >= 60 ? "text-amber-400" : "text-red-400"
              )}>
                {healthScore}/100
              </span>
            </div>
            <ChevronDown className={cn(
              "h-4 w-4 text-muted-foreground transition-transform",
              isCollapsed && "-rotate-90"
            )} />
          </div>
        </div>
        
        <AnimatePresence>
          {!isCollapsed && (
            <motion.div
              initial={{ height: 0 }}
              animate={{ height: "auto" }}
              exit={{ height: 0 }}
              className="overflow-hidden"
            >
              {/* Tabs */}
              <div className="flex border-b border-border px-4">
                {[
                  { id: "insights", label: "Insights", icon: Lightbulb },
                  { id: "versions", label: "Versions", icon: History },
                  { id: "testing", label: "A/B Testing", icon: FlaskConical },
                ].map((tab) => (
                  <button
                    key={tab.id}
                    onClick={() => setActiveTab(tab.id as typeof activeTab)}
                    className={cn(
                      "flex items-center gap-1.5 px-4 py-3 text-xs font-medium transition-colors border-b-2 -mb-px",
                      activeTab === tab.id
                        ? "text-foreground border-primary"
                        : "text-muted-foreground border-transparent hover:text-foreground"
                    )}
                  >
                    <tab.icon className="h-3.5 w-3.5" />
                    {tab.label}
                  </button>
                ))}
              </div>
              
              <div className="p-4">
                {activeTab === "insights" && (
                  <div className="space-y-6">
                    {/* Health Score Section */}
                    <div className="flex items-start gap-6">
                      <HealthScoreRing score={healthScore} />
                      
                      <div className="flex-1">
                        <h4 className="text-xs font-medium text-muted-foreground uppercase tracking-wide mb-3">
                          Score Dimensions
                        </h4>
                        <div className="grid grid-cols-2 gap-2">
                          {mockDimensions.map((dim) => (
                            <div key={dim.name} className="flex items-center gap-2">
                              <dim.icon className="h-3.5 w-3.5 text-muted-foreground" />
                              <span className="text-xs text-muted-foreground flex-1">{dim.name}</span>
                              <span className={cn(
                                "text-xs font-medium",
                                dim.score >= 80 ? "text-emerald-400" : dim.score >= 60 ? "text-amber-400" : "text-red-400"
                              )}>
                                {dim.score}
                              </span>
                              {dim.trend === "up" && <TrendingUp className="h-3 w-3 text-emerald-400" />}
                              {dim.trend === "down" && <TrendingDown className="h-3 w-3 text-red-400" />}
                            </div>
                          ))}
                        </div>
                      </div>
                      
                      <div className="w-40">
                        <h4 className="text-xs font-medium text-muted-foreground uppercase tracking-wide mb-2">
                          7-Day Trend
                        </h4>
                        <div className="h-16">
                          <ResponsiveContainer width="100%" height="100%">
                            <AreaChart data={mockScoreHistory}>
                              <defs>
                                <linearGradient id="scoreGradient" x1="0" y1="0" x2="0" y2="1">
                                  <stop offset="5%" stopColor="#10b981" stopOpacity={0.3}/>
                                  <stop offset="95%" stopColor="#10b981" stopOpacity={0}/>
                                </linearGradient>
                              </defs>
                              <Area
                                type="monotone"
                                dataKey="score"
                                stroke="#10b981"
                                strokeWidth={2}
                                fill="url(#scoreGradient)"
                              />
                            </AreaChart>
                          </ResponsiveContainer>
                        </div>
                      </div>
                    </div>
                    
                    {/* Recommendations */}
                    <div>
                      <div className="flex items-center justify-between mb-3">
                        <h4 className="text-xs font-medium text-muted-foreground uppercase tracking-wide">
                          Recommendations
                        </h4>
                        <Button variant="ghost" size="sm" className="h-6 text-[10px] gap-1">
                          <RefreshCw className="h-3 w-3" />
                          Refresh
                        </Button>
                      </div>
                      <div className="space-y-3">
                        {mockRecommendations.map((rec) => (
                          <RecommendationCard
                            key={rec.id}
                            recommendation={rec}
                            onPreview={() => {
                              setSelectedRecommendation(rec)
                              setPreviewOpen(true)
                            }}
                            onApply={() => {
                              setSelectedRecommendation(rec)
                              setPreviewOpen(true)
                            }}
                            onDismiss={() => {}}
                            onExplain={() => {
                              setSelectedRecommendation(rec)
                              setExplainOpen(true)
                            }}
                          />
                        ))}
                      </div>
                    </div>
                  </div>
                )}
                
                {activeTab === "versions" && (
                  <div className="space-y-3">
                    {mockVersions.map((version) => (
                      <div
                        key={version.id}
                        className={cn(
                          "p-4 rounded-lg border transition-colors",
                          version.status === "active"
                            ? "bg-emerald-500/5 border-emerald-500/30"
                            : "bg-secondary/30 border-border"
                        )}
                      >
                        <div className="flex items-center justify-between mb-2">
                          <div className="flex items-center gap-2">
                            <span className="font-medium text-sm">Version {version.version}</span>
                            {version.status === "active" && (
                              <Badge className="text-[10px] bg-emerald-500/20 text-emerald-400">Active</Badge>
                            )}
                            {version.status === "testing" && (
                              <Badge className="text-[10px] bg-blue-500/20 text-blue-400">Testing</Badge>
                            )}
                          </div>
                          <span className={cn(
                            "text-sm font-medium",
                            version.healthScore >= 80 ? "text-emerald-400" : "text-amber-400"
                          )}>
                            {version.healthScore}/100
                          </span>
                        </div>
                        <div className="flex items-center gap-2 text-xs text-muted-foreground mb-2">
                          <span>{version.createdBy}</span>
                          <span>•</span>
                          <span>{version.createdAt.toLocaleDateString()}</span>
                        </div>
                        <ul className="space-y-1">
                          {version.changes.map((change, i) => (
                            <li key={i} className="flex items-center gap-2 text-xs text-foreground">
                              <ChevronRight className="h-3 w-3 text-muted-foreground" />
                              {change}
                            </li>
                          ))}
                        </ul>
                        {version.status !== "active" && (
                          <div className="flex items-center gap-2 mt-3">
                            <Button variant="outline" size="sm" className="h-7 text-xs">
                              Restore
                            </Button>
                            <Button variant="ghost" size="sm" className="h-7 text-xs">
                              Compare
                            </Button>
                          </div>
                        )}
                      </div>
                    ))}
                  </div>
                )}
                
                {activeTab === "testing" && (
                  <div className="space-y-4">
                    <div className="p-4 rounded-lg bg-blue-500/5 border border-blue-500/20">
                      <div className="flex items-center gap-2 mb-3">
                        <FlaskConical className="h-5 w-5 text-blue-400" />
                        <span className="font-medium text-sm">A/B Test: Validation Optimization</span>
                        <Badge className="text-[10px] bg-blue-500/20 text-blue-400">Running</Badge>
                      </div>
                      
                      <div className="grid grid-cols-2 gap-4 mb-4">
                        <div className="p-3 rounded bg-secondary/50">
                          <div className="flex items-center justify-between mb-2">
                            <span className="text-xs text-muted-foreground">Version 3 (Current)</span>
                            <span className="text-xs text-muted-foreground">50% traffic</span>
                          </div>
                          <div className="text-xl font-bold text-foreground mb-1">82%</div>
                          <div className="text-[10px] text-muted-foreground">Success rate (124 runs)</div>
                        </div>
                        <div className="p-3 rounded bg-emerald-500/10 border border-emerald-500/20">
                          <div className="flex items-center justify-between mb-2">
                            <span className="text-xs text-emerald-400">Version 4 (Test)</span>
                            <span className="text-xs text-muted-foreground">50% traffic</span>
                          </div>
                          <div className="text-xl font-bold text-emerald-400 mb-1">91%</div>
                          <div className="text-[10px] text-muted-foreground">Success rate (118 runs)</div>
                        </div>
                      </div>
                      
                      <div className="flex items-center gap-2">
                        <Button variant="default" size="sm" className="h-7 text-xs gap-1">
                          <CheckCircle className="h-3 w-3" />
                          Promote Winner
                        </Button>
                        <Button variant="outline" size="sm" className="h-7 text-xs">
                          End Test
                        </Button>
                        <span className="text-[10px] text-muted-foreground ml-auto">
                          Started 3 days ago • 242 total runs
                        </span>
                      </div>
                    </div>
                    
                    <Button variant="outline" className="w-full gap-2">
                      <FlaskConical className="h-4 w-4" />
                      Start New A/B Test
                    </Button>
                  </div>
                )}
              </div>
            </motion.div>
          )}
        </AnimatePresence>
        
        {/* Dialogs */}
        <PreviewOptimizationDialog
          open={previewOpen}
          onOpenChange={setPreviewOpen}
          recommendation={selectedRecommendation}
          onApply={() => {
            setPreviewOpen(false)
          }}
          onSaveAsNew={() => {
            setPreviewOpen(false)
          }}
        />
        
        <AIExplanationDialog
          open={explainOpen}
          onOpenChange={setExplainOpen}
          recommendation={selectedRecommendation}
        />
      </div>
    </TooltipProvider>
  )
}
