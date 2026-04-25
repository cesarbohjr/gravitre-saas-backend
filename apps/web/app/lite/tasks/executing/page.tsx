"use client"

import { useState, useEffect } from "react"
import { motion, AnimatePresence } from "framer-motion"
import { Button } from "@/components/ui/button"
import { Card } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Icon } from "@/lib/icons"
import { cn } from "@/lib/utils"
import Link from "next/link"
import {
  Check,
  Clock,
  Mail,
  MessageSquare,
  Database,
  Package,
  Eye,
  Download,
  ChevronRight,
  Sparkles,
  FileText,
  Users,
  CheckCircle2
} from "lucide-react"

const executionSteps = [
  { id: 1, title: "Understanding Task", description: "Analyzing your request", duration: 2000 },
  { id: 2, title: "Planning Approach", description: "Determining best strategy", duration: 1500 },
  { id: 3, title: "Gathering Context", description: "Accessing relevant data", duration: 2500 },
  { id: 4, title: "Generating Content", description: "Creating deliverables", duration: 4000 },
  { id: 5, title: "Quality Check", description: "Reviewing outputs", duration: 1500 },
  { id: 6, title: "Finalizing", description: "Preparing for delivery", duration: 1000 },
]

// Simulated task completion data
const completedTask = {
  title: "Q3 Healthcare Campaign",
  agent: "Marketing Agent",
  outputs: [
    { type: "Email Drafts", count: 3, icon: Mail },
    { type: "Audience Segment", count: 1, icon: Users },
  ],
  confidence: 94,
  duration: "12s",
  actionsTaken: [
    { platform: "Email", action: "Sent to your inbox", icon: Mail, status: "success" },
    { platform: "Gravitre", action: "Stored in Deliverables", icon: Package, status: "success" },
  ],
  deliveredTo: ["Email", "Gravitre"],
}

