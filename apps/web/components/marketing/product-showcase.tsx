"use client"

import { useState, useEffect } from "react"
import { motion, AnimatePresence } from "framer-motion"
import { SHOW_MARKETING_TESTIMONIALS } from "@/lib/marketing-flags"
import { MARKETING_COPY } from "@/lib/marketing-copy"
import { MarketingTracingBeam } from "@/components/marketing/home/marketing-tracing-beam"
import { 
  Bot, 
  Users, 
  Workflow, 
  BarChart3, 
  FileText, 
  Zap, 
  GitBranch,
  Bell,
  Eye,
  Sparkles,
  ChevronRight,
  Play,
  Check,
  Clock,
  ArrowRight
} from "lucide-react"

// Tab-based product showcase like Chatbase's "Discover the platform"
const showcaseTabs = [
  { id: "operator", label: "Gravitre AI", icon: Bot },
  { id: "agents", label: "Agents", icon: Users },
  { id: "workflows", label: "Workflows", icon: Workflow },
  { id: "analytics", label: "Insights", icon: BarChart3 },
]

// Animated Operator Screen
function OperatorScreen() {
  const [messageIndex, setMessageIndex] = useState(0)
  const messages = [
    { type: "user", text: "Why did the HubSpot contact sync fail?" },
    {
      type: "ai",
      text: "HubSpot is connected, but contact search permission is missing. Estimated confidence: Medium. Complete OAuth scopes, then re-run the workflow.",
      agent: "Connector check",
    },
    { type: "user", text: "Show stalled deals over 30 days" },
    {
      type: "ai",
      text: "Here’s what your CRM signals show in-product: stalled deals, approval bottlenecks, and an advisory next step — with sources you can audit. Counts come from your workspace, not this marketing mock.",
      agent: "Insights",
    },
  ]

  useEffect(() => {
    const timer = setInterval(() => {
      setMessageIndex((prev) => (prev + 1) % (messages.length + 1))
    }, 2500)
    return () => clearInterval(timer)
  }, [messages.length])

  const visibleMessages = messages.slice(0, messageIndex)

  return (
    <div className="bg-foreground rounded-xl overflow-hidden shadow-2xl border border-border">
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-border bg-foreground/80">
        <div className="flex items-center gap-3">
          <div className="flex gap-1.5">
            <div className="h-3 w-3 rounded-full bg-red-500" />
            <div className="h-3 w-3 rounded-full bg-yellow-500" />
            <div className="h-3 w-3 rounded-full bg-green-500" />
          </div>
          <span className="text-sm font-medium text-muted-foreground">Gravitre AI</span>
        </div>
        <div className="flex items-center gap-2">
          <motion.div
            className="h-2 w-2 rounded-full bg-primary/100"
            animate={{ scale: [1, 1.3, 1] }}
            transition={{ duration: 1.5, repeat: Infinity }}
          />
          <span className="text-xs text-emerald-400">Online</span>
        </div>
      </div>

      {/* Chat Area */}
      <div className="p-4 min-h-[320px] space-y-4 bg-gradient-to-b from-card to-background">
        <AnimatePresence mode="popLayout">
          {visibleMessages.map((msg, i) => (
            <motion.div
              key={i}
              initial={{ opacity: 0, y: 20, scale: 0.95 }}
              animate={{ opacity: 1, y: 0, scale: 1 }}
              exit={{ opacity: 0, y: -10 }}
              transition={{ type: "spring", stiffness: 300, damping: 25 }}
              className={`flex gap-3 ${msg.type === 'ai' ? 'justify-end' : ''}`}
            >
              {msg.type === 'user' && (
                <div className="h-8 w-8 rounded-full bg-muted flex items-center justify-center text-xs font-medium text-muted-foreground shrink-0">
                  JD
                </div>
              )}
              <div className={`max-w-[80%] rounded-2xl px-4 py-3 ${
                msg.type === 'user' 
                  ? 'bg-foreground/90 text-foreground rounded-tl-sm' 
                  : 'bg-gradient-to-br from-emerald-600 to-emerald-700 text-white rounded-tr-sm'
              }`}>
                {msg.type === 'ai' && (
                  <div className="flex items-center gap-2 mb-1.5 text-emerald-200/80">
                    <Sparkles className="h-3 w-3" />
                    <span className="text-[10px] font-medium">via {msg.agent}</span>
                  </div>
                )}
                <p className="text-sm">{msg.text}</p>
              </div>
              {msg.type === 'ai' && (
                <div className="h-8 w-8 rounded-full bg-gradient-to-br from-primary/100 to-emerald-600 flex items-center justify-center shrink-0 shadow-lg shadow-emerald-500/20">
                  <Sparkles className="h-4 w-4 text-white" />
                </div>
              )}
            </motion.div>
          ))}
        </AnimatePresence>

        {/* Typing indicator */}
        {messageIndex < messages.length && messageIndex > 0 && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            className="flex items-center gap-2 ml-11"
          >
            <div className="flex gap-1">
              {[0, 1, 2].map((i) => (
                <motion.div
                  key={i}
                  className="h-1.5 w-1.5 rounded-full bg-primary/100"
                  animate={{ y: [0, -4, 0] }}
                  transition={{ duration: 0.6, repeat: Infinity, delay: i * 0.15 }}
                />
              ))}
            </div>
            <span className="text-xs text-muted-foreground">AI is thinking...</span>
          </motion.div>
        )}

        {/* Input */}
        <div className="mt-4 flex items-center gap-3 rounded-xl border border-border bg-foreground/90/50 px-4 py-3">
          <input
            type="text"
            placeholder="Ask anything..."
            className="flex-1 bg-transparent text-sm text-muted-foreground placeholder:text-muted-foreground outline-none"
            readOnly
          />
          <div className="h-8 w-8 rounded-lg bg-primary flex items-center justify-center">
            <ArrowRight className="h-4 w-4 text-white" />
          </div>
        </div>
      </div>
    </div>
  )
}

