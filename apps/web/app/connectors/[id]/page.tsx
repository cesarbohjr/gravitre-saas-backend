"use client"

import { useMemo, useState } from "react"
import { useParams, useRouter } from "next/navigation"
import Link from "next/link"
import { motion } from "framer-motion"
import useSWR from "swr"
import { AppShell } from "@/components/gravitre/app-shell"
import { ConnectorIcon } from "@/components/gravitre/connector-icon"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { toast } from "sonner"
import { cn } from "@/lib/utils"
import { fetcher } from "@/lib/fetcher"
import { EmptyState } from "@/components/gravitre/empty-state"
import { Skeleton } from "@/components/ui/skeleton"
import {
  ArrowLeft,
  CheckCircle2,
  XCircle,
  Loader2,
  WifiOff,
  RefreshCw,
  Settings,
  Trash2,
  ExternalLink,
  Activity,
  Zap,
  Clock,
  TrendingUp,
  TrendingDown,
  AlertTriangle,
  Eye,
  EyeOff,
  Copy,
  Check,
  Play,
  Pause,
  Workflow,
  Bot,
  Calendar,
  MoreVertical,
  Download,
  Key,
  Globe,
  Link2,
} from "lucide-react"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  AreaChart,
  Area,
} from "recharts"

interface SystemResponse {
  systems: Array<{
    id: string
    name: string
    type: string
    status: "connected" | "disconnected" | "error" | "syncing"
    config?: Record<string, unknown>
    lastSyncedAt?: string | null
    createdAt?: string
  }>
}

interface ConnectorHealthResponse {
  successRate: number
  avgLatency: number
  errorCount: number
  rateLimitHits: number
  lastSuccessfulSync: string | null
  status: string
  trendOverTime: Array<{ timestamp: string; success: boolean }>
}

const fallbackConnector = {
  id: "1",
  name: "salesforce-api",
  type: "Salesforce",
  status: "connected" as const,
  environment: "production" as const,
  lastSync: "2 minutes ago",
  health: 98,
  description: "Salesforce REST API connector for CRM data synchronization",
  dataFlowRate: "2.4 MB/s",
  requestsToday: 12847,
  latency: 45,
  category: "CRM / Marketing",
  authType: "oauth" as const,
  usedByWorkflows: 8,
  triggeredByAgents: 3,
  createdAt: "2024-01-15",
  config: {
    apiKey: "sf_live_xxxxxxxxxxxxxxxx",
    webhookUrl: "https://api.gravitre.io/webhooks/salesforce/abc123",
    syncInterval: "5m",
  },
}

const statusConfig = {
  connected: { color: "text-emerald-500", bg: "bg-emerald-500", icon: CheckCircle2, label: "Connected" },
  disconnected: { color: "text-zinc-500", bg: "bg-zinc-500", icon: WifiOff, label: "Disconnected" },
  error: { color: "text-red-500", bg: "bg-red-500", icon: XCircle, label: "Error" },
  syncing: { color: "text-blue-500", bg: "bg-blue-500", icon: Loader2, label: "Syncing" },
}

