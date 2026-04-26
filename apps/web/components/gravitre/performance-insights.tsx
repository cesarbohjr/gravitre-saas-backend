"use client"

import { useState } from "react"
import { motion } from "framer-motion"
import {
  Bot,
  Plug,
  TrendingUp,
  TrendingDown,
  AlertTriangle,
  CheckCircle,
  Clock,
  Zap,
  Activity,
  BarChart3,
  RefreshCw,
  ChevronRight,
  Target,
  Percent,
  Timer,
  AlertCircle,
} from "lucide-react"
import { cn } from "@/lib/utils"
import { Badge } from "@/components/ui/badge"
import { Progress } from "@/components/ui/progress"
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  ResponsiveContainer,
  Cell,
  LineChart,
  Line,
} from "recharts"

// Types
interface AgentPerformance {
  id: string
  name: string
  role: string
  tasksCompleted: number
  avgConfidence: number
  overrideRate: number
  errorRate: number
  avgResponseTime: number
  trend: "improving" | "declining" | "stable"
  topWorkflows: string[]
  weakAreas: string[]
}

interface ConnectorHealth {
  id: string
  name: string
  type: string
  icon: string
  status: "healthy" | "degraded" | "failing"
  successRate: number
  avgLatency: number
  errorCount: number
  rateLimitHits: number
  lastError?: string
  issues: string[]
}

// Mock data
const mockAgents: AgentPerformance[] = [
  {
    id: "agent-1",
    name: "Research Analyst",
    role: "Data analysis & insights",
    tasksCompleted: 847,
    avgConfidence: 87,
    overrideRate: 12,
    errorRate: 3,
    avgResponseTime: 2.4,
    trend: "improving",
    topWorkflows: ["Lead Enrichment", "Market Analysis"],
    weakAreas: ["Complex financial data"],
  },
  {
    id: "agent-2",
    name: "Content Writer",
    role: "Content generation",
    tasksCompleted: 523,
    avgConfidence: 74,
    overrideRate: 64,
    errorRate: 1,
    avgResponseTime: 4.2,
    trend: "stable",
    topWorkflows: ["Email Campaigns", "Social Posts"],
    weakAreas: ["Technical documentation", "Brand voice consistency"],
  },
  {
    id: "agent-3",
    name: "Data Validator",
    role: "Quality & accuracy",
    tasksCompleted: 1204,
    avgConfidence: 92,
    overrideRate: 5,
    errorRate: 2,
    avgResponseTime: 1.1,
    trend: "improving",
    topWorkflows: ["CRM Sync", "Data Import"],
    weakAreas: [],
  },
  {
    id: "agent-4",
    name: "Compliance Reviewer",
    role: "Risk & policy",
    tasksCompleted: 342,
    avgConfidence: 89,
    overrideRate: 8,
    errorRate: 0,
    avgResponseTime: 3.8,
    trend: "stable",
    topWorkflows: ["Contract Review", "Policy Check"],
    weakAreas: ["International regulations"],
  },
]

const mockConnectors: ConnectorHealth[] = [
  {
    id: "conn-1",
    name: "HubSpot",
    type: "CRM",
    icon: "H",
    status: "healthy",
    successRate: 98.7,
    avgLatency: 245,
    errorCount: 12,
    rateLimitHits: 3,
    issues: [],
  },
  {
    id: "conn-2",
    name: "Salesforce",
    type: "CRM",
    icon: "S",
    status: "degraded",
    successRate: 94.2,
    avgLatency: 890,
    errorCount: 47,
    rateLimitHits: 28,
    lastError: "Rate limit exceeded",
    issues: ["High latency detected", "Rate limits causing delays"],
  },
  {
    id: "conn-3",
    name: "Slack",
    type: "Communication",
    icon: "S",
    status: "healthy",
    successRate: 99.9,
    avgLatency: 120,
    errorCount: 1,
    rateLimitHits: 0,
    issues: [],
  },
  {
    id: "conn-4",
    name: "Stripe",
    type: "Payments",
    icon: "$",
    status: "healthy",
    successRate: 99.5,
    avgLatency: 380,
    errorCount: 4,
    rateLimitHits: 0,
    issues: [],
  },
  {
    id: "conn-5",
    name: "Google Sheets",
    type: "Data",
    icon: "G",
    status: "failing",
    successRate: 78.3,
    avgLatency: 1240,
    errorCount: 156,
    rateLimitHits: 89,
    lastError: "Authentication expired",
    issues: ["Auth token expired", "Reconnection required"],
  },
]