// Animated Agents Screen
function AgentsScreen() {
  // Status / role labels only — no fabricated accuracy percentages (Module C).
  const agents = [
    { name: "Data Analyst", status: "active", role: "Advisory", color: "emerald", icon: BarChart3 },
    { name: "Content Writer", status: "active", role: "Drafts", color: "blue", icon: FileText },
    { name: "Research Agent", status: "idle", role: "Lookup", color: "purple", icon: Eye },
    { name: "Code Reviewer", status: "active", role: "Review", color: "amber", icon: GitBranch },
  ]

  return (
    <div className="bg-foreground rounded-xl overflow-hidden shadow-2xl border border-border">
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-border">
        <div className="flex items-center gap-3">
          <div className="flex gap-1.5">
            <div className="h-3 w-3 rounded-full bg-red-500" />
            <div className="h-3 w-3 rounded-full bg-yellow-500" />
            <div className="h-3 w-3 rounded-full bg-green-500" />
          </div>
          <span className="text-sm font-medium text-muted-foreground">Agents</span>
        </div>
        <div className="px-2.5 py-1 rounded-md bg-primary/100/10 border border-primary/20 text-emerald-400 text-xs font-medium">
          + New Agent
        </div>
      </div>

      {/* Agent Grid */}
      <div className="p-4 grid grid-cols-2 gap-3">
        {agents.map((agent, i) => (
          <motion.div
            key={agent.name}
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: i * 0.1 }}
            whileHover={{ scale: 1.02, y: -2 }}
            className="relative p-4 rounded-xl border border-border bg-foreground/90/50 cursor-pointer hover:border-border transition-all group"
          >
            {/* Status indicator */}
            {agent.status === "active" && (
              <motion.div
                className="absolute top-3 right-3 h-2 w-2 rounded-full bg-primary/100"
                animate={{ scale: [1, 1.3, 1], opacity: [1, 0.6, 1] }}
                transition={{ duration: 1.5, repeat: Infinity }}
              />
            )}
            
            <div className={`h-12 w-12 rounded-xl flex items-center justify-center mb-3 ${
              agent.color === 'emerald' ? 'bg-primary/100/10' :
              agent.color === 'blue' ? 'bg-blue-500/10' :
              agent.color === 'purple' ? 'bg-purple-500/10' : 'bg-amber-500/10'
            }`}>
              <agent.icon className={`h-6 w-6 ${
                agent.color === 'emerald' ? 'text-emerald-400' :
                agent.color === 'blue' ? 'text-blue-400' :
                agent.color === 'purple' ? 'text-purple-400' : 'text-amber-400'
              }`} />
            </div>
            
            <h4 className="text-sm font-medium text-foreground">{agent.name}</h4>
            <div className="flex items-center gap-2 mt-1">
              <span className={`text-xs ${agent.status === 'active' ? 'text-emerald-400' : 'text-muted-foreground'}`}>
                {agent.status}
              </span>
              <span className="text-muted-foreground">·</span>
              <span className="text-xs text-muted-foreground">{agent.role}</span>
            </div>
            <span className="text-[10px] text-muted-foreground mt-3 block">
              Outcomes measured in your org — not a marketing accuracy score
            </span>
          </motion.div>
        ))}
      </div>
    </div>
  )
}

