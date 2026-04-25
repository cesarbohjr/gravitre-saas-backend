"use client"

import { useState, useEffect, use } from "react"
import Link from "next/link"
import { motion, AnimatePresence } from "framer-motion"
import { AppShell } from "@/components/gravitre/app-shell"
import { Button } from "@/components/ui/button"
import { Icon } from "@/lib/icons"
import { cn } from "@/lib/utils"

// Types
interface ExecutionStep {
  id: string
  name: string
  status: "completed" | "running" | "pending" | "error"
  duration?: string
  details?: string
}

interface Deliverable {
  id: string
  title: string
  type: "email" | "social" | "report" | "segment" | "workflow"
  status: "ready" | "pending" | "error"
  confidence: number
  preview: string
  sourceRefs: string[]
}

// Mock Data
const assignment = {
  id: "assign-001",
  title: "Q3 Healthcare Campaign",
  description: "Create a comprehensive Q3 campaign targeting mid-market healthcare prospects with email sequences, social posts, and audience segments.",
  agent: { name: "Atlas", role: "Marketing Agent", gradient: "from-emerald-500 to-teal-500", initials: "AT" },
  status: "running" as const,
  progress: 78,
  createdAt: "2 hours ago",
  estimatedCompletion: "5 minutes",
  destination: "HubSpot + Outlook",
  requiresApproval: true,
}

const executionSteps: ExecutionStep[] = [
  { id: "step-1", name: "Planning", status: "completed", duration: "8s", details: "Analyzed task requirements" },
  { id: "step-2", name: "Connecting Systems", status: "completed", duration: "3s", details: "Connected to HubSpot, Salesforce" },
  { id: "step-3", name: "Gathering Context", status: "completed", duration: "12s", details: "Retrieved audience data and historical campaigns" },
  { id: "step-4", name: "Generating Outputs", status: "running", details: "Creating emails and social content..." },
  { id: "step-5", name: "Quality Check", status: "pending" },
  { id: "step-6", name: "Finalizing", status: "pending" },
]

const deliverables: Deliverable[] = [
  {
    id: "del-1",
    title: "Welcome Email Sequence",
    type: "email",
    status: "ready",
    confidence: 94,
    preview: "Subject: [First Name], Transform Your Healthcare Marketing in Q3\n\nHi [First Name],\n\nI noticed that [Company Name] has been focused on expanding your healthcare practice. Our platform has helped similar organizations reduce manual marketing tasks by 60% while increasing engagement rates.\n\nWould you be open to a quick conversation about how we might help?",
    sourceRefs: ["Brand Voice Guidelines", "Q2 Campaign Performance", "ICP Data"],
  },
  {
    id: "del-2",
    title: "LinkedIn Post Series",
    type: "social",
    status: "ready",
    confidence: 89,
    preview: "Struggling to scale personalized outreach in healthcare?\n\nOur latest research shows that mid-market healthcare companies waste 20+ hours per week on manual marketing tasks.\n\nHere&apos;s what the top performers do differently:\n\n1. Automate without losing the human touch\n2. Use data to predict engagement\n3. Personalize at scale",
    sourceRefs: ["Brand Voice Guidelines", "Social Patterns"],
  },
  {
    id: "del-3",
    title: "Campaign Performance Report",
    type: "report",
    status: "pending",
    confidence: 0,
    preview: "Generating comprehensive analysis...",
    sourceRefs: [],
  },
  {
    id: "del-4",
    title: "Healthcare Decision Makers Segment",
    type: "segment",
    status: "ready",
    confidence: 97,
    preview: "1,247 contacts matching criteria:\n\n• Industry: Healthcare\n• Company Size: 50-500 employees\n• Title: VP Marketing, CMO, Growth Lead\n• Engagement: Active in last 90 days\n• Score: 70+ lead score",
    sourceRefs: ["ICP Definition", "HubSpot Data"],
  },
]

