"use client"

import { useState } from "react"
import { motion, AnimatePresence } from "framer-motion"
import { 
  Database, 
  Check, 
  RefreshCw, 
  Lock,
  ExternalLink,
  ChevronRight,
  AlertCircle
} from "lucide-react"

interface Connector {
  id: string
  name: string
  icon: string
  status: "available" | "connected" | "syncing"
  lastSync?: string
  records?: number
}

const CONNECTORS: Connector[] = [
  { id: "salesforce", name: "Salesforce", icon: "SF", status: "available" },
  { id: "hubspot", name: "HubSpot", icon: "HS", status: "available" },
  { id: "slack", name: "Slack", icon: "SL", status: "available" },
  { id: "postgresql", name: "PostgreSQL", icon: "PG", status: "available" },
]

export function ConnectorDemo() {
  const [connectors, setConnectors] = useState<Connector[]>(CONNECTORS)
  const [selectedConnector, setSelectedConnector] = useState<string | null>(null)
  const [step, setStep] = useState<"select" | "auth" | "sync" | "done">("select")
  const [apiKey, setApiKey] = useState("")

  const handleConnect = (id: string) => {
    setSelectedConnector(id)
    setStep("auth")
  }

  const handleAuth = () => {
    if (!apiKey) return
    setStep("sync")
    
    // Simulate syncing
    setConnectors((prev) =>
      prev.map((c) =>
        c.id === selectedConnector ? { ...c, status: "syncing" } : c
      )
    )
    
    setTimeout(() => {
      setConnectors((prev) =>
        prev.map((c) =>
          c.id === selectedConnector
            ? {
                ...c,
                status: "connected",
                lastSync: "Just now",
                records: Math.floor(Math.random() * 5000) + 1000,
              }
            : c
        )
      )
      setStep("done")
    }, 2500)
  }

  const handleReset = () => {
    setConnectors(CONNECTORS)
    setSelectedConnector(null)
    setStep("select")
    setApiKey("")
  }

  const currentConnector = connectors.find((c) => c.id === selectedConnector)

  return (
    <div className="relative rounded-xl border border-border bg-background overflow-hidden">
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-border bg-muted/30">
        <div className="flex items-center gap-2">
          <div className="h-8 w-8 rounded-lg bg-amber-100 flex items-center justify-center">
            <Database className="h-4 w-4 text-amber-600" />
          </div>
          <span className="font-medium text-sm text-foreground">Connect Integration</span>
        </div>
        {step !== "select" && (
          <button
            onClick={handleReset}
            className="text-xs text-muted-foreground hover:text-foreground transition-colors"
          >
            Start over
          </button>
        )}
      </div>

      {/* Content */}
      <div className="p-4 min-h-[280px]">
        <AnimatePresence mode="wait">
          {step === "select" && (
            <motion.div
              key="select"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
            >
              <p className="text-sm text-muted-foreground mb-4">
                Choose an integration to connect
              </p>
              <div className="grid grid-cols-2 gap-3">
                {connectors.map((connector) => (
                  <button
                    key={connector.id}
                    onClick={() => handleConnect(connector.id)}
                    disabled={connector.status === "connected"}
                    className={`flex items-center gap-3 p-3 rounded-lg border transition-all ${
                      connector.status === "connected"
                        ? "border-emerald-200 bg-emerald-50"
                        : "border-border hover:border-amber-500/50 hover:bg-amber-50/30"
                    }`}
                  >
                    <div className={`h-10 w-10 rounded-lg flex items-center justify-center text-xs font-bold ${
                      connector.id === "salesforce" ? "bg-blue-100 text-blue-600" :
                      connector.id === "hubspot" ? "bg-orange-100 text-orange-600" :
                      connector.id === "slack" ? "bg-purple-100 text-purple-600" :
                      "bg-zinc-100 text-zinc-600"
                    }`}>
                      {connector.icon}
                    </div>
                    <div className="text-left flex-1">
                      <div className="text-sm font-medium text-foreground">{connector.name}</div>
                      <div className="text-xs text-muted-foreground">
                        {connector.status === "connected" ? (
                          <span className="text-emerald-600 flex items-center gap-1">
                            <Check className="h-3 w-3" /> Connected
                          </span>
                        ) : (
                          "Click to connect"
                        )}
                      </div>
                    </div>
                    {connector.status !== "connected" && (
                      <ChevronRight className="h-4 w-4 text-muted-foreground" />
                    )}
                  </button>
                ))}
              </div>
            </motion.div>
          )}

          {step === "auth" && currentConnector && (
            <motion.div
              key="auth"
              initial={{ opacity: 0, x: 20 }}
              animate={{ opacity: 1, x: 0 }}
              exit={{ opacity: 0, x: -20 }}
            >
              <div className="flex items-center gap-3 mb-4">
                <div className={`h-10 w-10 rounded-lg flex items-center justify-center text-xs font-bold ${
                  currentConnector.id === "salesforce" ? "bg-blue-100 text-blue-600" :
                  currentConnector.id === "hubspot" ? "bg-orange-100 text-orange-600" :
                  currentConnector.id === "slack" ? "bg-purple-100 text-purple-600" :
                  "bg-zinc-100 text-zinc-600"
                }`}>
                  {currentConnector.icon}
                </div>
                <div>
                  <h3 className="font-medium text-foreground">Connect {currentConnector.name}</h3>
                  <p className="text-xs text-muted-foreground">Enter your API credentials</p>
                </div>
              </div>

              <div className="space-y-4">
                <div>
                  <label className="block text-sm font-medium text-foreground mb-1.5">
                    API Key
                  </label>
                  <div className="relative">
                    <Lock className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
                    <input
                      type="password"
                      value={apiKey}
                      onChange={(e) => setApiKey(e.target.value)}
                      placeholder="Enter your API key"
                      className="w-full pl-9 pr-3 py-2 rounded-lg border border-border bg-background text-sm focus:outline-none focus:ring-2 focus:ring-amber-500/20 focus:border-amber-500"
                    />
                  </div>
                </div>

                <div className="flex items-start gap-2 p-3 rounded-lg bg-muted/50 border border-border">
                  <AlertCircle className="h-4 w-4 text-muted-foreground shrink-0 mt-0.5" />
                  <div className="text-xs text-muted-foreground">
                    <span className="font-medium text-foreground">Demo mode:</span> Enter any value to simulate connection
                  </div>
                </div>

                <button
                  onClick={handleAuth}
                  disabled={!apiKey}
                  className="w-full flex items-center justify-center gap-2 px-4 py-2.5 rounded-lg bg-amber-600 text-white text-sm font-medium hover:bg-amber-500 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                >
                  <Lock className="h-4 w-4" />
                  Connect Securely
                </button>

                <a
                  href="#"
                  className="flex items-center justify-center gap-1 text-xs text-muted-foreground hover:text-foreground transition-colors"
                >
                  View documentation
                  <ExternalLink className="h-3 w-3" />
                </a>
              </div>
            </motion.div>
          )}

          {step === "sync" && currentConnector && (
            <motion.div
              key="sync"
              initial={{ opacity: 0, scale: 0.95 }}
              animate={{ opacity: 1, scale: 1 }}
              exit={{ opacity: 0 }}
              className="flex flex-col items-center justify-center py-8"
            >
              <div className="relative mb-4">
                <div className={`h-16 w-16 rounded-xl flex items-center justify-center text-lg font-bold ${
                  currentConnector.id === "salesforce" ? "bg-blue-100 text-blue-600" :
                  currentConnector.id === "hubspot" ? "bg-orange-100 text-orange-600" :
                  currentConnector.id === "slack" ? "bg-purple-100 text-purple-600" :
                  "bg-zinc-100 text-zinc-600"
                }`}>
                  {currentConnector.icon}
                </div>
                <div className="absolute -bottom-1 -right-1 h-6 w-6 rounded-full bg-amber-100 flex items-center justify-center">
                  <RefreshCw className="h-3 w-3 text-amber-600 animate-spin" />
                </div>
              </div>
              <h3 className="font-medium text-foreground mb-1">Syncing {currentConnector.name}</h3>
              <p className="text-sm text-muted-foreground">Fetching your data...</p>
              
              <div className="w-48 h-1 bg-muted rounded-full overflow-hidden mt-4">
                <motion.div
                  className="h-full bg-amber-500"
                  initial={{ width: "0%" }}
                  animate={{ width: "100%" }}
                  transition={{ duration: 2.5, ease: "linear" }}
                />
              </div>
            </motion.div>
          )}

          {step === "done" && currentConnector && (
            <motion.div
              key="done"
              initial={{ opacity: 0, scale: 0.95 }}
              animate={{ opacity: 1, scale: 1 }}
              className="flex flex-col items-center justify-center py-8"
            >
              <div className="h-16 w-16 rounded-full bg-emerald-100 flex items-center justify-center mb-4">
                <Check className="h-8 w-8 text-emerald-600" />
              </div>
              <h3 className="font-medium text-foreground mb-1">Connected!</h3>
              <p className="text-sm text-muted-foreground mb-4">
                {currentConnector.name} is now ready to use
              </p>
              
              <div className="flex items-center gap-4 text-sm">
                <div className="text-center">
                  <div className="font-semibold text-foreground">{currentConnector.records?.toLocaleString()}</div>
                  <div className="text-xs text-muted-foreground">Records synced</div>
                </div>
                <div className="w-px h-8 bg-border" />
                <div className="text-center">
                  <div className="font-semibold text-foreground">{currentConnector.lastSync}</div>
                  <div className="text-xs text-muted-foreground">Last sync</div>
                </div>
              </div>

              <button
                onClick={handleReset}
                className="mt-6 px-4 py-2 rounded-lg bg-muted text-sm font-medium hover:bg-muted/80 transition-colors"
              >
                Connect Another
              </button>
            </motion.div>
          )}
        </AnimatePresence>
      </div>
    </div>
  )
}
