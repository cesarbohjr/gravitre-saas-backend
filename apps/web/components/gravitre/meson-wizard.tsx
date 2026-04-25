"use client"

import { useState } from "react"
import { motion, AnimatePresence } from "framer-motion"
import { 
  Blocks, 
  ArrowRight, 
  ArrowLeft, 
  Check, 
  Loader2, 
  Sparkles,
  FileText,
  Workflow,
  Bot,
  Mail,
  BarChart3,
  Zap,
  Database,
  Calendar,
  Users,
  Target,
  X
} from "lucide-react"
import { Button } from "@/components/ui/button"
import { cn } from "@/lib/utils"
import Link from "next/link"

interface MesonWizardProps {
  open: boolean
  onClose: () => void
  onComplete?: (result: MesonResult) => void
  userPlan?: "node" | "control" | "command"
}

interface MesonResult {
  intent: string
  department: string
  systems: string[]
  outputTypes: string[]
  generatedConfig: {
    agent: string
    training: string[]
    workflows: string[]
    sampleOutputs: string[]
  }
}

const departments = [
  { id: "marketing", name: "Marketing", icon: Target },
  { id: "sales", name: "Sales", icon: Users },
  { id: "operations", name: "Operations", icon: Workflow },
  { id: "finance", name: "Finance", icon: BarChart3 },
  { id: "hr", name: "HR", icon: Users },
  { id: "custom", name: "Custom", icon: Sparkles },
]

const systems = [
  { id: "crm", name: "CRM", icon: Database, description: "Salesforce, HubSpot, Pipedrive" },
  { id: "email", name: "Email", icon: Mail, description: "Outlook, Gmail, Mailchimp" },
  { id: "calendar", name: "Calendar", icon: Calendar, description: "Google Calendar, Outlook" },
  { id: "data", name: "Data Sources", icon: Database, description: "Spreadsheets, APIs, databases" },
  { id: "messaging", name: "Messaging", icon: Zap, description: "Slack, Teams, Discord" },
]

const outputTypes = [
  { id: "campaigns", name: "Campaigns", description: "Email sequences, marketing campaigns" },
  { id: "workflows", name: "Workflows", description: "Automated multi-step processes" },
  { id: "reports", name: "Reports", description: "Analytics, summaries, insights" },
  { id: "sequences", name: "Sequences", description: "Outreach and follow-up sequences" },
]

const steps = [
  { id: 1, name: "Intent", description: "What do you want to build?" },
  { id: 2, name: "Context", description: "Select department and systems" },
  { id: 3, name: "Scope", description: "Choose output types" },
  { id: 4, name: "Generate", description: "Run Meson" },
  { id: 5, name: "Output", description: "Review and deploy" },
]

const generationStates = [
  { label: "Planning", description: "Analyzing your requirements..." },
  { label: "Structuring", description: "Building agent configuration..." },
  { label: "Generating", description: "Creating workflows and training..." },
  { label: "Finalizing", description: "Preparing your system..." },
]