const agentChartData = mockAgents.map(agent => ({
  name: agent.name.split(" ")[0],
  confidence: agent.avgConfidence,
  override: agent.overrideRate,
}))

// Agent Performance Card
function AgentPerformanceCard({ agent }: { agent: AgentPerformance }) {
  const trendColors = {
    improving: "text-emerald-400",
    declining: "text-red-400",
    stable: "text-amber-400",
  }
  
  const trendIcons = {
    improving: TrendingUp,
    declining: TrendingDown,
    stable: Activity,
  }
  
  const TrendIcon = trendIcons[agent.trend]
  
  const hasIssues = agent.overrideRate > 50 || agent.errorRate > 5
  
  return (
    <div className={cn(
      "p-4 rounded-xl border transition-colors",
      hasIssues 
        ? "bg-amber-500/5 border-amber-500/20" 
        : "bg-secondary/30 border-border hover:border-primary/30"
    )}>
      <div className="flex items-start gap-3 mb-4">
        <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-blue-500/20 border border-blue-500/30">
          <Bot className="h-5 w-5 text-blue-400" />
        </div>
        <div className="flex-1">
          <div className="flex items-center gap-2">
            <h4 className="font-medium text-sm text-foreground">{agent.name}</h4>
            <TrendIcon className={cn("h-3.5 w-3.5", trendColors[agent.trend])} />
          </div>
          <p className="text-xs text-muted-foreground">{agent.role}</p>
        </div>
        <div className="text-right">
          <div className="text-lg font-bold text-foreground">{agent.tasksCompleted}</div>
          <div className="text-[10px] text-muted-foreground">tasks</div>
        </div>
      </div>
      
      <div className="grid grid-cols-4 gap-3 mb-4">
        <div>
          <div className="flex items-center gap-1 mb-1">
            <Target className="h-3 w-3 text-muted-foreground" />
            <span className="text-[10px] text-muted-foreground">Confidence</span>
          </div>
          <div className={cn(
            "text-sm font-medium",
            agent.avgConfidence >= 80 ? "text-emerald-400" : agent.avgConfidence >= 60 ? "text-amber-400" : "text-red-400"
          )}>
            {agent.avgConfidence}%
          </div>
        </div>
        <div>
          <div className="flex items-center gap-1 mb-1">
            <RefreshCw className="h-3 w-3 text-muted-foreground" />
            <span className="text-[10px] text-muted-foreground">Override</span>
          </div>
          <div className={cn(
            "text-sm font-medium",
            agent.overrideRate <= 20 ? "text-emerald-400" : agent.overrideRate <= 40 ? "text-amber-400" : "text-red-400"
          )}>
            {agent.overrideRate}%
          </div>
        </div>
        <div>
          <div className="flex items-center gap-1 mb-1">
            <AlertCircle className="h-3 w-3 text-muted-foreground" />
            <span className="text-[10px] text-muted-foreground">Errors</span>
          </div>
          <div className={cn(
            "text-sm font-medium",
            agent.errorRate <= 2 ? "text-emerald-400" : agent.errorRate <= 5 ? "text-amber-400" : "text-red-400"
          )}>
            {agent.errorRate}%
          </div>
        </div>
        <div>
          <div className="flex items-center gap-1 mb-1">
            <Timer className="h-3 w-3 text-muted-foreground" />
            <span className="text-[10px] text-muted-foreground">Avg Time</span>
          </div>
          <div className="text-sm font-medium text-foreground">
            {agent.avgResponseTime}s
          </div>
        </div>
      </div>
      
      {hasIssues && agent.weakAreas.length > 0 && (
        <div className="p-2 rounded-lg bg-amber-500/10 border border-amber-500/20 mb-3">
          <div className="flex items-center gap-1.5 mb-1">
            <AlertTriangle className="h-3 w-3 text-amber-400" />
            <span className="text-[10px] font-medium text-amber-400">Improvement areas</span>
          </div>
          <div className="flex flex-wrap gap-1">
            {agent.weakAreas.map((area) => (
              <Badge key={area} variant="outline" className="text-[9px] bg-amber-500/10 text-amber-400 border-amber-500/20">
                {area}
              </Badge>
            ))}
          </div>
        </div>
      )}
      
      {agent.topWorkflows.length > 0 && (
        <div className="flex items-center gap-2">
          <span className="text-[10px] text-muted-foreground">Best in:</span>
          {agent.topWorkflows.map((workflow) => (
            <Badge key={workflow} variant="outline" className="text-[9px]">
              {workflow}
            </Badge>
          ))}
        </div>
      )}
    </div>
  )
}