// Animated Workflows Screen
function WorkflowsScreen() {
  // Illustrative workflow names/status only — no fabricated run counts or success % (Module C).
  const workflows = [
    { name: "Customer Onboarding", status: "active", detail: "Approval-gated" },
    { name: "Lead Qualification", status: "active", detail: "Connector-checked" },
    { name: "Report Generation", status: "paused", detail: "Awaiting review" },
  ]

  return (
    <div className="bg-foreground rounded-xl overflow-hidden shadow-2xl border border-border">
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-border">
        <div className="flex items-center gap-3">
          <div className="flex gap-1.5">
            <div className="h-3 w-3 rounded-full bg-red-500" />
            <div className="h-3 w-3 rounded-full bg-yellow-500" />
            <div className="h-3 w-3 rounded-full bg-green-500" />
          </div>
          <span className="text-sm font-medium text-muted-foreground">Workflows</span>
        </div>
      </div>

      {/* Workflow Builder Preview */}
      <div className="p-6 bg-foreground/50">
        <div className="flex items-center justify-center gap-4 mb-6">
          {/* Workflow nodes */}
          {[
            { icon: Zap, label: "Trigger", color: "emerald" },
            { icon: Bot, label: "AI Agent", color: "blue" },
            { icon: GitBranch, label: "Condition", color: "purple" },
            { icon: Bell, label: "Notify", color: "amber" },
          ].map((node, i) => (
            <motion.div
              key={node.label}
              initial={{ opacity: 0, scale: 0.8 }}
              animate={{ opacity: 1, scale: 1 }}
              transition={{ delay: i * 0.15 }}
              className="flex items-center"
            >
              <div className={`relative h-14 w-14 rounded-xl flex items-center justify-center border ${
                node.color === 'emerald' ? 'border-primary/30 bg-primary/100/10' :
                node.color === 'blue' ? 'border-blue-500/30 bg-blue-500/10' :
                node.color === 'purple' ? 'border-purple-500/30 bg-purple-500/10' : 'border-amber-500/30 bg-amber-500/10'
              }`}>
                <node.icon className={`h-6 w-6 ${
                  node.color === 'emerald' ? 'text-emerald-400' :
                  node.color === 'blue' ? 'text-blue-400' :
                  node.color === 'purple' ? 'text-purple-400' : 'text-amber-400'
                }`} />
              </div>
              {i < 3 && (
                <motion.div
                  initial={{ width: 0 }}
                  animate={{ width: 32 }}
                  transition={{ delay: i * 0.15 + 0.2 }}
                  className="h-0.5 bg-gradient-to-r from-muted-foreground to-muted-foreground"
                />
              )}
            </motion.div>
          ))}
        </div>

        {/* Workflow list */}
        <div className="space-y-2">
          {workflows.map((wf, i) => (
            <motion.div
              key={wf.name}
              initial={{ opacity: 0, x: -20 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ delay: 0.5 + i * 0.1 }}
              className="flex items-center justify-between p-3 rounded-lg border border-border bg-foreground/90/30 hover:border-border transition-colors"
            >
              <div className="flex items-center gap-3">
                <div className={`h-2 w-2 rounded-full ${wf.status === 'active' ? 'bg-primary/100' : 'bg-muted-foreground'}`} />
                <span className="text-sm text-muted-foreground">{wf.name}</span>
              </div>
              <div className="flex items-center gap-4 text-xs">
                <span className="text-muted-foreground">{wf.detail}</span>
              </div>
            </motion.div>
          ))}
        </div>
      </div>
    </div>
  )
}

