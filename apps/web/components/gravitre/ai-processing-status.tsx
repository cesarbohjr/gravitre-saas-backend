"use client"

import { useState, useEffect } from "react"
import { motion, AnimatePresence } from "framer-motion"
import { 
  Loader2, 
  Search, 
  Database, 
  TrendingUp, 
  Shield, 
  CheckCircle2,
  Sparkles,
  FileSearch,
  Cpu,
  Zap,
  GitBranch
} from "lucide-react"

interface ProcessingStep {
  id: string
  label: string
  icon: React.ElementType
  duration: number // ms
}

const processingSteps: ProcessingStep[] = [
  { id: "init", label: "Initializing analysis engine", icon: Cpu, duration: 800 },
  { id: "logs", label: "Checking pipeline logs", icon: FileSearch, duration: 1200 },
  { id: "metrics", label: "Analyzing latency patterns", icon: TrendingUp, duration: 1500 },
  { id: "db", label: "Querying historical data", icon: Database, duration: 1000 },
  { id: "correlate", label: "Correlating failure patterns", icon: GitBranch, duration: 1200 },
  { id: "security", label: "Verifying access permissions", icon: Shield, duration: 600 },
  { id: "synthesize", label: "Synthesizing insights", icon: Sparkles, duration: 1400 },
]

function AnimatedDots() {
  return (
    <span className="inline-flex ml-1">
      {[0, 1, 2].map((i) => (
        <motion.span
          key={i}
          className="w-1 h-1 rounded-full bg-current mx-[1px]"
          animate={{ opacity: [0.3, 1, 0.3] }}
          transition={{
            duration: 1,
            repeat: Infinity,
            delay: i * 0.2,
            ease: "easeInOut",
          }}
        />
      ))}
    </span>
  )
}

function PulsingOrb() {
  return (
    <div className="relative flex items-center justify-center">
      <motion.div
        className="absolute h-10 w-10 rounded-full bg-blue-500/20"
        animate={{ scale: [1, 1.5, 1], opacity: [0.5, 0, 0.5] }}
        transition={{ duration: 2, repeat: Infinity, ease: "easeOut" }}
      />
      <motion.div
        className="absolute h-8 w-8 rounded-full bg-blue-500/30"
        animate={{ scale: [1, 1.3, 1], opacity: [0.6, 0.2, 0.6] }}
        transition={{ duration: 1.5, repeat: Infinity, ease: "easeOut", delay: 0.2 }}
      />
      <div className="relative flex h-6 w-6 items-center justify-center rounded-full bg-gradient-to-br from-blue-400 to-blue-600 shadow-lg shadow-blue-500/30">
        <Sparkles className="h-3 w-3 text-white" />
      </div>
    </div>
  )
}

interface AIProcessingStatusProps {
  isProcessing: boolean
  onComplete?: () => void
}

