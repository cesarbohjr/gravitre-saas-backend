"use client"

import { useState, useEffect } from "react"
import { motion, AnimatePresence } from "framer-motion"
import { 
  Play, 
  Pause, 
  RotateCcw, 
  CheckCircle2, 
  Circle, 
  Loader2,
  GitBranch,
  Bot,
  Database,
  Send
} from "lucide-react"

interface WorkflowStep {
  id: string
  name: string
  type: "trigger" | "agent" | "connector" | "action"
  status: "pending" | "running" | "completed" | "error"
  duration?: number
  output?: string
}

const DEMO_WORKFLOW: WorkflowStep[] = [
  { id: "1", name: "Webhook Trigger", type: "trigger", status: "pending" },
  { id: "2", name: "Classify Intent", type: "agent", status: "pending" },
  { id: "3", name: "Fetch Customer Data", type: "connector", status: "pending" },
  { id: "4", name: "Generate Response", type: "agent", status: "pending" },
  { id: "5", name: "Send to Slack", type: "action", status: "pending" },
]

const STEP_OUTPUTS = [
  "Received webhook payload",
  "Intent: sales_inquiry (confidence: 0.94)",
  "Retrieved 3 records from Salesforce",
  "Generated personalized response",
  "Message sent to #sales channel",
]

function StepIcon({ type, status }: { type: string; status: string }) {
  const iconClass = status === "running" ? "animate-pulse" : ""
  
  if (status === "completed") {
    return <CheckCircle2 className="h-4 w-4 text-emerald-500" />
  }
  
  if (status === "running") {
    return <Loader2 className="h-4 w-4 text-emerald-500 animate-spin" />
  }
  
  switch (type) {
    case "trigger":
      return <GitBranch className={`h-4 w-4 text-blue-500 ${iconClass}`} />
    case "agent":
      return <Bot className={`h-4 w-4 text-purple-500 ${iconClass}`} />
    case "connector":
      return <Database className={`h-4 w-4 text-amber-500 ${iconClass}`} />
    case "action":
      return <Send className={`h-4 w-4 text-cyan-500 ${iconClass}`} />
    default:
      return <Circle className="h-4 w-4 text-muted-foreground" />
  }
}