const typeConfig: Record<string, { icon: string; color: string; label: string; bg: string }> = {
  email: { icon: "mail", color: "text-blue-400", label: "Email", bg: "bg-blue-500/10" },
  social: { icon: "share", color: "text-violet-400", label: "Social", bg: "bg-violet-500/10" },
  report: { icon: "chart", color: "text-emerald-400", label: "Report", bg: "bg-emerald-500/10" },
  segment: { icon: "users", color: "text-amber-400", label: "Segment", bg: "bg-amber-500/10" },
  workflow: { icon: "workflow", color: "text-rose-400", label: "Workflow", bg: "bg-rose-500/10" },
}

// Live Execution Timeline
function ExecutionTimeline({ steps, currentProgress }: { steps: ExecutionStep[]; currentProgress: number }) {
  const completedSteps = steps.filter(s => s.status === "completed").length
  const runningStep = steps.find(s => s.status === "running")

  return (
    <div className="rounded-2xl border border-border bg-card/50 p-6">
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-3">
          <div className="relative">
            <motion.div 
              className="h-10 w-10 rounded-xl bg-gradient-to-br from-blue-500/20 to-cyan-500/20 flex items-center justify-center"
              animate={{ 
                boxShadow: ["0 0 20px rgba(59, 130, 246, 0.2)", "0 0 30px rgba(59, 130, 246, 0.4)", "0 0 20px rgba(59, 130, 246, 0.2)"]
              }}
              transition={{ duration: 2, repeat: Infinity }}
            >
              <Icon name="activity" size="sm" className="text-blue-400" />
            </motion.div>
          </div>
          <div>
            <h3 className="font-semibold text-foreground">Execution Progress</h3>
            <p className="text-xs text-muted-foreground">{completedSteps} of {steps.length} steps complete</p>
          </div>
        </div>
        <div className="text-right">
          <motion.span 
            className="text-2xl font-bold text-foreground"
            key={currentProgress}
            initial={{ opacity: 0, y: -10 }}
            animate={{ opacity: 1, y: 0 }}
          >
            {currentProgress}%
          </motion.span>
        </div>
      </div>

      {/* Progress bar */}
      <div className="h-2 rounded-full bg-secondary overflow-hidden mb-6">
        <motion.div
          className="h-full rounded-full bg-gradient-to-r from-blue-500 via-cyan-500 to-blue-500 bg-[length:200%_100%]"
          style={{ backgroundPosition: "0% 0%" }}
          animate={{ 
            width: `${currentProgress}%`,
            backgroundPosition: ["0% 0%", "100% 0%", "0% 0%"]
          }}
          transition={{ 
            width: { duration: 0.5 },
            backgroundPosition: { duration: 2, repeat: Infinity, ease: "linear" }
          }}
        />
      </div>

      {/* Steps */}
      <div className="space-y-3">
        {steps.map((step, i) => (
          <motion.div
            key={step.id}
            initial={{ opacity: 0, x: -20 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ delay: i * 0.1 }}
            className={cn(
              "flex items-center gap-4 p-3 rounded-xl transition-all",
              step.status === "running" && "bg-blue-500/5 ring-1 ring-blue-500/20",
              step.status === "completed" && "opacity-70"
            )}
          >
            {/* Step indicator */}
            <div className="relative">
              {step.status === "completed" && (
                <motion.div 
                  className="h-8 w-8 rounded-lg bg-emerald-500/20 flex items-center justify-center"
                  initial={{ scale: 0 }}
                  animate={{ scale: 1 }}
                >
                  <Icon name="check" size="sm" className="text-emerald-400" />
                </motion.div>
              )}
              {step.status === "running" && (
                <motion.div 
                  className="h-8 w-8 rounded-lg bg-blue-500/20 flex items-center justify-center"
                  animate={{ scale: [1, 1.1, 1] }}
                  transition={{ duration: 1.5, repeat: Infinity }}
                >
                  <motion.div
                    animate={{ rotate: 360 }}
                    transition={{ duration: 1, repeat: Infinity, ease: "linear" }}
                  >
                    <Icon name="spinner" size="sm" className="text-blue-400" />
                  </motion.div>
                </motion.div>
              )}
              {step.status === "pending" && (
                <div className="h-8 w-8 rounded-lg bg-secondary flex items-center justify-center">
                  <span className="text-xs font-medium text-muted-foreground">{i + 1}</span>
                </div>
              )}
              {step.status === "error" && (
                <div className="h-8 w-8 rounded-lg bg-red-500/20 flex items-center justify-center">
                  <Icon name="warning" size="sm" className="text-red-400" />
                </div>
              )}
              
              {/* Connector line */}
              {i < steps.length - 1 && (
                <div className={cn(
                  "absolute left-1/2 top-full w-0.5 h-3 -translate-x-1/2",
                  step.status === "completed" ? "bg-emerald-500/30" : "bg-border"
                )} />
              )}
            </div>

            {/* Step content */}
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2">
                <span className={cn(
                  "font-medium",
                  step.status === "running" ? "text-foreground" : "text-muted-foreground"
                )}>
                  {step.name}
                </span>
                {step.duration && (
                  <span className="text-xs text-muted-foreground">{step.duration}</span>
                )}
              </div>
              {step.details && (
                <p className="text-xs text-muted-foreground mt-0.5">{step.details}</p>
              )}
            </div>
          </motion.div>
        ))}
      </div>
    </div>
  )
}