export function AIProcessingStatus({ isProcessing, onComplete }: AIProcessingStatusProps) {
  const [currentStepIndex, setCurrentStepIndex] = useState(0)
  const [completedSteps, setCompletedSteps] = useState<string[]>([])
  const [isComplete, setIsComplete] = useState(false)

  useEffect(() => {
    if (!isProcessing) {
      setCurrentStepIndex(0)
      setCompletedSteps([])
      setIsComplete(false)
      return
    }

    let timeoutId: NodeJS.Timeout

    const processNextStep = (index: number) => {
      if (index >= processingSteps.length) {
        setIsComplete(true)
        onComplete?.()
        return
      }

      setCurrentStepIndex(index)
      const step = processingSteps[index]

      timeoutId = setTimeout(() => {
        setCompletedSteps((prev) => [...prev, step.id])
        processNextStep(index + 1)
      }, step.duration)
    }

    processNextStep(0)

    return () => clearTimeout(timeoutId)
  }, [isProcessing, onComplete])

  if (!isProcessing && completedSteps.length === 0) return null

  const currentStep = processingSteps[currentStepIndex]

  return (
    <AnimatePresence>
      {(isProcessing || !isComplete) && (
        <motion.div
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0, y: -10 }}
          transition={{ duration: 0.3 }}
          className="rounded-xl border border-border bg-gradient-to-b from-card to-card/50 p-5 shadow-lg"
        >
          {/* Header */}
          <div className="flex items-center gap-3 mb-4">
            <PulsingOrb />
            <div>
              <div className="flex items-center gap-2">
                <h3 className="text-sm font-semibold text-foreground">
                  AI is analyzing
                </h3>
                <AnimatedDots />
              </div>
              <p className="text-xs text-muted-foreground mt-0.5">
                Processing your request with contextual awareness
              </p>
            </div>
          </div>

          {/* Current Action */}
          <motion.div
            key={currentStep?.id}
            initial={{ opacity: 0, x: -10 }}
            animate={{ opacity: 1, x: 0 }}
            className="mb-4 flex items-center gap-3 rounded-lg bg-blue-500/10 border border-blue-500/20 px-4 py-3"
          >
            <motion.div
              animate={{ rotate: 360 }}
              transition={{ duration: 1, repeat: Infinity, ease: "linear" }}
            >
              <Loader2 className="h-4 w-4 text-blue-400" />
            </motion.div>
            <span className="text-sm font-medium text-blue-400">
              {currentStep?.label}
            </span>
          </motion.div>

          {/* Progress Steps */}
          <div className="space-y-2">
            {processingSteps.slice(0, currentStepIndex + 1).map((step, index) => {
              const isCompleted = completedSteps.includes(step.id)
              const isCurrent = index === currentStepIndex && !isCompleted
              const StepIcon = step.icon

              return (
                <motion.div
                  key={step.id}
                  initial={{ opacity: 0, x: -20 }}
                  animate={{ opacity: 1, x: 0 }}
                  transition={{ delay: index * 0.05, duration: 0.2 }}
                  className={`flex items-center gap-3 rounded-lg px-3 py-2 transition-colors ${
                    isCompleted
                      ? "bg-emerald-500/5"
                      : isCurrent
                        ? "bg-secondary/50"
                        : ""
                  }`}
                >
                  <div
                    className={`flex h-6 w-6 items-center justify-center rounded-full transition-all ${
                      isCompleted
                        ? "bg-emerald-500/20 text-emerald-400"
                        : isCurrent
                          ? "bg-blue-500/20 text-blue-400"
                          : "bg-muted text-muted-foreground"
                    }`}
                  >
                    {isCompleted ? (
                      <motion.div
                        initial={{ scale: 0 }}
                        animate={{ scale: 1 }}
                        transition={{ type: "spring", stiffness: 500 }}
                      >
                        <CheckCircle2 className="h-3.5 w-3.5" />
                      </motion.div>
                    ) : (
                      <StepIcon className="h-3 w-3" />
                    )}
                  </div>
                  <span
                    className={`text-xs transition-colors ${
                      isCompleted
                        ? "text-emerald-400"
                        : isCurrent
                          ? "text-foreground"
                          : "text-muted-foreground"
                    }`}
                  >
                    {step.label}
                  </span>
                  {isCompleted && (
                    <motion.span
                      initial={{ opacity: 0 }}
                      animate={{ opacity: 1 }}
                      className="ml-auto text-[10px] text-emerald-400/70"
                    >
                      Done
                    </motion.span>
                  )}
                </motion.div>
              )
            })}
          </div>

          {/* Progress Bar */}
          <div className="mt-4 pt-4 border-t border-border">
            <div className="flex items-center justify-between mb-2">
              <span className="text-[10px] text-muted-foreground uppercase tracking-wide">
                Progress
              </span>
              <span className="text-xs text-muted-foreground">
                {Math.round((completedSteps.length / processingSteps.length) * 100)}%
              </span>
            </div>
            <div className="h-1.5 rounded-full bg-secondary overflow-hidden">
              <motion.div
                className="h-full rounded-full bg-gradient-to-r from-blue-500 to-emerald-500"
                initial={{ width: 0 }}
                animate={{
                  width: `${((currentStepIndex + (completedSteps.includes(processingSteps[currentStepIndex]?.id) ? 1 : 0.5)) / processingSteps.length) * 100}%`,
                }}
                transition={{ duration: 0.3 }}
              />
            </div>
          </div>
        </motion.div>
      )}
    </AnimatePresence>
  )
}

// Compact inline version for use in headers or smaller areas
export function AIProcessingInline({ isProcessing }: { isProcessing: boolean }) {
  const [statusIndex, setStatusIndex] = useState(0)
  
  const statuses = [
    "Analyzing system",
    "Checking logs",
    "Processing data",
    "Generating insights",
  ]

  useEffect(() => {
    if (!isProcessing) return
    
    const interval = setInterval(() => {
      setStatusIndex((prev) => (prev + 1) % statuses.length)
    }, 2000)
    
    return () => clearInterval(interval)
  }, [isProcessing, statuses.length])

  if (!isProcessing) return null

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      className="flex items-center gap-2 text-xs text-blue-400"
    >
      <motion.div
        animate={{ rotate: 360 }}
        transition={{ duration: 1, repeat: Infinity, ease: "linear" }}
      >
        <Loader2 className="h-3 w-3" />
      </motion.div>
      <motion.span
        key={statusIndex}
        initial={{ opacity: 0, y: 5 }}
        animate={{ opacity: 1, y: 0 }}
        exit={{ opacity: 0, y: -5 }}
      >
        {statuses[statusIndex]}
      </motion.span>
      <AnimatedDots />
    </motion.div>
  )
}