export default function ConnectorDetailPage() {
  const params = useParams()
  const router = useRouter()
  const connectorId = String(params.id ?? "")
  const { data: systemsData, error: systemsError, isLoading: isLoadingSystems } = useSWR<SystemResponse>(
    "/api/systems",
    fetcher
  )
  const { data: healthData, error: healthError, isLoading: isLoadingHealth } =
    useSWR<ConnectorHealthResponse>(
      connectorId ? `/api/connectors/${connectorId}/health` : null,
      fetcher
    )

  const [localStatus, setLocalStatus] = useState<"connected" | "disconnected" | "error" | "syncing" | null>(null)
  const [showApiKey, setShowApiKey] = useState(false)
  const [isSyncing, setIsSyncing] = useState(false)
  const [showDeleteDialog, setShowDeleteDialog] = useState(false)
  const [showConfigDialog, setShowConfigDialog] = useState(false)
  const [copied, setCopied] = useState<string | null>(null)

  const connector = useMemo(() => {
    const source = systemsData?.systems?.find((item) => item.id === connectorId)
    if (!source) {
      return fallbackConnector
    }
    const config = source.config ?? {}
    return {
      ...fallbackConnector,
      id: source.id,
      name: source.name,
      type: source.type,
      status: (localStatus ?? source.status) as typeof fallbackConnector.status,
      lastSync: healthData?.lastSuccessfulSync
        ? new Date(healthData.lastSuccessfulSync).toLocaleString()
        : "No recent sync",
      health: Math.round(healthData?.successRate ?? 0),
      requestsToday: Math.round((healthData?.trendOverTime?.length ?? 0) * 120),
      latency: Math.round(healthData?.avgLatency ?? 0),
      category: source.type,
      createdAt: source.createdAt ? new Date(source.createdAt).toLocaleDateString() : "-",
      config: {
        apiKey: String(config.apiKey ?? ""),
        webhookUrl: String(config.webhookUrl ?? ""),
        syncInterval: String(config.syncInterval ?? "15m"),
      },
    }
  }, [connectorId, healthData, localStatus, systemsData?.systems])

  const usageData = useMemo(
    () =>
      (healthData?.trendOverTime ?? []).map((item, index) => ({
        time: new Date(item.timestamp).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
        requests: item.success ? 120 + index * 8 : 40 + index * 4,
        latency: Math.round(healthData?.avgLatency ?? 0) || 0,
      })),
    [healthData]
  )

  const connectedWorkflows = useMemo(
    () => [
      { id: "all", name: "workflow integrations", status: "active", lastRun: connector.lastSync, runs: connector.requestsToday },
    ],
    [connector.lastSync, connector.requestsToday]
  )
  const connectedAgents = useMemo(
    () => [{ id: "team", name: "Assigned agents", type: "System consumers", actions: connector.requestsToday }],
    [connector.requestsToday]
  )
  const activityLogs = useMemo(
    () =>
      (healthData?.trendOverTime ?? []).slice(0, 8).map((item, index) => ({
        id: `${index}`,
        type: item.success ? "success" : "error",
        action: item.success ? "Connector execution succeeded" : "Connector execution failed",
        timestamp: new Date(item.timestamp).toLocaleString(),
        details: item.success ? "Sync completed successfully" : "Investigate downstream dependency failure",
      })),
    [healthData]
  )

  const config = statusConfig[connector.status]
  const StatusIcon = config.icon

  const handleSync = async () => {
    setIsSyncing(true)
    await new Promise(resolve => setTimeout(resolve, 2000))
    setIsSyncing(false)
    toast.success("Sync completed", { description: "All data has been synchronized" })
  }

  const handleCopy = (text: string, label: string) => {
    navigator.clipboard.writeText(text)
    setCopied(label)
    toast.success(`${label} copied to clipboard`)
    setTimeout(() => setCopied(null), 2000)
  }

  const handleDelete = () => {
    toast.success("Connector removed", { description: `${connector.name} has been disconnected` })
    router.push("/connectors")
  }

  const handleToggleStatus = () => {
    const newStatus = connector.status === "connected" ? "disconnected" : "connected"
    setLocalStatus(newStatus)
    toast.success(newStatus === "connected" ? "Connector enabled" : "Connector disabled")
  }

  if (isLoadingSystems || isLoadingHealth) {
    return (
      <AppShell title="Connector">
        <div className="p-6 space-y-4">
          <Skeleton className="h-12 w-56" />
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <Skeleton className="h-24 w-full" />
            <Skeleton className="h-24 w-full" />
            <Skeleton className="h-24 w-full" />
            <Skeleton className="h-24 w-full" />
          </div>
        </div>
      </AppShell>
    )
  }

  if (systemsError || healthError || !systemsData?.systems?.some((item) => item.id === connectorId)) {
    return (
      <AppShell title="Connector">
        <EmptyState
          variant="error"
          title="Connector not found"
          description="We could not load this connector health profile."
          action={{ label: "Back to connectors", onClick: () => router.push("/connectors") }}
        />
      </AppShell>
    )
  }

  return (
    <AppShell title={connector.name}>
      <div className="flex flex-col min-h-full">
        {/* Header */}
        <div className="border-b border-border px-4 md:px-6 py-4">
          <div className="flex flex-col gap-4 md:flex-row md:items-start md:justify-between">
            <div className="flex items-start gap-4">
              <Link 
                href="/connectors" 
                className="mt-1 p-1.5 rounded-md hover:bg-secondary transition-colors"
              >
                <ArrowLeft className="h-5 w-5 text-muted-foreground" />
              </Link>
              <div className="flex items-center gap-4">
                <ConnectorIcon 
                  vendor={connector.type}
                  status={isSyncing ? "syncing" : connector.status === "connected" ? "connected" : connector.status === "error" ? "error" : "disconnected"}
                  size="md"
                />
                <div>
                  <div className="flex items-center gap-2">
                    <h1 className="text-lg font-semibold text-foreground">{connector.name}</h1>
                    <span className={cn(
                      "text-[10px] px-2 py-0.5 rounded-full font-medium",
                      connector.environment === "production" 
                        ? "bg-emerald-500/10 text-emerald-400" 
                        : "bg-amber-500/10 text-amber-400"
                    )}>
                      {connector.environment}
                    </span>
                  </div>
                  <p className="text-sm text-muted-foreground">{connector.description}</p>
                  <div className="flex items-center gap-3 mt-1 text-xs text-muted-foreground">
                    <span>{connector.type}</span>
                    <span className="text-border">|</span>
                    <span>{connector.category}</span>
                    <span className="text-border">|</span>
                    <span>Created {connector.createdAt}</span>
                  </div>
                </div>
              </div>
            </div>
            <div className="flex items-center gap-2">
              <Button 
                variant="outline" 
                size="sm" 
                className="gap-2"
                onClick={handleSync}
                disabled={isSyncing || connector.status !== "connected"}
              >
                <RefreshCw className={cn("h-4 w-4", isSyncing && "animate-spin")} />
                {isSyncing ? "Syncing..." : "Sync Now"}
              </Button>
              <Button 
                variant="outline" 
                size="sm" 
                className="gap-2"
                onClick={() => setShowConfigDialog(true)}
              >
                <Settings className="h-4 w-4" />
                Configure
              </Button>
              <DropdownMenu>
                <DropdownMenuTrigger asChild>
                  <Button variant="outline" size="sm" className="h-8 w-8 p-0">
                    <MoreVertical className="h-4 w-4" />
                  </Button>
                </DropdownMenuTrigger>
                <DropdownMenuContent align="end">
                  <DropdownMenuItem onClick={handleToggleStatus}>
                    {connector.status === "connected" ? (
                      <><Pause className="h-4 w-4 mr-2" />Disable Connector</>
                    ) : (
                      <><Play className="h-4 w-4 mr-2" />Enable Connector</>
                    )}
                  </DropdownMenuItem>
                  <DropdownMenuItem>
                    <Download className="h-4 w-4 mr-2" />
                    Export Logs
                  </DropdownMenuItem>
                  <DropdownMenuSeparator />
                  <DropdownMenuItem 
                    className="text-destructive"
                    onClick={() => setShowDeleteDialog(true)}
                  >
                    <Trash2 className="h-4 w-4 mr-2" />
                    Remove Connector
                  </DropdownMenuItem>
                </DropdownMenuContent>
              </DropdownMenu>
            </div>
          </div>
        </div>

        {/* Main Content */}
        <div className="flex-1 p-4 md:p-6 space-y-6 overflow-auto">
          {/* Stats Overview */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <Card className="bg-card border-border">
              <CardContent className="pt-4 pb-3">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-xs text-muted-foreground">Health Score</p>
                    <p className="text-2xl font-bold text-foreground">{connector.health}%</p>
                  </div>
                  <div className={cn(
                    "h-10 w-10 rounded-full flex items-center justify-center",
                    connector.health >= 90 ? "bg-emerald-500/10" : 
                    connector.health >= 70 ? "bg-amber-500/10" : "bg-red-500/10"
                  )}>
                    <Activity className={cn(
                      "h-5 w-5",
                      connector.health >= 90 ? "text-emerald-500" : 
                      connector.health >= 70 ? "text-amber-500" : "text-red-500"
                    )} />
                  </div>
                </div>
              </CardContent>
            </Card>
            <Card className="bg-card border-border">
              <CardContent className="pt-4 pb-3">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-xs text-muted-foreground">Requests Today</p>
                    <p className="text-2xl font-bold text-foreground">{connector.requestsToday?.toLocaleString()}</p>
                  </div>
                  <div className="h-10 w-10 rounded-full flex items-center justify-center bg-blue-500/10">
                    <Zap className="h-5 w-5 text-blue-500" />
                  </div>
                </div>
                <div className="flex items-center gap-1 mt-1">
                  <TrendingUp className="h-3 w-3 text-emerald-500" />
                  <span className="text-[10px] text-emerald-500">+12% from yesterday</span>
                </div>
              </CardContent>
            </Card>
            <Card className="bg-card border-border">
              <CardContent className="pt-4 pb-3">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-xs text-muted-foreground">Avg Latency</p>
                    <p className="text-2xl font-bold text-foreground">{connector.latency}ms</p>
                  </div>
                  <div className="h-10 w-10 rounded-full flex items-center justify-center bg-violet-500/10">
                    <Clock className="h-5 w-5 text-violet-500" />
                  </div>
                </div>
                <div className="flex items-center gap-1 mt-1">
                  <TrendingDown className="h-3 w-3 text-emerald-500" />
                  <span className="text-[10px] text-emerald-500">-5ms from avg</span>
                </div>
              </CardContent>
            </Card>
            <Card className="bg-card border-border">
              <CardContent className="pt-4 pb-3">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-xs text-muted-foreground">Throughput</p>
                    <p className="text-2xl font-bold text-foreground">{connector.dataFlowRate}</p>
                  </div>
                  <div className="h-10 w-10 rounded-full flex items-center justify-center bg-amber-500/10">
                    <TrendingUp className="h-5 w-5 text-amber-500" />
                  </div>
                </div>
              </CardContent>
            </Card>
          </div>

          {/* Charts Row */}
          <div className="grid md:grid-cols-2 gap-6">
            {/* Request Volume Chart */}
            <Card className="bg-card border-border">
              <CardHeader className="pb-2">
                <CardTitle className="text-sm font-medium">Request Volume</CardTitle>
                <CardDescription className="text-xs">API requests over the last 24 hours</CardDescription>
              </CardHeader>
              <CardContent>
                <div className="h-48">
                  <ResponsiveContainer width="100%" height="100%">
                    <AreaChart data={usageData}>
                      <defs>
                        <linearGradient id="requestsGradient" x1="0" y1="0" x2="0" y2="1">
                          <stop offset="5%" stopColor="#3b82f6" stopOpacity={0.3}/>
                          <stop offset="95%" stopColor="#3b82f6" stopOpacity={0}/>
                        </linearGradient>
                      </defs>
                      <CartesianGrid strokeDasharray="3 3" stroke="#27272a" />
                      <XAxis dataKey="time" stroke="#71717a" fontSize={10} />
                      <YAxis stroke="#71717a" fontSize={10} />
                      <Tooltip 
                        contentStyle={{ 
                          backgroundColor: '#18181b', 
                          border: '1px solid #27272a',
                          borderRadius: '8px',
                          fontSize: '12px'
                        }} 
                      />
                      <Area 
                        type="monotone" 
                        dataKey="requests" 
                        stroke="#3b82f6" 
                        fill="url(#requestsGradient)" 
                        strokeWidth={2}
                      />
                    </AreaChart>
                  </ResponsiveContainer>
                </div>
              </CardContent>
            </Card>

            {/* Latency Chart */}
            <Card className="bg-card border-border">
              <CardHeader className="pb-2">
                <CardTitle className="text-sm font-medium">Latency Trends</CardTitle>
                <CardDescription className="text-xs">Response time in milliseconds</CardDescription>
              </CardHeader>
              <CardContent>
                <div className="h-48">
                  <ResponsiveContainer width="100%" height="100%">
                    <LineChart data={usageData}>
                      <CartesianGrid strokeDasharray="3 3" stroke="#27272a" />
                      <XAxis dataKey="time" stroke="#71717a" fontSize={10} />
                      <YAxis stroke="#71717a" fontSize={10} />
                      <Tooltip 
                        contentStyle={{ 
                          backgroundColor: '#18181b', 
                          border: '1px solid #27272a',
                          borderRadius: '8px',
                          fontSize: '12px'
                        }} 
                      />
                      <Line 
                        type="monotone" 
                        dataKey="latency" 
                        stroke="#8b5cf6" 
                        strokeWidth={2}
                        dot={{ fill: '#8b5cf6', strokeWidth: 0, r: 3 }}
                      />
                    </LineChart>
                  </ResponsiveContainer>
                </div>
              </CardContent>
            </Card>
          </div>

          {/* AI Integration & Activity Logs */}
          <div className="grid md:grid-cols-3 gap-6">
            {/* Connected Workflows */}
            <Card className="bg-card border-border">
              <CardHeader className="pb-2">
                <div className="flex items-center justify-between">
                  <CardTitle className="text-sm font-medium flex items-center gap-2">
                    <Workflow className="h-4 w-4 text-blue-400" />
                    Connected Workflows
                  </CardTitle>
                  <span className="text-xs text-muted-foreground">{connectedWorkflows.length} total</span>
                </div>
              </CardHeader>
              <CardContent className="space-y-2">
                {connectedWorkflows.map((workflow) => (
                  <Link 
                    key={workflow.id}
                    href={`/workflows/${workflow.id}`}
                    className="flex items-center justify-between p-2 rounded-lg bg-secondary/30 hover:bg-secondary/50 transition-colors"
                  >
                    <div className="flex items-center gap-2">
                      <div className={cn(
                        "h-2 w-2 rounded-full",
                        workflow.status === "active" ? "bg-emerald-500" : "bg-amber-500"
                      )} />
                      <span className="text-sm font-medium text-foreground">{workflow.name}</span>
                    </div>
                    <span className="text-[10px] text-muted-foreground">{workflow.runs.toLocaleString()} runs</span>
                  </Link>
                ))}
              </CardContent>
            </Card>

            {/* Connected Agents */}
            <Card className="bg-card border-border">
              <CardHeader className="pb-2">
                <div className="flex items-center justify-between">
                  <CardTitle className="text-sm font-medium flex items-center gap-2">
                    <Bot className="h-4 w-4 text-violet-400" />
                    AI Agents Using This
                  </CardTitle>
                  <span className="text-xs text-muted-foreground">{connectedAgents.length} agents</span>
                </div>
              </CardHeader>
              <CardContent className="space-y-2">
                {connectedAgents.map((agent) => (
                  <Link 
                    key={agent.id}
                    href={`/agents/${agent.id}`}
                    className="flex items-center justify-between p-2 rounded-lg bg-secondary/30 hover:bg-secondary/50 transition-colors"
                  >
                    <div>
                      <p className="text-sm font-medium text-foreground">{agent.name}</p>
                      <p className="text-[10px] text-muted-foreground">{agent.type}</p>
                    </div>
                    <span className="text-[10px] text-muted-foreground">{agent.actions} actions</span>
                  </Link>
                ))}
              </CardContent>
            </Card>

            {/* Configuration */}
            <Card className="bg-card border-border">
              <CardHeader className="pb-2">
                <CardTitle className="text-sm font-medium flex items-center gap-2">
                  <Key className="h-4 w-4 text-amber-400" />
                  Configuration
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-3">
                <div className="space-y-1.5">
                  <label className="text-[10px] uppercase tracking-wider text-muted-foreground">API Key</label>
                  <div className="flex items-center gap-2">
                    <code className="flex-1 text-xs bg-secondary px-2 py-1.5 rounded font-mono truncate">
                      {showApiKey ? connector.config.apiKey : "••••••••••••••••"}
                    </code>
                    <Button 
                      variant="ghost" 
                      size="sm" 
                      className="h-7 w-7 p-0"
                      onClick={() => setShowApiKey(!showApiKey)}
                    >
                      {showApiKey ? <EyeOff className="h-3.5 w-3.5" /> : <Eye className="h-3.5 w-3.5" />}
                    </Button>
                    <Button 
                      variant="ghost" 
                      size="sm" 
                      className="h-7 w-7 p-0"
                      onClick={() => handleCopy(connector.config.apiKey || "", "API Key")}
                    >
                      {copied === "API Key" ? <Check className="h-3.5 w-3.5 text-emerald-500" /> : <Copy className="h-3.5 w-3.5" />}
                    </Button>
                  </div>
                </div>
                <div className="space-y-1.5">
                  <label className="text-[10px] uppercase tracking-wider text-muted-foreground">Webhook URL</label>
                  <div className="flex items-center gap-2">
                    <code className="flex-1 text-xs bg-secondary px-2 py-1.5 rounded font-mono truncate">
                      {connector.config.webhookUrl}
                    </code>
                    <Button 
                      variant="ghost" 
                      size="sm" 
                      className="h-7 w-7 p-0"
                      onClick={() => handleCopy(connector.config.webhookUrl || "", "Webhook URL")}
                    >
                      {copied === "Webhook URL" ? <Check className="h-3.5 w-3.5 text-emerald-500" /> : <Copy className="h-3.5 w-3.5" />}
                    </Button>
                  </div>
                </div>
                <div className="space-y-1.5">
                  <label className="text-[10px] uppercase tracking-wider text-muted-foreground">Sync Interval</label>
                  <p className="text-sm font-medium">Every {connector.config.syncInterval}</p>
                </div>
              </CardContent>
            </Card>
          </div>

          {/* Activity Logs */}
          <Card className="bg-card border-border">
            <CardHeader className="pb-2">
              <div className="flex items-center justify-between">
                <CardTitle className="text-sm font-medium">Activity Logs</CardTitle>
                <Button variant="ghost" size="sm" className="text-xs gap-1.5">
                  <Download className="h-3.5 w-3.5" />
                  Export
                </Button>
              </div>
            </CardHeader>
            <CardContent>
              <div className="space-y-2">
                {activityLogs.map((log) => (
                  <div 
                    key={log.id}
                    className="flex items-center gap-3 p-2.5 rounded-lg bg-secondary/30 hover:bg-secondary/50 transition-colors"
                  >
                    <div className={cn(
                      "h-7 w-7 rounded-full flex items-center justify-center shrink-0",
                      log.type === "success" ? "bg-emerald-500/10" :
                      log.type === "warning" ? "bg-amber-500/10" : "bg-red-500/10"
                    )}>
                      {log.type === "success" ? (
                        <CheckCircle2 className="h-4 w-4 text-emerald-500" />
                      ) : log.type === "warning" ? (
                        <AlertTriangle className="h-4 w-4 text-amber-500" />
                      ) : (
                        <XCircle className="h-4 w-4 text-red-500" />
                      )}
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center justify-between gap-2">
                        <p className="text-sm font-medium text-foreground">{log.action}</p>
                        <span className="text-[10px] text-muted-foreground shrink-0">{log.timestamp}</span>
                      </div>
                      <p className="text-xs text-muted-foreground truncate">{log.details}</p>
                    </div>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>
        </div>

        {/* Delete Dialog */}
        <Dialog open={showDeleteDialog} onOpenChange={setShowDeleteDialog}>
          <DialogContent className="sm:max-w-md">
            <DialogHeader>
              <DialogTitle className="flex items-center gap-2 text-destructive">
                <Trash2 className="h-5 w-5" />
                Remove Connector
              </DialogTitle>
              <DialogDescription>
                This will disconnect {connector.name} and remove all associated configurations. 
                This action cannot be undone.
              </DialogDescription>
            </DialogHeader>
            <div className="py-4">
              <div className="flex items-center gap-3 p-3 rounded-lg bg-secondary/50 border border-border">
                <ConnectorIcon vendor={connector.type} size="sm" />
                <div>
                  <p className="text-sm font-medium">{connector.name}</p>
                  <p className="text-xs text-muted-foreground">{connector.type} - {connector.environment}</p>
                </div>
              </div>
            </div>
            <DialogFooter>
              <Button variant="outline" onClick={() => setShowDeleteDialog(false)}>Cancel</Button>
              <Button variant="destructive" onClick={handleDelete} className="gap-2">
                <Trash2 className="h-4 w-4" />
                Remove Connector
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>

        {/* Configure Dialog */}
        <Dialog open={showConfigDialog} onOpenChange={setShowConfigDialog}>
          <DialogContent className="sm:max-w-md">
            <DialogHeader>
              <div className="flex items-center gap-3">
                <ConnectorIcon vendor={connector.type} size="md" />
                <div>
                  <DialogTitle>{connector.name}</DialogTitle>
                  <DialogDescription>Update connector configuration</DialogDescription>
                </div>
              </div>
            </DialogHeader>
            <div className="space-y-4 py-4">
              <div className="space-y-2">
                <label className="text-sm font-medium">API Key</label>
                <div className="relative">
                  <Input 
                    type={showApiKey ? "text" : "password"} 
                    defaultValue={connector.config.apiKey}
                    className="pr-10 bg-secondary"
                  />
                  <button
                    type="button"
                    onClick={() => setShowApiKey(!showApiKey)}
                    className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
                  >
                    {showApiKey ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                  </button>
                </div>
              </div>
              <div className="space-y-2">
                <label className="text-sm font-medium">Sync Interval</label>
                <select 
                  defaultValue={connector.config.syncInterval}
                  className="w-full h-9 rounded-md border border-border bg-secondary px-3 text-sm"
                >
                  <option value="1m">Every 1 minute</option>
                  <option value="5m">Every 5 minutes</option>
                  <option value="15m">Every 15 minutes</option>
                  <option value="30m">Every 30 minutes</option>
                  <option value="1h">Every 1 hour</option>
                </select>
              </div>
            </div>
            <DialogFooter>
              <Button variant="outline" onClick={() => setShowConfigDialog(false)}>Cancel</Button>
              <Button onClick={() => {
                setShowConfigDialog(false)
                toast.success("Configuration updated")
              }}>
                Save Changes
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      </div>
    </AppShell>
  )
}
