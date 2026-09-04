"use client"

import Link from "next/link"
import { motion, AnimatePresence } from "framer-motion"
import React from "react"
import { 
  ArrowRight, 
  Bot, 
  Workflow, 
  Shield, 
  Users,
  MessageSquare,
  Database,
  Zap,
  Eye,
  Lock,
  BarChart3,
  Clock,
  Check,
  GitBranch,
  Bell,
  FileText,
  Sparkles,
  ChevronRight,
  Blocks,
  Layers,
  Play
} from "lucide-react"
import { IntegrationsGrid } from "@/components/gravitre/platform-logos"
import { VendorLogo } from "@/components/gravitre/vendor-logo"
import { ProductScreenshot } from "@/components/marketing/product-screenshot"
import { MARKETING_INTEGRATION_APPS } from "@/lib/connectors"
import { TestimonialsCarouselFull, SocialProofBanner } from "@/components/marketing/testimonials"
import { IntelligenceEngineSection } from "@/components/marketing/intelligence-engine-section"
import {
  GibeDataFlowSection,
  TransparencyMetricsSection,
  MarketplaceHighlightsSection,
  UseCasesSection,
  GovernanceAiStackSection,
} from "@/components/marketing/platform-sections"
import { MARKETING_COPY } from "@/lib/marketing-copy"
import { SHOW_MARKETING_TESTIMONIALS } from "@/lib/marketing-flags"
import type { FeaturesSectionId } from "@/lib/features-nav"

// Bento card component - Light theme
function BentoCard({ 
  children, 
  className = "",
  delay = 0 
}: { 
  children: React.ReactNode
  className?: string
  delay?: number
}) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true }}
      transition={{ delay }}
      className={`group relative rounded-3xl border border-border bg-card shadow-sm overflow-hidden transition-all hover:shadow-lg hover:border-border ${className}`}
    >
      <div className="absolute inset-0 bg-gradient-to-br from-muted/50 via-transparent to-transparent opacity-0 group-hover:opacity-100 transition-opacity duration-500" />
      {children}
    </motion.div>
  )
}

// Interactive App Screen Components
function AgentsScreen() {
  const agents = [
    { name: "Data Analyst", icon: BarChart3, color: "emerald", status: "active", role: "Advisory" },
    { name: "Content Writer", icon: FileText, color: "blue", status: "active", role: "Drafts" },
    { name: "Research Agent", icon: Eye, color: "purple", status: "idle", role: "Lookup" },
    { name: "Code Reviewer", icon: GitBranch, color: "amber", status: "active", role: "Review" },
  ]
  
  return (
    <div className="rounded-xl border border-border bg-card shadow-lg overflow-hidden">
      {/* App Header */}
      <div className="border-b border-border bg-muted/50 px-4 py-3 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <div className="flex gap-1.5">
            <div className="h-3 w-3 rounded-full bg-red-400" />
            <div className="h-3 w-3 rounded-full bg-amber-400" />
            <div className="h-3 w-3 rounded-full bg-emerald-400" />
          </div>
          <span className="text-xs font-medium text-muted-foreground ml-2">Agents</span>
        </div>
        <div className="flex items-center gap-2">
          <div className="h-6 px-2 rounded bg-primary/15 text-primary text-[10px] font-medium flex items-center">
            + New Agent
          </div>
        </div>
      </div>
      
      {/* Agent List */}
      <div className="p-4 space-y-3">
        {agents.map((agent, i) => (
          <motion.div
            key={agent.name}
            initial={{ opacity: 0, x: -20 }}
            whileInView={{ opacity: 1, x: 0 }}
            viewport={{ once: true }}
            transition={{ delay: i * 0.1 }}
            className="flex items-center gap-4 p-3 rounded-lg border border-border hover:border-border hover:bg-muted/50 transition-colors cursor-pointer"
          >
            <div className={`h-10 w-10 rounded-lg flex items-center justify-center relative ${
              agent.color === 'emerald' ? 'bg-primary/15' :
              agent.color === 'blue' ? 'bg-blue-100' :
              agent.color === 'purple' ? 'bg-purple-100' : 'bg-amber-100'
            }`}>
              <agent.icon className={`h-5 w-5 ${
                agent.color === 'emerald' ? 'text-primary' :
                agent.color === 'blue' ? 'text-blue-600' :
                agent.color === 'purple' ? 'text-purple-600' : 'text-amber-600'
              }`} />
              {agent.status === "active" && (
                <motion.div
                  className="absolute -bottom-0.5 -right-0.5 h-2.5 w-2.5 rounded-full bg-primary/100 ring-2 ring-white"
                  animate={{ scale: [1, 1.2, 1] }}
                  transition={{ duration: 1.5, repeat: Infinity }}
                />
              )}
            </div>
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2">
                <span className="text-sm font-medium text-foreground">{agent.name}</span>
                <span className={`text-[10px] px-1.5 py-0.5 rounded ${
                  agent.status === 'active' ? 'bg-primary/15 text-primary' : 'bg-muted text-muted-foreground'
                }`}>
                  {agent.status}
                </span>
              </div>
              <div className="flex items-center gap-3 mt-1">
                <span className="text-[10px] text-muted-foreground">{agent.role}</span>
                <span className="text-[10px] text-muted-foreground">Outcomes from your org</span>
              </div>
            </div>
            <ChevronRight className="h-4 w-4 text-muted-foreground" />
          </motion.div>
        ))}
      </div>
    </div>
  )
}

