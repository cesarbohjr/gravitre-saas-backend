"use client"

// Connectors Page - Integration Hub with Network Topology View
import { useState, useEffect } from "react"
import { motion, AnimatePresence } from "framer-motion"
import { AppShell } from "@/components/gravitre/app-shell"
import { VendorLogo } from "@/components/gravitre/vendor-logo"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { 
  Plus, 
  Search,
  RefreshCw,
  Settings,
  Trash2,
  ExternalLink,
  Zap,
  Activity,
  ArrowRight,
  Circle,
  CheckCircle2,
  XCircle,
  Loader2,
  MoreVertical,
  Eye,
  EyeOff,
  AlertTriangle,
  Wifi,
  WifiOff,
  Cable,
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
import { cn } from "@/lib/utils"

interface Connector {
  id: string
  name: string
  type: string
  status: "connected" | "disconnected" | "error" | "syncing"
  environment: "production" | "staging"
  lastSync: string
  health: number
  description: string
  dataFlowRate?: string
  requestsToday?: number
  latency?: number
  config?: {
    apiKey?: string
    webhookUrl?: string
    syncInterval?: string
  }
}

const initialConnectors: Connector[] = [
  {
    id: "1",
    name: "salesforce-api",
    type: "Salesforce",
    status: "connected",
    environment: "production",
    lastSync: "2 minutes ago",
    health: 98,
    description: "Salesforce REST API connector",
    dataFlowRate: "2.4 MB/s",
    requestsToday: 12847,
    latency: 45,
    config: { apiKey: "sf_live_xxx", syncInterval: "5m" },
  },
  {
    id: "2",
    name: "stripe-payments",
    type: "Stripe",
    status: "connected",
    environment: "production",
    lastSync: "5 minutes ago",
    health: 100,
    description: "Payment processing",
    dataFlowRate: "1.1 MB/s",
    requestsToday: 8234,
    latency: 32,
    config: { apiKey: "sk_live_xxx", syncInterval: "1m" },
  },
  {
    id: "3",
    name: "slack-notifications",
    type: "Slack",
    status: "syncing",
    environment: "production",
    lastSync: "Syncing...",
    health: 95,
    description: "Workspace notifications",
    dataFlowRate: "0.3 MB/s",
    requestsToday: 3421,
    latency: 28,
    config: { apiKey: "xoxb-xxx", syncInterval: "10m" },
  },
  {
    id: "4",
    name: "hubspot-crm",
    type: "HubSpot",
    status: "error",
    environment: "staging",
    lastSync: "1 hour ago",
    health: 0,
    description: "CRM integration (auth expired)",
    dataFlowRate: "0 MB/s",
    requestsToday: 0,
    latency: 0,
    config: { apiKey: "pat-xxx", syncInterval: "15m" },
  },
  {
    id: "5",
    name: "aws-s3-storage",
    type: "AWS S3",
    status: "connected",
    environment: "production",
    lastSync: "10 minutes ago",
    health: 100,
    description: "File storage bucket",
    dataFlowRate: "5.2 MB/s",
    requestsToday: 45892,
    latency: 18,
    config: { apiKey: "AKIA_xxx", syncInterval: "30m" },
  },
  {
    id: "6",
    name: "github-repos",
    type: "GitHub",
    status: "disconnected",
    environment: "staging",
    lastSync: "2 days ago",
    health: 0,
    description: "Repository access",
    dataFlowRate: "0 MB/s",
    requestsToday: 0,
    latency: 0,
    config: { apiKey: "ghp_xxx", syncInterval: "5m" },
  },
]

const statusConfig = {
  connected: { 
    color: "text-emerald-500", 
    bg: "bg-emerald-500", 
    ring: "ring-emerald-500/30",
    glow: "shadow-emerald-500/20",
    icon: CheckCircle2,
    label: "Connected" 
  },
  disconnected: { 
    color: "text-zinc-500", 
    bg: "bg-zinc-500", 
    ring: "ring-zinc-500/30",
    glow: "shadow-zinc-500/10",
    icon: WifiOff,
    label: "Disconnected" 
  },
  error: { 
    color: "text-red-500", 
    bg: "bg-red-500", 
    ring: "ring-red-500/30",
    glow: "shadow-red-500/20",
    icon: XCircle,
    label: "Error" 
  },
  syncing: { 
    color: "text-blue-500", 
    bg: "bg-blue-500", 
    ring: "ring-blue-500/30",
    glow: "shadow-blue-500/20",
    icon: Loader2,
    label: "Syncing" 
  },
}

// Animated Data Flow Line
function DataFlowLine({ active, direction = "right" }: { active: boolean; direction?: "right" | "left" }) {
  return (
    <div className="relative h-0.5 flex-1 bg-border/30 overflow-hidden">
      {active && (
        <motion.div
          className="absolute inset-y-0 w-8 bg-gradient-to-r from-transparent via-blue-500 to-transparent"
          animate={{ x: direction === "right" ? ["-100%", "400%"] : ["400%", "-100%"] }}
          transition={{ duration: 2, repeat: Infinity, ease: "linear" }}
        />
      )}
    </div>
  )
}

// Central Hub Node
function CentralHub({ connectedCount, totalCount }: { connectedCount: number; totalCount: number }) {
  return (
    <div className="relative">
      {/* Outer glow rings */}
      <div className="absolute inset-0 rounded-full bg-blue-500/10 animate-ping" style={{ animationDuration: "3s" }} />
      <div className="absolute -inset-2 rounded-full bg-gradient-to-br from-blue-500/20 to-violet-500/20 blur-xl" />
      
      {/* Main hub */}
      <div className="relative flex h-32 w-32 items-center justify-center rounded-full bg-gradient-to-br from-card to-secondary border-2 border-blue-500/30 shadow-2xl shadow-blue-500/10">
        <div className="text-center">
          <Cable className="h-8 w-8 text-blue-400 mx-auto mb-1" />
          <div className="text-2xl font-bold text-foreground">{connectedCount}</div>
          <div className="text-[10px] text-muted-foreground uppercase tracking-wider">of {totalCount} Active</div>
        </div>
      </div>
    </div>
  )
}

// Connector Node in topology view
function ConnectorNode({ 
  connector, 
  position,
  onConfigure,
  onSync,
  onDelete,
}: { 
  connector: Connector
  position: "left" | "right"
  onConfigure: () => void
  onSync: () => void
  onDelete: () => void
}) {
  const [isHovered, setIsHovered] = useState(false)
  const [isSyncing, setIsSyncing] = useState(connector.status === "syncing")
  const config = statusConfig[connector.status]
  const StatusIcon = config.icon

  const handleSync = async () => {
    setIsSyncing(true)
    await new Promise((resolve) => setTimeout(resolve, 2000))
    setIsSyncing(false)
    onSync()
  }

  return (
    <motion.div
      initial={{ opacity: 0, x: position === "left" ? -20 : 20 }}
      animate={{ opacity: 1, x: 0 }}
      className={cn(
        "relative group",
        position === "left" ? "flex-row-reverse" : "flex-row"
      )}
      onMouseEnter={() => setIsHovered(true)}
      onMouseLeave={() => setIsHovered(false)}
    >
      {/* Connection line */}
      <div className={cn(
        "flex items-center gap-2",
        position === "left" ? "flex-row-reverse" : "flex-row"
      )}>
        {/* Node */}
        <div className={cn(
          "relative rounded-xl border bg-card p-3 md:p-4 transition-all duration-300 w-full md:min-w-[240px]",
          isHovered ? "border-foreground/20 shadow-lg" : "border-border",
          connector.status === "connected" && "shadow-emerald-500/5",
          connector.status === "error" && "shadow-red-500/5 border-red-500/30"
        )}>
          {/* Status indicator */}
          <div className={cn(
            "absolute -top-1.5 -right-1.5 h-4 w-4 rounded-full flex items-center justify-center ring-4 ring-card",
            config.bg
          )}>
            {isSyncing ? (
              <Loader2 className="h-2.5 w-2.5 text-white animate-spin" />
            ) : (
              <div className="h-1.5 w-1.5 rounded-full bg-white" />
            )}
          </div>

          {/* Header */}
          <div className="flex items-start justify-between mb-3">
            <div className="flex items-center gap-3">
              <div className={cn(
                "rounded-lg p-2 ring-1",
                config.ring,
                connector.status === "connected" ? "bg-emerald-500/10" : 
                connector.status === "error" ? "bg-red-500/10" : "bg-secondary"
              )}>
                <VendorLogo vendor={connector.type} size="sm" />
              </div>
              <div>
                <h3 className="text-sm font-medium text-foreground">{connector.name}</h3>
                <p className="text-[10px] text-muted-foreground">{connector.type}</p>
              </div>
            </div>
            
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <Button variant="ghost" size="icon" className="h-6 w-6 opacity-0 group-hover:opacity-100 transition-opacity">
                  <MoreVertical className="h-3.5 w-3.5" />
                </Button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end" className="w-36">
                <DropdownMenuItem onClick={onConfigure}>
                  <Settings className="h-3.5 w-3.5 mr-2" />
                  Configure
                </DropdownMenuItem>
                <DropdownMenuItem onClick={handleSync} disabled={isSyncing}>
                  <RefreshCw className={cn("h-3.5 w-3.5 mr-2", isSyncing && "animate-spin")} />
                  Sync Now
                </DropdownMenuItem>
                <DropdownMenuSeparator />
                <DropdownMenuItem onClick={onDelete} className="text-destructive">
                  <Trash2 className="h-3.5 w-3.5 mr-2" />
                  Remove
                </DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>
          </div>

          {/* Live metrics */}
          <div className="grid grid-cols-3 gap-2 p-2 rounded-lg bg-secondary/50 mb-3">
            <div className="text-center">
              <div className="text-xs font-medium text-foreground">{connector.dataFlowRate}</div>
              <div className="text-[9px] text-muted-foreground">Throughput</div>
            </div>
            <div className="text-center border-x border-border/50">
              <div className="text-xs font-medium text-foreground">{connector.latency}ms</div>
              <div className="text-[9px] text-muted-foreground">Latency</div>
            </div>
            <div className="text-center">
              <div className="text-xs font-medium text-foreground">{(connector.requestsToday || 0).toLocaleString()}</div>
              <div className="text-[9px] text-muted-foreground">Requests</div>
            </div>
          </div>

          {/* Footer */}
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-1.5">
              <StatusIcon className={cn("h-3 w-3", config.color, isSyncing && "animate-spin")} />
              <span className={cn("text-[10px] font-medium", config.color)}>
                {isSyncing ? "Syncing..." : config.label}
              </span>
            </div>
            <span className={cn(
              "text-[10px] px-1.5 py-0.5 rounded",
              connector.environment === "production" 
                ? "bg-emerald-500/10 text-emerald-400" 
                : "bg-amber-500/10 text-amber-400"
            )}>
              {connector.environment}
            </span>
          </div>
        </div>

        {/* Data flow line - hidden on mobile */}
        <div className="hidden md:flex w-16 items-center">
          <DataFlowLine active={connector.status === "connected" || connector.status === "syncing"} direction={position === "left" ? "right" : "left"} />
        </div>
      </div>
    </motion.div>
  )
}

// Configure Modal
function ConfigureModal({
  connector,
  open,
  onClose,
  onSave,
}: {
  connector: Connector
  open: boolean
  onClose: () => void
  onSave: (config: Connector["config"]) => void
}) {
  const [config, setConfig] = useState(connector.config || {})
  const [showApiKey, setShowApiKey] = useState(false)
  const [isSaving, setIsSaving] = useState(false)

  const handleSave = async () => {
    setIsSaving(true)
    await new Promise((resolve) => setTimeout(resolve, 800))
    onSave(config)
    setIsSaving(false)
    onClose()
  }

  return (
    <Dialog open={open} onOpenChange={onClose}>
      <DialogContent className="sm:max-w-md bg-card border-border">
        <DialogHeader>
          <div className="flex items-center gap-3">
            <VendorLogo vendor={connector.type} size="md" />
            <div>
              <DialogTitle>{connector.name}</DialogTitle>
              <DialogDescription>{connector.type} Configuration</DialogDescription>
            </div>
          </div>
        </DialogHeader>
        <div className="space-y-4 py-4">
          <div className="space-y-2">
            <label className="text-xs font-medium text-muted-foreground uppercase tracking-wide">API Key</label>
            <div className="relative">
              <Input
                type={showApiKey ? "text" : "password"}
                value={config.apiKey || ""}
                onChange={(e) => setConfig({ ...config, apiKey: e.target.value })}
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
            <label className="text-xs font-medium text-muted-foreground uppercase tracking-wide">Sync Interval</label>
            <select
              value={config.syncInterval || "5m"}
              onChange={(e) => setConfig({ ...config, syncInterval: e.target.value })}
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
          <Button variant="outline" onClick={onClose}>Cancel</Button>
          <Button onClick={handleSave} disabled={isSaving}>
            {isSaving ? <><Loader2 className="h-4 w-4 mr-2 animate-spin" />Saving...</> : "Save Changes"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

// Delete Modal
function DeleteModal({
  connector,
  open,
  onClose,
  onConfirm,
}: {
  connector: Connector
  open: boolean
  onClose: () => void
  onConfirm: () => void
}) {
  const [confirmText, setConfirmText] = useState("")
  const [isDeleting, setIsDeleting] = useState(false)

  const handleDelete = async () => {
    setIsDeleting(true)
    await new Promise((resolve) => setTimeout(resolve, 800))
    onConfirm()
    setIsDeleting(false)
    onClose()
  }

  return (
    <Dialog open={open} onOpenChange={onClose}>
      <DialogContent className="sm:max-w-md bg-card border-border">
        <DialogHeader>
          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-full bg-destructive/10">
              <AlertTriangle className="h-5 w-5 text-destructive" />
            </div>
            <div>
              <DialogTitle>Remove Connector</DialogTitle>
              <DialogDescription>This cannot be undone</DialogDescription>
            </div>
          </div>
        </DialogHeader>
        <div className="py-4 space-y-4">
          <p className="text-sm text-muted-foreground">
            Type <span className="font-mono text-foreground">{connector.name}</span> to confirm removal.
          </p>
          <Input
            value={confirmText}
            onChange={(e) => setConfirmText(e.target.value)}
            placeholder={connector.name}
            className="bg-secondary"
          />
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={onClose}>Cancel</Button>
          <Button variant="destructive" onClick={handleDelete} disabled={confirmText !== connector.name || isDeleting}>
            {isDeleting ? <><Loader2 className="h-4 w-4 mr-2 animate-spin" />Removing...</> : "Remove"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

// Available connector types for adding
const availableConnectors = [
  { type: "Salesforce", description: "CRM and sales platform", category: "CRM" },
  { type: "Stripe", description: "Payment processing", category: "Payments" },
  { type: "Slack", description: "Team communication", category: "Communication" },
  { type: "HubSpot", description: "Marketing and CRM", category: "CRM" },
  { type: "AWS S3", description: "Cloud storage", category: "Storage" },
  { type: "GitHub", description: "Code repositories", category: "Development" },
  { type: "Snowflake", description: "Data warehouse", category: "Data" },
  { type: "PostgreSQL", description: "Database", category: "Database" },
  { type: "MongoDB", description: "NoSQL database", category: "Database" },
  { type: "Zendesk", description: "Customer support", category: "Support" },
  { type: "Jira", description: "Project management", category: "Development" },
  { type: "Google Sheets", description: "Spreadsheets", category: "Productivity" },
]

// Add Connector Modal
function AddConnectorModal({
  open,
  onClose,
  onAdd,
}: {
  open: boolean
  onClose: () => void
  onAdd: (connector: Connector) => void
}) {
  const [step, setStep] = useState<"select" | "configure">("select")
  const [selectedType, setSelectedType] = useState<string | null>(null)
  const [name, setName] = useState("")
  const [apiKey, setApiKey] = useState("")
  const [environment, setEnvironment] = useState<"production" | "staging">("staging")
  const [isConnecting, setIsConnecting] = useState(false)
  const [searchQuery, setSearchQuery] = useState("")

  const filteredConnectors = availableConnectors.filter(
    (c) =>
      c.type.toLowerCase().includes(searchQuery.toLowerCase()) ||
      c.description.toLowerCase().includes(searchQuery.toLowerCase()) ||
      c.category.toLowerCase().includes(searchQuery.toLowerCase())
  )

  const groupedConnectors = filteredConnectors.reduce((acc, c) => {
    if (!acc[c.category]) acc[c.category] = []
    acc[c.category].push(c)
    return acc
  }, {} as Record<string, typeof availableConnectors>)

  const handleConnect = async () => {
    if (!selectedType || !name || !apiKey) return
    
    setIsConnecting(true)
    await new Promise((resolve) => setTimeout(resolve, 1500))
    
    const newConnector: Connector = {
      id: `new-${Date.now()}`,
      name: name.toLowerCase().replace(/\s+/g, "-"),
      type: selectedType,
      status: "connected",
      environment,
      lastSync: "Just now",
      health: 100,
      description: availableConnectors.find((c) => c.type === selectedType)?.description || "",
      dataFlowRate: "0 MB/s",
      requestsToday: 0,
      latency: 0,
      config: { apiKey, syncInterval: "5m" },
    }
    
    onAdd(newConnector)
    setIsConnecting(false)
    handleClose()
  }

  const handleClose = () => {
    setStep("select")
    setSelectedType(null)
    setName("")
    setApiKey("")
    setEnvironment("staging")
    setSearchQuery("")
    onClose()
  }

  return (
    <Dialog open={open} onOpenChange={handleClose}>
      <DialogContent className="sm:max-w-2xl bg-card border-border max-h-[85vh] overflow-hidden flex flex-col">
        <DialogHeader>
          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-gradient-to-br from-blue-500/20 to-violet-500/20 ring-1 ring-blue-500/20">
              <Plus className="h-5 w-5 text-blue-400" />
            </div>
            <div>
              <DialogTitle>
                {step === "select" ? "Add Connector" : `Configure ${selectedType}`}
              </DialogTitle>
              <DialogDescription>
                {step === "select" 
                  ? "Choose a connector type to integrate with your workflows" 
                  : "Enter the credentials and settings for this connector"
                }
              </DialogDescription>
            </div>
          </div>
        </DialogHeader>

        <AnimatePresence mode="wait">
          {step === "select" ? (
            <motion.div
              key="select"
              initial={{ opacity: 0, x: -20 }}
              animate={{ opacity: 1, x: 0 }}
              exit={{ opacity: 0, x: -20 }}
              className="flex-1 overflow-hidden flex flex-col"
            >
              {/* Search */}
              <div className="relative mb-4">
                <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
                <Input
                  placeholder="Search connectors..."
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  className="pl-9 bg-secondary"
                />
              </div>

              {/* Connector Grid */}
              <div className="flex-1 overflow-y-auto pr-2 -mr-2 space-y-4">
                {Object.entries(groupedConnectors).map(([category, connectors]) => (
                  <div key={category}>
                    <h4 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground mb-2">
                      {category}
                    </h4>
                    <div className="grid grid-cols-2 gap-2">
                      {connectors.map((connector) => (
                        <button
                          key={connector.type}
                          onClick={() => {
                            setSelectedType(connector.type)
                            setName(connector.type.toLowerCase().replace(/\s+/g, "-"))
                            setStep("configure")
                          }}
                          className={cn(
                            "flex items-center gap-3 rounded-lg border border-border bg-secondary/30 p-3 text-left transition-all hover:border-blue-500/30 hover:bg-blue-500/5",
                            selectedType === connector.type && "border-blue-500 bg-blue-500/10"
                          )}
                        >
                          <div className="rounded-lg bg-card p-2 ring-1 ring-border">
                            <VendorLogo vendor={connector.type} size="sm" />
                          </div>
                          <div className="min-w-0 flex-1">
                            <div className="text-sm font-medium text-foreground">{connector.type}</div>
                            <div className="text-xs text-muted-foreground truncate">{connector.description}</div>
                          </div>
                          <ArrowRight className="h-4 w-4 text-muted-foreground opacity-0 group-hover:opacity-100" />
                        </button>
                      ))}
                    </div>
                  </div>
                ))}
              </div>
            </motion.div>
          ) : (
            <motion.div
              key="configure"
              initial={{ opacity: 0, x: 20 }}
              animate={{ opacity: 1, x: 0 }}
              exit={{ opacity: 0, x: 20 }}
              className="space-y-4 py-2"
            >
              {/* Selected Connector Preview */}
              <div className="flex items-center gap-3 rounded-lg border border-border bg-secondary/30 p-3">
                <div className="rounded-lg bg-card p-2 ring-1 ring-border">
                  <VendorLogo vendor={selectedType || ""} size="sm" />
                </div>
                <div>
                  <div className="text-sm font-medium text-foreground">{selectedType}</div>
                  <div className="text-xs text-muted-foreground">
                    {availableConnectors.find((c) => c.type === selectedType)?.description}
                  </div>
                </div>
                <Button
                  variant="ghost"
                  size="sm"
                  className="ml-auto text-xs"
                  onClick={() => setStep("select")}
                >
                  Change
                </Button>
              </div>

              {/* Configuration Form */}
              <div className="space-y-4">
                <div className="space-y-2">
                  <label className="text-sm font-medium text-foreground">Connector Name</label>
                  <Input
                    value={name}
                    onChange={(e) => setName(e.target.value)}
                    placeholder="my-salesforce-connector"
                    className="bg-secondary"
                  />
                  <p className="text-xs text-muted-foreground">
                    A unique identifier for this connector
                  </p>
                </div>

                <div className="space-y-2">
                  <label className="text-sm font-medium text-foreground">API Key / Credentials</label>
                  <div className="relative">
                    <Input
                      type="password"
                      value={apiKey}
                      onChange={(e) => setApiKey(e.target.value)}
                      placeholder="Enter your API key"
                      className="bg-secondary pr-10"
                    />
                    <Eye className="absolute right-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
                  </div>
                  <p className="text-xs text-muted-foreground">
                    Your {selectedType} API key or access token
                  </p>
                </div>

                <div className="space-y-2">
                  <label className="text-sm font-medium text-foreground">Environment</label>
                  <div className="flex gap-2">
                    <button
                      onClick={() => setEnvironment("staging")}
                      className={cn(
                        "flex-1 rounded-lg border px-4 py-2.5 text-sm font-medium transition-all",
                        environment === "staging"
                          ? "border-amber-500/50 bg-amber-500/10 text-amber-400"
                          : "border-border bg-secondary text-muted-foreground hover:text-foreground"
                      )}
                    >
                      <Circle className={cn("h-2 w-2 inline mr-2", environment === "staging" ? "fill-amber-500 text-amber-500" : "fill-muted-foreground text-muted-foreground")} />
                      Staging
                    </button>
                    <button
                      onClick={() => setEnvironment("production")}
                      className={cn(
                        "flex-1 rounded-lg border px-4 py-2.5 text-sm font-medium transition-all",
                        environment === "production"
                          ? "border-emerald-500/50 bg-emerald-500/10 text-emerald-400"
                          : "border-border bg-secondary text-muted-foreground hover:text-foreground"
                      )}
                    >
                      <Circle className={cn("h-2 w-2 inline mr-2", environment === "production" ? "fill-emerald-500 text-emerald-500" : "fill-muted-foreground text-muted-foreground")} />
                      Production
                    </button>
                  </div>
                </div>
              </div>
            </motion.div>
          )}
        </AnimatePresence>

        <DialogFooter className="mt-4 pt-4 border-t border-border">
          <Button variant="outline" onClick={handleClose}>Cancel</Button>
          {step === "configure" && (
            <Button 
              onClick={handleConnect} 
              disabled={!name || !apiKey || isConnecting}
              className="gap-2"
            >
              {isConnecting ? (
                <>
                  <Loader2 className="h-4 w-4 animate-spin" />
                  Connecting...
                </>
              ) : (
                <>
                  <Wifi className="h-4 w-4" />
                  Connect
                </>
              )}
            </Button>
          )}
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

export default function ConnectorsPage() {
  const [connectors, setConnectors] = useState(initialConnectors)
  const [searchQuery, setSearchQuery] = useState("")
  const [configureModal, setConfigureModal] = useState<Connector | null>(null)
  const [deleteModal, setDeleteModal] = useState<Connector | null>(null)
  const [addModal, setAddModal] = useState(false)

  const filteredConnectors = connectors.filter((c) =>
    c.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
    c.type.toLowerCase().includes(searchQuery.toLowerCase())
  )

  const leftConnectors = filteredConnectors.filter((_, i) => i % 2 === 0)
  const rightConnectors = filteredConnectors.filter((_, i) => i % 2 === 1)

  const connectedCount = connectors.filter((c) => c.status === "connected").length
  const totalRequests = connectors.reduce((sum, c) => sum + (c.requestsToday || 0), 0)
  const avgLatency = Math.round(
    connectors.filter((c) => c.latency).reduce((sum, c) => sum + (c.latency || 0), 0) /
    connectors.filter((c) => c.latency).length || 0
  )

  return (
    <AppShell title="Connectors">
      <div className="flex flex-col min-h-full">
        {/* Header */}
        <div className="border-b border-border px-4 md:px-6 py-4">
          <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
            <div className="flex items-center gap-3 md:gap-4">
              <div className="flex h-9 w-9 md:h-10 md:w-10 items-center justify-center rounded-xl bg-gradient-to-br from-blue-500/20 to-violet-500/20 ring-1 ring-blue-500/20">
                <Cable className="h-4 w-4 md:h-5 md:w-5 text-blue-400" />
              </div>
              <div>
                <h1 className="text-base md:text-lg font-semibold text-foreground">Integration Hub</h1>
                <p className="text-xs md:text-sm text-muted-foreground">Connect and manage your data sources</p>
              </div>
            </div>
            <div className="flex items-center gap-2 md:gap-3">
              <div className="relative flex-1 md:flex-none">
                <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
                <Input
                  placeholder="Search connectors..."
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  className="w-full md:w-64 pl-9 bg-secondary"
                />
              </div>
              <Button onClick={() => setAddModal(true)} className="gap-2 shrink-0">
                <Plus className="h-4 w-4" />
                <span className="hidden sm:inline">Add Connector</span>
              </Button>
            </div>
          </div>
        </div>

        {/* Live Stats Bar */}
        <div className="border-b border-border bg-secondary/30 px-4 md:px-6 py-3">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div className="flex flex-wrap items-center gap-4 md:gap-8">
              <div className="flex items-center gap-2">
                <div className="h-2 w-2 rounded-full bg-emerald-500 animate-pulse" />
                <span className="text-xs md:text-sm text-muted-foreground">
                  <span className="font-medium text-foreground">{connectedCount}</span> connected
                </span>
              </div>
              <div className="flex items-center gap-2">
                <Zap className="h-3.5 w-3.5 text-amber-500" />
                <span className="text-xs md:text-sm text-muted-foreground">
                  <span className="font-medium text-foreground">{totalRequests.toLocaleString()}</span> <span className="hidden sm:inline">requests</span> today
                </span>
              </div>
              <div className="flex items-center gap-2">
                <Activity className="h-3.5 w-3.5 text-blue-500" />
                <span className="text-xs md:text-sm text-muted-foreground">
                  <span className="font-medium text-foreground">{avgLatency}ms</span> <span className="hidden sm:inline">avg</span> latency
                </span>
              </div>
            </div>
            <div className="hidden md:flex items-center gap-2 text-xs text-muted-foreground">
              <div className="h-1.5 w-1.5 rounded-full bg-emerald-500 animate-pulse" />
              Live monitoring active
            </div>
          </div>
        </div>

        {/* Network Topology View */}
        <div className="flex-1 p-4 md:p-6 overflow-auto">
          {/* Mobile: Card list view */}
          <div className="md:hidden space-y-4">
            {/* Mobile Hub Summary */}
            <div className="flex items-center justify-center py-4">
              <div className="relative">
                <div className="absolute -inset-2 rounded-full bg-gradient-to-br from-blue-500/20 to-violet-500/20 blur-lg" />
                <div className="relative flex h-20 w-20 items-center justify-center rounded-full bg-gradient-to-br from-card to-secondary border-2 border-blue-500/30 shadow-xl">
                  <div className="text-center">
                    <Cable className="h-5 w-5 text-blue-400 mx-auto mb-0.5" />
                    <div className="text-lg font-bold text-foreground">{connectedCount}</div>
                    <div className="text-[8px] text-muted-foreground uppercase tracking-wider">of {connectors.length}</div>
                  </div>
                </div>
              </div>
            </div>
            
            {/* Mobile connector cards */}
            <div className="space-y-3">
              {filteredConnectors.map((connector) => (
                <ConnectorNode
                  key={connector.id}
                  connector={connector}
                  position="right"
                  onConfigure={() => setConfigureModal(connector)}
                  onSync={() => {}}
                  onDelete={() => setDeleteModal(connector)}
                />
              ))}
            </div>
          </div>

          {/* Desktop: Network topology view */}
          <div className="hidden md:block relative min-h-[600px]">
            <div className="flex items-center justify-center">
              {/* Left column */}
              <div className="flex flex-col gap-4 mr-8">
                {leftConnectors.map((connector) => (
                  <ConnectorNode
                    key={connector.id}
                    connector={connector}
                    position="left"
                    onConfigure={() => setConfigureModal(connector)}
                    onSync={() => {}}
                    onDelete={() => setDeleteModal(connector)}
                  />
                ))}
              </div>

              {/* Central Hub */}
              <CentralHub connectedCount={connectedCount} totalCount={connectors.length} />

              {/* Right column */}
              <div className="flex flex-col gap-4 ml-8">
                {rightConnectors.map((connector) => (
                  <ConnectorNode
                    key={connector.id}
                    connector={connector}
                    position="right"
                    onConfigure={() => setConfigureModal(connector)}
                    onSync={() => {}}
                    onDelete={() => setDeleteModal(connector)}
                  />
                ))}
              </div>
            </div>
          </div>
        </div>

        {/* Modals */}
        {configureModal && (
          <ConfigureModal
            connector={configureModal}
            open={!!configureModal}
            onClose={() => setConfigureModal(null)}
            onSave={(config) => {
              setConnectors((prev) =>
                prev.map((c) => (c.id === configureModal.id ? { ...c, config } : c))
              )
            }}
          />
        )}
        {deleteModal && (
          <DeleteModal
            connector={deleteModal}
            open={!!deleteModal}
            onClose={() => setDeleteModal(null)}
            onConfirm={() => {
              setConnectors((prev) => prev.filter((c) => c.id !== deleteModal.id))
            }}
          />
        )}
        <AddConnectorModal
          open={addModal}
          onClose={() => setAddModal(false)}
          onAdd={(newConnector) => {
            setConnectors((prev) => [...prev, newConnector])
          }}
        />
      </div>
    </AppShell>
  )
}
