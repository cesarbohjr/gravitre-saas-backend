"use client"

import { useState, useEffect } from "react"
import { motion, AnimatePresence } from "framer-motion"
import { cn } from "@/lib/utils"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Textarea } from "@/components/ui/textarea"
import { Badge } from "@/components/ui/badge"
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription } from "@/components/ui/dialog"
import {
  Target,
  Sparkles,
  Building2,
  Database,
  Users,
  Zap,
  CheckCircle,
  AlertTriangle,
  ArrowRight,
  ArrowLeft,
  Bot,
  Shield,
  GitBranch,
  FileText,
  Plug,
  Clock,
  RefreshCw,
  Edit3,
  Play,
  Save,
  RotateCcw,
  ChevronRight,
  Loader2,
  Brain,
  Workflow,
  MessageSquare,
  Mail,
  CreditCard,
  HelpCircle,
  TrendingUp,
  Calendar,
  BarChart3,
  Send,
  AlertCircle,
  Lock,
  Eye,
  X,
} from "lucide-react"

// Types
interface GoalCategory {
  id: string
  label: string
  icon: typeof Target
  color: string
  examples: string[]
}

interface Connector {
  id: string
  name: string
  icon: string
  category: "crm" | "finance" | "support" | "comms" | "knowledge" | "analytics"
  connected: boolean
  required?: boolean
}

interface ProposedStep {
  id: string
  name: string
  description: string
  type: "source" | "agent" | "task" | "connector" | "approval" | "decision" | "council"
  agent?: string
  connector?: string
  dataRequired?: string[]
  output?: string
  riskLevel?: "low" | "medium" | "high"
  requiresApproval?: boolean
}

interface GeneratedPlan {
  goalSummary: string
  steps: ProposedStep[]
  requiredConnectors: Connector[]
  agents: { id: string; name: string; role: string }[]
  approvalGates: { stepId: string; reason: string }[]
  estimatedRuntime: string
  riskLevel: "low" | "medium" | "high"
  successMetric: string
}

interface GoalWorkflowWizardProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  onBuildWorkflow?: (plan: GeneratedPlan) => void
}

const goalCategories: GoalCategory[] = [
  {
    id: "marketing",
    label: "Marketing & Campaigns",
    icon: Send,
    color: "bg-pink-500/20 text-pink-400 border-pink-500/30",
    examples: ["Launch reactivation campaign", "Create weekly newsletter", "Segment audience"],
  },
  {
    id: "sales",
    label: "Sales & Revenue",
    icon: TrendingUp,
    color: "bg-emerald-500/20 text-emerald-400 border-emerald-500/30",
    examples: ["Qualify new leads", "Follow up on opportunities", "Route leads to reps"],
  },
  {
    id: "support",
    label: "Customer Support",
    icon: HelpCircle,
    color: "bg-blue-500/20 text-blue-400 border-blue-500/30",
    examples: ["Monitor ticket trends", "Escalate high-priority issues", "Summarize support data"],
  },
  {
    id: "finance",
    label: "Finance & Billing",
    icon: CreditCard,
    color: "bg-amber-500/20 text-amber-400 border-amber-500/30",
    examples: ["Reduce overdue invoices", "Process refunds", "Generate billing reports"],
  },
  {
    id: "reporting",
    label: "Reports & Analytics",
    icon: BarChart3,
    color: "bg-violet-500/20 text-violet-400 border-violet-500/30",
    examples: ["Weekly executive summary", "Monthly performance report", "Trend analysis"],
  },
  {
    id: "operations",
    label: "Operations & Data",
    icon: Database,
    color: "bg-cyan-500/20 text-cyan-400 border-cyan-500/30",
    examples: ["Sync customer data", "Clean duplicate records", "Archive old data"],
  },
]