function AssignmentsScreen() {
  const assignments = [
    { title: "Q4 Sales Report", agent: "Data Analyst", status: "in_progress", progress: 65, priority: "high" },
    { title: "Blog Post Draft", agent: "Content Writer", status: "completed", progress: 100, priority: "medium" },
    { title: "Code PR Review", agent: "Code Reviewer", status: "pending", progress: 0, priority: "high" },
    { title: "Market Research", agent: "Research Agent", status: "in_progress", progress: 30, priority: "low" },
  ]
  
  return (
    <div className="rounded-xl border border-border bg-card shadow-lg overflow-hidden">
      {/* App Header */}
      <div className="border-b border-border bg-muted/50 px-4 py-3 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <div className="flex gap-1.5">
            <div className="h-3 w-3 rounded-full bg-red-400" />
            <div className="h-3 w-3 rounded-full bg-amber-400" />
            <div className="h-3 w-3 rounded-full bg-emerald-400" />
          </div>
          <span className="text-xs font-medium text-muted-foreground ml-2">Assignments</span>
        </div>
        <div className="flex items-center gap-2 text-[10px]">
          <span className="text-muted-foreground">4 active</span>
        </div>
      </div>
      
      {/* Assignment List */}
      <div className="p-4 space-y-3">
        {assignments.map((task, i) => (
          <motion.div
            key={task.title}
            initial={{ opacity: 0, y: 10 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            transition={{ delay: i * 0.1 }}
            className="p-3 rounded-lg border border-border hover:border-border transition-colors"
          >
            <div className="flex items-start justify-between gap-2 mb-2">
              <div>
                <div className="flex items-center gap-2">
                  <span className="text-sm font-medium text-foreground">{task.title}</span>
                  <span className={`h-1.5 w-1.5 rounded-full ${
                    task.priority === 'high' ? 'bg-red-500' :
                    task.priority === 'medium' ? 'bg-amber-500' : 'bg-muted-foreground'
                  }`} />
                </div>
                <span className="text-[10px] text-muted-foreground">Assigned to {task.agent}</span>
              </div>
              <span className={`text-[10px] px-1.5 py-0.5 rounded ${
                task.status === 'completed' ? 'bg-primary/15 text-primary' :
                task.status === 'in_progress' ? 'bg-blue-100 text-blue-700' : 'bg-muted text-muted-foreground'
              }`}>
                {task.status === 'in_progress' ? 'In Progress' : task.status === 'completed' ? 'Completed' : 'Pending'}
              </span>
            </div>
            <div className="flex items-center gap-2">
              <div className="flex-1 h-1.5 bg-muted rounded-full overflow-hidden">
                <motion.div 
                  className={`h-full rounded-full ${
                    task.status === 'completed' ? 'bg-primary/100' : 'bg-blue-500'
                  }`}
                  initial={{ width: 0 }}
                  whileInView={{ width: `${task.progress}%` }}
                  viewport={{ once: true }}
                  transition={{ delay: i * 0.1 + 0.2 }}
                />
              </div>
              <span className="text-[10px] text-muted-foreground w-8">{task.progress}%</span>
            </div>
          </motion.div>
        ))}
      </div>
    </div>
  )
}

function WorkflowBuilderScreen() {
  return (
    <div className="rounded-xl border border-border bg-card shadow-lg overflow-hidden">
      {/* App Header */}
      <div className="border-b border-border bg-muted/50 px-4 py-3 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <div className="flex gap-1.5">
            <div className="h-3 w-3 rounded-full bg-red-400" />
            <div className="h-3 w-3 rounded-full bg-amber-400" />
            <div className="h-3 w-3 rounded-full bg-emerald-400" />
          </div>
          <span className="text-xs font-medium text-muted-foreground ml-2">Create Workflow</span>
        </div>
        <div className="flex items-center gap-2">
          <div className="h-6 px-2 rounded bg-primary text-white text-[10px] font-medium flex items-center">
            Save
          </div>
        </div>
      </div>
      
      {/* Workflow Canvas */}
      <div className="p-6 bg-muted/50/50 min-h-[280px] relative">
        {/* Grid pattern */}
        <div className="absolute inset-0 opacity-30" style={{
          backgroundImage: 'radial-gradient(circle, #d4d4d8 1px, transparent 1px)',
          backgroundSize: '20px 20px'
        }} />
        
        {/* Workflow nodes */}
        <div className="relative flex items-center justify-center gap-4">
          {/* Trigger */}
          <motion.div
            initial={{ opacity: 0, scale: 0.8 }}
            whileInView={{ opacity: 1, scale: 1 }}
            viewport={{ once: true }}
            className="flex flex-col items-center"
          >
            <div className="h-14 w-14 rounded-xl border-2 border-dashed border-primary/30 bg-primary/10 flex items-center justify-center shadow-sm">
              <Zap className="h-6 w-6 text-primary" />
            </div>
            <span className="text-[10px] text-muted-foreground mt-1.5 font-medium">Trigger</span>
          </motion.div>
          
          {/* Connector */}
          <motion.div
            initial={{ width: 0 }}
            whileInView={{ width: 40 }}
            viewport={{ once: true }}
            transition={{ delay: 0.2 }}
            className="h-0.5 bg-gradient-to-r from-emerald-400 to-blue-400"
          />
          
          {/* Process */}
          <motion.div
            initial={{ opacity: 0, scale: 0.8 }}
            whileInView={{ opacity: 1, scale: 1 }}
            viewport={{ once: true }}
            transition={{ delay: 0.3 }}
            className="flex flex-col items-center"
          >
            <div className="h-14 w-14 rounded-xl border border-blue-200 bg-blue-50 flex items-center justify-center shadow-sm">
              <Bot className="h-6 w-6 text-blue-600" />
            </div>
            <span className="text-[10px] text-muted-foreground mt-1.5 font-medium">AI Agent</span>
          </motion.div>
          
          {/* Connector */}
          <motion.div
            initial={{ width: 0 }}
            whileInView={{ width: 40 }}
            viewport={{ once: true }}
            transition={{ delay: 0.4 }}
            className="h-0.5 bg-gradient-to-r from-blue-400 to-purple-400"
          />
          
          {/* Condition */}
          <motion.div
            initial={{ opacity: 0, scale: 0.8 }}
            whileInView={{ opacity: 1, scale: 1 }}
            viewport={{ once: true }}
            transition={{ delay: 0.5 }}
            className="flex flex-col items-center"
          >
            <div className="h-14 w-14 rounded-xl border border-purple-200 bg-purple-50 flex items-center justify-center shadow-sm rotate-45">
              <GitBranch className="h-5 w-5 text-purple-600 -rotate-45" />
            </div>
            <span className="text-[10px] text-muted-foreground mt-1.5 font-medium">Condition</span>
          </motion.div>
          
          {/* Connector */}
          <motion.div
            initial={{ width: 0 }}
            whileInView={{ width: 40 }}
            viewport={{ once: true }}
            transition={{ delay: 0.6 }}
            className="h-0.5 bg-gradient-to-r from-purple-400 to-amber-400"
          />
          
          {/* Action */}
          <motion.div
            initial={{ opacity: 0, scale: 0.8 }}
            whileInView={{ opacity: 1, scale: 1 }}
            viewport={{ once: true }}
            transition={{ delay: 0.7 }}
            className="flex flex-col items-center"
          >
            <div className="h-14 w-14 rounded-xl border border-amber-200 bg-amber-50 flex items-center justify-center shadow-sm">
              <Bell className="h-6 w-6 text-amber-600" />
            </div>
            <span className="text-[10px] text-muted-foreground mt-1.5 font-medium">Notify</span>
          </motion.div>
        </div>
        
        {/* Side panel hint */}
        <motion.div
          initial={{ opacity: 0, x: 20 }}
          whileInView={{ opacity: 0.8, x: 0 }}
          viewport={{ once: true }}
          transition={{ delay: 0.8 }}
          className="absolute right-4 top-4 w-28 p-2 rounded-lg border border-border bg-card shadow-sm"
        >
          <span className="text-[9px] font-medium text-muted-foreground block mb-1.5">Add Node</span>
          <div className="space-y-1">
            {['Agent', 'Condition', 'Action'].map((item) => (
              <div key={item} className="text-[9px] text-muted-foreground flex items-center gap-1.5">
                <div className="h-1.5 w-1.5 rounded-full bg-muted" />
                {item}
              </div>
            ))}
          </div>
        </motion.div>
      </div>
    </div>
  )
}

function AIOperatorScreen() {
  const conversation = [
    { 
      type: 'user', 
      message: "Analyze our Q4 sales data and find trends",
      agent: null
    },
    { 
      type: 'ai', 
      message: "In your workspace, Insights surfaces trends from your connected CRM and run telemetry — with sources you can audit. This marketing mock does not invent percentages.",
      agent: "Data Analyst"
    },
    { 
      type: 'user', 
      message: "Draft a summary email for the exec team",
      agent: null
    },
    { 
      type: 'ai', 
      message: "Done! I've drafted a concise executive summary highlighting the key wins and included a chart. Ready to review in your drafts.",
      agent: "Content Writer"
    },
  ]
  
  const [visibleMessages, setVisibleMessages] = React.useState<number[]>([])
  const [currentIndex, setCurrentIndex] = React.useState(0)
  
  React.useEffect(() => {
    const showNextMessage = () => {
      setVisibleMessages(prev => {
        if (prev.length >= conversation.length) {
          // Reset after showing all messages
          setTimeout(() => {
            setVisibleMessages([])
            setCurrentIndex(0)
          }, 2000)
          return prev
        }
        return [...prev, prev.length]
      })
    }
    
    const timer = setInterval(() => {
      if (visibleMessages.length < conversation.length) {
        showNextMessage()
      }
    }, 1500)
    
    // Show first message immediately
    if (visibleMessages.length === 0) {
      showNextMessage()
    }
    
    return () => clearInterval(timer)
  }, [visibleMessages.length, conversation.length])
  
  return (
    <div className="rounded-xl border border-border bg-card shadow-lg overflow-hidden">
      {/* App Header */}
      <div className="border-b border-border bg-muted/50 px-4 py-3 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <div className="flex gap-1.5">
            <div className="h-3 w-3 rounded-full bg-red-400" />
            <div className="h-3 w-3 rounded-full bg-amber-400" />
            <div className="h-3 w-3 rounded-full bg-emerald-400" />
          </div>
          <span className="text-xs font-medium text-muted-foreground ml-2">Gravitre AI</span>
        </div>
        <div className="flex items-center gap-1">
          <motion.div
            className="h-2 w-2 rounded-full bg-primary/100"
            animate={{ scale: [1, 1.2, 1] }}
            transition={{ duration: 1, repeat: Infinity }}
          />
          <span className="text-[10px] text-primary">Online</span>
        </div>
      </div>
      
      {/* Chat */}
      <div className="p-4 space-y-3 min-h-[320px] bg-muted/50/30 overflow-hidden">
        <AnimatePresence mode="popLayout">
          {conversation.map((msg, index) => (
            visibleMessages.includes(index) && (
              msg.type === 'user' ? (
                <motion.div 
                  key={`msg-${index}`}
                  className="flex items-start gap-3"
                  initial={{ opacity: 0, y: 20, scale: 0.95 }}
                  animate={{ opacity: 1, y: 0, scale: 1 }}
                  exit={{ opacity: 0, y: -10, scale: 0.95 }}
                  transition={{ type: "spring", stiffness: 300, damping: 25 }}
                >
                  <div className="h-8 w-8 rounded-full bg-muted flex items-center justify-center shrink-0 text-xs font-medium text-muted-foreground">
                    JD
                  </div>
                  <div className="flex-1 rounded-2xl rounded-tl-sm bg-card border border-border p-3 shadow-sm">
                    <p className="text-sm text-foreground">{msg.message}</p>
                  </div>
                </motion.div>
              ) : (
                <motion.div 
                  key={`msg-${index}`}
                  className="flex items-start gap-3 justify-end"
                  initial={{ opacity: 0, y: 20, scale: 0.95 }}
                  animate={{ opacity: 1, y: 0, scale: 1 }}
                  exit={{ opacity: 0, y: -10, scale: 0.95 }}
                  transition={{ type: "spring", stiffness: 300, damping: 25 }}
                >
                  <div className="flex-1 rounded-2xl rounded-tr-sm bg-gradient-to-br from-primary/10 to-emerald-100/80 border border-primary/20 p-3">
                    <div className="flex items-center gap-2 mb-1.5">
                      <Sparkles className="h-3 w-3 text-primary" />
                      <span className="text-[10px] font-medium text-primary">via {msg.agent}</span>
                    </div>
                    <p className="text-sm text-primary">{msg.message}</p>
                  </div>
                  <div className="h-8 w-8 rounded-full bg-gradient-to-br from-primary/100 to-emerald-600 flex items-center justify-center shrink-0 shadow-md">
                    <Sparkles className="h-4 w-4 text-white" />
                  </div>
                </motion.div>
              )
            )
          ))}
        </AnimatePresence>
        
        {/* Typing indicator */}
        <AnimatePresence>
          {visibleMessages.length > 0 && visibleMessages.length < conversation.length && (
            <motion.div
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0 }}
              className="flex items-center gap-2 pl-11"
            >
              <div className="flex gap-1">
                {[0, 1, 2].map((i) => (
                  <motion.div
                    key={i}
                    className="h-1.5 w-1.5 rounded-full bg-emerald-400"
                    animate={{ y: [0, -4, 0] }}
                    transition={{ duration: 0.6, repeat: Infinity, delay: i * 0.15 }}
                  />
                ))}
              </div>
              <span className="text-[10px] text-muted-foreground">
                {conversation[visibleMessages.length]?.type === 'user' ? 'typing...' : 'AI is thinking...'}
              </span>
            </motion.div>
          )}
        </AnimatePresence>
        
        {/* Input */}
        <div className="rounded-xl border border-border bg-card p-2.5 flex items-center gap-2 shadow-sm mt-auto">
          <input
            type="text"
            placeholder="Ask anything..."
            className="flex-1 text-sm text-foreground placeholder:text-muted-foreground bg-transparent outline-none"
            readOnly
          />
          <div className="h-7 w-7 rounded-lg bg-primary/100 flex items-center justify-center cursor-pointer hover:bg-primary transition-colors">
            <ArrowRight className="h-3.5 w-3.5 text-white" />
          </div>
        </div>
      </div>
    </div>
  )
}