// Animated Analytics Screen
function AnalyticsScreen() {
  // Directional / provenance labels only — no fabricated KPIs (Module C / STA-286).
  const stats = [
    {
      label: "Tasks completed",
      value: "Operational",
      change: "Counted from your runs",
      color: "emerald",
    },
    {
      label: "Success rate",
      value: "Live ops",
      change: "From recorded executions",
      color: "blue",
    },
    {
      label: "Hours saved",
      value: "Estimate",
      change: "Catalog estimate until measured",
      color: "purple",
    },
  ]

  return (
    <div className="bg-foreground rounded-xl overflow-hidden shadow-2xl border border-border">
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-border">
        <div className="flex items-center gap-3">
          <div className="flex gap-1.5">
            <div className="h-3 w-3 rounded-full bg-red-500" />
            <div className="h-3 w-3 rounded-full bg-yellow-500" />
            <div className="h-3 w-3 rounded-full bg-green-500" />
          </div>
          <span className="text-sm font-medium text-muted-foreground">Analytics</span>
        </div>
        <div className="flex items-center gap-2 text-xs text-muted-foreground">
          <Clock className="h-3 w-3" />
          Your workspace
        </div>
      </div>

      {/* Stats Grid */}
      <div className="p-4 grid grid-cols-3 gap-3">
        {stats.map((stat, i) => (
          <motion.div
            key={stat.label}
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: i * 0.1 }}
            className="p-4 rounded-xl border border-border bg-foreground/90/30"
          >
            <div className="text-xs text-muted-foreground mb-1">{stat.label}</div>
            <div className="text-lg font-bold text-foreground leading-tight">{stat.value}</div>
            <div className={`text-xs mt-1 ${
              stat.color === 'emerald' ? 'text-emerald-400' :
              stat.color === 'blue' ? 'text-blue-400' : 'text-purple-400'
            }`}>
              {stat.change}
            </div>
          </motion.div>
        ))}
      </div>

      {/* Chart placeholder */}
      <div className="px-4 pb-4">
        <div className="h-32 rounded-xl border border-border bg-foreground/90/20 flex items-end justify-around p-4 gap-2">
          {[65, 45, 80, 55, 90, 70, 85].map((height, i) => (
            <motion.div
              key={i}
              initial={{ height: 0 }}
              animate={{ height: `${height}%` }}
              transition={{ delay: 0.5 + i * 0.1, duration: 0.5, ease: "easeOut" }}
              className="flex-1 bg-gradient-to-t from-emerald-600 to-primary/100 rounded-t-sm"
            />
          ))}
        </div>
      </div>
    </div>
  )
}

