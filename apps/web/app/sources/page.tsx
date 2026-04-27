"use client"

import { useState } from "react"
import useSWR from "swr"
import { useRouter } from "next/navigation"
import { motion, AnimatePresence } from "framer-motion"
import { AppShell } from "@/components/gravitre/app-shell"
import { StatusBadge } from "@/components/gravitre/status-badge"
import {
  MorphingBackground,
  GlowOrb,
  NeuralNetwork,
  DataStream,
  StatusBeacon,
  AnimatedCounter,
  GridPattern
} from "@/components/gravitre/premium-effects"
import { Button } from "@/components/ui/button"
import { cn } from "@/lib/utils"
import { 
  Plus, 
  Database, 
  Server,
  HardDrive,
  Cloud,
  Workflow,
  Bot,
  RefreshCw,
  Activity,
  Layers,
  CircleDot,
  ArrowRight,
  ChevronDown,
  Check,
  Loader2,
  ExternalLink,
  Zap,
  Table2,
  Clock,
  TrendingUp,
  Sparkles
} from "lucide-react"
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { fetcher as apiFetcher } from "@/lib/fetcher"

interface Source {
  id: string
  name: string
  type: string
  category: "sql" | "nosql" | "warehouse"
  status: "connected" | "disconnected" | "error" | "syncing"
  environment: "production" | "staging"
  lastSync: string
  tables: number
  records: string
  description: string
  workflowsUsing: number
  operatorsUsing: number
  health: number // 0-100
  topTables?: string[]
}

const fallbackSources: Source[] = [
  {
    id: "1",
    name: "postgres-primary",
    type: "PostgreSQL",
    category: "sql",
    status: "connected",
    environment: "production",
    lastSync: "2 minutes ago",
    tables: 42,
    records: "2.4M",
    description: "Primary PostgreSQL database for customer data",
    workflowsUsing: 8,
    operatorsUsing: 3,
    health: 98,
    topTables: ["users", "orders", "products", "transactions"],
  },
  {
    id: "2",
    name: "mysql-analytics",
    type: "MySQL",
    category: "sql",
    status: "connected",
    environment: "production",
    lastSync: "5 minutes ago",
    tables: 18,
    records: "890K",
    description: "MySQL analytics database",
    workflowsUsing: 4,
    operatorsUsing: 2,
    health: 95,
    topTables: ["events", "sessions", "pageviews"],
  },
  {
    id: "3",
    name: "mongodb-events",
    type: "MongoDB",
    category: "nosql",
    status: "syncing",
    environment: "production",
    lastSync: "Syncing...",
    tables: 8,
    records: "12.1M",
    description: "MongoDB event store for real-time data",
    workflowsUsing: 6,
    operatorsUsing: 2,
    health: 100,
    topTables: ["events", "logs", "metrics"],
  },
  {
    id: "4",
    name: "snowflake-dw",
    type: "Snowflake",
    category: "warehouse",
    status: "connected",
    environment: "production",
    lastSync: "15 minutes ago",
    tables: 156,
    records: "45.2M",
    description: "Snowflake data warehouse for reporting",
    workflowsUsing: 12,
    operatorsUsing: 4,
    health: 92,
    topTables: ["fact_sales", "dim_customers", "fact_orders"],
  },
  {
    id: "5",
    name: "postgres-staging",
    type: "PostgreSQL",
    category: "sql",
    status: "error",
    environment: "staging",
    lastSync: "1 hour ago",
    tables: 42,
    records: "120K",
    description: "Staging PostgreSQL replica (connection timeout)",
    workflowsUsing: 2,
    operatorsUsing: 1,
    health: 0,
    topTables: ["users", "orders"],
  },
  {
    id: "6",
    name: "bigquery-ml",
    type: "BigQuery",
    category: "warehouse",
    status: "disconnected",
    environment: "staging",
    lastSync: "2 days ago",
    tables: 24,
    records: "8.5M",
    description: "BigQuery for ML training datasets",
    workflowsUsing: 3,
    operatorsUsing: 1,
    health: 0,
    topTables: ["training_data", "features"],
  },
]