export function WorkflowDemo() {
  const [steps, setSteps] = useState<WorkflowStep[]>(DEMO_WORKFLOW)
  const [isRunning, setIsRunning] = useState(false)
  const [currentStep, setCurrentStep] = useState(-1)
  const [totalDuration, setTotalDuration] = useState(0)

  useEffect(() => {
    if (!isRunning || currentStep >= steps.length) return

    const timer = setTimeout(() => {
      if (currentStep === -1) {
        setCurrentStep(0)
        setSteps((prev) =>
          prev.map((s, i) => (i === 0 ? { ...s, status: "running" } : s))
        )
      } else {
        const duration = Math.floor(Math.random() * 300) + 200
        setTotalDuration((prev) => prev + duration)
        
        setSteps((prev) =>
          prev.map((s, i) => {
            if (i === currentStep) {
              return { ...s, status: "completed", duration, output: STEP_OUTPUTS[i] }
            }
            if (i === currentStep + 1) {
              return { ...s, status: "running" }
            }
            return s
          })
        )
        
        if (currentStep + 1 >= steps.length) {
          setIsRunning(false)
        } else {
          setCurrentStep(currentStep + 1)
        }
      }
    }, currentStep === -1 ? 500 : Math.floor(Math.random() * 600) + 400)

    return () => clearTimeout(timer)
  }, [isRunning, currentStep, steps.length])

  const handleRun = () => {
    setIsRunning(true)
    setCurrentStep(-1)
  }

  const handleReset = () => {
    setIsRunning(false)
    setCurrentStep(-1)
    setTotalDuration(0)
    setSteps(DEMO_WORKFLOW)
  }

  const isComplete = steps.every((s) => s.status === "completed")

  return (
    <div className="relative rounded-xl border border-border bg-background overflow-hidden">
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-border bg-muted/30">
        <div className="flex items-center gap-2">
          <div className="h-8 w-8 rounded-lg bg-purple-100 flex items-center justify-center">
            <GitBranch className="h-4 w-4 text-purple-600" />
          </div>
          <div>
            <span className="font-medium text-sm text-foreground">Lead Qualification Workflow</span>
            <span className="text-xs text-muted-foreground ml-2">5 steps</span>
          </div>
        </div>
        <div className="flex items-center gap-2">
          {isComplete && (
            <span className="text-xs text-emerald-600 font-medium">
              {totalDuration}ms
            </span>
          )}
          <button
            onClick={handleReset}
            disabled={!isComplete && !isRunning}
            className="p-1.5 rounded-md hover:bg-muted disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
          >
            <RotateCcw className="h-4 w-4 text-muted-foreground" />
          </button>
          <button
            onClick={isRunning ? () => setIsRunning(false) : handleRun}
            disabled={isComplete}
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-sm font-medium transition-colors ${
              isComplete
                ? "bg-emerald-100 text-emerald-700"
                : isRunning
                ? "bg-amber-100 text-amber-700"
                : "bg-emerald-600 text-white hover:bg-emerald-500"
            }`}
          >
            {isComplete ? (
              <>
                <CheckCircle2 className="h-3.5 w-3.5" />
                Complete
              </>
            ) : isRunning ? (
              <>
                <Pause className="h-3.5 w-3.5" />
                Running
              </>
            ) : (
              <>
                <Play className="h-3.5 w-3.5" />
                Run
              </>
            )}
          </button>
        </div>
      </div>

      {/* Workflow Steps */}
      <div className="p-4">
        <div className="space-y-2">
          {steps.map((step, index) => (
            <motion.div
              key={step.id}
              initial={false}
              animate={{
                backgroundColor:
                  step.status === "running"
                    ? "rgb(236 253 245)"
                    : step.status === "completed"
                    ? "transparent"
                    : "transparent",
              }}
              className="relative flex items-start gap-3 p-3 rounded-lg"
            >
              {/* Connector line */}
              {index < steps.length - 1 && (
                <div
                  className={`absolute left-[21px] top-10 w-0.5 h-[calc(100%-16px)] transition-colors ${
                    step.status === "completed" ? "bg-emerald-200" : "bg-border"
                  }`}
                />
              )}
              
              {/* Icon */}
              <div className="relative z-10 h-6 w-6 rounded-full bg-background border border-border flex items-center justify-center">
                <StepIcon type={step.type} status={step.status} />
              </div>
              
              {/* Content */}
              <div className="flex-1 min-w-0">
                <div className="flex items-center justify-between">
                  <span className={`text-sm font-medium ${
                    step.status === "pending" ? "text-muted-foreground" : "text-foreground"
                  }`}>
                    {step.name}
                  </span>
                  {step.duration && (
                    <span className="text-xs text-muted-foreground">{step.duration}ms</span>
                  )}
                </div>
                
                <AnimatePresence>
                  {step.output && (
                    <motion.div
                      initial={{ opacity: 0, height: 0 }}
                      animate={{ opacity: 1, height: "auto" }}
                      exit={{ opacity: 0, height: 0 }}
                      className="mt-1 text-xs text-muted-foreground font-mono bg-muted/50 px-2 py-1 rounded"
                    >
                      {step.output}
                    </motion.div>
                  )}
                </AnimatePresence>
              </div>
            </motion.div>
          ))}
        </div>
      </div>

      {/* Footer stats */}
      <div className="flex items-center justify-between px-4 py-3 border-t border-border bg-muted/20 text-xs text-muted-foreground">
        <span>
          {steps.filter((s) => s.status === "completed").length} / {steps.length} steps
        </span>
        <span>
          {isComplete ? "Workflow completed successfully" : isRunning ? "Processing..." : "Ready to run"}
        </span>
      </div>
    </div>
  )
}