// Main Product Showcase Component
export function ProductShowcase() {
  const [activeTab, setActiveTab] = useState("operator")

  const screens: Record<string, React.ReactNode> = {
    operator: <OperatorScreen />,
    agents: <AgentsScreen />,
    workflows: <WorkflowsScreen />,
    analytics: <AnalyticsScreen />,
  }

  return (
    <div className="w-full">
      {/* Tabs */}
      <div className="flex items-center justify-center mb-8">
        <div className="inline-flex items-center gap-1 p-1 rounded-full bg-muted border border-border">
          {showcaseTabs.map((tab) => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={`relative flex items-center gap-2 px-4 py-2 rounded-full text-sm font-medium transition-all ${
                activeTab === tab.id
                  ? "text-foreground"
                  : "text-muted-foreground hover:text-foreground"
              }`}
            >
              {activeTab === tab.id && (
                <motion.div
                  layoutId="activeTab"
                  className="absolute inset-0 bg-card rounded-full shadow-sm"
                  transition={{ type: "spring", stiffness: 300, damping: 30 }}
                />
              )}
              <tab.icon className="relative h-4 w-4" />
              <span className="relative hidden sm:inline">{tab.label}</span>
            </button>
          ))}
        </div>
      </div>

      {/* Screen Display */}
      <div className="relative max-w-4xl mx-auto">
        {/* Glow effect */}
        <div className="absolute -inset-4 bg-gradient-to-r from-primary/100/10 via-blue-500/10 to-purple-500/10 rounded-3xl blur-2xl" />
        
        <AnimatePresence mode="wait">
          <motion.div
            key={activeTab}
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -20 }}
            transition={{ duration: 0.3 }}
            className="relative"
          >
            {screens[activeTab]}
          </motion.div>
        </AnimatePresence>
      </div>
    </div>
  )
}

// How It Works Step Component
interface HowItWorksStep {
  number: string
  title: string
  description: string
  visual: React.ReactNode
}

export function HowItWorks({ steps }: { steps: HowItWorksStep[] }) {
  const [activeStep, setActiveStep] = useState(0)

  useEffect(() => {
    const timer = setInterval(() => {
      setActiveStep((prev) => (prev + 1) % steps.length)
    }, 5000)
    return () => clearInterval(timer)
  }, [steps.length])

  return (
    <div className="grid items-center gap-12 lg:grid-cols-2">
      {/* Steps List */}
      <div className="relative space-y-4">
        <MarketingTracingBeam activeIndex={activeStep} total={steps.length} className="-left-3 sm:-left-4" />
        {steps.map((step, i) => (
          <motion.button
            key={i}
            onClick={() => setActiveStep(i)}
            className={`w-full rounded-2xl border p-6 text-left transition-all ${
              activeStep === i
                ? "border-primary/30 bg-primary/10"
                : "border-border bg-card hover:border-border"
            }`}
            whileHover={{ x: 4 }}
            transition={{ duration: 0.15 }}
          >
            <div className="flex items-start gap-4">
              <div className={`flex h-10 w-10 shrink-0 items-center justify-center rounded-full text-sm font-bold ${
                activeStep === i
                  ? "bg-primary text-white"
                  : "bg-muted text-muted-foreground"
              }`}>
                {step.number}
              </div>
              <div>
                <h4 className={`mb-1 text-lg font-semibold ${
                  activeStep === i ? "text-primary" : "text-foreground"
                }`}>
                  {step.title}
                </h4>
                <p className={`text-sm ${
                  activeStep === i ? "text-primary" : "text-muted-foreground"
                }`}>
                  {step.description}
                </p>
              </div>
            </div>
            
            {/* Progress bar */}
            {activeStep === i && (
              <div className="ml-14 mt-4 h-1 overflow-hidden rounded-full bg-muted">
                <motion.div
                  className="h-full bg-primary"
                  initial={{ width: 0 }}
                  animate={{ width: "100%" }}
                  transition={{ duration: 5, ease: "linear" }}
                />
              </div>
            )}
          </motion.button>
        ))}
      </div>

      {/* Visual */}
      <div className="relative">
        <AnimatePresence mode="wait">
          <motion.div
            key={activeStep}
            initial={{ opacity: 0, scale: 0.95 }}
            animate={{ opacity: 1, scale: 1 }}
            exit={{ opacity: 0, scale: 0.95 }}
            transition={{ duration: 0.3 }}
          >
            {steps[activeStep].visual}
          </motion.div>
        </AnimatePresence>
      </div>
    </div>
  )
}

