"use client"

import { useState, useEffect } from "react"
import { motion, AnimatePresence } from "framer-motion"
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
  { id: "operator", label: "AI Operator", icon: Bot },
  { id: "agents", label: "Agents", icon: Users },
  { id: "workflows", label: "Workflows", icon: Workflow },
  { id: "analytics", label: "Analytics", icon: BarChart3 },
]

// Animated Operator Screen
function OperatorScreen() {
  const [messageIndex, setMessageIndex] = useState(0)
  const messages = [
    { type: "user", text: "Show me failed workflows from the past week" },
    { type: "ai", text: "Found 3 failed workflows. The main issue is API rate limiting on the Salesforce connector. I recommend enabling retry with exponential backoff.", agent: "System Monitor" },
    { type: "user", text: "Apply that fix automatically" },
    { type: "ai", text: "Done! I've updated the Salesforce connector configuration and re-queued the 3 failed workflows. They should complete within the next 5 minutes.", agent: "Workflow Manager" },
  ]

  useEffect(() => {
    const timer = setInterval(() => {
      setMessageIndex((prev) => (prev + 1) % (messages.length + 1))
    }, 2500)
    return () => clearInterval(timer)
  }, [messages.length])

  const visibleMessages = messages.slice(0, messageIndex)

  return (
    <div className="bg-zinc-900 rounded-xl overflow-hidden shadow-2xl border border-zinc-800">
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-zinc-800 bg-zinc-900/80">
        <div className="flex items-center gap-3">
          <div className="flex gap-1.5">
            <div className="h-3 w-3 rounded-full bg-red-500" />
            <div className="h-3 w-3 rounded-full bg-yellow-500" />
            <div className="h-3 w-3 rounded-full bg-green-500" />
          </div>
          <span className="text-sm font-medium text-zinc-400">AI Operator</span>
        </div>
        <div className="flex items-center gap-2">
          <motion.div
            className="h-2 w-2 rounded-full bg-emerald-500"
            animate={{ scale: [1, 1.3, 1] }}
            transition={{ duration: 1.5, repeat: Infinity }}
          />
          <span className="text-xs text-emerald-400">Online</span>
        </div>
      </div>

      {/* Chat Area */}
      <div className="p-4 min-h-[320px] space-y-4 bg-gradient-to-b from-zinc-900 to-zinc-950">
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
                <div className="h-8 w-8 rounded-full bg-zinc-700 flex items-center justify-center text-xs font-medium text-zinc-300 shrink-0">
                  JD
                </div>
              )}
              <div className={`max-w-[80%] rounded-2xl px-4 py-3 ${
                msg.type === 'user' 
                  ? 'bg-zinc-800 text-zinc-200 rounded-tl-sm' 
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
                <div className="h-8 w-8 rounded-full bg-gradient-to-br from-emerald-500 to-emerald-600 flex items-center justify-center shrink-0 shadow-lg shadow-emerald-500/20">
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
                  className="h-1.5 w-1.5 rounded-full bg-emerald-500"
                  animate={{ y: [0, -4, 0] }}
                  transition={{ duration: 0.6, repeat: Infinity, delay: i * 0.15 }}
                />
              ))}
            </div>
            <span className="text-xs text-zinc-500">AI is thinking...</span>
          </motion.div>
        )}

        {/* Input */}
        <div className="mt-4 flex items-center gap-3 rounded-xl border border-zinc-700 bg-zinc-800/50 px-4 py-3">
          <input
            type="text"
            placeholder="Ask anything..."
            className="flex-1 bg-transparent text-sm text-zinc-300 placeholder-zinc-500 outline-none"
            readOnly
          />
          <div className="h-8 w-8 rounded-lg bg-emerald-600 flex items-center justify-center">
            <ArrowRight className="h-4 w-4 text-white" />
          </div>
        </div>
      </div>
    </div>
  )
}

// Animated Agents Screen
function AgentsScreen() {
  const agents = [
    { name: "Data Analyst", status: "active", tasks: 12, accuracy: 98, color: "emerald", icon: BarChart3 },
    { name: "Content Writer", status: "active", tasks: 8, accuracy: 95, color: "blue", icon: FileText },
    { name: "Research Agent", status: "idle", tasks: 0, accuracy: 97, color: "purple", icon: Eye },
    { name: "Code Reviewer", status: "active", tasks: 5, accuracy: 99, color: "amber", icon: GitBranch },
  ]

  return (
    <div className="bg-zinc-900 rounded-xl overflow-hidden shadow-2xl border border-zinc-800">
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-zinc-800">
        <div className="flex items-center gap-3">
          <div className="flex gap-1.5">
            <div className="h-3 w-3 rounded-full bg-red-500" />
            <div className="h-3 w-3 rounded-full bg-yellow-500" />
            <div className="h-3 w-3 rounded-full bg-green-500" />
          </div>
          <span className="text-sm font-medium text-zinc-400">Agents</span>
        </div>
        <div className="px-2.5 py-1 rounded-md bg-emerald-500/10 border border-emerald-500/20 text-emerald-400 text-xs font-medium">
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
            className="relative p-4 rounded-xl border border-zinc-800 bg-zinc-800/50 cursor-pointer hover:border-zinc-700 transition-all group"
          >
            {/* Status indicator */}
            {agent.status === "active" && (
              <motion.div
                className="absolute top-3 right-3 h-2 w-2 rounded-full bg-emerald-500"
                animate={{ scale: [1, 1.3, 1], opacity: [1, 0.6, 1] }}
                transition={{ duration: 1.5, repeat: Infinity }}
              />
            )}
            
            <div className={`h-12 w-12 rounded-xl flex items-center justify-center mb-3 ${
              agent.color === 'emerald' ? 'bg-emerald-500/10' :
              agent.color === 'blue' ? 'bg-blue-500/10' :
              agent.color === 'purple' ? 'bg-purple-500/10' : 'bg-amber-500/10'
            }`}>
              <agent.icon className={`h-6 w-6 ${
                agent.color === 'emerald' ? 'text-emerald-400' :
                agent.color === 'blue' ? 'text-blue-400' :
                agent.color === 'purple' ? 'text-purple-400' : 'text-amber-400'
              }`} />
            </div>
            
            <h4 className="text-sm font-medium text-zinc-200">{agent.name}</h4>
            <div className="flex items-center gap-2 mt-1">
              <span className={`text-xs ${agent.status === 'active' ? 'text-emerald-400' : 'text-zinc-500'}`}>
                {agent.status}
              </span>
              <span className="text-zinc-600">·</span>
              <span className="text-xs text-zinc-500">{agent.tasks} tasks</span>
            </div>
            
            {/* Performance bar */}
            <div className="mt-3 h-1 rounded-full bg-zinc-700 overflow-hidden">
              <motion.div
                className={`h-full rounded-full ${
                  agent.color === 'emerald' ? 'bg-emerald-500' :
                  agent.color === 'blue' ? 'bg-blue-500' :
                  agent.color === 'purple' ? 'bg-purple-500' : 'bg-amber-500'
                }`}
                initial={{ width: 0 }}
                animate={{ width: `${agent.accuracy}%` }}
                transition={{ delay: i * 0.1 + 0.3, duration: 0.8 }}
              />
            </div>
            <span className="text-[10px] text-zinc-500 mt-1 block">{agent.accuracy}% accuracy</span>
          </motion.div>
        ))}
      </div>
    </div>
  )
}

// Animated Workflows Screen
function WorkflowsScreen() {
  const workflows = [
    { name: "Customer Onboarding", status: "active", runs: 1247, success: 98.5 },
    { name: "Lead Qualification", status: "active", runs: 892, success: 95.2 },
    { name: "Report Generation", status: "paused", runs: 456, success: 99.1 },
  ]

  return (
    <div className="bg-zinc-900 rounded-xl overflow-hidden shadow-2xl border border-zinc-800">
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-zinc-800">
        <div className="flex items-center gap-3">
          <div className="flex gap-1.5">
            <div className="h-3 w-3 rounded-full bg-red-500" />
            <div className="h-3 w-3 rounded-full bg-yellow-500" />
            <div className="h-3 w-3 rounded-full bg-green-500" />
          </div>
          <span className="text-sm font-medium text-zinc-400">Workflows</span>
        </div>
      </div>

      {/* Workflow Builder Preview */}
      <div className="p-6 bg-zinc-950/50">
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
                node.color === 'emerald' ? 'border-emerald-500/30 bg-emerald-500/10' :
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
                  className="h-0.5 bg-gradient-to-r from-zinc-600 to-zinc-700"
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
              className="flex items-center justify-between p-3 rounded-lg border border-zinc-800 bg-zinc-800/30 hover:border-zinc-700 transition-colors"
            >
              <div className="flex items-center gap-3">
                <div className={`h-2 w-2 rounded-full ${wf.status === 'active' ? 'bg-emerald-500' : 'bg-zinc-600'}`} />
                <span className="text-sm text-zinc-300">{wf.name}</span>
              </div>
              <div className="flex items-center gap-4 text-xs">
                <span className="text-zinc-500">{wf.runs.toLocaleString()} runs</span>
                <span className="text-emerald-400">{wf.success}%</span>
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
  const [animatedValues, setAnimatedValues] = useState({ tasks: 0, success: 0, time: 0 })

  useEffect(() => {
    const timer = setTimeout(() => {
      setAnimatedValues({ tasks: 12847, success: 98.5, time: 2.3 })
    }, 500)
    return () => clearTimeout(timer)
  }, [])

  return (
    <div className="bg-zinc-900 rounded-xl overflow-hidden shadow-2xl border border-zinc-800">
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-zinc-800">
        <div className="flex items-center gap-3">
          <div className="flex gap-1.5">
            <div className="h-3 w-3 rounded-full bg-red-500" />
            <div className="h-3 w-3 rounded-full bg-yellow-500" />
            <div className="h-3 w-3 rounded-full bg-green-500" />
          </div>
          <span className="text-sm font-medium text-zinc-400">Analytics</span>
        </div>
        <div className="flex items-center gap-2 text-xs text-zinc-500">
          <Clock className="h-3 w-3" />
          Last 30 days
        </div>
      </div>

      {/* Stats Grid */}
      <div className="p-4 grid grid-cols-3 gap-3">
        {[
          { label: "Tasks Completed", value: animatedValues.tasks.toLocaleString(), change: "+12%", color: "emerald" },
          { label: "Success Rate", value: `${animatedValues.success}%`, change: "+2.3%", color: "blue" },
          { label: "Avg. Response", value: `${animatedValues.time}s`, change: "-15%", color: "purple" },
        ].map((stat, i) => (
          <motion.div
            key={stat.label}
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: i * 0.1 }}
            className="p-4 rounded-xl border border-zinc-800 bg-zinc-800/30"
          >
            <div className="text-xs text-zinc-500 mb-1">{stat.label}</div>
            <div className="text-2xl font-bold text-zinc-200">{stat.value}</div>
            <div className={`text-xs mt-1 ${
              stat.color === 'emerald' ? 'text-emerald-400' :
              stat.color === 'blue' ? 'text-blue-400' : 'text-purple-400'
            }`}>
              {stat.change} from last period
            </div>
          </motion.div>
        ))}
      </div>

      {/* Chart placeholder */}
      <div className="px-4 pb-4">
        <div className="h-32 rounded-xl border border-zinc-800 bg-zinc-800/20 flex items-end justify-around p-4 gap-2">
          {[65, 45, 80, 55, 90, 70, 85].map((height, i) => (
            <motion.div
              key={i}
              initial={{ height: 0 }}
              animate={{ height: `${height}%` }}
              transition={{ delay: 0.5 + i * 0.1, duration: 0.5, ease: "easeOut" }}
              className="flex-1 bg-gradient-to-t from-emerald-600 to-emerald-500 rounded-t-sm"
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
        <div className="inline-flex items-center gap-1 p-1 rounded-full bg-zinc-100 border border-zinc-200">
          {showcaseTabs.map((tab) => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={`relative flex items-center gap-2 px-4 py-2 rounded-full text-sm font-medium transition-all ${
                activeTab === tab.id
                  ? "text-zinc-900"
                  : "text-zinc-500 hover:text-zinc-700"
              }`}
            >
              {activeTab === tab.id && (
                <motion.div
                  layoutId="activeTab"
                  className="absolute inset-0 bg-white rounded-full shadow-sm"
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
        <div className="absolute -inset-4 bg-gradient-to-r from-emerald-500/10 via-blue-500/10 to-purple-500/10 rounded-3xl blur-2xl" />
        
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
    <div className="grid lg:grid-cols-2 gap-12 items-center">
      {/* Steps List */}
      <div className="space-y-4">
        {steps.map((step, i) => (
          <motion.button
            key={i}
            onClick={() => setActiveStep(i)}
            className={`w-full text-left p-6 rounded-2xl border transition-all ${
              activeStep === i
                ? "border-emerald-500/30 bg-emerald-50"
                : "border-zinc-200 bg-white hover:border-zinc-300"
            }`}
            whileHover={{ x: 4 }}
            transition={{ duration: 0.15 }}
          >
            <div className="flex items-start gap-4">
              <div className={`flex items-center justify-center h-10 w-10 rounded-full text-sm font-bold shrink-0 ${
                activeStep === i
                  ? "bg-emerald-600 text-white"
                  : "bg-zinc-100 text-zinc-500"
              }`}>
                {step.number}
              </div>
              <div>
                <h4 className={`text-lg font-semibold mb-1 ${
                  activeStep === i ? "text-emerald-900" : "text-zinc-900"
                }`}>
                  {step.title}
                </h4>
                <p className={`text-sm ${
                  activeStep === i ? "text-emerald-700" : "text-zinc-600"
                }`}>
                  {step.description}
                </p>
              </div>
            </div>
            
            {/* Progress bar */}
            {activeStep === i && (
              <div className="mt-4 ml-14 h-1 rounded-full bg-emerald-200 overflow-hidden">
                <motion.div
                  className="h-full bg-emerald-600"
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
  const [activeIndex, setActiveIndex] = useState(0)

  useEffect(() => {
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
          className="bg-white rounded-2xl border border-zinc-200 p-8 shadow-lg"
        >
          <blockquote className="text-xl text-zinc-700 leading-relaxed mb-6">
            "{testimonials[activeIndex].quote}"
          </blockquote>
          <div className="flex items-center gap-4">
            <div className="h-12 w-12 rounded-full bg-gradient-to-br from-emerald-500 to-teal-500 flex items-center justify-center text-white font-semibold">
              {testimonials[activeIndex].author.charAt(0)}
            </div>
            <div>
              <div className="font-semibold text-zinc-900">{testimonials[activeIndex].author}</div>
              <div className="text-sm text-zinc-500">
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
              i === activeIndex ? "w-8 bg-emerald-600" : "w-2 bg-zinc-300 hover:bg-zinc-400"
            }`}
          />
        ))}
      </div>
    </div>
  )
}

// Stats Counter Component
export function AnimatedStats() {
  const [inView, setInView] = useState(false)
  const stats = [
    { value: 10000, suffix: "+", label: "Businesses trust Gravitre" },
    { value: 50, suffix: "M+", label: "Tasks automated monthly" },
    { value: 99.9, suffix: "%", label: "Uptime guaranteed" },
    { value: 4.9, suffix: "/5", label: "Customer satisfaction" },
  ]

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
            className="text-4xl md:text-5xl font-bold text-zinc-900"
            initial={{ opacity: 0 }}
            animate={inView ? { opacity: 1 } : {}}
            transition={{ delay: i * 0.1 + 0.2 }}
          >
            {inView && (
              <motion.span
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
              >
                {stat.value.toLocaleString()}{stat.suffix}
              </motion.span>
            )}
          </motion.div>
          <div className="mt-2 text-sm text-zinc-500">{stat.label}</div>
        </motion.div>
      ))}
    </motion.div>
  )
}