function inferCategory(type: string): Source["category"] {
  const normalized = type.toLowerCase()
  if (normalized.includes("postgres") || normalized.includes("mysql")) return "sql"
  if (normalized.includes("mongo")) return "nosql"
  return "warehouse"
}

function formatRelativeSync(iso: string | null | undefined): string {
  if (!iso) return "Never"
  const timestamp = new Date(iso)
  if (Number.isNaN(timestamp.getTime())) return "Never"
  const diffMs = Date.now() - timestamp.getTime()
  const minutes = Math.max(0, Math.floor(diffMs / 60000))
  if (minutes < 1) return "Just now"
  if (minutes < 60) return `${minutes} minute${minutes === 1 ? "" : "s"} ago`
  const hours = Math.floor(minutes / 60)
  if (hours < 24) return `${hours} hour${hours === 1 ? "" : "s"} ago`
  const days = Math.floor(hours / 24)
  return `${days} day${days === 1 ? "" : "s"} ago`
}

function formatCompactCount(value: number): string {
  if (!Number.isFinite(value) || value <= 0) return "0"
  if (value >= 1_000_000) return `${(value / 1_000_000).toFixed(1)}M`
  if (value >= 1_000) return `${(value / 1_000).toFixed(1)}K`
  return String(value)
}

function normalizeSource(input: Record<string, unknown>): Source {
  const status = String(input.status ?? "connected")
  const type = String(input.type ?? "Unknown")
  const rawRecordCount = Number(input.recordCount ?? input.record_count ?? 0)
  const stringRecords = String(input.records ?? "")
  const parsedStringRecords = Number.parseFloat(stringRecords.replace(/[^\d.]/g, ""))
  const recordsFromString = stringRecords.includes("M")
    ? parsedStringRecords * 1_000_000
    : stringRecords.includes("K")
    ? parsedStringRecords * 1_000
    : parsedStringRecords
  const effectiveRecordCount =
    Number.isFinite(rawRecordCount) && rawRecordCount > 0
      ? rawRecordCount
      : Number.isFinite(recordsFromString)
      ? recordsFromString
      : 0
  const environment = String(input.environment ?? "production")
  return {
    id: String(input.id ?? ""),
    name: String(input.name ?? "source"),
    type,
    category:
      input.category === "sql" || input.category === "nosql" || input.category === "warehouse"
        ? input.category
        : inferCategory(type),
    status:
      status === "disconnected" || status === "error" || status === "syncing"
        ? status
        : "connected",
    environment: environment === "staging" ? "staging" : "production",
    lastSync: formatRelativeSync((input.lastSync as string | null) ?? (input.last_sync as string | null)),
    tables: Number(input.tables ?? 0),
    records: formatCompactCount(effectiveRecordCount),
    description: String(input.description ?? `${type} data source`),
    workflowsUsing: Number(input.workflowsUsing ?? input.workflows_using ?? 0),
    operatorsUsing: Number(input.operatorsUsing ?? input.operators_using ?? 0),
    health:
      Number.isFinite(Number(input.health)) && Number(input.health) > 0
        ? Number(input.health)
        : status === "error" || status === "disconnected"
        ? 0
        : status === "syncing"
        ? 85
        : 98,
    topTables: Array.isArray(input.topTables) ? (input.topTables as string[]) : [],
  }
}

function normalizeSourcesResponse(payload: unknown): Source[] {
  if (!payload || typeof payload !== "object") return fallbackSources
  const model = payload as Record<string, unknown>
  const raw = Array.isArray(model.sources) ? model.sources : null
  if (!raw) return fallbackSources
  const normalized = raw
    .filter((item): item is Record<string, unknown> => Boolean(item) && typeof item === "object")
    .map((item) => normalizeSource(item))
    .filter((item) => item.id.length > 0)
  return normalized.length > 0 ? normalized : fallbackSources
}