// Testimonials Carousel
interface Testimonial {
  quote: string
  author: string
  role: string
  company: string
  avatar?: string
}

export function TestimonialsCarousel({ testimonials }: { testimonials: Testimonial[] }) {
  if (!SHOW_MARKETING_TESTIMONIALS) return null
  return <TestimonialsCarouselActive testimonials={testimonials} />
}

function TestimonialsCarouselActive({ testimonials }: { testimonials: Testimonial[] }) {
  const [activeIndex, setActiveIndex] = useState(0)

  useEffect(() => {
    if (testimonials.length === 0) return
    const timer = setInterval(() => {
      setActiveIndex((prev) => (prev + 1) % testimonials.length)
    }, 6000)
    return () => clearInterval(timer)
  }, [testimonials.length])

  return (
    <div className="relative">
      <AnimatePresence mode="wait">
        <motion.div
          key={activeIndex}
          initial={{ opacity: 0, x: 50 }}
          animate={{ opacity: 1, x: 0 }}
          exit={{ opacity: 0, x: -50 }}
          transition={{ duration: 0.4 }}
          className="bg-card rounded-2xl border border-border p-8 shadow-lg"
        >
          <blockquote className="text-xl text-foreground leading-relaxed mb-6">
            &ldquo;{testimonials[activeIndex].quote}&rdquo;
          </blockquote>
          <div className="flex items-center gap-4">
            <div className="h-12 w-12 rounded-full bg-gradient-to-br from-primary/100 to-teal-500 flex items-center justify-center text-white font-semibold">
              {testimonials[activeIndex].author.charAt(0)}
            </div>
            <div>
              <div className="font-semibold text-foreground">{testimonials[activeIndex].author}</div>
              <div className="text-sm text-muted-foreground">
                {testimonials[activeIndex].role}, {testimonials[activeIndex].company}
              </div>
            </div>
          </div>
        </motion.div>
      </AnimatePresence>

      {/* Indicators */}
      <div className="flex items-center justify-center gap-2 mt-6">
        {testimonials.map((_, i) => (
          <button
            key={i}
            onClick={() => setActiveIndex(i)}
            className={`h-2 rounded-full transition-all ${
              i === activeIndex ? "w-8 bg-primary" : "w-2 bg-muted hover:bg-muted-foreground/40"
            }`}
          />
        ))}
      </div>
    </div>
  )
}

// Stats Counter Component — product-truth metrics only
export function AnimatedStats() {
  const [inView, setInView] = useState(false)
  const stats = MARKETING_COPY.stats.map((stat) => ({
    value: stat.value,
    suffix: "suffix" in stat ? stat.suffix : "",
    label: stat.label,
  }))

  return (
    <motion.div
      onViewportEnter={() => setInView(true)}
      className="grid grid-cols-2 md:grid-cols-4 gap-8"
    >
      {stats.map((stat, i) => (
        <motion.div
          key={stat.label}
          initial={{ opacity: 0, y: 20 }}
          animate={inView ? { opacity: 1, y: 0 } : {}}
          transition={{ delay: i * 0.1 }}
          className="text-center"
        >
          <motion.div
            className="text-4xl md:text-5xl font-bold text-foreground"
            initial={{ opacity: 0 }}
            animate={inView ? { opacity: 1 } : {}}
            transition={{ delay: i * 0.1 + 0.2 }}
          >
            {inView && (
              <motion.span
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
              >
                {stat.value}
                {stat.suffix}
              </motion.span>
            )}
          </motion.div>
          <div className="mt-2 text-sm text-muted-foreground">{stat.label}</div>
        </motion.div>
      ))}
    </motion.div>
  )
}
