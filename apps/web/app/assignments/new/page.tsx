"use client"

import { Suspense, useState } from "react"
import { useRouter, useSearchParams } from "next/navigation"
import { motion, AnimatePresence } from "framer-motion"
import { AppShell } from "@/components/gravitre/app-shell"
import { Button } from "@/components/ui/button"
import { Icon } from "@/lib/icons"
import { cn } from "@/lib/utils"

// Types
interface Agent {
  id: string
  name: string
  role: string
  gradient: string
  trainingProgress: number
}

// Mock Data
const agents: Agent[] = [
  { id: "agent-001", name: "Atlas", role: "Marketing Agent", gradient: "from-emerald-500 to-teal-500", trainingProgress: 87 },
  { id: "agent-002", name: "Nexus", role: "Sales Assistant", gradient: "from-blue-500 to-indigo-500", trainingProgress: 92 },
  { id: "agent-003", name: "Sentinel", role: "Data Quality Agent", gradient: "from-amber-500 to-orange-500", trainingProgress: 78 },
  { id: "agent-004", name: "Oracle", role: "Finance Reporter", gradient: "from-violet-500 to-purple-500", trainingProgress: 65 },
]

const dataSources = [
  { id: "ds-1", name: "HubSpot CRM", icon: "database", connected: true },
  { id: "ds-2", name: "Salesforce", icon: "database", connected: true },
  { id: "ds-3", name: "Google Analytics", icon: "chart", connected: true },
  { id: "ds-4", name: "Notion Workspace", icon: "file", connected: false },
]

const outputTypes = [
  { id: "out-1", name: "Emails", icon: "mail", description: "Email drafts and sequences" },
  { id: "out-2", name: "Social Posts", icon: "share", description: "Content for social platforms" },
  { id: "out-3", name: "Segments", icon: "users", description: "Audience segments and lists" },
  { id: "out-4", name: "Workflows", icon: "workflow", description: "Automated workflows" },
  { id: "out-5", name: "Reports", icon: "chart", description: "Analysis and reports" },
]

const destinations = [
  { id: "dest-1", name: "HubSpot", icon: "database", description: "Push to marketing platform" },
  { id: "dest-2", name: "Outlook", icon: "mail", description: "Send via email" },
  { id: "dest-3", name: "Slack", icon: "chat", description: "Post to channels" },
  { id: "dest-4", name: "Salesforce", icon: "database", description: "Update CRM records" },
  { id: "dest-5", name: "Export", icon: "download", description: "Download files" },
]

const steps = [
  { id: 1, title: "Select Agent", description: "Choose which AI agent to assign" },
  { id: 2, title: "Task Brief", description: "Describe what you need done" },
  { id: 3, title: "Context", description: "Select data sources" },
  { id: 4, title: "Outputs", description: "Choose deliverables" },
  { id: 5, title: "Destination", description: "Where to send results" },
  { id: 6, title: "Review", description: "Confirm and run" },
]