// Deliverable Card
function DeliverableCard({ 
  deliverable, 
  isSelected, 
  isApproved,
  onClick, 
  onApprove 
}: { 
  deliverable: Deliverable; 
  isSelected: boolean;
  isApproved: boolean;
  onClick: () => void;
  onApprove: () => void;
}) {
  const config = typeConfig[deliverable.type]

  return (
    <motion.div
      layout
      onClick={onClick}
      className={cn(
        "relative rounded-xl border p-4 cursor-pointer transition-all",
        isSelected 
          ? "bg-secondary/50 border-emerald-500/50 ring-1 ring-emerald-500/20" 
          : "bg-card/50 border-border hover:border-muted-foreground/30",
        isApproved && "border-emerald-500/30"
      )}
      whileHover={{ scale: 1.01 }}
      whileTap={{ scale: 0.99 }}
    >
      {/* Approved badge */}
      {isApproved && (
        <motion.div
          initial={{ scale: 0 }}
          animate={{ scale: 1 }}
          className="absolute -top-2 -right-2 h-6 w-6 rounded-full bg-emerald-500 flex items-center justify-center shadow-lg shadow-emerald-500/30"
        >
          <Icon name="check" size="xs" className="text-white" />
        </motion.div>
      )}

      <div className="flex items-start justify-between mb-3">
        <div className={cn("h-9 w-9 rounded-lg flex items-center justify-center", config.bg)}>
          <Icon name={config.icon as any} size="sm" className={config.color} />
        </div>
        
        {/* Confidence ring */}
        {deliverable.status === "ready" && (
          <div className="relative h-9 w-9">
            <svg className="h-9 w-9 -rotate-90">
              <circle cx="18" cy="18" r="14" fill="none" stroke="currentColor" strokeWidth="3" className="text-secondary" />
              <motion.circle
                cx="18" cy="18" r="14" fill="none"
                stroke={deliverable.confidence >= 90 ? "#10b981" : deliverable.confidence >= 70 ? "#f59e0b" : "#ef4444"}
                strokeWidth="3" strokeLinecap="round" strokeDasharray={88}
                initial={{ strokeDashoffset: 88 }}
                animate={{ strokeDashoffset: 88 - (deliverable.confidence / 100) * 88 }}
                transition={{ duration: 1 }}
              />
            </svg>
            <span className="absolute inset-0 flex items-center justify-center text-[10px] font-bold text-foreground">
              {deliverable.confidence}
            </span>
          </div>
        )}
        
        {deliverable.status === "pending" && (
          <motion.div
            className="h-9 w-9 rounded-lg bg-secondary flex items-center justify-center"
            animate={{ opacity: [0.5, 1, 0.5] }}
            transition={{ duration: 1.5, repeat: Infinity }}
          >
            <Icon name="clock" size="sm" className="text-muted-foreground" />
          </motion.div>
        )}
      </div>

      <h4 className="font-medium text-foreground mb-1 line-clamp-1">{deliverable.title}</h4>
      <p className="text-xs text-muted-foreground line-clamp-2 mb-3">{deliverable.preview.slice(0, 80)}...</p>

      <div className="flex items-center justify-between">
        <span className={cn("text-xs font-medium px-2 py-0.5 rounded-full", config.bg, config.color)}>
          {config.label}
        </span>
        
        {deliverable.status === "ready" && !isApproved && (
          <Button 
            size="sm" 
            variant="ghost" 
            className="h-7 text-xs gap-1"
            onClick={(e) => { e.stopPropagation(); onApprove(); }}
          >
            <Icon name="check" size="xs" />
            Approve
          </Button>
        )}
      </div>
    </motion.div>
  )
}

