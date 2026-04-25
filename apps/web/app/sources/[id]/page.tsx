"use client"

import { useState } from "react"
import { useRouter, useParams } from "next/navigation"
import { AppShell } from "@/components/gravitre/app-shell"
import { StatusBadge } from "@/components/gravitre/status-badge"
import { EnvironmentBadge } from "@/components/gravitre/environment-badge"
import { Button } from "@/components/ui/button"
import { cn } from "@/lib/utils"
import {
  ArrowLeft,
  Database,
  Server,
  RefreshCw,
  Settings,
  Trash2,
  Activity,
  Layers,
  CircleDot,
  Workflow,
  Bot,
  Check,
  AlertCircle,
  Copy,
  ExternalLink,
  Table2,
  Clock,
  Loader2,
  ChevronRight,
  Play,
} from "lucide-react"
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
} from "@/components/ui/dialog"

// Mock source data
const sourceData = {
  id: "1",
  name: "postgres-primary",
  type: "PostgreSQL",
  status: "connected" as const,
  environment: "production" as const,
  lastSync: "2 minutes ago",
  tables: 42,
  records: "2.4M",
  description: "Primary PostgreSQL database for customer data",
  workflowsUsing: 8,
  operatorsUsing: 3,
  connectionHost: "db.example.com",
  connectionPort: "5432",
  connectionDatabase: "production_db",
  createdAt: "Jan 15, 2024",
  syncFrequency: "Every 5 minutes",
}

const tableSchema = [
  { name: "customers", columns: 12, rows: "1.2M", lastUpdated: "2 min ago" },
  { name: "orders", columns: 18, rows: "890K", lastUpdated: "2 min ago" },
  { name: "products", columns: 24, rows: "45K", lastUpdated: "5 min ago" },
  { name: "transactions", columns: 15, rows: "2.1M", lastUpdated: "2 min ago" },
  { name: "invoices", columns: 20, rows: "320K", lastUpdated: "10 min ago" },
  { name: "users", columns: 8, rows: "15K", lastUpdated: "1 hour ago" },
]

const linkedWorkflows = [
  { id: "1", name: "Customer Sync Pipeline", status: "active", lastRun: "5 min ago" },
  { id: "2", name: "Order Processing", status: "active", lastRun: "2 min ago" },
  { id: "3", name: "Daily Analytics Export", status: "active", lastRun: "1 hour ago" },
  { id: "4", name: "Inventory Update", status: "paused", lastRun: "2 days ago" },
]

const linkedOperators = [
  { id: "1", name: "Sales Assistant", uses: "Query customer data" },
  { id: "2", name: "Data Quality Agent", uses: "Validate records" },
  { id: "3", name: "Finance Reporter", uses: "Generate reports" },
]

const syncHistory = [
  { id: "1", status: "success", records: "2,450", duration: "12s", timestamp: "2 min ago" },
  { id: "2", status: "success", records: "1,823", duration: "9s", timestamp: "7 min ago" },
  { id: "3", status: "success", records: "3,102", duration: "15s", timestamp: "12 min ago" },
  { id: "4", status: "error", records: "0", duration: "2s", timestamp: "17 min ago", error: "Connection timeout" },
  { id: "5", status: "success", records: "2,891", duration: "11s", timestamp: "22 min ago" },
]

const statusVariants: Record<string, "success" | "warning" | "error" | "info" | "muted"> = {
  connected: "success",
  disconnected: "muted",
  error: "error",
  syncing: "info",
}