// Connector Health Card
function ConnectorHealthCard({ connector }: { connector: ConnectorHealth }) {
  const statusConfig = {
    healthy: { color: "text-emerald-400", bg: "bg-emerald-500/20", border: "border-emerald-500/30" },
    degraded: { color: "text-amber-400", bg: "bg-amber-500/20", border: "border-amber-500/30" },
    failing: { color: "text-red-400", bg: "bg-red-500/20", border: "border-red-500/30" },
  }
  
  const config = statusConfig[connector.status]
  
  return (
    <div className={cn(
      "p-4 rounded-xl border transition-colors",
      connector.status === "healthy" 
        ? "bg-secondary/30 border-border hover:border-primary/30" 
        : connector.status === "degraded"
        ? "bg-amber-500/5 border-amber-500/20"
        : "bg-red-500/5 border-red-500/20"
    )}>
      <div className="flex items-start gap-3 mb-4">
        <div className={cn(
          "flex h-10 w-10 items-center justify-center rounded-lg font-bold text-sm",
          config.bg, config.border, "border"
        )}>
          <span className={config.color}>{connector.icon}</span>
        </div>
        <div className="flex-1">
          <div className="flex items-center gap-2">
            <h4 className="font-medium text-sm text-foreground">{connector.name}</h4>
            <Badge variant="outline" className={cn(
              "text-[9px]",
              connector.status === "healthy" && "bg-emerald-500/10 text-emerald-400 border-emerald-500/20",
              connector.status === "degraded" && "bg-amber-500/10 text-amber-400 border-amber-500/20",
              connector.status === "failing" && "bg-red-500/10 text-red-400 border-red-500/20"
            )}>
              {connector.status}
            </Badge>
          </div>
          <p className="text-xs text-muted-foreground">{connector.type}</p>
        </div>
      </div>
      
      <div className="grid grid-cols-4 gap-3 mb-3">
        <div>
          <div className="text-[10px] text-muted-foreground mb-1">Success</div>
          <div className={cn(
            "text-sm font-medium",
            connector.successRate >= 98 ? "text-emerald-400" : connector.successRate >= 90 ? "text-amber-400" : "text-red-400"
          )}>
            {connector.successRate}%
          </div>
        </div>
        <div>
          <div className="text-[10px] text-muted-foreground mb-1">Latency</div>
          <div className={cn(
            "text-sm font-medium",
            connector.avgLatency <= 300 ? "text-emerald-400" : connector.avgLatency <= 800 ? "text-amber-400" : "text-red-400"
          )}>
            {connector.avgLatency}ms
          </div>
        </div>
        <div>
          <div className="text-[10px] text-muted-foreground mb-1">Errors</div>
          <div className={cn(
            "text-sm font-medium",
            connector.errorCount <= 10 ? "text-emerald-400" : connector.errorCount <= 50 ? "text-amber-400" : "text-red-400"
          )}>
            {connector.errorCount}
          </div>
        </div>
        <div>
          <div className="text-[10px] text-muted-foreground mb-1">Rate Limits</div>
          <div className={cn(
            "text-sm font-medium",
            connector.rateLimitHits <= 5 ? "text-emerald-400" : connector.rateLimitHits <= 20 ? "text-amber-400" : "text-red-400"
          )}>
            {connector.rateLimitHits}
          </div>
        </div>
      </div>
      
      {connector.issues.length > 0 && (
        <div className="p-2 rounded-lg bg-red-500/10 border border-red-500/20">
          <div className="flex items-center gap-1.5 mb-1">
            <AlertTriangle className="h-3 w-3 text-red-400" />
            <span className="text-[10px] font-medium text-red-400">Issues detected</span>
          </div>
          <ul className="space-y-0.5">
            {connector.issues.map((issue, i) => (
              <li key={i} className="text-xs text-red-300 flex items-center gap-1">
                <ChevronRight className="h-3 w-3" />
                {issue}
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  )
}

// Main Performance Insights Component
export function PerformanceInsights({ className }: { className?: string }) {
  const [activeTab, setActiveTab] = useState<"agents" | "connectors">("agents")
  
  const healthyConnectors = mockConnectors.filter(c => c.status === "healthy").length
  const degradedConnectors = mockConnectors.filter(c => c.status === "degraded").length
  const failingConnectors = mockConnectors.filter(c => c.status === "failing").length
  
  return (
    <div className={cn("space-y-6", className)}>
      {/* Summary Stats */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <div className="p-4 rounded-xl bg-secondary/30 border border-border">
          <div className="flex items-center gap-2 mb-2">
            <Bot className="h-4 w-4 text-blue-400" />
            <span className="text-xs text-muted-foreground">Active Agents</span>
          </div>
          <div className="text-2xl font-bold text-foreground">{mockAgents.length}</div>
          <div className="text-[10px] text-muted-foreground mt-1">
            {mockAgents.filter(a => a.trend === "improving").length} improving
          </div>
        </div>
        
        <div className="p-4 rounded-xl bg-secondary/30 border border-border">
          <div className="flex items-center gap-2 mb-2">
            <Plug className="h-4 w-4 text-amber-400" />
            <span className="text-xs text-muted-foreground">Connectors</span>
          </div>
          <div className="flex items-baseline gap-2">
            <span className="text-2xl font-bold text-foreground">{mockConnectors.length}</span>
            <span className={cn(
              "text-xs",
              failingConnectors > 0 ? "text-red-400" : degradedConnectors > 0 ? "text-amber-400" : "text-emerald-400"
            )}>
              {failingConnectors > 0 
                ? `${failingConnectors} failing` 
                : degradedConnectors > 0 
                ? `${degradedConnectors} degraded` 
                : "all healthy"}
            </span>
          </div>
        </div>
        
        <div className="p-4 rounded-xl bg-secondary/30 border border-border">
          <div className="flex items-center gap-2 mb-2">
            <Target className="h-4 w-4 text-emerald-400" />
            <span className="text-xs text-muted-foreground">Avg Confidence</span>
          </div>
          <div className="text-2xl font-bold text-emerald-400">
            {Math.round(mockAgents.reduce((acc, a) => acc + a.avgConfidence, 0) / mockAgents.length)}%
          </div>
        </div>
        
        <div className="p-4 rounded-xl bg-secondary/30 border border-border">
          <div className="flex items-center gap-2 mb-2">
            <RefreshCw className="h-4 w-4 text-violet-400" />
            <span className="text-xs text-muted-foreground">Override Rate</span>
          </div>
          <div className={cn(
            "text-2xl font-bold",
            Math.round(mockAgents.reduce((acc, a) => acc + a.overrideRate, 0) / mockAgents.length) > 30 
              ? "text-amber-400" 
              : "text-emerald-400"
          )}>
            {Math.round(mockAgents.reduce((acc, a) => acc + a.overrideRate, 0) / mockAgents.length)}%
          </div>
        </div>
      </div>
      
      {/* Tabs */}
      <div className="flex border-b border-border">
        <button
          onClick={() => setActiveTab("agents")}
          className={cn(
            "flex items-center gap-2 px-4 py-3 text-sm font-medium transition-colors border-b-2 -mb-px",
            activeTab === "agents"
              ? "text-foreground border-primary"
              : "text-muted-foreground border-transparent hover:text-foreground"
          )}
        >
          <Bot className="h-4 w-4" />
          Agent Performance
        </button>
        <button
          onClick={() => setActiveTab("connectors")}
          className={cn(
            "flex items-center gap-2 px-4 py-3 text-sm font-medium transition-colors border-b-2 -mb-px",
            activeTab === "connectors"
              ? "text-foreground border-primary"
              : "text-muted-foreground border-transparent hover:text-foreground"
          )}
        >
          <Plug className="h-4 w-4" />
          Connector Health
          {(degradedConnectors > 0 || failingConnectors > 0) && (
            <Badge variant="outline" className={cn(
              "text-[9px] ml-1",
              failingConnectors > 0 
                ? "bg-red-500/10 text-red-400 border-red-500/20" 
                : "bg-amber-500/10 text-amber-400 border-amber-500/20"
            )}>
              {failingConnectors + degradedConnectors}
            </Badge>
          )}
        </button>
      </div>
      
      {/* Content */}
      {activeTab === "agents" && (
        <div className="space-y-6">
          {/* Agent Chart */}
          <div className="p-4 rounded-xl bg-secondary/30 border border-border">
            <h4 className="text-xs font-medium text-muted-foreground uppercase tracking-wide mb-4">
              Confidence vs Override Rate
            </h4>
            <div className="h-40">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={agentChartData} barGap={8}>
                  <XAxis 
                    dataKey="name" 
                    tick={{ fill: "hsl(var(--muted-foreground))", fontSize: 10 }}
                    axisLine={false}
                    tickLine={false}
                  />
                  <Bar dataKey="confidence" radius={[4, 4, 0, 0]} maxBarSize={30}>
                    {agentChartData.map((entry, index) => (
                      <Cell 
                        key={`cell-${index}`} 
                        fill={entry.confidence >= 80 ? "#10b981" : entry.confidence >= 60 ? "#f59e0b" : "#ef4444"}
                        fillOpacity={0.8}
                      />
                    ))}
                  </Bar>
                  <Bar dataKey="override" radius={[4, 4, 0, 0]} maxBarSize={30}>
                    {agentChartData.map((entry, index) => (
                      <Cell 
                        key={`cell-${index}`} 
                        fill={entry.override <= 20 ? "#10b981" : entry.override <= 40 ? "#f59e0b" : "#ef4444"}
                        fillOpacity={0.4}
                      />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </div>
            <div className="flex items-center justify-center gap-6 mt-2">
              <div className="flex items-center gap-2">
                <div className="h-3 w-3 rounded bg-emerald-500/80" />
                <span className="text-[10px] text-muted-foreground">Confidence</span>
              </div>
              <div className="flex items-center gap-2">
                <div className="h-3 w-3 rounded bg-emerald-500/40" />
                <span className="text-[10px] text-muted-foreground">Override Rate</span>
              </div>
            </div>
          </div>
          
          {/* Agent Cards */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {mockAgents.map((agent) => (
              <AgentPerformanceCard key={agent.id} agent={agent} />
            ))}
          </div>
        </div>
      )}
      
      {activeTab === "connectors" && (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {mockConnectors.map((connector) => (
            <ConnectorHealthCard key={connector.id} connector={connector} />
          ))}
        </div>
      )}
    </div>
  )
}