// Preview Panel
function PreviewPanel({ deliverable, isApproved, onApprove, onPush }: { 
  deliverable: Deliverable | null; 
  isApproved: boolean;
  onApprove: () => void;
  onPush: () => void;
}) {
  if (!deliverable) {
    return (
      <div className="h-full flex flex-col items-center justify-center text-center p-8">
        <div className="h-16 w-16 rounded-2xl bg-secondary flex items-center justify-center mb-4">
          <Icon name="eye" size="xl" className="text-muted-foreground" />
        </div>
        <h3 className="font-semibold text-foreground mb-2">Select a Deliverable</h3>
        <p className="text-sm text-muted-foreground max-w-xs">
          Click on any deliverable to preview its content and approve for publishing
        </p>
      </div>
    )
  }

  const config = typeConfig[deliverable.type]

  return (
    <div className="h-full flex flex-col">
      {/* Header */}
      <div className="p-4 border-b border-border">
        <div className="flex items-start justify-between mb-3">
          <div className="flex items-center gap-3">
            <div className={cn("h-10 w-10 rounded-xl flex items-center justify-center", config.bg)}>
              <Icon name={config.icon as any} size="sm" className={config.color} />
            </div>
            <div>
              <h3 className="font-semibold text-foreground">{deliverable.title}</h3>
              <div className="flex items-center gap-2 mt-0.5">
                <span className={cn("text-xs", config.color)}>{config.label}</span>
                {deliverable.confidence > 0 && (
                  <>
                    <span className="text-muted-foreground/50">|</span>
                    <span className={cn(
                      "text-xs font-medium",
                      deliverable.confidence >= 90 ? "text-emerald-400" : "text-amber-400"
                    )}>
                      {deliverable.confidence}% confidence
                    </span>
                  </>
                )}
              </div>
            </div>
          </div>
          
          {isApproved && (
            <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-emerald-500/10 text-emerald-400 text-xs font-medium">
              <Icon name="check" size="xs" />
              Approved
            </div>
          )}
        </div>

        {/* Source references */}
        {deliverable.sourceRefs.length > 0 && (
          <div className="flex items-center gap-2 flex-wrap">
            <span className="text-xs text-muted-foreground">Sources:</span>
            {deliverable.sourceRefs.map((ref, i) => (
              <span key={i} className="text-xs px-2 py-0.5 rounded-md bg-secondary text-muted-foreground">
                {ref}
              </span>
            ))}
          </div>
        )}
      </div>

      {/* Preview Content */}
      <div className="flex-1 overflow-y-auto p-4">
        <div className="rounded-xl bg-secondary/50 p-4">
          <pre className="text-sm text-foreground whitespace-pre-wrap font-sans leading-relaxed">
            {deliverable.preview}
          </pre>
        </div>
      </div>

      {/* Actions */}
      <div className="p-4 border-t border-border">
        <div className="flex items-center gap-3">
          {!isApproved ? (
            <>
              <Button 
                className="flex-1 gap-2 bg-gradient-to-r from-emerald-500 to-teal-500 hover:from-emerald-600 hover:to-teal-600 text-white border-0"
                onClick={onApprove}
              >
                <Icon name="check" size="sm" />
                Approve
              </Button>
              <Button variant="outline" className="gap-2">
                <Icon name="edit" size="sm" />
                Edit
              </Button>
            </>
          ) : (
            <>
              <Button 
                className="flex-1 gap-2 bg-gradient-to-r from-blue-500 to-indigo-500 hover:from-blue-600 hover:to-indigo-600 text-white border-0"
                onClick={onPush}
              >
                <Icon name="upload" size="sm" />
                Push to {assignment.destination.split("+")[0].trim()}
              </Button>
              <Button variant="outline" className="gap-2">
                <Icon name="download" size="sm" />
                Export
              </Button>
            </>
          )}
        </div>
      </div>
    </div>
  )
}