export default function ExecutingPage() {
  const [currentStep, setCurrentStep] = useState(0)
  const [progress, setProgress] = useState(0)
  const [isComplete, setIsComplete] = useState(false)
  const [mounted, setMounted] = useState(false)
  const [showEmailPreview, setShowEmailPreview] = useState(false)

  useEffect(() => {
    setMounted(true)
    
    let stepIndex = 0
    let totalDuration = executionSteps.reduce((acc, s) => acc + s.duration, 0)
    let elapsed = 0
    
    const interval = setInterval(() => {
      if (stepIndex < executionSteps.length) {
        const stepDuration = executionSteps[stepIndex].duration
        elapsed += 100
        
        if (elapsed >= stepDuration) {
          stepIndex++
          setCurrentStep(stepIndex)
          elapsed = 0
        }
        
        // Calculate overall progress
        const completedStepsDuration = executionSteps
          .slice(0, stepIndex)
          .reduce((acc, s) => acc + s.duration, 0)
        const currentProgress = ((completedStepsDuration + elapsed) / totalDuration) * 100
        setProgress(Math.min(currentProgress, 100))
      } else {
        setIsComplete(true)
        clearInterval(interval)
        // Show email preview after a short delay
        setTimeout(() => setShowEmailPreview(true), 800)
      }
    }, 100)

    return () => clearInterval(interval)
  }, [])

  return (
    <div className="min-h-screen bg-background flex items-center justify-center p-4 sm:p-6">
      <div className={cn(
        "max-w-2xl w-full transition-all duration-700",
        mounted ? "opacity-100 scale-100" : "opacity-0 scale-95"
      )}>
        <AnimatePresence mode="wait">
          {!isComplete ? (
            <motion.div
              key="executing"
              initial={{ opacity: 1 }}
              exit={{ opacity: 0, y: -20 }}
            >
              {/* Animated orb */}
              <div className="relative w-24 h-24 sm:w-32 sm:h-32 mx-auto mb-6 sm:mb-8">
                {/* Outer glow */}
                <div className="absolute inset-0 rounded-full bg-emerald-500/20 animate-ping" style={{ animationDuration: "2s" }} />
                {/* Middle ring */}
                <div className="absolute inset-2 rounded-full border-2 border-emerald-500/30 animate-spin" style={{ animationDuration: "8s" }} />
                {/* Inner orb */}
                <div className="absolute inset-4 rounded-full bg-gradient-to-br from-emerald-500/30 to-blue-500/30 backdrop-blur-sm flex items-center justify-center">
                  <Icon name="ai" size="xl" className="text-emerald-500" />
                </div>
                {/* Orbiting dots */}
                {[0, 1, 2].map((i) => (
                  <div
                    key={i}
                    className="absolute w-2 h-2 rounded-full bg-emerald-500"
                    style={{
                      animation: `orbit 3s linear infinite`,
                      animationDelay: `${i * 1}s`,
                      top: "50%",
                      left: "50%",
                      transformOrigin: "0 0",
                    }}
                  />
                ))}
              </div>

              {/* Current step */}
              <div className="text-center mb-6 sm:mb-8">
                <h1 className="text-xl sm:text-2xl font-bold text-foreground mb-2">
                  {executionSteps[currentStep]?.title || "Processing..."}
                </h1>
                <p className="text-sm sm:text-base text-muted-foreground">
                  {executionSteps[currentStep]?.description || "Please wait..."}
                </p>
              </div>

              {/* Progress bar */}
              <div className="mb-6 sm:mb-8">
                <div className="h-2 bg-secondary rounded-full overflow-hidden">
                  <motion.div 
                    className="h-full bg-gradient-to-r from-emerald-500 to-blue-500 rounded-full"
                    initial={{ width: 0 }}
                    animate={{ width: `${progress}%` }}
                    transition={{ duration: 0.3 }}
                  />
                </div>
                <div className="flex items-center justify-between mt-2 text-xs text-muted-foreground">
                  <span>{Math.round(progress)}% complete</span>
                  <span>Step {currentStep + 1} of {executionSteps.length}</span>
                </div>
              </div>

              {/* Steps timeline */}
              <Card className="p-4 border-border/50">
                <div className="space-y-3">
                  {executionSteps.map((step, index) => (
                    <div 
                      key={step.id}
                      className={cn(
                        "flex items-center gap-3 transition-all duration-300",
                        index < currentStep && "opacity-50",
                        index === currentStep && "scale-[1.02]"
                      )}
                    >
                      <div className={cn(
                        "w-6 h-6 rounded-full flex items-center justify-center shrink-0 transition-all",
                        index < currentStep && "bg-emerald-500 text-white",
                        index === currentStep && "bg-emerald-500/20 ring-2 ring-emerald-500",
                        index > currentStep && "bg-secondary"
                      )}>
                        {index < currentStep ? (
                          <Check className="w-3 h-3" />
                        ) : index === currentStep ? (
                          <Icon name="spinner" size="xs" className="animate-spin text-emerald-500" />
                        ) : (
                          <span className="text-xs text-muted-foreground">{index + 1}</span>
                        )}
                      </div>
                      <div>
                        <p className={cn(
                          "text-sm font-medium transition-colors",
                          index === currentStep ? "text-foreground" : "text-muted-foreground"
                        )}>
                          {step.title}
                        </p>
                      </div>
                    </div>
                  ))}
                </div>
              </Card>

              {/* Cancel button */}
              <div className="text-center mt-6">
                <Button variant="ghost" className="text-muted-foreground">
                  Cancel
                </Button>
              </div>
            </motion.div>
          ) : (
            /* Completion State */
            <motion.div
              key="complete"
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.5 }}
              className="text-center"
            >
              {/* Success animation */}
              <motion.div 
                className="relative w-20 h-20 sm:w-24 sm:h-24 mx-auto mb-6"
                initial={{ scale: 0.5, opacity: 0 }}
                animate={{ scale: 1, opacity: 1 }}
                transition={{ type: "spring", stiffness: 300, damping: 20 }}
              >
                <div className="absolute inset-0 rounded-full bg-emerald-500/20 animate-ping" style={{ animationDuration: "1.5s" }} />
                <div className="absolute inset-0 rounded-full bg-emerald-500/10 flex items-center justify-center">
                  <CheckCircle2 className="w-10 h-10 sm:w-12 sm:h-12 text-emerald-500" />
                </div>
              </motion.div>

              <motion.div
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: 0.2 }}
              >
                <h1 className="text-xl sm:text-2xl font-bold text-foreground mb-2">Task Complete</h1>
                <p className="text-sm sm:text-base text-muted-foreground mb-6 sm:mb-8">
                  Your deliverables are ready
                </p>
              </motion.div>

              {/* Output Preview Card */}
              <motion.div
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: 0.3 }}
              >
                <Card className="p-4 sm:p-6 border-border/50 text-left mb-6">
                  <div className="flex items-start gap-4 mb-4 pb-4 border-b border-border">
                    <div className="w-10 h-10 sm:w-12 sm:h-12 rounded-xl bg-emerald-500/10 flex items-center justify-center shrink-0">
                      <Sparkles className="w-5 h-5 sm:w-6 sm:h-6 text-emerald-500" />
                    </div>
                    <div className="flex-1 min-w-0">
                      <h3 className="font-semibold text-foreground text-sm sm:text-base">{completedTask.title}</h3>
                      <p className="text-xs sm:text-sm text-muted-foreground">{completedTask.agent}</p>
                    </div>
                    <Badge className="bg-emerald-500/10 text-emerald-500 border-emerald-500/20 text-xs">
                      {completedTask.confidence}% confidence
                    </Badge>
                  </div>

                  {/* Outputs generated */}
                  <div className="mb-4">
                    <h4 className="text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-3">
                      Outputs Generated
                    </h4>
                    <div className="flex flex-wrap gap-2">
                      {completedTask.outputs.map((output, i) => (
                        <div 
                          key={i}
                          className="flex items-center gap-2 px-3 py-2 rounded-lg bg-secondary/50"
                        >
                          <output.icon className="w-4 h-4 text-muted-foreground" />
                          <span className="text-sm text-foreground">{output.count} {output.type}</span>
                        </div>
                      ))}
                    </div>
                  </div>

                  {/* Actions Completed - "What Gravitre Did" */}
                  <div className="pt-4 border-t border-border">
                    <h4 className="text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-3 flex items-center gap-2">
                      <CheckCircle2 className="w-3.5 h-3.5 text-emerald-500" />
                      What Gravitre Did
                    </h4>
                    <div className="space-y-2">
                      {completedTask.actionsTaken.map((action, i) => (
                        <motion.div
                          key={i}
                          initial={{ opacity: 0, x: -10 }}
                          animate={{ opacity: 1, x: 0 }}
                          transition={{ delay: 0.5 + i * 0.15 }}
                          className="flex items-center gap-3 p-2 rounded-lg hover:bg-secondary/30 transition-colors"
                        >
                          <div className="w-8 h-8 rounded-lg bg-emerald-500/10 flex items-center justify-center shrink-0">
                            <action.icon className="w-4 h-4 text-emerald-500" />
                          </div>
                          <div className="flex-1">
                            <p className="text-sm text-foreground">{action.action}</p>
                            <p className="text-xs text-muted-foreground">{action.platform}</p>
                          </div>
                          <Check className="w-4 h-4 text-emerald-500" />
                        </motion.div>
                      ))}
                    </div>
                  </div>
                </Card>
              </motion.div>

              {/* Email Confirmation Preview */}
              <AnimatePresence>
                {showEmailPreview && (
                  <motion.div
                    initial={{ opacity: 0, y: 20, scale: 0.95 }}
                    animate={{ opacity: 1, y: 0, scale: 1 }}
                    transition={{ delay: 0.2, type: "spring", stiffness: 300, damping: 25 }}
                    className="mb-6"
                  >
                    <Card className="p-4 bg-blue-500/5 border-blue-500/20 text-left">
                      <div className="flex items-start gap-3">
                        <div className="w-10 h-10 rounded-lg bg-blue-500/10 flex items-center justify-center shrink-0">
                          <Mail className="w-5 h-5 text-blue-500" />
                        </div>
                        <div className="flex-1 min-w-0">
                          <div className="flex items-center gap-2 mb-1">
                            <p className="text-sm font-medium text-foreground">Email confirmation sent</p>
                            <Badge variant="outline" className="text-[10px] text-blue-500 border-blue-500/30">
                              Just now
                            </Badge>
                          </div>
                          <p className="text-xs text-muted-foreground">
                            A summary of this task has been sent to your email with links to all deliverables.
                          </p>
                          <div className="mt-3 p-3 rounded-lg bg-background/50 border border-border/50">
                            <p className="text-xs font-medium text-muted-foreground mb-1">Subject:</p>
                            <p className="text-sm text-foreground">Your Gravitre task is complete</p>
                            <div className="mt-2 pt-2 border-t border-border/50">
                              <p className="text-xs text-muted-foreground line-clamp-2">
                                {completedTask.title} has been completed with {completedTask.outputs.length} outputs. 
                                Actions taken: {completedTask.actionsTaken.map(a => a.action).join(", ")}.
                              </p>
                            </div>
                          </div>
                        </div>
                      </div>
                    </Card>
                  </motion.div>
                )}
              </AnimatePresence>

              {/* Quick stats */}
              <motion.div
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: 0.4 }}
                className="grid grid-cols-3 gap-3 sm:gap-4 mb-6 sm:mb-8"
              >
                <Card className="p-3 sm:p-4 border-border/50">
                  <p className="text-xl sm:text-2xl font-bold text-foreground">
                    {completedTask.outputs.reduce((acc, o) => acc + o.count, 0)}
                  </p>
                  <p className="text-[10px] sm:text-xs text-muted-foreground">Outputs</p>
                </Card>
                <Card className="p-3 sm:p-4 border-border/50">
                  <p className="text-xl sm:text-2xl font-bold text-emerald-500">{completedTask.confidence}%</p>
                  <p className="text-[10px] sm:text-xs text-muted-foreground">Confidence</p>
                </Card>
                <Card className="p-3 sm:p-4 border-border/50">
                  <p className="text-xl sm:text-2xl font-bold text-foreground">{completedTask.duration}</p>
                  <p className="text-[10px] sm:text-xs text-muted-foreground">Duration</p>
                </Card>
              </motion.div>

              {/* Actions */}
              <motion.div
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: 0.5 }}
                className="flex flex-col sm:flex-row gap-3 justify-center"
              >
                <Link href="/lite/deliverables" className="w-full sm:w-auto">
                  <Button className="w-full gap-2 bg-emerald-500 hover:bg-emerald-600 text-white">
                    <Eye className="w-4 h-4" />
                    Review Deliverables
                  </Button>
                </Link>
                <Link href="/lite" className="w-full sm:w-auto">
                  <Button variant="outline" className="w-full">
                    Back to Home
                  </Button>
                </Link>
              </motion.div>
            </motion.div>
          )}
        </AnimatePresence>
      </div>

      {/* CSS for orbit animation */}
      <style jsx>{`
        @keyframes orbit {
          from {
            transform: rotate(0deg) translateX(50px) rotate(0deg);
          }
          to {
            transform: rotate(360deg) translateX(50px) rotate(-360deg);
          }
        }
        @media (min-width: 640px) {
          @keyframes orbit {
            from {
              transform: rotate(0deg) translateX(60px) rotate(0deg);
            }
            to {
              transform: rotate(360deg) translateX(60px) rotate(-360deg);
            }
          }
        }
      `}</style>
    </div>
  )
}