// Feature visual component - Light theme
function FeatureVisual({ type }: { type: string }) {
  if (type === "governance") {
    return (
      <div className="relative h-full min-h-[300px] p-6 space-y-3 bg-muted/50/50">
        {[
          { icon: Lock, label: "Role-based access control", status: true },
          { icon: FileText, label: "Complete audit trail", status: true },
          { icon: Shield, label: "End-to-end encryption", status: true },
          { icon: Check, label: "Human-in-the-loop approvals", status: true },
        ].map((item, i) => (
          <motion.div
            key={i}
            initial={{ opacity: 0, x: -20 }}
            whileInView={{ opacity: 1, x: 0 }}
            viewport={{ once: true }}
            transition={{ delay: i * 0.1 }}
            className="flex items-center justify-between rounded-xl border border-border bg-card p-4 shadow-sm"
          >
            <div className="flex items-center gap-3">
              <item.icon className="h-4 w-4 text-amber-500" />
              <span className="text-sm text-foreground">{item.label}</span>
            </div>
            <div className="h-6 w-6 rounded-full bg-primary/15 flex items-center justify-center">
              <Check className="h-3 w-3 text-primary" />
            </div>
          </motion.div>
        ))}
      </div>
    )
  }

  return null
}

export function FeaturesLegacyContent({
  section = "all",
  showHero = true,
  showTail = true,
  exclude = [],
}: {
  section?: FeaturesSectionId | "all"
  showHero?: boolean
  showTail?: boolean
  exclude?: FeaturesSectionId[]
}) {
  const excluded = new Set<string>(exclude)
  // Show a gated block when the active section matches one of `ids`.
  // With section="all", every non-excluded section renders; `exclude` lets the
  // main Features page hide sections that now live on their own tab (GIBE,
  // Governance, Marketplace) without duplicating any content.
  function showSection(active: FeaturesSectionId | "all", ...ids: (FeaturesSectionId | "all")[]) {
    const realIds = ids.filter((id): id is FeaturesSectionId => id !== "all")
    if (active === "all") {
      return realIds.some((id) => !excluded.has(id))
    }
    return ids.includes(active) && !excluded.has(active)
  }
  return (
    <div className="relative overflow-hidden bg-card">
      {showHero && section === "all" ? (
      <>
      {/* Hero */}
      <section className="relative py-32 overflow-hidden">
        {/* Animated gradient background */}
        <div className="absolute inset-0 bg-gradient-to-b from-primary/10 via-transparent to-transparent" />
        
        {/* Animated floating orbs */}
        <motion.div 
          className="absolute top-0 left-1/2 -translate-x-1/2 w-[800px] h-[600px] bg-primary/15 rounded-full blur-3xl"
          animate={{ 
            scale: [1, 1.15, 1],
            opacity: [0.3, 0.4, 0.3],
          }}
          transition={{ duration: 10, repeat: Infinity, ease: "easeInOut" }}
        />
        <motion.div 
          className="absolute top-20 -left-32 w-[400px] h-[400px] bg-blue-100 rounded-full blur-3xl"
          animate={{ 
            x: [0, 50, 0],
            opacity: [0.2, 0.3, 0.2],
          }}
          transition={{ duration: 12, repeat: Infinity, ease: "easeInOut", delay: 2 }}
        />
        <motion.div 
          className="absolute top-40 -right-32 w-[350px] h-[350px] bg-purple-100 rounded-full blur-3xl"
          animate={{ 
            x: [0, -30, 0],
            opacity: [0.15, 0.25, 0.15],
          }}
          transition={{ duration: 14, repeat: Infinity, ease: "easeInOut", delay: 4 }}
        />
        
        {/* Neural connection lines */}
        <svg className="absolute inset-0 w-full h-full opacity-[0.05]" xmlns="http://www.w3.org/2000/svg">
          {Array.from({ length: 6 }).map((_, i) => (
            <motion.line
              key={i}
              x1={`${15 + i * 15}%`}
              y1="0%"
              x2={`${25 + i * 10}%`}
              y2="100%"
              stroke="#10b981"
              strokeWidth="1"
              initial={{ pathLength: 0 }}
              animate={{ pathLength: [0, 1, 0] }}
              transition={{
                duration: 5,
                delay: i * 0.8,
                repeat: Infinity,
                ease: "easeInOut",
              }}
            />
          ))}
        </svg>
        
        {/* Floating icons */}
        <div className="absolute inset-0 overflow-hidden pointer-events-none">
          {[
            { icon: "M12 2L2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5", left: "15%", top: "20%", delay: 0 },
            { icon: "M20 7h-9M14 17H5M17 17a2 2 0 100-4 2 2 0 000 4zM7 7a2 2 0 100-4 2 2 0 000 4z", left: "80%", top: "30%", delay: 1 },
            { icon: "M12 2v20M17 5H9.5a3.5 3.5 0 000 7h5a3.5 3.5 0 010 7H6", left: "10%", top: "70%", delay: 2 },
          ].map((item, i) => (
            <motion.div
              key={i}
              className="absolute w-12 h-12 rounded-xl bg-card/60 backdrop-blur-sm border border-primary/20/50 flex items-center justify-center shadow-sm"
              style={{ left: item.left, top: item.top }}
              animate={{ 
                y: [0, -15, 0],
                rotate: [0, 5, 0],
              }}
              transition={{
                duration: 6,
                delay: item.delay,
                repeat: Infinity,
                ease: "easeInOut",
              }}
            >
              <svg className="w-5 h-5 text-primary" fill="none" stroke="currentColor" viewBox="0 0 24 24" strokeWidth="1.5">
                <path strokeLinecap="round" strokeLinejoin="round" d={item.icon} />
              </svg>
            </motion.div>
          ))}
        </div>
        
        <div className="relative mx-auto max-w-7xl px-6">
          <motion.div
            initial={{ opacity: 0, y: 30 }}
            animate={{ opacity: 1, y: 0 }}
            className="mx-auto max-w-3xl text-center"
          >
            <motion.div
              initial={{ opacity: 0, scale: 0.9 }}
              animate={{ opacity: 1, scale: 1 }}
              transition={{ delay: 0.1 }}
              className="mb-6 inline-flex items-center gap-2 rounded-full border border-primary/20 bg-primary/10/80 backdrop-blur-sm px-4 py-2"
            >
              <motion.div
                animate={{ rotate: [0, 360] }}
                transition={{ duration: 8, repeat: Infinity, ease: "linear" }}
              >
                <Sparkles className="h-4 w-4 text-primary" />
              </motion.div>
              <span className="text-sm font-medium text-primary">{MARKETING_COPY.featuresHero.badge}</span>
            </motion.div>
            
            {/* Staggered headline */}
            <div className="overflow-hidden">
              <motion.h1
                initial={{ opacity: 0, y: 50 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: 0.2, duration: 0.7, ease: [0.16, 1, 0.3, 1] }}
                className="text-5xl sm:text-6xl lg:text-7xl font-bold tracking-tight"
              >
                <span className="text-foreground">
                  {MARKETING_COPY.featuresHero.headline[0]}
                </span>
              </motion.h1>
            </div>
            <div className="overflow-hidden">
              <motion.h1
                initial={{ opacity: 0, y: 50 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: 0.3, duration: 0.7, ease: [0.16, 1, 0.3, 1] }}
                className="text-5xl sm:text-6xl lg:text-7xl font-bold tracking-tight bg-gradient-to-r from-emerald-600 to-teal-500 bg-clip-text text-transparent"
              >
                {MARKETING_COPY.featuresHero.headline[1]}
              </motion.h1>
            </div>
            
            <motion.p 
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.5 }}
              className="mt-6 text-lg text-muted-foreground max-w-2xl mx-auto"
            >
              {MARKETING_COPY.featuresHero.subtitle}
            </motion.p>
            
            {/* Feature pills */}
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.7 }}
              className="mt-10 flex flex-wrap items-center justify-center gap-3"
            >
              {MARKETING_COPY.featuresHero.pills.map((feature, i) => (
                <motion.span
                  key={feature}
                  initial={{ opacity: 0, scale: 0.9 }}
                  animate={{ opacity: 1, scale: 1 }}
                  transition={{ delay: 0.8 + i * 0.1 }}
                  className="px-4 py-2 rounded-full bg-card/80 backdrop-blur-sm border border-border text-sm font-medium text-foreground shadow-sm"
                >
                  {feature}
                </motion.span>
              ))}
            </motion.div>
          </motion.div>
        </div>
      </section>
      </>
      ) : null}

      {showSection(section, "intelligence", "all") ? (
      <>
      <IntelligenceEngineSection variant="compact" />

      <GibeDataFlowSection compact />
      </>
      ) : null}

      {showSection(section, "how-it-works", "all") ? (
      <>
      {/* How Gravitre Works - Architecture Diagram */}
      <section className="relative pb-32">
        <div className="mx-auto max-w-7xl px-6">
          {/* Section header */}
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            className="text-center mb-16"
          >
            <h2 className="text-3xl font-bold text-foreground mb-4">How Gravitre works</h2>
            <p className="text-muted-foreground max-w-2xl mx-auto">
              Your team → Gravitre AI → agents → connected tools — with GIBE learning from every verified run.
            </p>
          </motion.div>

          {/* Architecture Diagram */}
          <motion.div
            initial={{ opacity: 0, y: 30 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            className="relative"
          >
            {/* Background pattern */}
            <div className="absolute inset-0 bg-gradient-to-b from-muted/50 to-white rounded-3xl" />
            <div className="absolute inset-0 opacity-[0.03]" style={{
              backgroundImage: 'radial-gradient(circle, #000 1px, transparent 1px)',
              backgroundSize: '24px 24px'
            }} />
            
            <div className="relative p-8 lg:p-12">
              {/* Main Flow */}
              <div className="flex flex-col lg:flex-row items-center justify-center gap-6 lg:gap-4">
                
                {/* Your Team */}
                <motion.div
                  initial={{ opacity: 0, x: -20 }}
                  whileInView={{ opacity: 1, x: 0 }}
                  viewport={{ once: true }}
                  className="flex flex-col items-center"
                >
                  <div className="relative">
                    <div className="h-24 w-24 rounded-2xl bg-gradient-to-br from-muted to-muted/50 border border-border flex items-center justify-center shadow-sm">
                      <Users className="h-10 w-10 text-muted-foreground" />
                    </div>
                    <motion.div 
                      className="absolute -top-1 -right-1 h-5 w-5 rounded-full bg-primary/100 border-2 border-white"
                      animate={{ scale: [1, 1.2, 1] }}
                      transition={{ duration: 2, repeat: Infinity }}
                    />
                  </div>
                  <span className="mt-3 text-sm font-semibold text-foreground">Your Team</span>
                  <span className="text-xs text-muted-foreground">Natural language</span>
                </motion.div>

                {/* Arrow 1 */}
                <motion.div
                  initial={{ opacity: 0, scaleX: 0 }}
                  whileInView={{ opacity: 1, scaleX: 1 }}
                  viewport={{ once: true }}
                  transition={{ delay: 0.2 }}
                  className="hidden lg:flex items-center"
                >
                  <div className="w-16 h-0.5 bg-gradient-to-r from-border to-primary" />
                  <ArrowRight className="h-5 w-5 text-primary -ml-1" />
                </motion.div>
                <motion.div
                  initial={{ opacity: 0 }}
                  whileInView={{ opacity: 1 }}
                  viewport={{ once: true }}
                  transition={{ delay: 0.2 }}
                  className="lg:hidden flex flex-col items-center"
                >
                  <div className="w-0.5 h-8 bg-gradient-to-b from-border to-primary" />
                </motion.div>

                {/* Gravitre AI (Central Hub) */}
                <motion.div
                  initial={{ opacity: 0, scale: 0.9 }}
                  whileInView={{ opacity: 1, scale: 1 }}
                  viewport={{ once: true }}
                  transition={{ delay: 0.3 }}
                  className="relative"
                >
                  {/* Pulse rings */}
                  <motion.div
                    className="absolute inset-0 rounded-3xl bg-emerald-400"
                    animate={{ scale: [1, 1.15, 1], opacity: [0.3, 0, 0.3] }}
                    transition={{ duration: 3, repeat: Infinity }}
                  />
                  <motion.div
                    className="absolute inset-0 rounded-3xl bg-emerald-400"
                    animate={{ scale: [1, 1.25, 1], opacity: [0.2, 0, 0.2] }}
                    transition={{ duration: 3, repeat: Infinity, delay: 0.5 }}
                  />
                  
                  <div className="relative h-32 w-32 lg:h-40 lg:w-40 rounded-3xl bg-gradient-to-br from-primary/100 to-emerald-600 flex flex-col items-center justify-center shadow-xl shadow-emerald-500/20">
                    <Sparkles className="h-12 w-12 text-white mb-2" />
                    <span className="text-sm font-bold text-white">Gravitre AI</span>
                    <span className="text-[10px] text-emerald-100">Intelligence + execution</span>
                  </div>
                </motion.div>

                {/* Arrow 2 */}
                <motion.div
                  initial={{ opacity: 0, scaleX: 0 }}
                  whileInView={{ opacity: 1, scaleX: 1 }}
                  viewport={{ once: true }}
                  transition={{ delay: 0.4 }}
                  className="hidden lg:flex items-center"
                >
                  <div className="w-16 h-0.5 bg-gradient-to-r from-emerald-400 to-blue-400" />
                  <ArrowRight className="h-5 w-5 text-blue-500 -ml-1" />
                </motion.div>
                <motion.div
                  initial={{ opacity: 0 }}
                  whileInView={{ opacity: 1 }}
                  viewport={{ once: true }}
                  transition={{ delay: 0.4 }}
                  className="lg:hidden flex flex-col items-center"
                >
                  <div className="w-0.5 h-8 bg-gradient-to-b from-emerald-400 to-blue-400" />
                </motion.div>

                {/* AI Agents */}
                <motion.div
                  initial={{ opacity: 0, x: 20 }}
                  whileInView={{ opacity: 1, x: 0 }}
                  viewport={{ once: true }}
                  transition={{ delay: 0.5 }}
                  className="flex flex-col items-center"
                >
                  <div className="flex gap-2">
                    {[
                      { color: "blue", icon: Bot },
                      { color: "purple", icon: Bot },
                      { color: "amber", icon: Bot },
                    ].map((agent, i) => (
                      <motion.div
                        key={i}
                        initial={{ opacity: 0, y: 10 }}
                        whileInView={{ opacity: 1, y: 0 }}
                        viewport={{ once: true }}
                        transition={{ delay: 0.5 + i * 0.1 }}
                        className={`h-16 w-16 rounded-xl border flex items-center justify-center shadow-sm ${
                          agent.color === 'blue' ? 'bg-blue-50 border-blue-200' :
                          agent.color === 'purple' ? 'bg-purple-50 border-purple-200' :
                          'bg-amber-50 border-amber-200'
                        }`}
                      >
                        <agent.icon className={`h-7 w-7 ${
                          agent.color === 'blue' ? 'text-blue-500' :
                          agent.color === 'purple' ? 'text-purple-500' :
                          'text-amber-500'
                        }`} />
                      </motion.div>
                    ))}
                  </div>
                  <span className="mt-3 text-sm font-semibold text-foreground">AI Agents</span>
                  <span className="text-xs text-muted-foreground">Specialized workers</span>
                </motion.div>

                {/* Arrow 3 */}
                <motion.div
                  initial={{ opacity: 0, scaleX: 0 }}
                  whileInView={{ opacity: 1, scaleX: 1 }}
                  viewport={{ once: true }}
                  transition={{ delay: 0.6 }}
                  className="hidden lg:flex items-center"
                >
                  <div className="w-16 h-0.5 bg-gradient-to-r from-blue-400 to-rose-400" />
                  <ArrowRight className="h-5 w-5 text-rose-500 -ml-1" />
                </motion.div>
                <motion.div
                  initial={{ opacity: 0 }}
                  whileInView={{ opacity: 1 }}
                  viewport={{ once: true }}
                  transition={{ delay: 0.6 }}
                  className="lg:hidden flex flex-col items-center"
                >
                  <div className="w-0.5 h-8 bg-gradient-to-b from-blue-400 to-rose-400" />
                </motion.div>

                {/* Your Tools */}
                <motion.div
                  initial={{ opacity: 0, x: 20 }}
                  whileInView={{ opacity: 1, x: 0 }}
                  viewport={{ once: true }}
                  transition={{ delay: 0.7 }}
                  className="flex flex-col items-center"
                >
                  <div className="grid grid-cols-2 gap-2">
                    {MARKETING_INTEGRATION_APPS.slice(0, 4).map((tool, i) => (
                      <motion.div
                        key={tool}
                        initial={{ opacity: 0, scale: 0.8 }}
                        whileInView={{ opacity: 1, scale: 1 }}
                        viewport={{ once: true }}
                        transition={{ delay: 0.7 + i * 0.05 }}
                        className="flex items-center justify-center"
                      >
                        <VendorLogo vendor={tool} size="md" variant="light" />
                      </motion.div>
                    ))}
                  </div>
                  <span className="mt-3 text-sm font-semibold text-foreground">Your Tools</span>
                  <span className="text-xs text-muted-foreground">50+ integrations when configured</span>
                </motion.div>
              </div>

              {/* Process Labels */}
              <motion.div
                initial={{ opacity: 0, y: 20 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true }}
                transition={{ delay: 0.8 }}
                className="mt-12 flex flex-wrap justify-center gap-4"
              >
                {[
                  { step: "1", label: "Ask anything", desc: "Natural language requests" },
                  { step: "2", label: "Smart routing", desc: "AI selects the right agent" },
                  { step: "3", label: "Execute tasks", desc: "Agents take real actions" },
                  { step: "4", label: "Get results", desc: "Instant, actionable outputs" },
                ].map((item, i) => (
                  <motion.div
                    key={item.step}
                    initial={{ opacity: 0, y: 10 }}
                    whileInView={{ opacity: 1, y: 0 }}
                    viewport={{ once: true }}
                    transition={{ delay: 0.8 + i * 0.1 }}
                    className="flex items-center gap-3 px-4 py-3 rounded-xl bg-card border border-border shadow-sm"
                  >
                    <div className="h-8 w-8 rounded-lg bg-primary/15 flex items-center justify-center">
                      <span className="text-sm font-bold text-primary">{item.step}</span>
                    </div>
                    <div>
                      <div className="text-sm font-medium text-foreground">{item.label}</div>
                      <div className="text-xs text-muted-foreground">{item.desc}</div>
                    </div>
                  </motion.div>
                ))}
              </motion.div>
            </div>
          </motion.div>

          {/* Value Props */}
          <motion.div
            initial={{ opacity: 0, y: 30 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            className="mt-16 grid md:grid-cols-3 gap-8"
          >
            {[
              { 
                icon: Zap, 
                title: "Accelerated execution", 
                desc: "Agents run routine work around the clock once your tools are connected.",
                color: "emerald"
              },
              { 
                icon: Shield, 
                title: "Full control", 
                desc: "Asks before it acts, shows its work, and never guesses silently.",
                color: "blue"
              },
              { 
                icon: BarChart3, 
                title: "Honest metrics", 
                desc: "Live counts and labeled estimates — with open gaps named, not faked.",
                color: "purple"
              },
            ].map((item, i) => (
              <motion.div
                key={item.title}
                initial={{ opacity: 0, y: 20 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true }}
                transition={{ delay: i * 0.1 }}
                className="text-center"
              >
                <div className={`h-14 w-14 mx-auto rounded-2xl flex items-center justify-center mb-4 ${
                  item.color === 'emerald' ? 'bg-primary/15' :
                  item.color === 'blue' ? 'bg-blue-100' : 'bg-purple-100'
                }`}>
                  <item.icon className={`h-7 w-7 ${
                    item.color === 'emerald' ? 'text-primary' :
                    item.color === 'blue' ? 'text-blue-600' : 'text-purple-600'
                  }`} />
                </div>
                <h3 className="text-lg font-semibold text-foreground mb-2">{item.title}</h3>
                <p className="text-sm text-muted-foreground">{item.desc}</p>
              </motion.div>
            ))}
          </motion.div>
        </div>
      </section>
      </>
      ) : null}

      {showSection(section, "gravitre-ai", "agents", "workflows", "integrations", "governance", "meson", "all") ? (
      <>
      {/* 5 Key Features - Light Theme Screens */}
      <section className="relative py-32 border-t border-border bg-card">
        <div className="mx-auto max-w-7xl px-6">
          {section === "all" ? (
          <motion.div
            initial={{ opacity: 0, y: 30 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            className="mx-auto max-w-2xl text-center mb-20"
          >
            <span className="text-sm font-semibold text-primary tracking-wide uppercase">Platform Features</span>
            <h2 className="mt-4 text-4xl font-bold tracking-tight text-foreground">
              Everything you need to automate intelligently
            </h2>
          </motion.div>
          ) : null}

          <div className={section === "all" ? "space-y-32" : ""}>
            {/* Feature 1: Gravitre AI */}
            {showSection(section, "gravitre-ai", "all") ? (
            <motion.div
              initial={{ opacity: 0, y: 30 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true }}
              className="grid lg:grid-cols-2 gap-12 items-center"
            >
              <div>
                <div className="inline-flex items-center gap-2 rounded-full bg-primary/10 border border-primary/20 px-3 py-1 mb-4">
                  <Sparkles className="h-3.5 w-3.5 text-primary" />
                  <span className="text-xs font-medium text-primary">Gravitre AI</span>
                </div>
                <h3 className="text-3xl font-bold text-foreground mb-4">Natural language command center</h3>
                <p className="text-muted-foreground mb-6 leading-relaxed text-lg">
                  Talk to your AI workforce like a colleague — ask, analyze, and trigger
                  workflows through natural conversation.
                </p>
                <ul className="space-y-3">
                  {['Conversational AI interface', 'Context-aware responses', 'Multi-agent workflows (when configured)', 'Async task analysis with progress tracking'].map((item) => (
                    <li key={item} className="flex items-center gap-3 text-sm text-muted-foreground">
                      <div className="h-5 w-5 rounded-full bg-primary/15 flex items-center justify-center">
                        <Check className="h-3 w-3 text-primary" />
                      </div>
                      {item}
                    </li>
                  ))}
                </ul>
              </div>
              <ProductScreenshot
                src="/product/app-ai.png"
                alt="Gravitre AI workspace with the conversation history panel open, showing three past threads and the ask box with org-specific suggestion chips."
                chromeLabel="Gravitre AI"
                glowClassName="bg-gradient-to-r from-emerald-100/60 to-teal-100/60"
              />
            </motion.div>
            ) : null}

            {/* Feature 2: Smart Agents */}
            {showSection(section, "agents", "all") ? (
            <motion.div
              initial={{ opacity: 0, y: 30 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true }}
              className="grid lg:grid-cols-2 gap-12 items-center"
            >
              <div className="lg:order-2">
                <div className="inline-flex items-center gap-2 rounded-full bg-blue-50 border border-blue-200 px-3 py-1 mb-4">
                  <Bot className="h-3.5 w-3.5 text-blue-600" />
                  <span className="text-xs font-medium text-blue-700">Smart Agents</span>
                </div>
                <h3 className="text-3xl font-bold text-foreground mb-4">Your AI team, configured your way</h3>
                <p className="text-muted-foreground mb-6 leading-relaxed text-lg">
                  Deploy specialized AI agents for different roles - data analysis, content writing, 
                  research, and more. Each agent learns your business context and improves over time.
                </p>
                <ul className="space-y-3">
                  {['Pre-built agent templates', 'Custom capability configuration', 'Continuous learning', 'Role-based permissions'].map((item) => (
                    <li key={item} className="flex items-center gap-3 text-sm text-muted-foreground">
                      <div className="h-5 w-5 rounded-full bg-blue-100 flex items-center justify-center">
                        <Check className="h-3 w-3 text-blue-600" />
                      </div>
                      {item}
                    </li>
                  ))}
                </ul>
              </div>
              <ProductScreenshot
                src="/product/app-agents.png"
                alt="Agents roster showing four configured agents with their department, status, tasks today, and success rate."
                chromeLabel="Agents"
                glowClassName="bg-gradient-to-r from-blue-100/60 to-indigo-100/60"
                className="lg:order-1"
              />
            </motion.div>
            ) : null}

            {/* Feature 3: Visual Workflow Builder */}
            {showSection(section, "workflows", "all") ? (
            <motion.div
              initial={{ opacity: 0, y: 30 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true }}
              className="grid lg:grid-cols-2 gap-12 items-center"
            >
              <div>
                <div className="inline-flex items-center gap-2 rounded-full bg-purple-50 border border-purple-200 px-3 py-1 mb-4">
                  <Workflow className="h-3.5 w-3.5 text-purple-600" />
                  <span className="text-xs font-medium text-purple-700">Workflow Builder</span>
                </div>
                <h3 className="text-3xl font-bold text-foreground mb-4">Visual automation, zero code</h3>
                <p className="text-muted-foreground mb-6 leading-relaxed text-lg">
                  Build sophisticated automation workflows with our drag-and-drop builder. 
                  Connect triggers, conditions, and actions without writing a single line of code.
                </p>
                <ul className="space-y-3">
                  {['Drag-and-drop interface', 'Conditional branching', 'Human-in-the-loop approvals', 'Version control'].map((item) => (
                    <li key={item} className="flex items-center gap-3 text-sm text-muted-foreground">
                      <div className="h-5 w-5 rounded-full bg-purple-100 flex items-center justify-center">
                        <Check className="h-3 w-3 text-purple-600" />
                      </div>
                      {item}
                    </li>
                  ))}
                </ul>
              </div>
              <ProductScreenshot
                src="/product/app-workflows.png"
                alt="Workflows list showing five workflows with their environment, last run, success rate, and run count, including a paused and a draft workflow."
                chromeLabel="Workflows"
                glowClassName="bg-gradient-to-r from-purple-100/60 to-pink-100/60"
              />
            </motion.div>
            ) : null}

            {/* Feature 4: Connected Integrations */}
            {showSection(section, "integrations", "all") ? (
            <motion.div
              initial={{ opacity: 0, y: 30 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true }}
              className="grid lg:grid-cols-2 gap-12 items-center"
            >
              <div className="lg:order-2">
                <div className="inline-flex items-center gap-2 rounded-full bg-amber-50 border border-amber-200 px-3 py-1 mb-4">
                  <Zap className="h-3.5 w-3.5 text-amber-600" />
                  <span className="text-xs font-medium text-amber-700">Integrations</span>
                </div>
                <h3 className="text-3xl font-bold text-foreground mb-4">50+ integrations when configured</h3>
                <p className="text-muted-foreground mb-6 leading-relaxed text-lg">
                  One-click integrations with Salesforce, HubSpot, Slack, Google Workspace, and more. 
                  When integrations are connected, agents can read, write, and take actions across your linked tools. Each run reflects what was executed—not every action is guaranteed without a connected integration.
                </p>
                <ul className="space-y-3">
                  {['Pre-built connectors', 'OAuth authentication', 'Sync when connected', 'Custom API support'].map((item) => (
                    <li key={item} className="flex items-center gap-3 text-sm text-muted-foreground">
                      <div className="h-5 w-5 rounded-full bg-amber-100 flex items-center justify-center">
                        <Check className="h-3 w-3 text-amber-600" />
                      </div>
                      {item}
                    </li>
                  ))}
                </ul>
              </div>
              <ProductScreenshot
                src="/product/app-connectors.png"
                alt="Connectors page showing connected and available integrations with their sync status."
                chromeLabel="Connectors"
                glowClassName="bg-gradient-to-r from-amber-100/60 to-orange-100/60"
                className="lg:order-1"
              />
            </motion.div>
            ) : null}

            {/* Feature 5: Enterprise Security */}
            {showSection(section, "governance", "all") ? (
            <motion.div
              initial={{ opacity: 0, y: 30 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true }}
              className="grid lg:grid-cols-2 gap-12 items-center"
            >
              <div>
                <div className="inline-flex items-center gap-2 rounded-full bg-rose-50 border border-rose-200 px-3 py-1 mb-4">
                  <Shield className="h-3.5 w-3.5 text-rose-600" />
                  <span className="text-xs font-medium text-rose-700">Enterprise Security</span>
                </div>
                <h3 className="text-3xl font-bold text-foreground mb-4">Security you can trust</h3>
                <p className="text-muted-foreground mb-6 leading-relaxed text-lg">
                  Built with security-first principles including role-based access control, complete audit trails, 
                  encrypted data, and human-in-the-loop approvals for sensitive actions.
                </p>
                <ul className="space-y-3">
                  {['Role-based access control', 'Complete audit trails', 'End-to-end encryption', 'Human-in-the-loop approvals'].map((item) => (
                    <li key={item} className="flex items-center gap-3 text-sm text-muted-foreground">
                      <div className="h-5 w-5 rounded-full bg-rose-100 flex items-center justify-center">
                        <Check className="h-3 w-3 text-rose-600" />
                      </div>
                      {item}
                    </li>
                  ))}
                </ul>
              </div>
              {/* The approvals queue, rather than a list of security toggles: the
                  old mockup restated the four bullets on the left verbatim, so it
                  carried no information. This shows the human-in-the-loop gate
                  actually holding a pending write. */}
              <ProductScreenshot
                src="/product/app-approvals.png"
                alt="Approvals queue with a pending write request awaiting human review, showing the requesting agent, target system, and the diff to be applied."
                chromeLabel="Approvals"
                glowClassName="bg-gradient-to-r from-rose-100/60 to-red-100/60"
              />
            </motion.div>
            ) : null}

            {/* Feature 6: Meson - The AI System Builder */}
            {showSection(section, "meson", "all") ? (
            <motion.div
              initial={{ opacity: 0, y: 30 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true }}
              className="grid lg:grid-cols-2 gap-12 items-center"
            >
              <div className="lg:order-2">
                <div className="inline-flex items-center gap-2 rounded-full bg-violet-50 border border-violet-200 px-3 py-1 mb-4">
                  <Blocks className="h-3.5 w-3.5 text-violet-600" />
                  <span className="text-xs font-medium text-violet-700">Meson</span>
                </div>
                <h3 className="text-3xl font-bold text-foreground mb-4">{MARKETING_COPY.meson.title}</h3>
                <p className="text-muted-foreground mb-6 leading-relaxed text-lg">
                  {MARKETING_COPY.meson.description}
                </p>
                <ul className="space-y-3">
                  {MARKETING_COPY.meson.bullets.map((item) => (
                    <li key={item} className="flex items-center gap-3 text-sm text-muted-foreground">
                      <div className="h-5 w-5 rounded-full bg-violet-100 flex items-center justify-center">
                        <Check className="h-3 w-3 text-violet-600" />
                      </div>
                      {item}
                    </li>
                  ))}
                </ul>
                <div className="mt-6 p-4 rounded-xl bg-gradient-to-r from-violet-50 to-purple-50 border border-violet-200">
                  <p className="text-sm text-violet-800">
                    <span className="font-semibold">Why upgrade?</span> Meson is available in Control and Command plans. 
                    Build in seconds what would take hours manually.
                  </p>
                </div>
              </div>
              <div className="lg:order-1 relative">
                <div className="absolute -inset-4 bg-gradient-to-r from-violet-100/60 to-purple-100/60 rounded-3xl blur-2xl" />
                <div className="relative rounded-xl border border-border bg-card shadow-2xl overflow-hidden">
                  <div className="flex items-center gap-2 px-4 py-3 bg-muted/50 border-b border-border">
                    <div className="flex gap-1.5">
                      <div className="h-3 w-3 rounded-full bg-red-400" />
                      <div className="h-3 w-3 rounded-full bg-amber-400" />
                      <div className="h-3 w-3 rounded-full bg-emerald-400" />
                    </div>
                    <div className="flex-1 flex justify-center">
                      <div className="px-3 py-1 rounded-md bg-violet-100 text-[10px] text-violet-600 font-medium">Meson Builder</div>
                    </div>
                  </div>
                  <div className="p-5 bg-muted/50/50 min-h-[340px]">
                    {/* User prompt */}
                    <div className="mb-4 p-3 rounded-xl border border-border bg-card">
                      <p className="text-xs text-muted-foreground mb-1">Your request</p>
                      <p className="text-sm text-foreground">&quot;Create a marketing agent for SaaS onboarding campaigns that sends personalized welcome sequences&quot;</p>
                    </div>
                    
                    {/* Meson processing visualization */}
                    <div className="space-y-3">
                      <div className="flex items-center gap-2 mb-3">
                        <motion.div 
                          className="h-2 w-2 rounded-full bg-violet-500"
                          animate={{ scale: [1, 1.2, 1] }}
                          transition={{ duration: 1.5, repeat: Infinity }}
                        />
                        <span className="text-xs font-medium text-violet-600">Meson generating...</span>
                      </div>
                      
                      {[
                        { icon: Bot, label: "Marketing Agent", desc: "Configured with brand voice", status: "created", color: "emerald" },
                        { icon: Layers, label: "Training Data", desc: "ICP docs, campaign history", status: "generated", color: "blue" },
                        { icon: Workflow, label: "Welcome Workflow", desc: "5-email nurture sequence", status: "built", color: "purple" },
                        { icon: Play, label: "Ready to Deploy", desc: "One click to activate", status: "ready", color: "violet" },
                      ].map((item, i) => (
                        <motion.div
                          key={item.label}
                          initial={{ opacity: 0, x: -20 }}
                          whileInView={{ opacity: 1, x: 0 }}
                          viewport={{ once: true }}
                          transition={{ delay: i * 0.15 }}
                          className="flex items-center justify-between p-3 rounded-xl border border-border bg-card shadow-sm"
                        >
                          <div className="flex items-center gap-3">
                            <div className={`h-9 w-9 rounded-lg flex items-center justify-center ${
                              item.color === 'emerald' ? 'bg-primary/10' :
                              item.color === 'blue' ? 'bg-blue-50' :
                              item.color === 'purple' ? 'bg-purple-50' : 'bg-violet-50'
                            }`}>
                              <item.icon className={`h-4 w-4 ${
                                item.color === 'emerald' ? 'text-primary' :
                                item.color === 'blue' ? 'text-blue-500' :
                                item.color === 'purple' ? 'text-purple-500' : 'text-violet-500'
                              }`} />
                            </div>
                            <div>
                              <p className="text-sm font-medium text-foreground">{item.label}</p>
                              <p className="text-[10px] text-muted-foreground">{item.desc}</p>
                            </div>
                          </div>
                          <div className="flex items-center gap-2">
                            <div className={`h-2 w-2 rounded-full ${
                              item.color === 'emerald' ? 'bg-primary/100' :
                              item.color === 'blue' ? 'bg-blue-500' :
                              item.color === 'purple' ? 'bg-purple-500' : 'bg-violet-500'
                            }`} />
                            <span className={`text-[10px] capitalize ${
                              item.color === 'emerald' ? 'text-primary' :
                              item.color === 'blue' ? 'text-blue-600' :
                              item.color === 'purple' ? 'text-purple-600' : 'text-violet-600'
                            }`}>{item.status}</span>
                          </div>
                        </motion.div>
                      ))}
                    </div>
                  </div>
                </div>
              </div>
            </motion.div>
            ) : null}
          </div>
        </div>
      </section>
      </>
      ) : null}

      {showSection(section, "integrations", "all") ? (
      <>
      {/* Detailed Features */}
      <section className="relative py-32 border-t border-border bg-muted/50">
        <div className="mx-auto max-w-7xl px-6">
          <motion.div
            initial={{ opacity: 0, y: 30 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            className="mx-auto max-w-2xl text-center mb-20"
          >
            <h2 className="text-4xl font-bold tracking-tight text-foreground">
              Capabilities that scale
            </h2>
            <p className="mt-4 text-lg text-muted-foreground">
              Every feature designed for enterprise requirements.
            </p>
          </motion.div>

          <div className="grid gap-8 sm:grid-cols-2 lg:grid-cols-4">
            {[
              { icon: MessageSquare, title: "Natural Language", description: "Control everything with simple commands" },
              { icon: Eye, title: "Routing traces", description: "See how Gravitre picked an answer — stages, not hidden reasoning" },
              { icon: Bell, title: "Failure predictions", description: "Alerts before workflows fail on auth, scopes, or rate limits" },
              { icon: Clock, title: "Predictive ops", description: "SLA, capacity, and deal-risk models with honest readiness gates" },
              { icon: Database, title: "50+ integrations", description: "Live Configured → Executable checks on every connector" },
              { icon: GitBranch, title: "Version Control", description: "Track and rollback changes" },
              { icon: Lock, title: "SSO & SAML", description: "Enterprise authentication" },
              { icon: BarChart3, title: "Analytics", description: "Deep insights into performance" },
            ].map((feature, i) => (
              <motion.div
                key={feature.title}
                initial={{ opacity: 0, y: 20 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true }}
                transition={{ delay: i * 0.05 }}
                className="text-center"
              >
                <div className="mx-auto mb-4 h-12 w-12 rounded-xl bg-card border border-border shadow-sm flex items-center justify-center">
                  <feature.icon className="h-5 w-5 text-muted-foreground" />
                </div>
                <h3 className="text-sm font-semibold text-foreground">{feature.title}</h3>
                <p className="mt-1 text-xs text-muted-foreground">{feature.description}</p>
              </motion.div>
            ))}
          </div>
        </div>
      </section>

      {/* Integrations - Now with real logos */}
      <section className="relative py-32 border-t border-border">
        <div className="mx-auto max-w-7xl px-6">
          <motion.div
            initial={{ opacity: 0, y: 30 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            className="mx-auto max-w-2xl text-center mb-16"
          >
            <h2 className="text-4xl font-bold tracking-tight text-foreground">
              Connects to your entire stack
            </h2>
            <p className="mt-4 text-muted-foreground">
              50+ pre-built integrations when configured — with live health and executability checks.
            </p>
          </motion.div>

          <IntegrationsGrid theme="light" />
        </div>
      </section>
      </>
      ) : null}

      {showSection(section, "insights", "all") ? <TransparencyMetricsSection /> : null}

      {showSection(section, "marketplace", "all") ? <MarketplaceHighlightsSection /> : null}

      {showSection(section, "insights", "all") ? <UseCasesSection /> : null}

      {showSection(section, "governance", "all") ? <GovernanceAiStackSection /> : null}

      {section === "all" && SHOW_MARKETING_TESTIMONIALS ? (
      <section className="relative py-32 border-t border-border bg-muted/50">
        <div className="mx-auto max-w-7xl px-6">
          <motion.div
            initial={{ opacity: 0, y: 30 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            className="mx-auto max-w-2xl text-center mb-16"
          >
            <span className="text-sm font-semibold text-primary tracking-wide uppercase">Testimonials</span>
            <h2 className="mt-4 text-4xl font-bold tracking-tight text-foreground">
              What our customers say
            </h2>
            <p className="mt-4 text-muted-foreground">
              Join teams running AI operations with verified learning, not guesswork
            </p>
          </motion.div>

          <div className="max-w-4xl mx-auto">
            <TestimonialsCarouselFull />
          </div>
        </div>
      </section>
      ) : null}

      {showTail && section !== "overview" ? (
      <>
      {/* Social Proof Stats */}
      <SocialProofBanner />

      {/* CTA */}
      <section className="relative py-32 bg-card">
        <div className="absolute inset-0 bg-gradient-to-t from-primary/10 via-transparent to-transparent" />
        <div className="relative mx-auto max-w-7xl px-6">
          <motion.div
            initial={{ opacity: 0, scale: 0.95 }}
            whileInView={{ opacity: 1, scale: 1 }}
            viewport={{ once: true }}
            className="mx-auto max-w-2xl text-center"
          >
            <h2 className="text-4xl font-bold tracking-tight text-foreground">
              Ready to get started?
            </h2>
            <p className="mt-4 text-muted-foreground">
              Start your free trial today.
            </p>
            <div className="mt-10 flex items-center justify-center gap-4 flex-wrap">
              <Link
                href="/get-started"
                className="group inline-flex items-center gap-2 rounded-full bg-foreground px-8 py-4 text-base font-semibold text-white transition-all hover:bg-foreground/90"
              >
                Start free trial
                <ArrowRight className="h-5 w-5 transition-transform group-hover:translate-x-1" />
              </Link>
              <Link
                href="/contact"
                className="inline-flex items-center gap-2 rounded-full border border-border bg-card px-8 py-4 text-base font-semibold text-foreground transition-all hover:bg-muted/50"
              >
                Talk to sales
              </Link>
            </div>
          </motion.div>
        </div>
      </section>
      </>
      ) : null}
    </div>
  )
}