export default function AssignmentDetailPage({
  params,
}: {
  params: Promise<{ id: string }>
}) {
  const { id } = use(params)
  const [selectedDeliverable, setSelectedDeliverable] = useState<string | null>(null)
  const [approvedItems, setApprovedItems] = useState<string[]>([])
  const [progress, setProgress] = useState(assignment.progress)
  
  // Simulate progress
  useEffect(() => {
    if (assignment.status === "running" && progress < 100) {
      const timer = setInterval(() => {
        setProgress(prev => Math.min(prev + 1, 100))
      }, 500)
      return () => clearInterval(timer)
    }
  }, [progress])

  const selectedItem = deliverables.find(d => d.id === selectedDeliverable)
  const readyCount = deliverables.filter(d => d.status === "ready").length
  const approvedCount = approvedItems.length

  const handleApprove = (id: string) => {
    setApprovedItems(prev => [...prev, id])
  }

  const handleApproveAll = () => {
    setApprovedItems(deliverables.filter(d => d.status === "ready").map(d => d.id))
  }

  return (
    <AppShell title={assignment.title}>
      <div className="flex h-full">
        {/* Left Column - Execution & Deliverables */}
        <div className="w-[420px] border-r border-border flex flex-col overflow-hidden">
          {/* Header */}
          <div className="p-6 border-b border-border">
            <Link href="/assignments" className="flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground mb-4">
              <Icon name="chevronLeft" size="sm" />
              Back to Assignments
            </Link>
            
            <div className="flex items-center gap-3 mb-3">
              <motion.div 
                className={cn("h-12 w-12 rounded-xl flex items-center justify-center bg-gradient-to-br text-white font-bold", assignment.agent.gradient)}
                animate={{ 
                  boxShadow: ["0 0 20px rgba(16, 185, 129, 0.2)", "0 0 30px rgba(16, 185, 129, 0.4)", "0 0 20px rgba(16, 185, 129, 0.2)"]
                }}
                transition={{ duration: 2, repeat: Infinity }}
              >
                {assignment.agent.initials}
              </motion.div>
              <div>
                <h1 className="font-semibold text-foreground">{assignment.title}</h1>
                <p className="text-xs text-muted-foreground">{assignment.agent.name} | Started {assignment.createdAt}</p>
              </div>
            </div>
          </div>

          {/* Scrollable Content */}
          <div className="flex-1 overflow-y-auto p-6 space-y-6">
            {/* Execution Timeline */}
            <ExecutionTimeline steps={executionSteps} currentProgress={progress} />

            {/* Deliverables */}
            <div>
              <div className="flex items-center justify-between mb-4">
                <div>
                  <h3 className="font-semibold text-foreground">Deliverables</h3>
                  <p className="text-xs text-muted-foreground">{readyCount} ready | {approvedCount} approved</p>
                </div>
                {readyCount > 0 && approvedCount < readyCount && (
                  <Button size="sm" variant="outline" className="gap-1 text-xs" onClick={handleApproveAll}>
                    <Icon name="check" size="xs" />
                    Approve All
                  </Button>
                )}
              </div>

              <div className="grid grid-cols-2 gap-3">
                {deliverables.map((deliverable) => (
                  <DeliverableCard
                    key={deliverable.id}
                    deliverable={deliverable}
                    isSelected={selectedDeliverable === deliverable.id}
                    isApproved={approvedItems.includes(deliverable.id)}
                    onClick={() => setSelectedDeliverable(deliverable.id)}
                    onApprove={() => handleApprove(deliverable.id)}
                  />
                ))}
              </div>
            </div>
          </div>
        </div>

        {/* Right Column - Preview Panel */}
        <div className="flex-1 bg-card/30">
          <PreviewPanel
            deliverable={selectedItem || null}
            isApproved={selectedItem ? approvedItems.includes(selectedItem.id) : false}
            onApprove={() => selectedItem && handleApprove(selectedItem.id)}
            onPush={() => console.log("Push to destination")}
          />
        </div>
      </div>
    </AppShell>
  )
}
