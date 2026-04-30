"use client"

import { useState } from "react"
import { motion, AnimatePresence } from "framer-motion"
import { Bot, Plus, Sparkles, Check, ChevronRight, Settings, Zap } from "lucide-react"

const AGENT_TEMPLATES = [
  { id: "lead-router", name: "Lead Router", description: "Route leads based on criteria", icon: "zap" },
  { id: "data-sync", name: "Data Sync", description: "Sync data between systems", icon: "refresh" },
  { id: "email-responder", name: "Email Responder", description: "Auto-respond to emails", icon: "mail" },
  { id: "custom", name: "Custom Agent", description: "Build from scratch", icon: "plus" },
]

const CAPABILITIES = [
  { id: "salesforce", name: "Salesforce", type: "connector" },
  { id: "hubspot", name: "HubSpot", type: "connector" },
  { id: "slack", name: "Slack", type: "connector" },
  { id: "email", name: "Email", type: "connector" },
]

export function AgentDemo() {
  const [step, setStep] = useState(0)
  const [agentName, setAgentName] = useState("")
  const [selectedTemplate, setSelectedTemplate] = useState<string | null>(null)
  const [selectedCapabilities, setSelectedCapabilities] = useState<string[]>([])
  const [isCreating, setIsCreating] = useState(false)
  const [isComplete, setIsComplete] = useState(false)

  const handleCreate = () => {
    setIsCreating(true)
    setTimeout(() => {
      setIsCreating(false)
      setIsComplete(true)
    }, 2000)
  }

  const reset = () => {
    setStep(0)
    setAgentName("")
    setSelectedTemplate(null)
    setSelectedCapabilities([])
    setIsCreating(false)
    setIsComplete(false)
  }

  return (
    <div className="relative rounded-xl border border-border bg-background overflow-hidden">
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-border bg-muted/30">
        <div className="flex items-center gap-2">
          <div className="h-8 w-8 rounded-lg bg-emerald-100 flex items-center justify-center">
            <Bot className="h-4 w-4 text-emerald-600" />
          </div>
          <span className="font-medium text-sm text-foreground">Create AI Agent</span>
        </div>
        <div className="flex items-center gap-1">
          {[0, 1, 2].map((i) => (
            <div
              key={i}
              className={`h-1.5 w-6 rounded-full transition-colors ${
                i <= step ? "bg-emerald-500" : "bg-muted"
              }`}
            />
          ))}
        </div>
      </div>

      {/* Content */}
      <div className="p-6 min-h-[320px]">
        <AnimatePresence mode="wait">
          {isComplete ? (
            <motion.div
              key="complete"
              initial={{ opacity: 0, scale: 0.95 }}
              animate={{ opacity: 1, scale: 1 }}
              className="flex flex-col items-center justify-center h-full py-8"
            >
              <div className="h-16 w-16 rounded-full bg-emerald-100 flex items-center justify-center mb-4">
                <Check className="h-8 w-8 text-emerald-600" />
              </div>
              <h3 className="text-lg font-semibold text-foreground mb-2">Agent Created!</h3>
              <p className="text-sm text-muted-foreground text-center mb-6">
                {agentName || "Your agent"} is ready to use
              </p>
              <button
                onClick={reset}
                className="px-4 py-2 rounded-lg bg-muted text-sm font-medium hover:bg-muted/80 transition-colors"
              >
                Create Another
              </button>
            </motion.div>
          ) : step === 0 ? (
            <motion.div
              key="step-0"
              initial={{ opacity: 0, x: 20 }}
              animate={{ opacity: 1, x: 0 }}
              exit={{ opacity: 0, x: -20 }}
            >
              <h3 className="text-lg font-semibold text-foreground mb-1">Choose a template</h3>
              <p className="text-sm text-muted-foreground mb-4">Start with a pre-built agent or create your own</p>
              <div className="grid grid-cols-2 gap-3">
                {AGENT_TEMPLATES.map((template) => (
                  <button
                    key={template.id}
                    onClick={() => {
                      setSelectedTemplate(template.id)
                      setStep(1)
                    }}
                    className={`p-4 rounded-lg border text-left transition-all hover:border-emerald-500/50 hover:bg-emerald-50/50 ${
                      selectedTemplate === template.id
                        ? "border-emerald-500 bg-emerald-50"
                        : "border-border"
                    }`}
                  >
                    <div className="h-8 w-8 rounded-lg bg-muted flex items-center justify-center mb-2">
                      {template.icon === "plus" ? (
                        <Plus className="h-4 w-4 text-muted-foreground" />
                      ) : (
                        <Zap className="h-4 w-4 text-muted-foreground" />
                      )}
                    </div>
                    <div className="font-medium text-sm text-foreground">{template.name}</div>
                    <div className="text-xs text-muted-foreground">{template.description}</div>
                  </button>
                ))}
              </div>
            </motion.div>
          ) : step === 1 ? (
            <motion.div
              key="step-1"
              initial={{ opacity: 0, x: 20 }}
              animate={{ opacity: 1, x: 0 }}
              exit={{ opacity: 0, x: -20 }}
            >
              <h3 className="text-lg font-semibold text-foreground mb-1">Configure your agent</h3>
              <p className="text-sm text-muted-foreground mb-4">Give it a name and select capabilities</p>
              
              <div className="space-y-4">
                <div>
                  <label className="block text-sm font-medium text-foreground mb-1.5">Agent Name</label>
                  <input
                    type="text"
                    value={agentName}
                    onChange={(e) => setAgentName(e.target.value)}
                    placeholder="e.g., Sales Lead Router"
                    className="w-full px-3 py-2 rounded-lg border border-border bg-background text-sm focus:outline-none focus:ring-2 focus:ring-emerald-500/20 focus:border-emerald-500"
                  />
                </div>
                
                <div>
                  <label className="block text-sm font-medium text-foreground mb-1.5">Capabilities</label>
                  <div className="flex flex-wrap gap-2">
                    {CAPABILITIES.map((cap) => (
                      <button
                        key={cap.id}
                        onClick={() => {
                          setSelectedCapabilities((prev) =>
                            prev.includes(cap.id)
                              ? prev.filter((c) => c !== cap.id)
                              : [...prev, cap.id]
                          )
                        }}
                        className={`px-3 py-1.5 rounded-full text-xs font-medium transition-colors ${
                          selectedCapabilities.includes(cap.id)
                            ? "bg-emerald-100 text-emerald-700 border border-emerald-200"
                            : "bg-muted text-muted-foreground border border-transparent hover:bg-muted/80"
                        }`}
                      >
                        {cap.name}
                      </button>
                    ))}
                  </div>
                </div>
              </div>
            </motion.div>
          ) : (
            <motion.div
              key="step-2"
              initial={{ opacity: 0, x: 20 }}
              animate={{ opacity: 1, x: 0 }}
              exit={{ opacity: 0, x: -20 }}
            >
              <h3 className="text-lg font-semibold text-foreground mb-1">Review and create</h3>
              <p className="text-sm text-muted-foreground mb-4">Confirm your agent configuration</p>
              
              <div className="rounded-lg border border-border p-4 space-y-3">
                <div className="flex items-center justify-between">
                  <span className="text-sm text-muted-foreground">Name</span>
                  <span className="text-sm font-medium text-foreground">{agentName || "Unnamed Agent"}</span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-sm text-muted-foreground">Template</span>
                  <span className="text-sm font-medium text-foreground">
                    {AGENT_TEMPLATES.find((t) => t.id === selectedTemplate)?.name || "Custom"}
                  </span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-sm text-muted-foreground">Capabilities</span>
                  <span className="text-sm font-medium text-foreground">
                    {selectedCapabilities.length} selected
                  </span>
                </div>
              </div>
              
              {isCreating && (
                <div className="mt-4 flex items-center gap-2 text-sm text-muted-foreground">
                  <Sparkles className="h-4 w-4 animate-pulse text-emerald-500" />
                  <span>Creating agent...</span>
                </div>
              )}
            </motion.div>
          )}
        </AnimatePresence>
      </div>

      {/* Footer */}
      {!isComplete && (
        <div className="flex items-center justify-between px-6 py-4 border-t border-border bg-muted/20">
          <button
            onClick={() => setStep(Math.max(0, step - 1))}
            disabled={step === 0}
            className="px-4 py-2 rounded-lg text-sm font-medium text-muted-foreground hover:text-foreground disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
          >
            Back
          </button>
          {step < 2 ? (
            <button
              onClick={() => setStep(step + 1)}
              disabled={step === 1 && !agentName}
              className="flex items-center gap-1 px-4 py-2 rounded-lg bg-emerald-600 text-white text-sm font-medium hover:bg-emerald-500 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
            >
              Continue
              <ChevronRight className="h-4 w-4" />
            </button>
          ) : (
            <button
              onClick={handleCreate}
              disabled={isCreating}
              className="flex items-center gap-2 px-4 py-2 rounded-lg bg-emerald-600 text-white text-sm font-medium hover:bg-emerald-500 disabled:opacity-50 transition-colors"
            >
              {isCreating ? (
                <>
                  <span className="h-4 w-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                  Creating...
                </>
              ) : (
                <>
                  <Sparkles className="h-4 w-4" />
                  Create Agent
                </>
              )}
            </button>
          )}
        </div>
      )}
    </div>
  )
}