const availableConnectors: Connector[] = [
  { id: "hubspot", name: "HubSpot", icon: "H", category: "crm", connected: true },
  { id: "salesforce", name: "Salesforce", icon: "S", category: "crm", connected: false },
  { id: "stripe", name: "Stripe", icon: "$", category: "finance", connected: true },
  { id: "quickbooks", name: "QuickBooks", icon: "Q", category: "finance", connected: false },
  { id: "zendesk", name: "Zendesk", icon: "Z", category: "support", connected: true },
  { id: "intercom", name: "Intercom", icon: "I", category: "support", connected: false },
  { id: "slack", name: "Slack", icon: "#", category: "comms", connected: true },
  { id: "gmail", name: "Gmail", icon: "G", category: "comms", connected: true },
  { id: "notion", name: "Notion", icon: "N", category: "knowledge", connected: false },
  { id: "confluence", name: "Confluence", icon: "C", category: "knowledge", connected: false },
  { id: "google-analytics", name: "Google Analytics", icon: "A", category: "analytics", connected: true },
  { id: "mixpanel", name: "Mixpanel", icon: "M", category: "analytics", connected: false },
]

const planningStages = [
  { id: "understanding", label: "Understanding goal", icon: Brain },
  { id: "data", label: "Identifying required data", icon: Database },
  { id: "connectors", label: "Mapping connectors", icon: Plug },
  { id: "agents", label: "Selecting agents", icon: Bot },
  { id: "workflow", label: "Creating workflow steps", icon: Workflow },
  { id: "controls", label: "Adding review controls", icon: Shield },
  { id: "deliverables", label: "Preparing deliverables", icon: FileText },
]