const typeConfig: Record<string, { icon: typeof Database; color: string; bgColor: string }> = {
  PostgreSQL: { icon: Database, color: "text-blue-400", bgColor: "bg-blue-500/20" },
  MySQL: { icon: Database, color: "text-orange-400", bgColor: "bg-orange-500/20" },
  MongoDB: { icon: HardDrive, color: "text-green-400", bgColor: "bg-green-500/20" },
  Snowflake: { icon: Cloud, color: "text-cyan-400", bgColor: "bg-cyan-500/20" },
  BigQuery: { icon: Server, color: "text-yellow-400", bgColor: "bg-yellow-500/20" },
}

const categoryLabels = {
  sql: "SQL Databases",
  nosql: "NoSQL",
  warehouse: "Data Warehouses",
}

// Health ring component
function HealthRing({ health, size = 40 }: { health: number; size?: number }) {
  const radius = (size - 4) / 2
  const circumference = 2 * Math.PI * radius
  const offset = circumference - (health / 100) * circumference
  
  const color = health >= 90 ? "stroke-emerald-500" : health >= 70 ? "stroke-amber-500" : "stroke-red-500"
  
  return (
    <div className="relative" style={{ width: size, height: size }}>
      <svg className="transform -rotate-90" width={size} height={size}>
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          strokeWidth={3}
          fill="none"
          className="stroke-secondary"
        />
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          strokeWidth={3}
          fill="none"
          strokeLinecap="round"
          strokeDasharray={circumference}
          strokeDashoffset={offset}
          className={cn("transition-all duration-500", color)}
        />
      </svg>
      <span className="absolute inset-0 flex items-center justify-center text-[10px] font-medium text-foreground">
        {health}%
      </span>
    </div>
  )
}