function NewAssignmentPageContent() {
  const router = useRouter()
  const searchParams = useSearchParams()
  const preselectedAgent = searchParams.get("agent")
  
  const [currentStep, setCurrentStep] = useState(1)
  const [selectedAgent, setSelectedAgent] = useState<string | null>(preselectedAgent)
  const [taskBrief, setTaskBrief] = useState("")
  const [selectedSources, setSelectedSources] = useState<string[]>([])
  const [useTrainingKnowledge, setUseTrainingKnowledge] = useState(true)
  const [selectedOutputs, setSelectedOutputs] = useState<string[]>([])
  const [selectedDestinations, setSelectedDestinations] = useState<string[]>([])
  const [requireApproval, setRequireApproval] = useState(true)
  const [isRunning, setIsRunning] = useState(false)

  const agent = agents.find(a => a.id === selectedAgent)

  const canProceed = () => {
    switch (currentStep) {
      case 1: return selectedAgent !== null
      case 2: return taskBrief.length >= 10
      case 3: return true
      case 4: return selectedOutputs.length > 0
      case 5: return selectedDestinations.length > 0
      case 6: return true
      default: return false
    }
  }

  const handleNext = () => {
    if (currentStep < 6) {
      setCurrentStep(currentStep + 1)
    }
  }

  const handleBack = () => {
    if (currentStep > 1) {
      setCurrentStep(currentStep - 1)
    }
  }

  const handleRun = async () => {
    setIsRunning(true)
    await new Promise(resolve => setTimeout(resolve, 2000))
    router.push("/assignments/assign-001")
  }

  const toggleSource = (id: string) => {
    setSelectedSources(prev => 
      prev.includes(id) ? prev.filter(s => s !== id) : [...prev, id]
    )
  }

  const toggleOutput = (id: string) => {
    setSelectedOutputs(prev => 
      prev.includes(id) ? prev.filter(o => o !== id) : [...prev, id]
    )
  }

  const toggleDestination = (id: string) => {
    setSelectedDestinations(prev => 
      prev.includes(id) ? prev.filter(d => d !== id) : [...prev, id]
    )
  }

  return (
    <AppShell title="New Assignment">
      <div className="flex h-full">
        {/* Left Sidebar - Steps */}
        <div className="w-72 border-r border-border bg-card/50 flex flex-col">
          <div className="p-6 border-b border-border">
            <h2 className="font-semibold text-foreground">Assign Work</h2>
            <p className="text-sm text-muted-foreground mt-1">Create a new task for your agent</p>
          </div>
          
          <div className="p-6 flex-1">
            <div className="space-y-1">
              {steps.map((step, index) => {
                const isActive = step.id === currentStep
                const isCompleted = step.id < currentStep
                const isUpcoming = step.id > currentStep
                
                return (
                  <button
                    key={step.id}
                    onClick={() => step.id < currentStep && setCurrentStep(step.id)}
                    disabled={isUpcoming}
                    className={cn(
                      "w-full flex items-center gap-3 px-3 py-3 rounded-lg text-left transition-all",
                      isActive && "bg-secondary",
                      isCompleted && "hover:bg-secondary/50 cursor-pointer",
                      isUpcoming && "opacity-50 cursor-not-allowed"
                    )}
                  >
                    <div className={cn(
                      "h-8 w-8 rounded-full flex items-center justify-center text-sm font-medium shrink-0",
                      isActive && "bg-emerald-500 text-white",
                      isCompleted && "bg-emerald-500/20 text-emerald-400",
                      isUpcoming && "bg-secondary text-muted-foreground"
                    )}>
                      {isCompleted ? (
                        <Icon name="check" size="sm" />
                      ) : (
                        step.id
                      )}
                    </div>
                    <div>
                      <p className={cn(
                        "text-sm font-medium",
                        isActive ? "text-foreground" : "text-muted-foreground"
                      )}>
                        {step.title}
                      </p>
                      <p className="text-xs text-muted-foreground">{step.description}</p>
                    </div>
                  </button>
                )
              })}
            </div>
          </div>

          {/* Selected Agent Preview */}
          {agent && (
            <div className="p-6 border-t border-border">
              <div className="flex items-center gap-3">
                <div className={cn(
                  "h-10 w-10 rounded-xl flex items-center justify-center bg-gradient-to-br",
                  agent.gradient
                )}>
                  <Icon name="ai" size="sm" className="text-white" />
                </div>
                <div>
                  <p className="text-sm font-medium text-foreground">{agent.name}</p>
                  <p className="text-xs text-muted-foreground">{agent.role}</p>
                </div>
              </div>
            </div>
          )}
        </div>

        {/* Main Content */}
        <div className="flex-1 flex flex-col overflow-hidden">
          {/* Header */}
          <div className="px-8 py-6 border-b border-border">
            <div className="flex items-center justify-between">
              <div>
                <h1 className="text-xl font-bold text-foreground">{steps[currentStep - 1].title}</h1>
                <p className="text-sm text-muted-foreground mt-1">{steps[currentStep - 1].description}</p>
              </div>
              <div className="flex items-center gap-3">
                {currentStep > 1 && (
                  <Button variant="outline" onClick={handleBack}>
                    <Icon name="chevronLeft" size="sm" className="mr-1" />
                    Back
                  </Button>
                )}
                {currentStep < 6 ? (
                  <Button 
                    onClick={handleNext} 
                    disabled={!canProceed()}
                    className="gap-2"
                  >
                    Continue
                    <Icon name="chevronRight" size="sm" />
                  </Button>
                ) : (
                  <Button 
                    onClick={handleRun}
                    disabled={isRunning}
                    className="gap-2 bg-gradient-to-r from-emerald-500 to-teal-500 hover:from-emerald-600 hover:to-teal-600 text-white border-0"
                  >
                    {isRunning ? (
                      <>
                        <Icon name="running" size="sm" className="animate-spin" />
                        Starting...
                      </>
                    ) : (
                      <>
                        <Icon name="play" size="sm" />
                        Run Task
                      </>
                    )}
                  </Button>
                )}
              </div>
            </div>
          </div>

          {/* Step Content */}
          <div className="flex-1 overflow-y-auto p-8">
            <AnimatePresence mode="wait">
              {/* Step 1: Select Agent */}
              {currentStep === 1 && (
                <motion.div
                  key="step-1"
                  initial={{ opacity: 0, x: 20 }}
                  animate={{ opacity: 1, x: 0 }}
                  exit={{ opacity: 0, x: -20 }}
                  className="grid grid-cols-2 gap-4"
                >
                  {agents.map((a) => (
                    <button
                      key={a.id}
                      onClick={() => setSelectedAgent(a.id)}
                      className={cn(
                        "flex items-center gap-4 p-5 rounded-xl border transition-all text-left",
                        selectedAgent === a.id
                          ? "border-emerald-500/50 bg-emerald-500/5 ring-1 ring-emerald-500/20"
                          : "border-border bg-card hover:border-border/80 hover:bg-secondary/30"
                      )}
                    >
                      <div className={cn(
                        "h-14 w-14 rounded-xl flex items-center justify-center bg-gradient-to-br shrink-0",
                        a.gradient
                      )}>
                        <Icon name="ai" size="lg" className="text-white" />
                      </div>
                      <div className="flex-1">
                        <p className="font-semibold text-foreground">{a.name}</p>
                        <p className="text-sm text-muted-foreground">{a.role}</p>
                        <div className="flex items-center gap-2 mt-2">
                          <div className="flex-1 h-1.5 bg-secondary rounded-full overflow-hidden">
                            <div 
                              className="h-full bg-gradient-to-r from-emerald-500 to-teal-500 rounded-full"
                              style={{ width: `${a.trainingProgress}%` }}
                            />
                          </div>
                          <span className="text-xs text-emerald-400">{a.trainingProgress}%</span>
                        </div>
                      </div>
                      {selectedAgent === a.id && (
                        <div className="h-6 w-6 rounded-full bg-emerald-500 flex items-center justify-center">
                          <Icon name="check" size="xs" className="text-white" />
                        </div>
                      )}
                    </button>
                  ))}
                </motion.div>
              )}

              {/* Step 2: Task Brief */}
              {currentStep === 2 && (
                <motion.div
                  key="step-2"
                  initial={{ opacity: 0, x: 20 }}
                  animate={{ opacity: 1, x: 0 }}
                  exit={{ opacity: 0, x: -20 }}
                  className="max-w-2xl"
                >
                  <div className="rounded-xl border border-border bg-card overflow-hidden">
                    <div className="px-6 py-4 border-b border-border bg-gradient-to-r from-emerald-500/5 to-transparent">
                      <h3 className="font-semibold text-foreground">What do you need done?</h3>
                      <p className="text-sm text-muted-foreground mt-1">
                        Describe the task in detail. Be specific about what you want to achieve.
                      </p>
                    </div>
                    <div className="p-6">
                      <textarea
                        value={taskBrief}
                        onChange={(e) => setTaskBrief(e.target.value)}
                        placeholder="e.g., Create a Q3 campaign for mid-market healthcare prospects. Include email sequences, social posts for LinkedIn, and audience segments based on engagement data..."
                        className="w-full h-48 rounded-lg border border-border bg-secondary px-4 py-3 text-sm resize-none focus:outline-none focus:ring-1 focus:ring-ring"
                      />
                      <div className="flex items-center justify-between mt-4">
                        <span className="text-xs text-muted-foreground">
                          {taskBrief.length} characters
                        </span>
                        <div className="flex gap-2">
                          {["Campaign", "Report", "Analysis", "Content"].map((template) => (
                            <Button
                              key={template}
                              variant="outline"
                              size="sm"
                              className="text-xs"
                              onClick={() => setTaskBrief(prev => prev + ` [${template} template]`)}
                            >
                              {template}
                            </Button>
                          ))}
                        </div>
                      </div>
                    </div>
                  </div>
                </motion.div>
              )}

              {/* Step 3: Context Selection */}
              {currentStep === 3 && (
                <motion.div
                  key="step-3"
                  initial={{ opacity: 0, x: 20 }}
                  animate={{ opacity: 1, x: 0 }}
                  exit={{ opacity: 0, x: -20 }}
                  className="space-y-6"
                >
                  {/* Training Knowledge Toggle */}
                  <div className="rounded-xl border border-emerald-500/30 bg-emerald-500/5 p-5">
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-4">
                        <div className="h-10 w-10 rounded-lg bg-emerald-500/10 flex items-center justify-center">
                          <Icon name="brain" size="md" className="text-emerald-400" />
                        </div>
                        <div>
                          <p className="font-semibold text-foreground">Use Training Knowledge</p>
                          <p className="text-sm text-muted-foreground">
                            Apply everything the agent has learned about your business
                          </p>
                        </div>
                      </div>
                      <button
                        onClick={() => setUseTrainingKnowledge(!useTrainingKnowledge)}
                        className={cn(
                          "h-6 w-11 rounded-full transition-colors",
                          useTrainingKnowledge ? "bg-emerald-500" : "bg-secondary"
                        )}
                      >
                        <div className={cn(
                          "h-5 w-5 rounded-full bg-white shadow transition-transform",
                          useTrainingKnowledge ? "translate-x-5" : "translate-x-0.5"
                        )} />
                      </button>
                    </div>
                  </div>

                  {/* Data Sources */}
                  <div className="rounded-xl border border-border bg-card overflow-hidden">
                    <div className="px-6 py-4 border-b border-border">
                      <h3 className="font-semibold text-foreground">Data Sources</h3>
                      <p className="text-sm text-muted-foreground">Select systems to pull data from</p>
                    </div>
                    <div className="p-6 grid grid-cols-2 gap-3">
                      {dataSources.map((source) => (
                        <button
                          key={source.id}
                          onClick={() => source.connected && toggleSource(source.id)}
                          disabled={!source.connected}
                          className={cn(
                            "flex items-center gap-3 p-4 rounded-lg border transition-all text-left",
                            selectedSources.includes(source.id)
                              ? "border-blue-500/50 bg-blue-500/5"
                              : "border-border hover:border-border/80",
                            !source.connected && "opacity-50 cursor-not-allowed"
                          )}
                        >
                          <div className={cn(
                            "h-10 w-10 rounded-lg flex items-center justify-center",
                            selectedSources.includes(source.id) ? "bg-blue-500/10" : "bg-secondary"
                          )}>
                            <Icon 
                              name={source.icon as any} 
                              size="sm" 
                              className={selectedSources.includes(source.id) ? "text-blue-400" : "text-muted-foreground"} 
                            />
                          </div>
                          <div className="flex-1">
                            <p className="text-sm font-medium text-foreground">{source.name}</p>
                            <p className="text-xs text-muted-foreground">
                              {source.connected ? "Connected" : "Not connected"}
                            </p>
                          </div>
                          {selectedSources.includes(source.id) && (
                            <Icon name="check" size="sm" className="text-blue-400" />
                          )}
                        </button>
                      ))}
                    </div>
                  </div>
                </motion.div>
              )}

              {/* Step 4: Output Types */}
              {currentStep === 4 && (
                <motion.div
                  key="step-4"
                  initial={{ opacity: 0, x: 20 }}
                  animate={{ opacity: 1, x: 0 }}
                  exit={{ opacity: 0, x: -20 }}
                  className="space-y-4"
                >
                  <p className="text-sm text-muted-foreground mb-4">
                    Select the types of deliverables you want the agent to create
                  </p>
                  <div className="grid grid-cols-3 gap-4">
                    {outputTypes.map((output) => (
                      <button
                        key={output.id}
                        onClick={() => toggleOutput(output.id)}
                        className={cn(
                          "flex flex-col items-center gap-3 p-6 rounded-xl border transition-all",
                          selectedOutputs.includes(output.id)
                            ? "border-violet-500/50 bg-violet-500/5 ring-1 ring-violet-500/20"
                            : "border-border bg-card hover:border-border/80"
                        )}
                      >
                        <div className={cn(
                          "h-12 w-12 rounded-xl flex items-center justify-center",
                          selectedOutputs.includes(output.id) ? "bg-violet-500/10" : "bg-secondary"
                        )}>
                          <Icon 
                            name={output.icon as any} 
                            size="lg" 
                            className={selectedOutputs.includes(output.id) ? "text-violet-400" : "text-muted-foreground"} 
                          />
                        </div>
                        <div className="text-center">
                          <p className="font-medium text-foreground">{output.name}</p>
                          <p className="text-xs text-muted-foreground mt-1">{output.description}</p>
                        </div>
                        {selectedOutputs.includes(output.id) && (
                          <div className="h-5 w-5 rounded-full bg-violet-500 flex items-center justify-center">
                            <Icon name="check" size="xs" className="text-white" />
                          </div>
                        )}
                      </button>
                    ))}
                  </div>
                </motion.div>
              )}

              {/* Step 5: Destination */}
              {currentStep === 5 && (
                <motion.div
                  key="step-5"
                  initial={{ opacity: 0, x: 20 }}
                  animate={{ opacity: 1, x: 0 }}
                  exit={{ opacity: 0, x: -20 }}
                  className="space-y-6"
                >
                  <p className="text-sm text-muted-foreground">
                    Choose where to send the results
                  </p>
                  <div className="grid grid-cols-3 gap-4">
                    {destinations.map((dest) => (
                      <button
                        key={dest.id}
                        onClick={() => toggleDestination(dest.id)}
                        className={cn(
                          "flex items-center gap-4 p-5 rounded-xl border transition-all text-left",
                          selectedDestinations.includes(dest.id)
                            ? "border-amber-500/50 bg-amber-500/5"
                            : "border-border bg-card hover:border-border/80"
                        )}
                      >
                        <div className={cn(
                          "h-10 w-10 rounded-lg flex items-center justify-center shrink-0",
                          selectedDestinations.includes(dest.id) ? "bg-amber-500/10" : "bg-secondary"
                        )}>
                          <Icon 
                            name={dest.icon as any} 
                            size="sm" 
                            className={selectedDestinations.includes(dest.id) ? "text-amber-400" : "text-muted-foreground"} 
                          />
                        </div>
                        <div className="flex-1">
                          <p className="font-medium text-foreground">{dest.name}</p>
                          <p className="text-xs text-muted-foreground">{dest.description}</p>
                        </div>
                        {selectedDestinations.includes(dest.id) && (
                          <Icon name="check" size="sm" className="text-amber-400" />
                        )}
                      </button>
                    ))}
                  </div>

                  {/* Approval Settings */}
                  <div className="rounded-xl border border-border bg-card p-5">
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-4">
                        <div className="h-10 w-10 rounded-lg bg-secondary flex items-center justify-center">
                          <Icon name="shield" size="sm" className="text-muted-foreground" />
                        </div>
                        <div>
                          <p className="font-medium text-foreground">Require Approval Before Sending</p>
                          <p className="text-sm text-muted-foreground">
                            Review and approve outputs before they are delivered
                          </p>
                        </div>
                      </div>
                      <button
                        onClick={() => setRequireApproval(!requireApproval)}
                        className={cn(
                          "h-6 w-11 rounded-full transition-colors",
                          requireApproval ? "bg-emerald-500" : "bg-secondary"
                        )}
                      >
                        <div className={cn(
                          "h-5 w-5 rounded-full bg-white shadow transition-transform",
                          requireApproval ? "translate-x-5" : "translate-x-0.5"
                        )} />
                      </button>
                    </div>
                  </div>
                </motion.div>
              )}

              {/* Step 6: Review */}
              {currentStep === 6 && (
                <motion.div
                  key="step-6"
                  initial={{ opacity: 0, x: 20 }}
                  animate={{ opacity: 1, x: 0 }}
                  exit={{ opacity: 0, x: -20 }}
                  className="max-w-2xl space-y-6"
                >
                  {/* Summary Card */}
                  <div className="rounded-xl border border-border bg-card overflow-hidden">
                    <div className="px-6 py-4 border-b border-border bg-gradient-to-r from-emerald-500/5 to-transparent">
                      <h3 className="font-semibold text-foreground">Assignment Summary</h3>
                    </div>
                    <div className="divide-y divide-border">
                      {/* Agent */}
                      <div className="px-6 py-4 flex items-center justify-between">
                        <span className="text-sm text-muted-foreground">Agent</span>
                        <div className="flex items-center gap-2">
                          <div className={cn(
                            "h-6 w-6 rounded-md flex items-center justify-center bg-gradient-to-br",
                            agent?.gradient
                          )}>
                            <Icon name="ai" size="xs" className="text-white" />
                          </div>
                          <span className="text-sm font-medium text-foreground">{agent?.name}</span>
                        </div>
                      </div>
                      
                      {/* Task */}
                      <div className="px-6 py-4">
                        <span className="text-sm text-muted-foreground block mb-2">Task Brief</span>
                        <p className="text-sm text-foreground">{taskBrief || "No task description"}</p>
                      </div>
                      
                      {/* Context */}
                      <div className="px-6 py-4 flex items-center justify-between">
                        <span className="text-sm text-muted-foreground">Training Knowledge</span>
                        <span className={cn(
                          "text-sm font-medium",
                          useTrainingKnowledge ? "text-emerald-400" : "text-muted-foreground"
                        )}>
                          {useTrainingKnowledge ? "Enabled" : "Disabled"}
                        </span>
                      </div>
                      
                      {/* Outputs */}
                      <div className="px-6 py-4">
                        <span className="text-sm text-muted-foreground block mb-2">Outputs</span>
                        <div className="flex flex-wrap gap-2">
                          {selectedOutputs.map((id) => {
                            const output = outputTypes.find(o => o.id === id)
                            return output && (
                              <span key={id} className="px-3 py-1 rounded-lg bg-violet-500/10 text-sm text-violet-400">
                                {output.name}
                              </span>
                            )
                          })}
                        </div>
                      </div>
                      
                      {/* Destinations */}
                      <div className="px-6 py-4">
                        <span className="text-sm text-muted-foreground block mb-2">Destinations</span>
                        <div className="flex flex-wrap gap-2">
                          {selectedDestinations.map((id) => {
                            const dest = destinations.find(d => d.id === id)
                            return dest && (
                              <span key={id} className="px-3 py-1 rounded-lg bg-amber-500/10 text-sm text-amber-400">
                                {dest.name}
                              </span>
                            )
                          })}
                        </div>
                      </div>
                      
                      {/* Approval */}
                      <div className="px-6 py-4 flex items-center justify-between">
                        <span className="text-sm text-muted-foreground">Approval Required</span>
                        <span className={cn(
                          "text-sm font-medium",
                          requireApproval ? "text-emerald-400" : "text-amber-400"
                        )}>
                          {requireApproval ? "Yes" : "No (Auto-send)"}
                        </span>
                      </div>
                    </div>
                  </div>

                  {/* Ready Notice */}
                  <div className="rounded-xl border border-emerald-500/30 bg-emerald-500/5 p-5">
                    <div className="flex items-start gap-4">
                      <div className="h-10 w-10 rounded-lg bg-emerald-500/10 flex items-center justify-center shrink-0">
                        <Icon name="sparkles" size="md" className="text-emerald-400" />
                      </div>
                      <div>
                        <p className="font-semibold text-foreground">Ready to run</p>
                        <p className="text-sm text-muted-foreground mt-1">
                          {agent?.name} will start working on this task immediately. You can track progress in real-time.
                        </p>
                      </div>
                    </div>
                  </div>
                </motion.div>
              )}
            </AnimatePresence>
          </div>
        </div>
      </div>
    </AppShell>
  )
}

export default function NewAssignmentPage() {
  return (
    <Suspense fallback={<AppShell title="New Assignment" />}>
      <NewAssignmentPageContent />
    </Suspense>
  )
}