export function GoalWorkflowWizard({ open, onOpenChange, onBuildWorkflow }: GoalWorkflowWizardProps) {
  const [step, setStep] = useState(1)
  const [isPlanning, setIsPlanning] = useState(false)
  const [planningStage, setPlanningStage] = useState(0)
  const [generatedPlan, setGeneratedPlan] = useState<GeneratedPlan | null>(null)
  
  // Step 1: Goal definition
  const [goalText, setGoalText] = useState("")
  const [selectedCategory, setSelectedCategory] = useState<string | null>(null)
  const [priority, setPriority] = useState<"low" | "medium" | "high">("medium")
  const [frequency, setFrequency] = useState<"once" | "daily" | "weekly" | "monthly">("once")
  
  // Step 2: Business context
  const [selectedDepartment, setSelectedDepartment] = useState<string | null>(null)
  const [selectedConnectors, setSelectedConnectors] = useState<string[]>([])
  const [successMetric, setSuccessMetric] = useState("")

  // Reset when dialog closes
  useEffect(() => {
    if (!open) {
      setTimeout(() => {
        setStep(1)
        setIsPlanning(false)
        setPlanningStage(0)
        setGeneratedPlan(null)
        setGoalText("")
        setSelectedCategory(null)
        setPriority("medium")
        setFrequency("once")
        setSelectedDepartment(null)
        setSelectedConnectors([])
        setSuccessMetric("")
      }, 300)
    }
  }, [open])

  const handleGeneratePlan = async () => {
    setStep(3)
    setIsPlanning(true)
    
    // Simulate AI planning stages
    for (let i = 0; i < planningStages.length; i++) {
      await new Promise(resolve => setTimeout(resolve, 600 + Math.random() * 400))
      setPlanningStage(i + 1)
    }
    
    // Generate mock plan based on goal
    await new Promise(resolve => setTimeout(resolve, 500))
    
    const mockPlan: GeneratedPlan = {
      goalSummary: goalText || "Re-engage inactive leads and create a ready-to-send email campaign",
      steps: [
        {
          id: "step-1",
          name: "Pull Inactive Contacts",
          description: "Retrieve contacts with no engagement in the last 90 days",
          type: "source",
          connector: "HubSpot",
          output: "Contact list with engagement data",
          riskLevel: "low",
        },
        {
          id: "step-2",
          name: "Segment by Engagement",
          description: "Categorize contacts based on historical engagement patterns",
          type: "agent",
          agent: "Research Analyst",
          dataRequired: ["Contact list", "Engagement history"],
          output: "Segmented contact groups",
          riskLevel: "low",
        },
        {
          id: "step-3",
          name: "Generate Email Variants",
          description: "Create personalized email content for each segment",
          type: "agent",
          agent: "Content Writer",
          dataRequired: ["Segmented groups", "Brand guidelines"],
          output: "Email drafts per segment",
          riskLevel: "medium",
        },
        {
          id: "step-4",
          name: "Compliance Review",
          description: "Check content against legal and brand guidelines",
          type: "council",
          agent: "Compliance Council",
          dataRequired: ["Email drafts"],
          output: "Approved/flagged content",
          riskLevel: "medium",
          requiresApproval: true,
        },
        {
          id: "step-5",
          name: "Human Approval",
          description: "Final review before campaign execution",
          type: "approval",
          dataRequired: ["Reviewed content"],
          output: "Approved campaign",
          riskLevel: "high",
          requiresApproval: true,
        },
        {
          id: "step-6",
          name: "Schedule Campaign",
          description: "Set up campaign in email system with optimal send times",
          type: "connector",
          connector: "HubSpot",
          dataRequired: ["Approved content", "Contact segments"],
          output: "Scheduled campaign",
          riskLevel: "high",
        },
        {
          id: "step-7",
          name: "Report Results",
          description: "Generate performance summary and recommendations",
          type: "agent",
          agent: "Research Analyst",
          dataRequired: ["Campaign metrics"],
          output: "Performance report",
          riskLevel: "low",
        },
      ],
      requiredConnectors: [
        { id: "hubspot", name: "HubSpot", icon: "H", category: "crm", connected: true, required: true },
        { id: "slack", name: "Slack", icon: "#", category: "comms", connected: true, required: false },
      ],
      agents: [
        { id: "analyst", name: "Research Analyst", role: "Data analysis and insights" },
        { id: "writer", name: "Content Writer", role: "Email content generation" },
        { id: "compliance", name: "Compliance Reviewer", role: "Legal and brand compliance" },
      ],
      approvalGates: [
        { stepId: "step-4", reason: "Content compliance check" },
        { stepId: "step-5", reason: "External email send" },
      ],
      estimatedRuntime: "15-30 minutes",
      riskLevel: "medium",
      successMetric: successMetric || "Email open rate > 20%, click rate > 5%",
    }
    
    setGeneratedPlan(mockPlan)
    setIsPlanning(false)
    setStep(4)
  }

  const handleBuildWorkflow = () => {
    if (generatedPlan && onBuildWorkflow) {
      onBuildWorkflow(generatedPlan)
    }
    onOpenChange(false)
  }

  const handleRegeneratePlan = () => {
    setGeneratedPlan(null)
    setIsPlanning(false)
    setPlanningStage(0)
    handleGeneratePlan()
  }

  const getStepTypeIcon = (type: ProposedStep["type"]) => {
    switch (type) {
      case "source": return Database
      case "agent": return Bot
      case "task": return FileText
      case "connector": return Plug
      case "approval": return Shield
      case "decision": return GitBranch
      case "council": return Users
      default: return Zap
    }
  }

  const getStepTypeColor = (type: ProposedStep["type"]) => {
    switch (type) {
      case "source": return "bg-slate-500/20 text-slate-400 border-slate-500/30"
      case "agent": return "bg-blue-500/20 text-blue-400 border-blue-500/30"
      case "task": return "bg-emerald-500/20 text-emerald-400 border-emerald-500/30"
      case "connector": return "bg-amber-500/20 text-amber-400 border-amber-500/30"
      case "approval": return "bg-red-500/20 text-red-400 border-red-500/30"
      case "decision": return "bg-violet-500/20 text-violet-400 border-violet-500/30"
      case "council": return "bg-amber-500/20 text-amber-400 border-amber-500/30"
      default: return "bg-muted text-muted-foreground"
    }
  }

  const getRiskColor = (risk: "low" | "medium" | "high") => {
    switch (risk) {
      case "low": return "text-emerald-400"
      case "medium": return "text-amber-400"
      case "high": return "text-red-400"
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-3xl max-h-[90vh] overflow-hidden flex flex-col p-0">
        {/* Header */}
        <div className="px-6 pt-6 pb-4 border-b border-border">
          <DialogHeader>
            <div className="flex items-center gap-3">
              <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-gradient-to-br from-violet-500/20 to-purple-500/20 border border-violet-500/30">
                <Target className="h-5 w-5 text-violet-400" />
              </div>
              <div>
                <DialogTitle className="text-lg">Create from Goal</DialogTitle>
                <DialogDescription>
                  {step === 1 && "Define your business outcome"}
                  {step === 2 && "Select your business context"}
                  {step === 3 && "Gravitre is designing your workflow"}
                  {step === 4 && "Review your generated plan"}
                </DialogDescription>
              </div>
            </div>
          </DialogHeader>
          
          {/* Progress indicator */}
          <div className="flex items-center gap-2 mt-4">
            {[1, 2, 3, 4].map((s) => (
              <div key={s} className="flex items-center gap-2 flex-1">
                <div className={cn(
                  "flex h-7 w-7 items-center justify-center rounded-full text-xs font-medium transition-all",
                  step > s ? "bg-emerald-500 text-white" :
                  step === s ? "bg-violet-500 text-white" :
                  "bg-secondary text-muted-foreground"
                )}>
                  {step > s ? <CheckCircle className="h-4 w-4" /> : s}
                </div>
                {s < 4 && (
                  <div className={cn(
                    "flex-1 h-0.5 rounded-full transition-all",
                    step > s ? "bg-emerald-500" : "bg-border"
                  )} />
                )}
              </div>
            ))}
          </div>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto p-6">
          <AnimatePresence mode="wait">
            {/* Step 1: Define Goal */}
            {step === 1 && (
              <motion.div
                key="step1"
                initial={{ opacity: 0, x: 20 }}
                animate={{ opacity: 1, x: 0 }}
                exit={{ opacity: 0, x: -20 }}
                className="space-y-6"
              >
                {/* Goal input */}
                <div>
                  <label className="text-sm font-medium text-foreground mb-2 block">
                    What do you want to achieve?
                  </label>
                  <Textarea
                    value={goalText}
                    onChange={(e) => setGoalText(e.target.value)}
                    placeholder="e.g., Launch a reactivation campaign for dormant leads, Monitor high-priority support tickets and escalate risks, Create weekly revenue summary for leadership..."
                    className="min-h-[100px] text-base bg-secondary/50 border-border resize-none"
                  />
                </div>

                {/* Category selection */}
                <div>
                  <label className="text-sm font-medium text-foreground mb-3 block">
                    Goal Category
                  </label>
                  <div className="grid grid-cols-2 md:grid-cols-3 gap-2">
                    {goalCategories.map((cat) => {
                      const IconComponent = cat.icon
                      return (
                        <button
                          key={cat.id}
                          onClick={() => setSelectedCategory(cat.id)}
                          className={cn(
                            "flex items-center gap-2.5 p-3 rounded-lg border text-left transition-all",
                            selectedCategory === cat.id
                              ? `${cat.color} border-current`
                              : "bg-secondary/30 border-border hover:bg-secondary/50"
                          )}
                        >
                          <IconComponent className="h-4 w-4 shrink-0" />
                          <span className="text-sm font-medium">{cat.label}</span>
                        </button>
                      )
                    })}
                  </div>
                </div>

                {/* Priority and frequency */}
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className="text-sm font-medium text-foreground mb-2 block">Priority</label>
                    <div className="flex gap-2">
                      {(["low", "medium", "high"] as const).map((p) => (
                        <button
                          key={p}
                          onClick={() => setPriority(p)}
                          className={cn(
                            "flex-1 py-2 px-3 rounded-lg border text-sm font-medium capitalize transition-all",
                            priority === p
                              ? p === "low" ? "bg-emerald-500/20 text-emerald-400 border-emerald-500/30" :
                                p === "medium" ? "bg-amber-500/20 text-amber-400 border-amber-500/30" :
                                "bg-red-500/20 text-red-400 border-red-500/30"
                              : "bg-secondary/30 border-border text-muted-foreground hover:bg-secondary/50"
                          )}
                        >
                          {p}
                        </button>
                      ))}
                    </div>
                  </div>
                  <div>
                    <label className="text-sm font-medium text-foreground mb-2 block">Frequency</label>
                    <div className="flex gap-2">
                      {(["once", "daily", "weekly", "monthly"] as const).map((f) => (
                        <button
                          key={f}
                          onClick={() => setFrequency(f)}
                          className={cn(
                            "flex-1 py-2 px-2 rounded-lg border text-xs font-medium capitalize transition-all",
                            frequency === f
                              ? "bg-violet-500/20 text-violet-400 border-violet-500/30"
                              : "bg-secondary/30 border-border text-muted-foreground hover:bg-secondary/50"
                          )}
                        >
                          {f}
                        </button>
                      ))}
                    </div>
                  </div>
                </div>

                {/* Example goals */}
                {selectedCategory && (
                  <motion.div
                    initial={{ opacity: 0, height: 0 }}
                    animate={{ opacity: 1, height: "auto" }}
                    className="p-3 rounded-lg bg-violet-500/5 border border-violet-500/20"
                  >
                    <p className="text-xs text-violet-400 mb-2">Example goals for this category:</p>
                    <div className="flex flex-wrap gap-2">
                      {goalCategories.find(c => c.id === selectedCategory)?.examples.map((ex, i) => (
                        <button
                          key={i}
                          onClick={() => setGoalText(ex)}
                          className="text-xs text-muted-foreground hover:text-foreground bg-secondary/50 px-2.5 py-1 rounded-full transition-colors"
                        >
                          {ex}
                        </button>
                      ))}
                    </div>
                  </motion.div>
                )}
              </motion.div>
            )}

            {/* Step 2: Business Context */}
            {step === 2 && (
              <motion.div
                key="step2"
                initial={{ opacity: 0, x: 20 }}
                animate={{ opacity: 1, x: 0 }}
                exit={{ opacity: 0, x: -20 }}
                className="space-y-6"
              >
                {/* Department selection */}
                <div>
                  <label className="text-sm font-medium text-foreground mb-3 block">
                    Which department owns this?
                  </label>
                  <div className="grid grid-cols-3 gap-2">
                    {["Marketing", "Sales", "Support", "Finance", "Operations", "Executive"].map((dept) => (
                      <button
                        key={dept}
                        onClick={() => setSelectedDepartment(dept)}
                        className={cn(
                          "py-2.5 px-3 rounded-lg border text-sm font-medium transition-all",
                          selectedDepartment === dept
                            ? "bg-violet-500/20 text-violet-400 border-violet-500/30"
                            : "bg-secondary/30 border-border text-muted-foreground hover:bg-secondary/50"
                        )}
                      >
                        {dept}
                      </button>
                    ))}
                  </div>
                </div>

                {/* Connector selection */}
                <div>
                  <label className="text-sm font-medium text-foreground mb-3 block">
                    Which systems should be used?
                  </label>
                  <div className="grid grid-cols-2 md:grid-cols-3 gap-2">
                    {availableConnectors.map((conn) => {
                      const isSelected = selectedConnectors.includes(conn.id)
                      return (
                        <button
                          key={conn.id}
                          onClick={() => {
                            setSelectedConnectors(prev =>
                              isSelected
                                ? prev.filter(c => c !== conn.id)
                                : [...prev, conn.id]
                            )
                          }}
                          className={cn(
                            "flex items-center gap-2.5 p-3 rounded-lg border text-left transition-all",
                            isSelected
                              ? "bg-emerald-500/10 border-emerald-500/30"
                              : "bg-secondary/30 border-border hover:bg-secondary/50"
                          )}
                        >
                          <div className={cn(
                            "h-8 w-8 rounded-lg flex items-center justify-center text-sm font-bold",
                            isSelected ? "bg-emerald-500/20 text-emerald-400" : "bg-secondary text-muted-foreground"
                          )}>
                            {conn.icon}
                          </div>
                          <div className="flex-1 min-w-0">
                            <div className="text-sm font-medium text-foreground">{conn.name}</div>
                            <div className="flex items-center gap-1">
                              {conn.connected ? (
                                <span className="text-[10px] text-emerald-400">Connected</span>
                              ) : (
                                <span className="text-[10px] text-muted-foreground">Not connected</span>
                              )}
                            </div>
                          </div>
                          {isSelected && <CheckCircle className="h-4 w-4 text-emerald-400" />}
                        </button>
                      )
                    })}
                  </div>
                </div>

                {/* Success metric */}
                <div>
                  <label className="text-sm font-medium text-foreground mb-2 block">
                    How will you measure success? <span className="text-muted-foreground">(optional)</span>
                  </label>
                  <Input
                    value={successMetric}
                    onChange={(e) => setSuccessMetric(e.target.value)}
                    placeholder="e.g., Email open rate > 20%, Response time < 2 hours, Revenue increase > 10%"
                    className="bg-secondary/50 border-border"
                  />
                </div>
              </motion.div>
            )}

            {/* Step 3: AI Planning */}
            {step === 3 && isPlanning && (
              <motion.div
                key="step3"
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                exit={{ opacity: 0 }}
                className="flex flex-col items-center justify-center py-12"
              >
                {/* Animated brain icon */}
                <div className="relative mb-8">
                  <motion.div
                    className="absolute inset-0 rounded-full bg-violet-500/20 blur-xl"
                    animate={{ scale: [1, 1.2, 1], opacity: [0.3, 0.5, 0.3] }}
                    transition={{ duration: 2, repeat: Infinity }}
                  />
                  <motion.div
                    className="relative h-20 w-20 rounded-full bg-gradient-to-br from-violet-500/20 to-purple-500/20 border border-violet-500/30 flex items-center justify-center"
                    animate={{ rotate: 360 }}
                    transition={{ duration: 8, repeat: Infinity, ease: "linear" }}
                  >
                    <Brain className="h-10 w-10 text-violet-400" />
                  </motion.div>
                </div>

                <h3 className="text-lg font-semibold text-foreground mb-2">
                  Designing your workflow
                </h3>
                <p className="text-sm text-muted-foreground mb-8 text-center max-w-md">
                  Gravitre is analyzing your goal and creating an optimized execution plan
                </p>

                {/* Planning stages */}
                <div className="w-full max-w-sm space-y-2">
                  {planningStages.map((stage, idx) => {
                    const StageIcon = stage.icon
                    const isComplete = planningStage > idx
                    const isActive = planningStage === idx
                    
                    return (
                      <motion.div
                        key={stage.id}
                        initial={{ opacity: 0, x: -20 }}
                        animate={{ opacity: 1, x: 0 }}
                        transition={{ delay: idx * 0.1 }}
                        className={cn(
                          "flex items-center gap-3 p-3 rounded-lg transition-all",
                          isComplete ? "bg-emerald-500/10" :
                          isActive ? "bg-violet-500/10" :
                          "bg-secondary/30"
                        )}
                      >
                        <div className={cn(
                          "h-8 w-8 rounded-full flex items-center justify-center transition-all",
                          isComplete ? "bg-emerald-500 text-white" :
                          isActive ? "bg-violet-500 text-white" :
                          "bg-secondary text-muted-foreground"
                        )}>
                          {isComplete ? (
                            <CheckCircle className="h-4 w-4" />
                          ) : isActive ? (
                            <Loader2 className="h-4 w-4 animate-spin" />
                          ) : (
                            <StageIcon className="h-4 w-4" />
                          )}
                        </div>
                        <span className={cn(
                          "text-sm font-medium",
                          isComplete ? "text-emerald-400" :
                          isActive ? "text-violet-400" :
                          "text-muted-foreground"
                        )}>
                          {stage.label}
                        </span>
                        {isActive && (
                          <motion.div
                            className="ml-auto flex gap-1"
                            initial={{ opacity: 0 }}
                            animate={{ opacity: 1 }}
                          >
                            {[0, 1, 2].map((i) => (
                              <motion.div
                                key={i}
                                className="h-1.5 w-1.5 rounded-full bg-violet-400"
                                animate={{ opacity: [0.3, 1, 0.3] }}
                                transition={{ duration: 0.8, delay: i * 0.2, repeat: Infinity }}
                              />
                            ))}
                          </motion.div>
                        )}
                      </motion.div>
                    )
                  })}
                </div>
              </motion.div>
            )}

            {/* Step 4: Plan Review */}
            {step === 4 && generatedPlan && (
              <motion.div
                key="step4"
                initial={{ opacity: 0, x: 20 }}
                animate={{ opacity: 1, x: 0 }}
                exit={{ opacity: 0, x: -20 }}
                className="space-y-6"
              >
                {/* Goal summary */}
                <div className="p-4 rounded-xl bg-gradient-to-br from-violet-500/10 to-purple-500/10 border border-violet-500/20">
                  <div className="flex items-center gap-2 mb-2">
                    <Target className="h-4 w-4 text-violet-400" />
                    <span className="text-xs font-medium text-violet-400 uppercase tracking-wide">Goal</span>
                  </div>
                  <p className="text-foreground font-medium">{generatedPlan.goalSummary}</p>
                  <div className="flex items-center gap-4 mt-3">
                    <div className="flex items-center gap-1.5 text-xs text-muted-foreground">
                      <Clock className="h-3.5 w-3.5" />
                      {generatedPlan.estimatedRuntime}
                    </div>
                    <div className={cn("flex items-center gap-1.5 text-xs", getRiskColor(generatedPlan.riskLevel))}>
                      <AlertTriangle className="h-3.5 w-3.5" />
                      {generatedPlan.riskLevel} risk
                    </div>
                    <div className="flex items-center gap-1.5 text-xs text-muted-foreground">
                      <TrendingUp className="h-3.5 w-3.5" />
                      {generatedPlan.successMetric}
                    </div>
                  </div>
                </div>

                {/* Proposed steps */}
                <div>
                  <h4 className="text-sm font-medium text-foreground mb-3">Proposed Workflow Steps</h4>
                  <div className="space-y-2">
                    {generatedPlan.steps.map((stepItem, idx) => {
                      const StepIcon = getStepTypeIcon(stepItem.type)
                      return (
                        <div
                          key={stepItem.id}
                          className="flex items-start gap-3 p-3 rounded-lg bg-secondary/30 border border-border hover:bg-secondary/50 transition-colors group"
                        >
                          <div className="flex items-center gap-2 shrink-0">
                            <span className="text-xs font-medium text-muted-foreground w-5">{idx + 1}</span>
                            <div className={cn(
                              "h-8 w-8 rounded-lg flex items-center justify-center border",
                              getStepTypeColor(stepItem.type)
                            )}>
                              <StepIcon className="h-4 w-4" />
                            </div>
                          </div>
                          <div className="flex-1 min-w-0">
                            <div className="flex items-center gap-2">
                              <span className="font-medium text-sm text-foreground">{stepItem.name}</span>
                              {stepItem.requiresApproval && (
                                <Badge variant="outline" className="text-[9px] py-0 h-4 bg-red-500/10 text-red-400 border-red-500/30">
                                  <Lock className="h-2.5 w-2.5 mr-1" />
                                  Approval
                                </Badge>
                              )}
                            </div>
                            <p className="text-xs text-muted-foreground mt-0.5">{stepItem.description}</p>
                            <div className="flex items-center gap-3 mt-2">
                              {stepItem.agent && (
                                <span className="text-[10px] text-blue-400 flex items-center gap-1">
                                  <Bot className="h-3 w-3" />
                                  {stepItem.agent}
                                </span>
                              )}
                              {stepItem.connector && (
                                <span className="text-[10px] text-amber-400 flex items-center gap-1">
                                  <Plug className="h-3 w-3" />
                                  {stepItem.connector}
                                </span>
                              )}
                              {stepItem.riskLevel && (
                                <span className={cn("text-[10px] flex items-center gap-1", getRiskColor(stepItem.riskLevel))}>
                                  <AlertTriangle className="h-3 w-3" />
                                  {stepItem.riskLevel} risk
                                </span>
                              )}
                            </div>
                          </div>
                          <button className="opacity-0 group-hover:opacity-100 p-1.5 rounded-md hover:bg-secondary transition-all">
                            <Edit3 className="h-3.5 w-3.5 text-muted-foreground" />
                          </button>
                        </div>
                      )
                    })}
                  </div>
                </div>

                {/* Required connectors */}
                <div>
                  <h4 className="text-sm font-medium text-foreground mb-3">Required Connectors</h4>
                  <div className="flex flex-wrap gap-2">
                    {generatedPlan.requiredConnectors.map((conn) => (
                      <div
                        key={conn.id}
                        className={cn(
                          "flex items-center gap-2 px-3 py-2 rounded-lg border",
                          conn.connected
                            ? "bg-emerald-500/10 border-emerald-500/30"
                            : "bg-amber-500/10 border-amber-500/30"
                        )}
                      >
                        <div className="h-6 w-6 rounded flex items-center justify-center bg-secondary text-xs font-bold">
                          {conn.icon}
                        </div>
                        <span className="text-sm font-medium text-foreground">{conn.name}</span>
                        {conn.connected ? (
                          <CheckCircle className="h-4 w-4 text-emerald-400" />
                        ) : (
                          <AlertCircle className="h-4 w-4 text-amber-400" />
                        )}
                      </div>
                    ))}
                  </div>
                  {generatedPlan.requiredConnectors.some(c => !c.connected) && (
                    <p className="text-xs text-amber-400 mt-2 flex items-center gap-1">
                      <AlertTriangle className="h-3 w-3" />
                      Some connectors need to be connected before activation
                    </p>
                  )}
                </div>

                {/* Approval gates */}
                {generatedPlan.approvalGates.length > 0 && (
                  <div className="p-3 rounded-lg bg-red-500/5 border border-red-500/20">
                    <div className="flex items-center gap-2 mb-2">
                      <Shield className="h-4 w-4 text-red-400" />
                      <span className="text-sm font-medium text-foreground">Human Approval Required</span>
                    </div>
                    <p className="text-xs text-muted-foreground mb-2">
                      This workflow includes steps that require human confirmation before execution:
                    </p>
                    <div className="space-y-1">
                      {generatedPlan.approvalGates.map((gate) => (
                        <div key={gate.stepId} className="flex items-center gap-2 text-xs text-red-400">
                          <Lock className="h-3 w-3" />
                          {gate.reason}
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* Suggestions */}
                <div className="p-3 rounded-lg bg-blue-500/5 border border-blue-500/20">
                  <div className="flex items-center gap-2 mb-2">
                    <Sparkles className="h-4 w-4 text-blue-400" />
                    <span className="text-sm font-medium text-foreground">Smart Suggestions</span>
                  </div>
                  <div className="space-y-1.5">
                    <p className="text-xs text-muted-foreground flex items-center gap-2">
                      <ChevronRight className="h-3 w-3 text-blue-400" />
                      Add Slack notification when campaign is scheduled
                    </p>
                    <p className="text-xs text-muted-foreground flex items-center gap-2">
                      <ChevronRight className="h-3 w-3 text-blue-400" />
                      Track email open rate as success metric
                    </p>
                    <p className="text-xs text-muted-foreground flex items-center gap-2">
                      <ChevronRight className="h-3 w-3 text-blue-400" />
                      Use Agent Council for content review decisions
                    </p>
                  </div>
                </div>
              </motion.div>
            )}
          </AnimatePresence>
        </div>

        {/* Footer */}
        <div className="px-6 py-4 border-t border-border flex items-center justify-between">
          <div>
            {step > 1 && step < 4 && (
              <Button
                variant="ghost"
                size="sm"
                onClick={() => setStep(step - 1)}
                className="gap-2"
              >
                <ArrowLeft className="h-4 w-4" />
                Back
              </Button>
            )}
          </div>
          <div className="flex items-center gap-2">
            {step === 1 && (
              <Button
                onClick={() => setStep(2)}
                disabled={!goalText.trim()}
                className="gap-2"
              >
                Continue
                <ArrowRight className="h-4 w-4" />
              </Button>
            )}
            {step === 2 && (
              <Button
                onClick={handleGeneratePlan}
                className="gap-2 bg-violet-600 hover:bg-violet-700"
              >
                <Sparkles className="h-4 w-4" />
                Generate Plan
              </Button>
            )}
            {step === 4 && (
              <>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={handleRegeneratePlan}
                  className="gap-2"
                >
                  <RotateCcw className="h-4 w-4" />
                  Regenerate
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  className="gap-2"
                >
                  <Save className="h-4 w-4" />
                  Save Draft
                </Button>
                <Button
                  onClick={handleBuildWorkflow}
                  className="gap-2 bg-emerald-600 hover:bg-emerald-700"
                >
                  <Play className="h-4 w-4" />
                  Build Workflow
                </Button>
              </>
            )}
          </div>
        </div>
      </DialogContent>
    </Dialog>
  )
}