export function MesonWizard({ open, onClose, onComplete, userPlan = "control" }: MesonWizardProps) {
  const [currentStep, setCurrentStep] = useState(1)
  
  // Feature gate check - Node users cannot access Meson
  const canAccessMeson = userPlan === "control" || userPlan === "command"
  const [intent, setIntent] = useState("")
  const [selectedDepartment, setSelectedDepartment] = useState<string | null>(null)
  const [selectedSystems, setSelectedSystems] = useState<string[]>([])
  const [selectedOutputs, setSelectedOutputs] = useState<string[]>([])
  const [isGenerating, setIsGenerating] = useState(false)
  const [generationStep, setGenerationStep] = useState(0)
  const [generatedResult, setGeneratedResult] = useState<MesonResult | null>(null)

  const canProceed = () => {
    switch (currentStep) {
      case 1: return intent.trim().length > 10
      case 2: return selectedDepartment && selectedSystems.length > 0
      case 3: return selectedOutputs.length > 0
      case 4: return true
      default: return false
    }
  }

  const handleNext = () => {
    if (currentStep < 4) {
      setCurrentStep(currentStep + 1)
    } else if (currentStep === 4) {
      runMeson()
    }
  }

  const handleBack = () => {
    if (currentStep > 1) {
      setCurrentStep(currentStep - 1)
    }
  }

  const runMeson = async () => {
    setIsGenerating(true)
    
    // Simulate generation steps
    for (let i = 0; i < generationStates.length; i++) {
      setGenerationStep(i)
      await new Promise(resolve => setTimeout(resolve, 1200))
    }
    
    // Generate mock result
    const result: MesonResult = {
      intent,
      department: selectedDepartment || "custom",
      systems: selectedSystems,
      outputTypes: selectedOutputs,
      generatedConfig: {
        agent: `${selectedDepartment?.charAt(0).toUpperCase()}${selectedDepartment?.slice(1)} Agent`,
        training: [
          "Brand voice guidelines",
          "ICP documentation",
          "Historical campaign data",
          "Performance benchmarks"
        ],
        workflows: [
          "Lead qualification workflow",
          "Content generation pipeline",
          "Approval routing system",
          "Delivery automation"
        ],
        sampleOutputs: [
          "Welcome email sequence (5 emails)",
          "Lead scoring report",
          "Campaign performance summary",
          "Follow-up reminder workflow"
        ]
      }
    }
    
    setGeneratedResult(result)
    setIsGenerating(false)
    setCurrentStep(5)
  }

  const handleDeploy = () => {
    if (generatedResult && onComplete) {
      onComplete(generatedResult)
    }
    handleClose()
  }

  const handleClose = () => {
    // Reset state
    setCurrentStep(1)
    setIntent("")
    setSelectedDepartment(null)
    setSelectedSystems([])
    setSelectedOutputs([])
    setIsGenerating(false)
    setGenerationStep(0)
    setGeneratedResult(null)
    onClose()
  }

  const toggleSystem = (id: string) => {
    setSelectedSystems(prev => 
      prev.includes(id) ? prev.filter(s => s !== id) : [...prev, id]
    )
  }

  const toggleOutput = (id: string) => {
    setSelectedOutputs(prev => 
      prev.includes(id) ? prev.filter(o => o !== id) : [...prev, id]
    )
  }

  if (!open) return null

  // Show upgrade prompt for Node users
  if (!canAccessMeson) {
    return (
      <div className="fixed inset-0 z-50 flex items-center justify-center">
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          className="absolute inset-0 bg-black/80 backdrop-blur-sm"
          onClick={handleClose}
        />
        <motion.div
          initial={{ opacity: 0, scale: 0.95, y: 20 }}
          animate={{ opacity: 1, scale: 1, y: 0 }}
          exit={{ opacity: 0, scale: 0.95, y: 20 }}
          className="relative w-full max-w-md overflow-hidden rounded-2xl border border-border bg-card shadow-2xl"
        >
          <div className="relative p-6 bg-gradient-to-br from-violet-500/10 to-transparent">
            <button
              onClick={handleClose}
              className="absolute top-4 right-4 h-8 w-8 rounded-lg hover:bg-secondary flex items-center justify-center transition-colors"
            >
              <X className="h-4 w-4 text-muted-foreground" />
            </button>
            <div className="h-14 w-14 rounded-2xl bg-gradient-to-br from-violet-500 to-purple-500 flex items-center justify-center mb-4">
              <Blocks className="h-7 w-7 text-white" />
            </div>
            <h2 className="text-xl font-semibold text-foreground">
              Meson is available in Control and Command
            </h2>
            <p className="mt-2 text-sm text-muted-foreground">
              Meson creates agents, training, and workflows from a single request. Upgrade to unlock this powerful system builder.
            </p>
          </div>
          <div className="p-6 space-y-4">
            <p className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
              What you get with Meson
            </p>
            <ul className="space-y-3">
              {["Create agents automatically", "Generate training structures", "Build workflows in seconds", "Deploy immediately"].map((benefit, i) => (
                <li key={i} className="flex items-center gap-3">
                  <div className="h-5 w-5 rounded-full bg-gradient-to-br from-violet-500 to-purple-500 flex items-center justify-center">
                    <Check className="h-3 w-3 text-white" />
                  </div>
                  <span className="text-sm text-foreground">{benefit}</span>
                </li>
              ))}
            </ul>
          </div>
          <div className="p-6 bg-secondary/30 border-t border-border">
            <div className="flex items-center justify-between mb-4">
              <div>
                <p className="text-sm font-medium text-foreground">Control Plan</p>
                <p className="text-xs text-muted-foreground">Includes 10 Mesons / month</p>
              </div>
              <div className="text-right">
                <p className="text-lg font-semibold text-foreground">$129/month</p>
              </div>
            </div>
            <div className="flex gap-3">
              <Button variant="outline" className="flex-1" onClick={handleClose}>
                Maybe later
              </Button>
              <Button asChild className="flex-1 bg-gradient-to-r from-violet-500 to-purple-500 hover:opacity-90">
                <Link href="/pricing">
                  Upgrade now
                  <ArrowRight className="h-4 w-4 ml-2" />
                </Link>
              </Button>
            </div>
          </div>
        </motion.div>
      </div>
    )
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      {/* Backdrop */}
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        exit={{ opacity: 0 }}
        className="absolute inset-0 bg-black/80 backdrop-blur-sm"
        onClick={handleClose}
      />

      {/* Modal */}
      <motion.div
        initial={{ opacity: 0, scale: 0.95, y: 20 }}
        animate={{ opacity: 1, scale: 1, y: 0 }}
        exit={{ opacity: 0, scale: 0.95, y: 20 }}
        className="relative w-full max-w-2xl max-h-[90vh] overflow-hidden rounded-2xl border border-violet-500/20 bg-card shadow-2xl shadow-violet-500/10"
      >
        {/* Header */}
        <div className="border-b border-border px-6 py-4 bg-gradient-to-r from-violet-500/10 to-transparent">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="h-10 w-10 rounded-xl bg-violet-500/20 flex items-center justify-center">
                <Blocks className="h-5 w-5 text-violet-400" />
              </div>
              <div>
                <h2 className="text-lg font-semibold text-foreground">Build with Meson</h2>
                <p className="text-xs text-muted-foreground">Create your system from a single request</p>
              </div>
            </div>
            <button
              onClick={handleClose}
              className="h-8 w-8 rounded-lg hover:bg-secondary flex items-center justify-center transition-colors"
            >
              <X className="h-4 w-4 text-muted-foreground" />
            </button>
          </div>

          {/* Progress Steps */}
          <div className="mt-4 flex items-center gap-2">
            {steps.map((step, i) => (
              <div key={step.id} className="flex items-center">
                <div className={cn(
                  "h-2 w-2 rounded-full transition-colors",
                  currentStep >= step.id 
                    ? "bg-violet-500" 
                    : "bg-secondary"
                )} />
                {i < steps.length - 1 && (
                  <div className={cn(
                    "h-px w-8 transition-colors",
                    currentStep > step.id 
                      ? "bg-violet-500" 
                      : "bg-secondary"
                  )} />
                )}
              </div>
            ))}
          </div>
        </div>

        {/* Content */}
        <div className="p-6 max-h-[60vh] overflow-y-auto">
          <AnimatePresence mode="wait">
            {/* Step 1: Intent */}
            {currentStep === 1 && (
              <motion.div
                key="step1"
                initial={{ opacity: 0, x: 20 }}
                animate={{ opacity: 1, x: 0 }}
                exit={{ opacity: 0, x: -20 }}
                className="space-y-4"
              >
                <div>
                  <h3 className="text-lg font-semibold text-foreground mb-1">What do you want to build?</h3>
                  <p className="text-sm text-muted-foreground">Describe the agent or system you need in plain language.</p>
                </div>
                
                <textarea
                  value={intent}
                  onChange={(e) => setIntent(e.target.value)}
                  placeholder="Example: Create a marketing agent for SaaS onboarding campaigns that sends personalized welcome sequences based on user behavior..."
                  className="w-full h-32 rounded-xl border border-border bg-secondary/50 px-4 py-3 text-sm text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-violet-500/50 focus:border-violet-500/50 resize-none"
                />
                
                <div className="flex flex-wrap gap-2">
                  {[
                    "Lead nurturing agent",
                    "Report generation workflow",
                    "Customer onboarding sequence"
                  ].map((suggestion) => (
                    <button
                      key={suggestion}
                      onClick={() => setIntent(suggestion)}
                      className="px-3 py-1.5 rounded-full text-xs text-muted-foreground bg-secondary hover:bg-secondary/80 hover:text-foreground transition-colors"
                    >
                      {suggestion}
                    </button>
                  ))}
                </div>
              </motion.div>
            )}

            {/* Step 2: Context */}
            {currentStep === 2 && (
              <motion.div
                key="step2"
                initial={{ opacity: 0, x: 20 }}
                animate={{ opacity: 1, x: 0 }}
                exit={{ opacity: 0, x: -20 }}
                className="space-y-6"
              >
                <div>
                  <h3 className="text-lg font-semibold text-foreground mb-1">Select department</h3>
                  <p className="text-sm text-muted-foreground">Which team will use this agent?</p>
                </div>
                
                <div className="grid grid-cols-3 gap-3">
                  {departments.map((dept) => {
                    const Icon = dept.icon
                    return (
                      <button
                        key={dept.id}
                        onClick={() => setSelectedDepartment(dept.id)}
                        className={cn(
                          "p-4 rounded-xl border text-center transition-all",
                          selectedDepartment === dept.id
                            ? "border-violet-500 bg-violet-500/10"
                            : "border-border hover:border-violet-500/50 hover:bg-secondary/50"
                        )}
                      >
                        <Icon className={cn(
                          "h-5 w-5 mx-auto mb-2",
                          selectedDepartment === dept.id ? "text-violet-400" : "text-muted-foreground"
                        )} />
                        <span className="text-sm font-medium text-foreground">{dept.name}</span>
                      </button>
                    )
                  })}
                </div>

                <div>
                  <h3 className="text-sm font-semibold text-foreground mb-3">Choose systems to connect</h3>
                  <div className="space-y-2">
                    {systems.map((system) => {
                      const Icon = system.icon
                      const isSelected = selectedSystems.includes(system.id)
                      return (
                        <button
                          key={system.id}
                          onClick={() => toggleSystem(system.id)}
                          className={cn(
                            "w-full p-3 rounded-xl border flex items-center gap-3 transition-all text-left",
                            isSelected
                              ? "border-violet-500 bg-violet-500/10"
                              : "border-border hover:border-violet-500/50 hover:bg-secondary/50"
                          )}
                        >
                          <div className={cn(
                            "h-8 w-8 rounded-lg flex items-center justify-center",
                            isSelected ? "bg-violet-500/20" : "bg-secondary"
                          )}>
                            <Icon className={cn(
                              "h-4 w-4",
                              isSelected ? "text-violet-400" : "text-muted-foreground"
                            )} />
                          </div>
                          <div className="flex-1 min-w-0">
                            <p className="text-sm font-medium text-foreground">{system.name}</p>
                            <p className="text-xs text-muted-foreground truncate">{system.description}</p>
                          </div>
                          <div className={cn(
                            "h-5 w-5 rounded-full border flex items-center justify-center",
                            isSelected ? "border-violet-500 bg-violet-500" : "border-border"
                          )}>
                            {isSelected && <Check className="h-3 w-3 text-white" />}
                          </div>
                        </button>
                      )
                    })}
                  </div>
                </div>
              </motion.div>
            )}

            {/* Step 3: Scope */}
            {currentStep === 3 && (
              <motion.div
                key="step3"
                initial={{ opacity: 0, x: 20 }}
                animate={{ opacity: 1, x: 0 }}
                exit={{ opacity: 0, x: -20 }}
                className="space-y-4"
              >
                <div>
                  <h3 className="text-lg font-semibold text-foreground mb-1">What outputs do you need?</h3>
                  <p className="text-sm text-muted-foreground">Select the types of work this agent will produce.</p>
                </div>
                
                <div className="grid grid-cols-2 gap-3">
                  {outputTypes.map((output) => {
                    const isSelected = selectedOutputs.includes(output.id)
                    return (
                      <button
                        key={output.id}
                        onClick={() => toggleOutput(output.id)}
                        className={cn(
                          "p-4 rounded-xl border text-left transition-all",
                          isSelected
                            ? "border-violet-500 bg-violet-500/10"
                            : "border-border hover:border-violet-500/50 hover:bg-secondary/50"
                        )}
                      >
                        <div className="flex items-center justify-between mb-2">
                          <span className="text-sm font-medium text-foreground">{output.name}</span>
                          <div className={cn(
                            "h-5 w-5 rounded-full border flex items-center justify-center",
                            isSelected ? "border-violet-500 bg-violet-500" : "border-border"
                          )}>
                            {isSelected && <Check className="h-3 w-3 text-white" />}
                          </div>
                        </div>
                        <p className="text-xs text-muted-foreground">{output.description}</p>
                      </button>
                    )
                  })}
                </div>
              </motion.div>
            )}

            {/* Step 4: Generate */}
            {currentStep === 4 && !isGenerating && (
              <motion.div
                key="step4"
                initial={{ opacity: 0, x: 20 }}
                animate={{ opacity: 1, x: 0 }}
                exit={{ opacity: 0, x: -20 }}
                className="space-y-6"
              >
                <div className="text-center py-8">
                  <div className="h-20 w-20 mx-auto rounded-2xl bg-violet-500/10 border border-violet-500/20 flex items-center justify-center mb-6">
                    <Sparkles className="h-10 w-10 text-violet-400" />
                  </div>
                  <h3 className="text-xl font-semibold text-foreground mb-2">Ready to build</h3>
                  <p className="text-sm text-muted-foreground max-w-sm mx-auto">
                    Meson will create your agent configuration, training structure, and workflows based on your requirements.
                  </p>
                </div>

                {/* Summary */}
                <div className="rounded-xl border border-border bg-secondary/30 p-4 space-y-3">
                  <div className="flex items-start gap-3">
                    <FileText className="h-4 w-4 text-muted-foreground mt-0.5" />
                    <div>
                      <p className="text-xs text-muted-foreground">Intent</p>
                      <p className="text-sm text-foreground">{intent}</p>
                    </div>
                  </div>
                  <div className="flex items-start gap-3">
                    <Target className="h-4 w-4 text-muted-foreground mt-0.5" />
                    <div>
                      <p className="text-xs text-muted-foreground">Department</p>
                      <p className="text-sm text-foreground capitalize">{selectedDepartment}</p>
                    </div>
                  </div>
                  <div className="flex items-start gap-3">
                    <Database className="h-4 w-4 text-muted-foreground mt-0.5" />
                    <div>
                      <p className="text-xs text-muted-foreground">Systems</p>
                      <p className="text-sm text-foreground">{selectedSystems.join(", ")}</p>
                    </div>
                  </div>
                  <div className="flex items-start gap-3">
                    <Zap className="h-4 w-4 text-muted-foreground mt-0.5" />
                    <div>
                      <p className="text-xs text-muted-foreground">Output Types</p>
                      <p className="text-sm text-foreground">{selectedOutputs.join(", ")}</p>
                    </div>
                  </div>
                </div>

                <p className="text-xs text-center text-muted-foreground">
                  This will use 1 Meson from your plan
                </p>
              </motion.div>
            )}

            {/* Generating State */}
            {currentStep === 4 && isGenerating && (
              <motion.div
                key="generating"
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                exit={{ opacity: 0 }}
                className="py-12 text-center"
              >
                <div className="h-16 w-16 mx-auto rounded-2xl bg-violet-500/10 border border-violet-500/20 flex items-center justify-center mb-6">
                  <Loader2 className="h-8 w-8 text-violet-400 animate-spin" />
                </div>
                <h3 className="text-lg font-semibold text-foreground mb-2">
                  Meson is building your system...
                </h3>
                
                <div className="mt-8 max-w-xs mx-auto space-y-3">
                  {generationStates.map((state, i) => (
                    <div 
                      key={state.label}
                      className={cn(
                        "flex items-center gap-3 transition-opacity",
                        i <= generationStep ? "opacity-100" : "opacity-30"
                      )}
                    >
                      <div className={cn(
                        "h-6 w-6 rounded-full flex items-center justify-center",
                        i < generationStep 
                          ? "bg-emerald-500" 
                          : i === generationStep 
                            ? "bg-violet-500 animate-pulse" 
                            : "bg-secondary"
                      )}>
                        {i < generationStep ? (
                          <Check className="h-3 w-3 text-white" />
                        ) : i === generationStep ? (
                          <Loader2 className="h-3 w-3 text-white animate-spin" />
                        ) : (
                          <div className="h-2 w-2 rounded-full bg-muted-foreground/30" />
                        )}
                      </div>
                      <div className="text-left">
                        <p className="text-sm font-medium text-foreground">{state.label}</p>
                        <p className="text-xs text-muted-foreground">{state.description}</p>
                      </div>
                    </div>
                  ))}
                </div>
              </motion.div>
            )}

            {/* Step 5: Output */}
            {currentStep === 5 && generatedResult && (
              <motion.div
                key="step5"
                initial={{ opacity: 0, x: 20 }}
                animate={{ opacity: 1, x: 0 }}
                exit={{ opacity: 0, x: -20 }}
                className="space-y-6"
              >
                <div className="text-center">
                  <div className="h-16 w-16 mx-auto rounded-2xl bg-emerald-500/10 border border-emerald-500/20 flex items-center justify-center mb-4">
                    <Check className="h-8 w-8 text-emerald-400" />
                  </div>
                  <h3 className="text-xl font-semibold text-foreground mb-1">System generated</h3>
                  <p className="text-sm text-muted-foreground">
                    Your agent and workflows are ready to deploy
                  </p>
                </div>

                {/* Generated Items */}
                <div className="space-y-4">
                  {/* Agent */}
                  <div className="rounded-xl border border-border bg-secondary/30 p-4">
                    <div className="flex items-center gap-3 mb-3">
                      <div className="h-8 w-8 rounded-lg bg-blue-500/10 flex items-center justify-center">
                        <Bot className="h-4 w-4 text-blue-400" />
                      </div>
                      <div>
                        <p className="text-sm font-medium text-foreground">Agent Configuration</p>
                        <p className="text-xs text-muted-foreground">{generatedResult.generatedConfig.agent}</p>
                      </div>
                    </div>
                  </div>

                  {/* Training */}
                  <div className="rounded-xl border border-border bg-secondary/30 p-4">
                    <div className="flex items-center gap-3 mb-3">
                      <div className="h-8 w-8 rounded-lg bg-amber-500/10 flex items-center justify-center">
                        <FileText className="h-4 w-4 text-amber-400" />
                      </div>
                      <div>
                        <p className="text-sm font-medium text-foreground">Training Structure</p>
                        <p className="text-xs text-muted-foreground">{generatedResult.generatedConfig.training.length} training modules</p>
                      </div>
                    </div>
                    <div className="flex flex-wrap gap-2">
                      {generatedResult.generatedConfig.training.map((item, i) => (
                        <span key={i} className="px-2 py-1 rounded-md text-xs bg-secondary text-muted-foreground">
                          {item}
                        </span>
                      ))}
                    </div>
                  </div>

                  {/* Workflows */}
                  <div className="rounded-xl border border-border bg-secondary/30 p-4">
                    <div className="flex items-center gap-3 mb-3">
                      <div className="h-8 w-8 rounded-lg bg-violet-500/10 flex items-center justify-center">
                        <Workflow className="h-4 w-4 text-violet-400" />
                      </div>
                      <div>
                        <p className="text-sm font-medium text-foreground">Workflows</p>
                        <p className="text-xs text-muted-foreground">{generatedResult.generatedConfig.workflows.length} workflows generated</p>
                      </div>
                    </div>
                    <div className="flex flex-wrap gap-2">
                      {generatedResult.generatedConfig.workflows.map((item, i) => (
                        <span key={i} className="px-2 py-1 rounded-md text-xs bg-secondary text-muted-foreground">
                          {item}
                        </span>
                      ))}
                    </div>
                  </div>

                  {/* Sample Outputs */}
                  <div className="rounded-xl border border-border bg-secondary/30 p-4">
                    <div className="flex items-center gap-3 mb-3">
                      <div className="h-8 w-8 rounded-lg bg-emerald-500/10 flex items-center justify-center">
                        <Zap className="h-4 w-4 text-emerald-400" />
                      </div>
                      <div>
                        <p className="text-sm font-medium text-foreground">Sample Outputs</p>
                        <p className="text-xs text-muted-foreground">Ready to generate</p>
                      </div>
                    </div>
                    <div className="space-y-1">
                      {generatedResult.generatedConfig.sampleOutputs.map((item, i) => (
                        <p key={i} className="text-xs text-muted-foreground flex items-center gap-2">
                          <Check className="h-3 w-3 text-emerald-500" />
                          {item}
                        </p>
                      ))}
                    </div>
                  </div>
                </div>
              </motion.div>
            )}
          </AnimatePresence>
        </div>

        {/* Footer */}
        <div className="border-t border-border px-6 py-4 flex items-center justify-between bg-secondary/30">
          <div>
            {currentStep > 1 && currentStep < 5 && !isGenerating && (
              <Button variant="ghost" size="sm" onClick={handleBack}>
                <ArrowLeft className="h-4 w-4 mr-2" />
                Back
              </Button>
            )}
          </div>
          
          <div className="flex items-center gap-3">
            <Button variant="outline" size="sm" onClick={handleClose}>
              {currentStep === 5 ? "Close" : "Cancel"}
            </Button>
            
            {currentStep < 4 && (
              <Button 
                size="sm" 
                onClick={handleNext}
                disabled={!canProceed()}
                className="bg-violet-600 hover:bg-violet-500"
              >
                Continue
                <ArrowRight className="h-4 w-4 ml-2" />
              </Button>
            )}
            
            {currentStep === 4 && !isGenerating && (
              <Button 
                size="sm" 
                onClick={handleNext}
                className="bg-violet-600 hover:bg-violet-500"
              >
                <Sparkles className="h-4 w-4 mr-2" />
                Run Meson
              </Button>
            )}
            
            {currentStep === 5 && (
              <div className="flex items-center gap-2">
                <Button variant="outline" size="sm">
                  Edit
                </Button>
                <Button 
                  size="sm" 
                  onClick={handleDeploy}
                  className="bg-emerald-600 hover:bg-emerald-500"
                >
                  <Check className="h-4 w-4 mr-2" />
                  Deploy
                </Button>
              </div>
            )}
          </div>
        </div>
      </motion.div>
    </div>
  )
}