// Data source tile with hierarchy preview - Premium
function SourceTile({ 
  source, 
  isExpanded,
  onToggle,
  index
}: { 
  source: Source
  isExpanded: boolean
  onToggle: () => void
  index: number
}) {
  const router = useRouter()
  const config = typeConfig[source.type] || { icon: Database, color: "text-muted-foreground", bgColor: "bg-secondary" }
  const TypeIcon = config.icon

  return (
    <motion.div
      layout
      initial={{ opacity: 0, y: 20, scale: 0.95 }}
      animate={{ opacity: 1, y: 0, scale: 1 }}
      transition={{ delay: index * 0.05, type: "spring", stiffness: 100 }}
      whileHover={{ y: -4, scale: 1.02 }}
      className={cn(
        "group relative rounded-2xl border transition-all duration-300 overflow-hidden",
        source.status === "error" 
          ? "border-red-500/30 bg-gradient-to-br from-red-500/5 via-card to-card" 
          : "border-border/50 bg-card/50 backdrop-blur-sm hover:border-primary/30 hover:shadow-xl hover:shadow-primary/5",
        source.status === "syncing" && "border-blue-500/30",
        source.status === "connected" && "ring-1 ring-emerald-500/10"
      )}
    >
      {/* Top accent gradient */}
      <div className={cn(
        "absolute top-0 left-0 right-0 h-1",
        source.status === "connected" && "bg-gradient-to-r from-emerald-500 via-emerald-400 to-emerald-500",
        source.status === "syncing" && "bg-gradient-to-r from-blue-500 via-cyan-400 to-blue-500",
        source.status === "error" && "bg-gradient-to-r from-red-500 via-red-400 to-red-500",
        source.status === "disconnected" && "bg-gradient-to-r from-zinc-500 via-zinc-400 to-zinc-500"
      )} />
      
      {/* Syncing animation overlay */}
      {source.status === "syncing" && (
        <div className="absolute inset-0 rounded-2xl overflow-hidden pointer-events-none">
          <motion.div 
            className="absolute inset-0 bg-gradient-to-r from-transparent via-blue-500/10 to-transparent"
            animate={{ x: ["-100%", "100%"] }}
            transition={{ duration: 2, repeat: Infinity, ease: "linear" }}
          />
          <DataStream direction="horizontal" color="blue" speed={0.5} className="opacity-20" />
        </div>
      )}
      
      {/* Connected glow */}
      {source.status === "connected" && (
        <div className="absolute top-0 right-0 w-32 h-32 -translate-y-1/2 translate-x-1/2 pointer-events-none">
          <GlowOrb size={80} color="emerald" intensity={0.3} />
        </div>
      )}

      <div className="relative p-5" onClick={onToggle}>
        {/* Header */}
        <div className="flex items-start justify-between mb-4">
          <div className="flex items-center gap-3">
            <motion.div 
              className={cn(
                "flex h-12 w-12 items-center justify-center rounded-xl transition-all relative",
                config.bgColor,
                source.status === "connected" && "shadow-lg shadow-emerald-500/20"
              )}
              animate={source.status === "syncing" ? { scale: [1, 1.05, 1] } : {}}
              transition={{ duration: 1.5, repeat: Infinity }}
            >
              <TypeIcon className={cn("h-5 w-5", config.color)} />
              {source.status === "syncing" && (
                <motion.div 
                  className="absolute inset-0 rounded-xl border-2 border-blue-400"
                  animate={{ scale: [1, 1.2], opacity: [0.8, 0] }}
                  transition={{ duration: 1, repeat: Infinity }}
                />
              )}
            </motion.div>
            <div>
              <h3 className="text-sm font-semibold text-foreground">{source.name}</h3>
              <p className="text-xs text-muted-foreground">{source.type}</p>
            </div>
          </div>
          <HealthRing health={source.health} />
        </div>

        {/* Connection status with live pulse */}
        <div className="flex items-center gap-2 mb-4">
          <div className={cn(
            "flex items-center gap-2 px-2.5 py-1 rounded-full text-[10px] font-semibold uppercase tracking-wide",
            source.status === "connected" && "bg-emerald-500/10 text-emerald-400 border border-emerald-500/20",
            source.status === "syncing" && "bg-blue-500/10 text-blue-400 border border-blue-500/20",
            source.status === "error" && "bg-red-500/10 text-red-400 border border-red-500/20",
            source.status === "disconnected" && "bg-zinc-500/10 text-zinc-400 border border-zinc-500/20"
          )}>
            <StatusBeacon 
              status={source.status === "connected" ? "active" : source.status === "syncing" ? "processing" : source.status === "error" ? "error" : "idle"} 
              size="sm" 
              pulse={source.status === "syncing" || source.status === "connected"}
            />
            {source.status}
          </div>
          <span className="text-[10px] text-muted-foreground flex items-center gap-1">
            <Clock className="h-2.5 w-2.5" />
            {source.lastSync}
          </span>
        </div>

        {/* Stats row */}
        <div className="grid grid-cols-3 gap-2 mb-4">
          <div className="text-center p-2 rounded-lg bg-secondary/50">
            <div className="flex items-center justify-center gap-1 text-muted-foreground mb-1">
              <Table2 className="h-3 w-3" />
            </div>
            <p className="text-sm font-semibold text-foreground">{source.tables}</p>
            <p className="text-[9px] text-muted-foreground">tables</p>
          </div>
          <div className="text-center p-2 rounded-lg bg-secondary/50">
            <div className="flex items-center justify-center gap-1 text-muted-foreground mb-1">
              <CircleDot className="h-3 w-3" />
            </div>
            <p className="text-sm font-semibold text-foreground">{source.records}</p>
            <p className="text-[9px] text-muted-foreground">records</p>
          </div>
          <div className="text-center p-2 rounded-lg bg-secondary/50">
            <div className="flex items-center justify-center gap-1 text-muted-foreground mb-1">
              <Workflow className="h-3 w-3" />
            </div>
            <p className="text-sm font-semibold text-foreground">{source.workflowsUsing}</p>
            <p className="text-[9px] text-muted-foreground">workflows</p>
          </div>
        </div>

        {/* Table preview */}
        {source.topTables && (
          <div className="mb-3">
            <div className="flex items-center gap-1 flex-wrap">
              {source.topTables.slice(0, 3).map((table) => (
                <span 
                  key={table}
                  className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-secondary text-muted-foreground"
                >
                  {table}
                </span>
              ))}
              {source.topTables.length > 3 && (
                <span className="text-[10px] text-muted-foreground">
                  +{source.topTables.length - 3} more
                </span>
              )}
            </div>
          </div>
        )}

        {/* Expand toggle */}
        <button 
          className="w-full flex items-center justify-center gap-1 text-[10px] text-muted-foreground hover:text-foreground transition-colors py-1"
          onClick={(e) => {
            e.stopPropagation()
            onToggle()
          }}
        >
          {isExpanded ? "Less" : "More"}
          <ChevronDown className={cn("h-3 w-3 transition-transform", isExpanded && "rotate-180")} />
        </button>
      </div>

      {/* Expanded details */}
      <AnimatePresence>
        {isExpanded && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: "auto", opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            className="overflow-hidden border-t border-border"
          >
            <div className="p-4 space-y-3">
              <p className="text-xs text-muted-foreground">{source.description}</p>
              
              <div className="flex items-center gap-3 text-xs text-muted-foreground">
                <span className="flex items-center gap-1">
                  <Bot className="h-3 w-3" />
                  {source.operatorsUsing} operators
                </span>
              </div>

              <div className="flex items-center gap-2">
                <Button 
                  variant="outline" 
                  size="sm" 
                  className="h-7 gap-1.5 text-xs flex-1"
                  onClick={() => router.push(`/sources/${source.id}`)}
                >
                  <ExternalLink className="h-3 w-3" />
                  Details
                </Button>
                <Button 
                  variant="outline" 
                  size="sm" 
                  className="h-7 gap-1.5 text-xs flex-1"
                  onClick={() => router.push("/workflows/new")}
                >
                  <Workflow className="h-3 w-3" />
                  Use
                </Button>
                <Button 
                  size="sm" 
                  className="h-7 gap-1.5 text-xs"
                >
                  <RefreshCw className="h-3 w-3" />
                  Sync
                </Button>
              </div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </motion.div>
  )
}

// Add Source Modal
function AddSourceModal({ open, onClose }: { open: boolean; onClose: () => void }) {
  const [step, setStep] = useState(1)
  const [selectedType, setSelectedType] = useState<string | null>(null)
  const [testing, setTesting] = useState(false)
  const [testResult, setTestResult] = useState<"success" | "error" | null>(null)

  const sourceTypes = [
    { id: "postgresql", name: "PostgreSQL", icon: Database, color: "text-blue-400" },
    { id: "mysql", name: "MySQL", icon: Database, color: "text-orange-400" },
    { id: "mongodb", name: "MongoDB", icon: HardDrive, color: "text-green-400" },
    { id: "snowflake", name: "Snowflake", icon: Cloud, color: "text-cyan-400" },
    { id: "bigquery", name: "BigQuery", icon: Server, color: "text-yellow-400" },
  ]

  const handleTest = () => {
    setTesting(true)
    setTimeout(() => {
      setTesting(false)
      setTestResult("success")
    }, 2000)
  }

  const resetAndClose = () => {
    onClose()
    setStep(1)
    setSelectedType(null)
    setTestResult(null)
  }

  return (
    <Dialog open={open} onOpenChange={resetAndClose}>
      <DialogContent className="max-w-lg">
        <DialogHeader>
          <DialogTitle>
            {step === 1 && "Add Data Source"}
            {step === 2 && "Configure Connection"}
            {step === 3 && "Test & Connect"}
          </DialogTitle>
        </DialogHeader>

        {/* Progress */}
        <div className="flex items-center gap-2 mb-4">
          {[1, 2, 3].map((s) => (
            <div
              key={s}
              className={cn(
                "h-1.5 flex-1 rounded-full transition-colors",
                s <= step ? "bg-primary" : "bg-secondary"
              )}
            />
          ))}
        </div>

        {step === 1 && (
          <div className="grid grid-cols-2 gap-3">
            {sourceTypes.map((type) => (
              <button
                key={type.id}
                onClick={() => {
                  setSelectedType(type.id)
                  setStep(2)
                }}
                className="flex items-center gap-3 rounded-lg border border-border bg-card p-4 text-left transition-all hover:border-primary/30 hover:bg-card/80"
              >
                <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-secondary">
                  <type.icon className={cn("h-5 w-5", type.color)} />
                </div>
                <span className="text-sm font-medium text-foreground">{type.name}</span>
              </button>
            ))}
          </div>
        )}

        {step === 2 && (
          <div className="space-y-4">
            <div>
              <label className="text-xs font-medium text-muted-foreground uppercase tracking-wide">
                Source Name
              </label>
              <input
                type="text"
                placeholder="my-database"
                className="mt-2 w-full rounded-md border border-border bg-secondary px-3 py-2 text-sm text-foreground placeholder:text-muted-foreground focus:border-primary/50 focus:outline-none"
              />
            </div>
            <div>
              <label className="text-xs font-medium text-muted-foreground uppercase tracking-wide">
                Connection String
              </label>
              <input
                type="text"
                placeholder="postgresql://user:pass@host:5432/db"
                className="mt-2 w-full rounded-md border border-border bg-secondary px-3 py-2 text-sm text-foreground font-mono placeholder:text-muted-foreground focus:border-primary/50 focus:outline-none"
              />
            </div>
            <div className="flex justify-end gap-2 pt-4">
              <Button variant="outline" onClick={() => setStep(1)}>Back</Button>
              <Button onClick={() => setStep(3)}>Continue <ArrowRight className="ml-2 h-4 w-4" /></Button>
            </div>
          </div>
        )}

        {step === 3 && (
          <div className="space-y-4">
            {!testing && testResult === null && (
              <div className="text-center py-6">
                <p className="text-sm text-muted-foreground mb-4">Test your connection before adding</p>
                <Button onClick={handleTest} className="gap-2">
                  <Activity className="h-4 w-4" />
                  Test Connection
                </Button>
              </div>
            )}

            {testing && (
              <div className="text-center py-6">
                <Loader2 className="h-8 w-8 animate-spin text-primary mx-auto mb-3" />
                <p className="text-sm text-muted-foreground">Testing connection...</p>
              </div>
            )}

            {testResult === "success" && (
              <div className="rounded-lg border border-emerald-500/30 bg-emerald-500/10 p-4 text-center">
                <Check className="h-8 w-8 text-emerald-500 mx-auto mb-2" />
                <p className="text-sm font-medium text-emerald-400">Connection successful!</p>
                <p className="text-xs text-muted-foreground mt-1">Found 24 tables, 1.2M records</p>
              </div>
            )}

            <div className="flex justify-end gap-2 pt-4">
              <Button variant="outline" onClick={() => setStep(2)}>Back</Button>
              <Button onClick={resetAndClose} disabled={testResult !== "success"} className="gap-2">
                <Check className="h-4 w-4" />
                Add Source
              </Button>
            </div>
          </div>
        )}
      </DialogContent>
    </Dialog>
  )
}

export default function SourcesPage() {
  const [expandedSource, setExpandedSource] = useState<string | null>(null)
  const [addModalOpen, setAddModalOpen] = useState(false)
  const [selectedCategory, setSelectedCategory] = useState<string | null>(null)
  const { data } = useSWR("/api/sources", apiFetcher, {
    fallbackData: { sources: fallbackSources },
    revalidateOnFocus: false,
  })
  const sources = normalizeSourcesResponse(data)

  // Group sources by category
  const groupedSources = sources.reduce((acc, source) => {
    if (!acc[source.category]) acc[source.category] = []
    acc[source.category].push(source)
    return acc
  }, {} as Record<string, Source[]>)

  const categories = Object.keys(groupedSources) as (keyof typeof categoryLabels)[]

  // Stats
  const connectedCount = sources.filter(s => s.status === "connected" || s.status === "syncing").length
  const totalRecords = sources.reduce((acc, s) => {
    const num = parseFloat(s.records.replace(/[KM]/g, ""))
    const multiplier = s.records.includes("M") ? 1000000 : s.records.includes("K") ? 1000 : 1
    return acc + num * multiplier
  }, 0)

  return (
    <AppShell title="Sources">
      <div className="relative flex flex-col h-full overflow-hidden">
        {/* Premium ambient background */}
        <div className="absolute inset-0 pointer-events-none z-0">
          <MorphingBackground colors={["cyan", "blue", "violet"]} />
          <div className="absolute inset-0 bg-background/90 backdrop-blur-3xl" />
        </div>
        
        {/* Neural network visualization */}
        <div className="absolute inset-0 pointer-events-none z-0 opacity-15">
          <NeuralNetwork nodeCount={15} color="cyan" />
        </div>
        
        {/* Ambient orbs */}
        <div className="absolute top-40 right-20 pointer-events-none z-0">
          <GlowOrb size={300} color="blue" intensity={0.2} />
        </div>
        <div className="absolute bottom-20 left-1/4 pointer-events-none z-0">
          <GlowOrb size={200} color="blue" intensity={0.15} />
        </div>

        {/* Header */}
        <div className="relative z-10 flex-shrink-0 px-6 pt-6 pb-4 border-b border-border/50 bg-card/30 backdrop-blur-sm">
          <div className="flex items-center justify-between mb-6">
            <motion.div
              initial={{ opacity: 0, x: -20 }}
              animate={{ opacity: 1, x: 0 }}
            >
              <h1 className="text-2xl font-bold text-foreground">Data Landscape</h1>
              <p className="text-sm text-muted-foreground mt-1">Your connected data ecosystem</p>
            </motion.div>
            <motion.div
              initial={{ opacity: 0, scale: 0.9 }}
              animate={{ opacity: 1, scale: 1 }}
              whileHover={{ scale: 1.02 }}
              whileTap={{ scale: 0.98 }}
            >
              <Button size="sm" className="h-9 gap-2 shadow-lg" onClick={() => setAddModalOpen(true)}>
                <Sparkles className="h-3.5 w-3.5" />
                Add Source
              </Button>
            </motion.div>
          </div>

          {/* Ecosystem stats - Premium */}
          <motion.div 
            className="flex items-center gap-4"
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.2 }}
          >
            <motion.div 
              className="flex items-center gap-3 px-4 py-2.5 rounded-xl bg-gradient-to-br from-emerald-500/15 to-emerald-500/5 border border-emerald-500/20 shadow-lg shadow-emerald-500/5"
              whileHover={{ scale: 1.02, y: -2 }}
            >
              <div className="h-9 w-9 rounded-lg bg-emerald-500/20 flex items-center justify-center">
                <Database className="h-4 w-4 text-emerald-400" />
              </div>
              <div>
                <span className="text-xl font-bold text-emerald-400"><AnimatedCounter value={connectedCount} duration={1} /></span>
                <span className="text-xs text-muted-foreground ml-1.5">connected</span>
              </div>
            </motion.div>
            <motion.div 
              className="flex items-center gap-3 px-4 py-2.5 rounded-xl bg-gradient-to-br from-blue-500/15 to-blue-500/5 border border-blue-500/20 shadow-lg shadow-blue-500/5"
              whileHover={{ scale: 1.02, y: -2 }}
            >
              <div className="h-9 w-9 rounded-lg bg-blue-500/20 flex items-center justify-center">
                <CircleDot className="h-4 w-4 text-blue-400" />
              </div>
              <div>
                <span className="text-xl font-bold text-blue-400">{(totalRecords / 1000000).toFixed(1)}M</span>
                <span className="text-xs text-muted-foreground ml-1.5">records</span>
              </div>
            </motion.div>
            <motion.div 
              className="flex items-center gap-3 px-4 py-2.5 rounded-xl bg-gradient-to-br from-violet-500/15 to-violet-500/5 border border-violet-500/20 shadow-lg shadow-violet-500/5"
              whileHover={{ scale: 1.02, y: -2 }}
            >
              <div className="h-9 w-9 rounded-lg bg-violet-500/20 flex items-center justify-center">
                <Layers className="h-4 w-4 text-violet-400" />
              </div>
              <div>
                <span className="text-xl font-bold text-violet-400"><AnimatedCounter value={sources.reduce((a, s) => a + s.tables, 0)} duration={1.5} /></span>
                <span className="text-xs text-muted-foreground ml-1.5">tables</span>
              </div>
            </motion.div>

            {/* Category filters */}
            <div className="ml-auto flex items-center gap-2">
              <button
                onClick={() => setSelectedCategory(null)}
                className={cn(
                  "px-3 py-1.5 rounded-lg text-xs font-medium transition-all",
                  selectedCategory === null 
                    ? "bg-primary text-primary-foreground" 
                    : "bg-secondary text-muted-foreground hover:text-foreground"
                )}
              >
                All
              </button>
              {categories.map((cat) => (
                <button
                  key={cat}
                  onClick={() => setSelectedCategory(cat)}
                  className={cn(
                    "px-3 py-1.5 rounded-lg text-xs font-medium transition-all",
                    selectedCategory === cat 
                      ? "bg-primary text-primary-foreground" 
                      : "bg-secondary text-muted-foreground hover:text-foreground"
                  )}
                >
                  {categoryLabels[cat]}
                </button>
              ))}
            </div>
          </motion.div>
        </div>

        {/* Data landscape grid - Premium */}
        <div className="relative z-10 flex-1 overflow-auto p-6">
          {/* Grid pattern */}
          <div className="absolute inset-0 pointer-events-none opacity-20">
            <GridPattern size={50} color="blue" animated />
          </div>
          
          <AnimatePresence mode="wait">
            {categories
              .filter(cat => selectedCategory === null || cat === selectedCategory)
              .map((category, catIndex) => (
              <motion.div 
                key={category} 
                className="relative mb-10"
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -20 }}
                transition={{ delay: catIndex * 0.1 }}
              >
                <div className="flex items-center gap-3 mb-5">
                  <div className="h-8 w-1 rounded-full bg-gradient-to-b from-cyan-500 to-blue-500" />
                  <h2 className="text-base font-semibold text-foreground">{categoryLabels[category]}</h2>
                  <span className="text-xs text-muted-foreground px-2 py-0.5 rounded-full bg-secondary">
                    {groupedSources[category].length} source{groupedSources[category].length !== 1 ? "s" : ""}
                  </span>
                </div>
                <div className="grid gap-5 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
                  {groupedSources[category].map((source, index) => (
                    <SourceTile
                      key={source.id}
                      source={source}
                      index={index}
                      isExpanded={expandedSource === source.id}
                      onToggle={() => setExpandedSource(expandedSource === source.id ? null : source.id)}
                    />
                  ))}
                </div>
              </motion.div>
            ))}
          </AnimatePresence>
        </div>
      </div>

      <AddSourceModal open={addModalOpen} onClose={() => setAddModalOpen(false)} />
    </AppShell>
  )
}