export default function SourceDetailPage() {
  const router = useRouter()
  const params = useParams()
  const [syncing, setSyncing] = useState(false)
  const [deleteModalOpen, setDeleteModalOpen] = useState(false)
  const [testingConnection, setTestingConnection] = useState(false)
  const [testResult, setTestResult] = useState<"success" | "error" | null>(null)

  const handleSync = () => {
    setSyncing(true)
    setTimeout(() => setSyncing(false), 3000)
  }

  const handleTestConnection = () => {
    setTestingConnection(true)
    setTestResult(null)
    setTimeout(() => {
      setTestingConnection(false)
      setTestResult("success")
    }, 2000)
  }

  return (
    <AppShell title={sourceData.name}>
      <div className="p-6">
        {/* Back Button */}
        <button
          onClick={() => router.push("/sources")}
          className="mb-4 flex items-center gap-2 text-sm text-muted-foreground hover:text-foreground transition-colors"
        >
          <ArrowLeft className="h-4 w-4" />
          Back to Sources
        </button>

        {/* Header */}
        <div className="mb-8 flex items-start justify-between">
          <div className="flex items-start gap-4">
            <div className="flex h-14 w-14 items-center justify-center rounded-xl bg-blue-400/10">
              <Database className="h-7 w-7 text-blue-400" />
            </div>
            <div>
              <h1 className="text-2xl font-semibold text-foreground">{sourceData.name}</h1>
              <p className="text-sm text-muted-foreground mt-1">{sourceData.description}</p>
              <div className="flex items-center gap-2 mt-3">
                <StatusBadge variant={statusVariants[sourceData.status]} dot>
                  {sourceData.status}
                </StatusBadge>
                <EnvironmentBadge environment={sourceData.environment} />
                <span className="text-xs text-muted-foreground">{sourceData.type}</span>
              </div>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <Button variant="outline" size="sm" className="h-9 gap-2" onClick={handleTestConnection} disabled={testingConnection}>
              {testingConnection ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <Activity className="h-4 w-4" />
              )}
              Test Connection
            </Button>
            <Button variant="outline" size="sm" className="h-9 gap-2">
              <Settings className="h-4 w-4" />
              Edit
            </Button>
            <Button size="sm" className="h-9 gap-2 bg-emerald-600 hover:bg-emerald-700" onClick={handleSync} disabled={syncing}>
              {syncing ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <RefreshCw className="h-4 w-4" />
              )}
              Sync Now
            </Button>
          </div>
        </div>

        {/* Test Result Banner */}
        {testResult && (
          <div className={cn(
            "mb-6 rounded-lg border p-4 flex items-center gap-3",
            testResult === "success" 
              ? "border-emerald-500/30 bg-emerald-500/10" 
              : "border-destructive/30 bg-destructive/10"
          )}>
            {testResult === "success" ? (
              <>
                <Check className="h-5 w-5 text-emerald-500" />
                <span className="text-sm text-emerald-500">Connection test successful. Database is reachable.</span>
              </>
            ) : (
              <>
                <AlertCircle className="h-5 w-5 text-destructive" />
                <span className="text-sm text-destructive">Connection test failed. Please check your credentials.</span>
              </>
            )}
            <button onClick={() => setTestResult(null)} className="ml-auto text-muted-foreground hover:text-foreground">
              <span className="sr-only">Dismiss</span>×
            </button>
          </div>
        )}

        <div className="grid gap-6 lg:grid-cols-3">
          {/* Main Content - 2 columns */}
          <div className="lg:col-span-2 space-y-6">
            {/* Overview */}
            <div className="rounded-lg border border-border bg-card p-5">
              <h2 className="text-sm font-semibold text-foreground mb-4">Overview</h2>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <p className="text-xs text-muted-foreground uppercase tracking-wide">Connection</p>
                  <p className="text-sm text-foreground mt-1 font-mono">{sourceData.connectionHost}:{sourceData.connectionPort}</p>
                </div>
                <div>
                  <p className="text-xs text-muted-foreground uppercase tracking-wide">Database</p>
                  <p className="text-sm text-foreground mt-1 font-mono">{sourceData.connectionDatabase}</p>
                </div>
                <div>
                  <p className="text-xs text-muted-foreground uppercase tracking-wide">Last Sync</p>
                  <p className="text-sm text-foreground mt-1">{sourceData.lastSync}</p>
                </div>
                <div>
                  <p className="text-xs text-muted-foreground uppercase tracking-wide">Sync Frequency</p>
                  <p className="text-sm text-foreground mt-1">{sourceData.syncFrequency}</p>
                </div>
                <div>
                  <p className="text-xs text-muted-foreground uppercase tracking-wide">Tables</p>
                  <p className="text-sm text-foreground mt-1">{sourceData.tables}</p>
                </div>
                <div>
                  <p className="text-xs text-muted-foreground uppercase tracking-wide">Total Records</p>
                  <p className="text-sm text-foreground mt-1">{sourceData.records}</p>
                </div>
              </div>
            </div>

            {/* Schema Preview */}
            <div className="rounded-lg border border-border bg-card p-5">
              <div className="flex items-center justify-between mb-4">
                <h2 className="text-sm font-semibold text-foreground">Schema Preview</h2>
                <Button variant="outline" size="sm" className="h-7 text-xs gap-1">
                  <ExternalLink className="h-3 w-3" />
                  Browse All
                </Button>
              </div>
              <div className="overflow-x-auto">
                <table className="w-full text-xs">
                  <thead>
                    <tr className="border-b border-border">
                      <th className="text-left py-2 px-3 text-muted-foreground font-medium">Table</th>
                      <th className="text-left py-2 px-3 text-muted-foreground font-medium">Columns</th>
                      <th className="text-left py-2 px-3 text-muted-foreground font-medium">Rows</th>
                      <th className="text-left py-2 px-3 text-muted-foreground font-medium">Updated</th>
                    </tr>
                  </thead>
                  <tbody>
                    {tableSchema.map((table) => (
                      <tr key={table.name} className="border-b border-border/50 hover:bg-secondary/50">
                        <td className="py-2 px-3">
                          <span className="font-mono text-foreground">{table.name}</span>
                        </td>
                        <td className="py-2 px-3 text-muted-foreground">{table.columns}</td>
                        <td className="py-2 px-3 text-muted-foreground">{table.rows}</td>
                        <td className="py-2 px-3 text-muted-foreground">{table.lastUpdated}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>

            {/* Sync History */}
            <div className="rounded-lg border border-border bg-card p-5">
              <h2 className="text-sm font-semibold text-foreground mb-4">Sync History</h2>
              <div className="space-y-2">
                {syncHistory.map((sync) => (
                  <div key={sync.id} className="flex items-center justify-between py-2 border-b border-border/50 last:border-0">
                    <div className="flex items-center gap-3">
                      {sync.status === "success" ? (
                        <Check className="h-4 w-4 text-emerald-500" />
                      ) : (
                        <AlertCircle className="h-4 w-4 text-destructive" />
                      )}
                      <div>
                        <p className="text-xs text-foreground">
                          {sync.status === "success" ? `Synced ${sync.records} records` : sync.error}
                        </p>
                        <p className="text-xs text-muted-foreground">{sync.timestamp}</p>
                      </div>
                    </div>
                    <span className="text-xs text-muted-foreground">{sync.duration}</span>
                  </div>
                ))}
              </div>
            </div>
          </div>

          {/* Sidebar */}
          <div className="space-y-6">
            {/* Quick Stats */}
            <div className="rounded-lg border border-border bg-card p-5">
              <h2 className="text-sm font-semibold text-foreground mb-4">Quick Stats</h2>
              <div className="space-y-4">
                <div className="flex items-center justify-between">
                  <span className="text-xs text-muted-foreground">Created</span>
                  <span className="text-xs text-foreground">{sourceData.createdAt}</span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-xs text-muted-foreground">Tables</span>
                  <span className="text-xs text-foreground">{sourceData.tables}</span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-xs text-muted-foreground">Records</span>
                  <span className="text-xs text-foreground">{sourceData.records}</span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-xs text-muted-foreground">Workflows</span>
                  <span className="text-xs text-foreground">{sourceData.workflowsUsing}</span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-xs text-muted-foreground">Operators</span>
                  <span className="text-xs text-foreground">{sourceData.operatorsUsing}</span>
                </div>
              </div>
            </div>

            {/* Linked Workflows */}
            <div className="rounded-lg border border-border bg-card p-5">
              <div className="flex items-center justify-between mb-4">
                <h2 className="text-sm font-semibold text-foreground">Used in Workflows</h2>
                <span className="text-xs text-muted-foreground">{linkedWorkflows.length}</span>
              </div>
              <div className="space-y-2">
                {linkedWorkflows.slice(0, 4).map((workflow) => (
                  <button
                    key={workflow.id}
                    onClick={() => router.push(`/workflows/${workflow.id}`)}
                    className="w-full flex items-center justify-between py-2 px-3 rounded-md hover:bg-secondary/50 transition-colors text-left"
                  >
                    <div className="flex items-center gap-2">
                      <Workflow className="h-3.5 w-3.5 text-muted-foreground" />
                      <span className="text-xs text-foreground">{workflow.name}</span>
                    </div>
                    <ChevronRight className="h-3.5 w-3.5 text-muted-foreground" />
                  </button>
                ))}
              </div>
            </div>

            {/* Linked Operators */}
            <div className="rounded-lg border border-border bg-card p-5">
              <div className="flex items-center justify-between mb-4">
                <h2 className="text-sm font-semibold text-foreground">Used by Operators</h2>
                <span className="text-xs text-muted-foreground">{linkedOperators.length}</span>
              </div>
              <div className="space-y-2">
                {linkedOperators.map((operator) => (
                  <button
                    key={operator.id}
                    onClick={() => router.push(`/agents/${operator.id}`)}
                    className="w-full flex items-center justify-between py-2 px-3 rounded-md hover:bg-secondary/50 transition-colors text-left"
                  >
                    <div className="flex items-center gap-2">
                      <Bot className="h-3.5 w-3.5 text-muted-foreground" />
                      <div>
                        <span className="text-xs text-foreground block">{operator.name}</span>
                        <span className="text-[10px] text-muted-foreground">{operator.uses}</span>
                      </div>
                    </div>
                    <ChevronRight className="h-3.5 w-3.5 text-muted-foreground" />
                  </button>
                ))}
              </div>
            </div>

            {/* Actions */}
            <div className="rounded-lg border border-border bg-card p-5">
              <h2 className="text-sm font-semibold text-foreground mb-4">Actions</h2>
              <div className="space-y-2">
                <Button variant="outline" size="sm" className="w-full h-9 justify-start gap-2">
                  <Play className="h-4 w-4" />
                  Use in new Workflow
                </Button>
                <Button variant="outline" size="sm" className="w-full h-9 justify-start gap-2">
                  <Bot className="h-4 w-4" />
                  Open in Operator
                </Button>
                <Button variant="outline" size="sm" className="w-full h-9 justify-start gap-2">
                  <Copy className="h-4 w-4" />
                  Copy Connection String
                </Button>
                <Button 
                  variant="outline" 
                  size="sm" 
                  className="w-full h-9 justify-start gap-2 text-destructive hover:text-destructive hover:bg-destructive/10 border-destructive/30"
                  onClick={() => setDeleteModalOpen(true)}
                >
                  <Trash2 className="h-4 w-4" />
                  Remove Source
                </Button>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Delete Confirmation Modal */}
      <Dialog open={deleteModalOpen} onOpenChange={setDeleteModalOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Remove Source</DialogTitle>
            <DialogDescription>
              This will disconnect {sourceData.name} from Gravitre. This action cannot be undone.
            </DialogDescription>
          </DialogHeader>
          <div className="rounded-lg border border-amber-500/30 bg-amber-500/10 p-4 my-4">
            <div className="flex items-start gap-3">
              <AlertCircle className="h-5 w-5 text-amber-500 shrink-0 mt-0.5" />
              <div className="text-sm text-amber-500">
                <p className="font-medium">This source is used by:</p>
                <ul className="mt-1 text-xs space-y-1">
                  <li>• {sourceData.workflowsUsing} workflows</li>
                  <li>• {sourceData.operatorsUsing} operators</li>
                </ul>
                <p className="mt-2 text-xs">Removing it may break these integrations.</p>
              </div>
            </div>
          </div>
          <div className="flex justify-end gap-2">
            <Button variant="outline" onClick={() => setDeleteModalOpen(false)}>Cancel</Button>
            <Button variant="destructive" onClick={() => { setDeleteModalOpen(false); router.push("/sources") }}>
              Remove Source
            </Button>
          </div>
        </DialogContent>
      </Dialog>
    </AppShell>
  )
}
