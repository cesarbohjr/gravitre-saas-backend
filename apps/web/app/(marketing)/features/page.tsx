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
  Send
} from "lucide-react"
import { IntegrationsGrid } from "@/components/gravitre/platform-logos"
import { VendorLogo } from "@/components/gravitre/vendor-logo"
import { TestimonialsCarouselFull, SocialProofBanner } from "@/components/marketing/testimonials"

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
      className={`group relative rounded-3xl border border-zinc-200 bg-white shadow-sm overflow-hidden transition-all hover:shadow-lg hover:border-zinc-300 ${className}`}
    >
      <div className="absolute inset-0 bg-gradient-to-br from-zinc-50 via-transparent to-transparent opacity-0 group-hover:opacity-100 transition-opacity duration-500" />
      {children}
    </motion.div>
  )
}

// Interactive App Screen Components
function AgentsScreen() {
  const agents = [
    { name: "Data Analyst", icon: BarChart3, color: "emerald", status: "active", tasks: 12, accuracy: "98%" },
    { name: "Content Writer", icon: FileText, color: "blue", status: "active", tasks: 8, accuracy: "95%" },
    { name: "Research Agent", icon: Eye, color: "purple", status: "idle", tasks: 0, accuracy: "97%" },
    { name: "Code Reviewer", icon: GitBranch, color: "amber", status: "active", tasks: 5, accuracy: "99%" },
  ]
  
  return (
    <div className="rounded-xl border border-zinc-200 bg-white shadow-lg overflow-hidden">
      {/* App Header */}
      <div className="border-b border-zinc-200 bg-zinc-50 px-4 py-3 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <div className="flex gap-1.5">
            <div className="h-3 w-3 rounded-full bg-red-400" />
            <div className="h-3 w-3 rounded-full bg-amber-400" />
            <div className="h-3 w-3 rounded-full bg-emerald-400" />
          </div>
          <span className="text-xs font-medium text-zinc-500 ml-2">Agents</span>
        </div>
        <div className="flex items-center gap-2">
          <div className="h-6 px-2 rounded bg-emerald-100 text-emerald-700 text-[10px] font-medium flex items-center">
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
            className="flex items-center gap-4 p-3 rounded-lg border border-zinc-100 hover:border-zinc-200 hover:bg-zinc-50 transition-colors cursor-pointer"
          >
            <div className={`h-10 w-10 rounded-lg flex items-center justify-center relative ${
              agent.color === 'emerald' ? 'bg-emerald-100' :
              agent.color === 'blue' ? 'bg-blue-100' :
              agent.color === 'purple' ? 'bg-purple-100' : 'bg-amber-100'
            }`}>
              <agent.icon className={`h-5 w-5 ${
                agent.color === 'emerald' ? 'text-emerald-600' :
                agent.color === 'blue' ? 'text-blue-600' :
                agent.color === 'purple' ? 'text-purple-600' : 'text-amber-600'
              }`} />
              {agent.status === "active" && (
                <motion.div
                  className="absolute -bottom-0.5 -right-0.5 h-2.5 w-2.5 rounded-full bg-emerald-500 ring-2 ring-white"
                  animate={{ scale: [1, 1.2, 1] }}
                  transition={{ duration: 1.5, repeat: Infinity }}
                />
              )}
            </div>
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2">
                <span className="text-sm font-medium text-zinc-900">{agent.name}</span>
                <span className={`text-[10px] px-1.5 py-0.5 rounded ${
                  agent.status === 'active' ? 'bg-emerald-100 text-emerald-700' : 'bg-zinc-100 text-zinc-500'
                }`}>
                  {agent.status}
                </span>
              </div>
              <div className="flex items-center gap-3 mt-1">
                <span className="text-[10px] text-zinc-500">{agent.tasks} tasks</span>
                <span className="text-[10px] text-zinc-500">{agent.accuracy} accuracy</span>
              </div>
            </div>
            <ChevronRight className="h-4 w-4 text-zinc-400" />
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
    <div className="rounded-xl border border-zinc-200 bg-white shadow-lg overflow-hidden">
      {/* App Header */}
      <div className="border-b border-zinc-200 bg-zinc-50 px-4 py-3 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <div className="flex gap-1.5">
            <div className="h-3 w-3 rounded-full bg-red-400" />
            <div className="h-3 w-3 rounded-full bg-amber-400" />
            <div className="h-3 w-3 rounded-full bg-emerald-400" />
          </div>
          <span className="text-xs font-medium text-zinc-500 ml-2">Assignments</span>
        </div>
        <div className="flex items-center gap-2 text-[10px]">
          <span className="text-zinc-500">4 active</span>
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
            className="p-3 rounded-lg border border-zinc-100 hover:border-zinc-200 transition-colors"
          >
            <div className="flex items-start justify-between gap-2 mb-2">
              <div>
                <div className="flex items-center gap-2">
                  <span className="text-sm font-medium text-zinc-900">{task.title}</span>
                  <span className={`h-1.5 w-1.5 rounded-full ${
                    task.priority === 'high' ? 'bg-red-500' :
                    task.priority === 'medium' ? 'bg-amber-500' : 'bg-zinc-400'
                  }`} />
                </div>
                <span className="text-[10px] text-zinc-500">Assigned to {task.agent}</span>
              </div>
              <span className={`text-[10px] px-1.5 py-0.5 rounded ${
                task.status === 'completed' ? 'bg-emerald-100 text-emerald-700' :
                task.status === 'in_progress' ? 'bg-blue-100 text-blue-700' : 'bg-zinc-100 text-zinc-600'
              }`}>
                {task.status === 'in_progress' ? 'In Progress' : task.status === 'completed' ? 'Completed' : 'Pending'}
              </span>
            </div>
            <div className="flex items-center gap-2">
              <div className="flex-1 h-1.5 bg-zinc-100 rounded-full overflow-hidden">
                <motion.div 
                  className={`h-full rounded-full ${
                    task.status === 'completed' ? 'bg-emerald-500' : 'bg-blue-500'
                  }`}
                  initial={{ width: 0 }}
                  whileInView={{ width: `${task.progress}%` }}
                  viewport={{ once: true }}
                  transition={{ delay: i * 0.1 + 0.2 }}
                />
              </div>
              <span className="text-[10px] text-zinc-500 w-8">{task.progress}%</span>
            </div>
          </motion.div>
        ))}
      </div>
    </div>
  )
}

function WorkflowBuilderScreen() {
  return (
    <div className="rounded-xl border border-zinc-200 bg-white shadow-lg overflow-hidden">
      {/* App Header */}
      <div className="border-b border-zinc-200 bg-zinc-50 px-4 py-3 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <div className="flex gap-1.5">
            <div className="h-3 w-3 rounded-full bg-red-400" />
            <div className="h-3 w-3 rounded-full bg-amber-400" />
            <div className="h-3 w-3 rounded-full bg-emerald-400" />
          </div>
          <span className="text-xs font-medium text-zinc-500 ml-2">Create Workflow</span>
        </div>
        <div className="flex items-center gap-2">
          <div className="h-6 px-2 rounded bg-emerald-600 text-white text-[10px] font-medium flex items-center">
            Save
          </div>
        </div>
      </div>
      
      {/* Workflow Canvas */}
      <div className="p-6 bg-zinc-50/50 min-h-[280px] relative">
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
            <div className="h-14 w-14 rounded-xl border-2 border-dashed border-emerald-300 bg-emerald-50 flex items-center justify-center shadow-sm">
              <Zap className="h-6 w-6 text-emerald-600" />
            </div>
            <span className="text-[10px] text-zinc-600 mt-1.5 font-medium">Trigger</span>
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
            <span className="text-[10px] text-zinc-600 mt-1.5 font-medium">AI Agent</span>
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
            <span className="text-[10px] text-zinc-600 mt-1.5 font-medium">Condition</span>
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
            <span className="text-[10px] text-zinc-600 mt-1.5 font-medium">Notify</span>
          </motion.div>
        </div>
        
        {/* Side panel hint */}
        <motion.div
          initial={{ opacity: 0, x: 20 }}
          whileInView={{ opacity: 0.8, x: 0 }}
          viewport={{ once: true }}
          transition={{ delay: 0.8 }}
          className="absolute right-4 top-4 w-28 p-2 rounded-lg border border-zinc-200 bg-white shadow-sm"
        >
          <span className="text-[9px] font-medium text-zinc-500 block mb-1.5">Add Node</span>
          <div className="space-y-1">
            {['Agent', 'Condition', 'Action'].map((item) => (
              <div key={item} className="text-[9px] text-zinc-400 flex items-center gap-1.5">
                <div className="h-1.5 w-1.5 rounded-full bg-zinc-300" />
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
      message: "I found 3 key trends: 1) 23% increase in enterprise deals, 2) APAC region outperformed by 15%, 3) New product line contributed 40% of growth.",
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
    <div className="rounded-xl border border-zinc-200 bg-white shadow-lg overflow-hidden">
      {/* App Header */}
      <div className="border-b border-zinc-200 bg-zinc-50 px-4 py-3 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <div className="flex gap-1.5">
            <div className="h-3 w-3 rounded-full bg-red-400" />
            <div className="h-3 w-3 rounded-full bg-amber-400" />
            <div className="h-3 w-3 rounded-full bg-emerald-400" />
          </div>
          <span className="text-xs font-medium text-zinc-500 ml-2">AI Operator</span>
        </div>
        <div className="flex items-center gap-1">
          <motion.div
            className="h-2 w-2 rounded-full bg-emerald-500"
            animate={{ scale: [1, 1.2, 1] }}
            transition={{ duration: 1, repeat: Infinity }}
          />
          <span className="text-[10px] text-emerald-600">Online</span>
        </div>
      </div>
      
      {/* Chat */}
      <div className="p-4 space-y-3 min-h-[320px] bg-zinc-50/30 overflow-hidden">
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
                  <div className="h-8 w-8 rounded-full bg-zinc-200 flex items-center justify-center shrink-0 text-xs font-medium text-zinc-600">
                    JD
                  </div>
                  <div className="flex-1 rounded-2xl rounded-tl-sm bg-white border border-zinc-200 p-3 shadow-sm">
                    <p className="text-sm text-zinc-700">{msg.message}</p>
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
                  <div className="flex-1 rounded-2xl rounded-tr-sm bg-gradient-to-br from-emerald-50 to-emerald-100/80 border border-emerald-200 p-3">
                    <div className="flex items-center gap-2 mb-1.5">
                      <Sparkles className="h-3 w-3 text-emerald-600" />
                      <span className="text-[10px] font-medium text-emerald-700">via {msg.agent}</span>
                    </div>
                    <p className="text-sm text-emerald-800">{msg.message}</p>
                  </div>
                  <div className="h-8 w-8 rounded-full bg-gradient-to-br from-emerald-500 to-emerald-600 flex items-center justify-center shrink-0 shadow-md">
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
              <span className="text-[10px] text-zinc-400">
                {conversation[visibleMessages.length]?.type === 'user' ? 'typing...' : 'AI is thinking...'}
              </span>
            </motion.div>
          )}
        </AnimatePresence>
        
        {/* Input */}
        <div className="rounded-xl border border-zinc-200 bg-white p-2.5 flex items-center gap-2 shadow-sm mt-auto">
          <input
            type="text"
            placeholder="Ask anything..."
            className="flex-1 text-sm text-zinc-700 placeholder-zinc-400 bg-transparent outline-none"
            readOnly
          />
          <div className="h-7 w-7 rounded-lg bg-emerald-500 flex items-center justify-center cursor-pointer hover:bg-emerald-600 transition-colors">
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
      <div className="relative h-full min-h-[300px] p-6 space-y-3 bg-zinc-50/50">
        {[
          { icon: Lock, label: "Role-based access control", status: true },
          { icon: FileText, label: "Complete audit trail", status: true },
          { icon: Shield, label: "SOC 2 Type II certified", status: true },
          { icon: Check, label: "Human-in-the-loop approvals", status: true },
        ].map((item, i) => (
          <motion.div
            key={i}
            initial={{ opacity: 0, x: -20 }}
            whileInView={{ opacity: 1, x: 0 }}
            viewport={{ once: true }}
            transition={{ delay: i * 0.1 }}
            className="flex items-center justify-between rounded-xl border border-zinc-200 bg-white p-4 shadow-sm"
          >
            <div className="flex items-center gap-3">
              <item.icon className="h-4 w-4 text-amber-500" />
              <span className="text-sm text-zinc-900">{item.label}</span>
            </div>
            <div className="h-6 w-6 rounded-full bg-emerald-100 flex items-center justify-center">
              <Check className="h-3 w-3 text-emerald-600" />
            </div>
          </motion.div>
        ))}
      </div>
    )
  }

  return null
}

export default function FeaturesPage() {
  return (
    <div className="relative overflow-hidden bg-white">
      {/* Hero */}
      <section className="relative py-32 overflow-hidden">
        {/* Animated gradient background */}
        <div className="absolute inset-0 bg-gradient-to-b from-emerald-50 via-transparent to-transparent" />
        
        {/* Animated floating orbs */}
        <motion.div 
          className="absolute top-0 left-1/2 -translate-x-1/2 w-[800px] h-[600px] bg-emerald-100 rounded-full blur-3xl"
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
              className="absolute w-12 h-12 rounded-xl bg-white/60 backdrop-blur-sm border border-emerald-200/50 flex items-center justify-center shadow-sm"
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
              <svg className="w-5 h-5 text-emerald-600" fill="none" stroke="currentColor" viewBox="0 0 24 24" strokeWidth="1.5">
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
              className="mb-6 inline-flex items-center gap-2 rounded-full border border-emerald-200 bg-emerald-50/80 backdrop-blur-sm px-4 py-2"
            >
              <motion.div
                animate={{ rotate: [0, 360] }}
                transition={{ duration: 8, repeat: Infinity, ease: "linear" }}
              >
                <Sparkles className="h-4 w-4 text-emerald-600" />
              </motion.div>
              <span className="text-sm font-medium text-emerald-700">Powerful capabilities</span>
            </motion.div>
            
            {/* Staggered headline */}
            <div className="overflow-hidden">
              <motion.h1
                initial={{ opacity: 0, y: 50 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: 0.2, duration: 0.7, ease: [0.16, 1, 0.3, 1] }}
                className="text-5xl sm:text-6xl lg:text-7xl font-bold tracking-tight"
              >
                <span className="text-zinc-900">
                  Everything you need
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
                to work with AI
              </motion.h1>
            </div>
            
            <motion.p 
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.5 }}
              className="mt-6 text-lg text-zinc-600 max-w-2xl mx-auto"
            >
              A simple platform to set up, manage, and keep your AI team running smoothly.
            </motion.p>
            
            {/* Feature pills */}
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.7 }}
              className="mt-10 flex flex-wrap items-center justify-center gap-3"
            >
              {["AI Assistant", "Smart Agents", "Workflows", "Integrations", "Analytics"].map((feature, i) => (
                <motion.span
                  key={feature}
                  initial={{ opacity: 0, scale: 0.9 }}
                  animate={{ opacity: 1, scale: 1 }}
                  transition={{ delay: 0.8 + i * 0.1 }}
                  className="px-4 py-2 rounded-full bg-white/80 backdrop-blur-sm border border-zinc-200 text-sm font-medium text-zinc-700 shadow-sm"
                >
                  {feature}
                </motion.span>
              ))}
            </motion.div>
          </motion.div>
        </div>
      </section>

      {/* Interactive Product Screens */}
      <section className="relative pb-32">
        <div className="mx-auto max-w-7xl px-6">
          {/* Section header */}
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            className="text-center mb-16"
          >
            <h2 className="text-3xl font-bold text-zinc-900 mb-4">See it in action</h2>
            <p className="text-zinc-600 max-w-2xl mx-auto">
              Explore the key screens that power your AI workforce
            </p>
          </motion.div>

          {/* AI Operator - Full width featured */}
          <motion.div
            initial={{ opacity: 0, y: 30 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            className="mb-8"
          >
            <div className="grid lg:grid-cols-2 gap-8 items-center">
              <div className="lg:pr-8">
                <div className="flex items-center gap-3 mb-4">
                  <div className="h-12 w-12 rounded-xl bg-gradient-to-br from-emerald-100 to-emerald-50 ring-1 ring-emerald-200 flex items-center justify-center">
                    <Bot className="h-6 w-6 text-emerald-600" />
                  </div>
                  <div>
                    <h3 className="text-2xl font-semibold text-zinc-900">AI Operator</h3>
                    <p className="text-sm text-emerald-600">Your command center</p>
                  </div>
                </div>
                <p className="text-zinc-600 mb-6">
                  Talk to your AI team in plain English. Ask questions, start tasks, and get instant answers. 
                  The AI Operator understands context, routes requests to the right agents, and provides 
                  actionable insights.
                </p>
                <ul className="space-y-2">
                  {['Natural language commands', 'Real-time task execution', 'Smart agent routing'].map((item) => (
                    <li key={item} className="flex items-center gap-2 text-sm text-zinc-600">
                      <Check className="h-4 w-4 text-emerald-600" />
                      {item}
                    </li>
                  ))}
                </ul>
              </div>
              <AIOperatorScreen />
            </div>
          </motion.div>

          {/* Three column grid */}
          <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-6">
            {/* Agents */}
            <motion.div
              initial={{ opacity: 0, y: 30 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true }}
              transition={{ delay: 0.1 }}
            >
              <div className="mb-4">
                <div className="flex items-center gap-3 mb-2">
                  <div className="h-10 w-10 rounded-lg bg-blue-100 flex items-center justify-center">
                    <Users className="h-5 w-5 text-blue-600" />
                  </div>
                  <h3 className="text-lg font-semibold text-zinc-900">Agents</h3>
                </div>
                <p className="text-sm text-zinc-600">Manage your AI workforce. Monitor status, track performance, and configure agent capabilities.</p>
              </div>
              <AgentsScreen />
            </motion.div>

            {/* Assignments */}
            <motion.div
              initial={{ opacity: 0, y: 30 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true }}
              transition={{ delay: 0.2 }}
            >
              <div className="mb-4">
                <div className="flex items-center gap-3 mb-2">
                  <div className="h-10 w-10 rounded-lg bg-rose-100 flex items-center justify-center">
                    <FileText className="h-5 w-5 text-rose-600" />
                  </div>
                  <h3 className="text-lg font-semibold text-zinc-900">Assignments</h3>
                </div>
                <p className="text-sm text-zinc-600">Track all tasks across your AI team. See progress, priorities, and completion status at a glance.</p>
              </div>
              <AssignmentsScreen />
            </motion.div>

            {/* Workflow Builder */}
            <motion.div
              initial={{ opacity: 0, y: 30 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true }}
              transition={{ delay: 0.3 }}
            >
              <div className="mb-4">
                <div className="flex items-center gap-3 mb-2">
                  <div className="h-10 w-10 rounded-lg bg-purple-100 flex items-center justify-center">
                    <Workflow className="h-5 w-5 text-purple-600" />
                  </div>
                  <h3 className="text-lg font-semibold text-zinc-900">Automations</h3>
                </div>
                <p className="text-sm text-zinc-600">Build powerful workflows visually. Connect triggers, agents, conditions, and actions with drag-and-drop.</p>
              </div>
              <WorkflowBuilderScreen />
            </motion.div>
          </div>

          {/* Safety Card */}
          <motion.div
            initial={{ opacity: 0, y: 30 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            transition={{ delay: 0.4 }}
            className="mt-8"
          >
            <BentoCard className="lg:col-span-2">
              <div className="grid lg:grid-cols-2">
                <div className="p-8">
                  <div className="flex items-center gap-3 mb-4">
                    <div className="h-10 w-10 rounded-lg bg-amber-100 flex items-center justify-center">
                      <Shield className="h-5 w-5 text-amber-600" />
                    </div>
                    <h3 className="text-lg font-semibold text-zinc-900">Built-in Safety</h3>
                  </div>
                  <p className="text-zinc-600 mb-6">
                    Control who can do what, keep a full history, and require approval before big changes.
                  </p>
                  <Link 
                    href="/security"
                    className="inline-flex items-center gap-2 text-sm text-amber-600 hover:text-amber-700 transition-colors font-medium"
                  >
                    Learn about security
                    <ChevronRight className="h-4 w-4" />
                  </Link>
                </div>
                <FeatureVisual type="governance" />
              </div>
            </BentoCard>
          </motion.div>
        </div>
      </section>

      {/* 5 Key Features - Light Theme Screens */}
      <section className="relative py-32 border-t border-zinc-200 bg-white">
        <div className="mx-auto max-w-7xl px-6">
          <motion.div
            initial={{ opacity: 0, y: 30 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            className="mx-auto max-w-2xl text-center mb-20"
          >
            <span className="text-sm font-semibold text-emerald-600 tracking-wide uppercase">Platform Features</span>
            <h2 className="mt-4 text-4xl font-bold tracking-tight text-zinc-900">
              Everything you need to automate intelligently
            </h2>
          </motion.div>

          <div className="space-y-32">
            {/* Feature 1: AI Operator */}
            <motion.div
              initial={{ opacity: 0, y: 30 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true }}
              className="grid lg:grid-cols-2 gap-12 items-center"
            >
              <div>
                <div className="inline-flex items-center gap-2 rounded-full bg-emerald-50 border border-emerald-200 px-3 py-1 mb-4">
                  <Sparkles className="h-3.5 w-3.5 text-emerald-600" />
                  <span className="text-xs font-medium text-emerald-700">AI Operator</span>
                </div>
                <h3 className="text-3xl font-bold text-zinc-900 mb-4">Natural language command center</h3>
                <p className="text-zinc-600 mb-6 leading-relaxed text-lg">
                  Talk to your AI workforce like you would a colleague. Ask questions, request analysis, 
                  trigger workflows, and get instant responses - all through natural conversation.
                </p>
                <ul className="space-y-3">
                  {['Conversational AI interface', 'Context-aware responses', 'Multi-agent orchestration', 'Real-time task execution'].map((item) => (
                    <li key={item} className="flex items-center gap-3 text-sm text-zinc-600">
                      <div className="h-5 w-5 rounded-full bg-emerald-100 flex items-center justify-center">
                        <Check className="h-3 w-3 text-emerald-600" />
                      </div>
                      {item}
                    </li>
                  ))}
                </ul>
              </div>
              <div className="relative">
                <div className="absolute -inset-4 bg-gradient-to-r from-emerald-100/60 to-teal-100/60 rounded-3xl blur-2xl" />
                <div className="relative rounded-xl border border-zinc-200 bg-white shadow-2xl overflow-hidden">
                  {/* Browser chrome */}
                  <div className="flex items-center gap-2 px-4 py-3 bg-zinc-50 border-b border-zinc-200">
                    <div className="flex gap-1.5">
                      <div className="h-3 w-3 rounded-full bg-red-400" />
                      <div className="h-3 w-3 rounded-full bg-amber-400" />
                      <div className="h-3 w-3 rounded-full bg-emerald-400" />
                    </div>
                    <div className="flex-1 flex justify-center">
                      <div className="px-3 py-1 rounded-md bg-zinc-100 text-[10px] text-zinc-500">AI Operator</div>
                    </div>
                  </div>
                  {/* Chat interface */}
                  <div className="p-5 space-y-4 bg-zinc-50/50 min-h-[280px]">
                    <div className="flex gap-3 items-start">
                      <div className="h-8 w-8 rounded-full bg-zinc-200 flex items-center justify-center text-xs font-medium text-zinc-600 shrink-0">JD</div>
                      <div className="bg-white border border-zinc-200 rounded-2xl rounded-tl-sm p-3 shadow-sm">
                        <p className="text-sm text-zinc-700">Analyze our Q4 sales data and find the top trends</p>
                      </div>
                    </div>
                    <motion.div 
                      initial={{ opacity: 0, y: 10 }}
                      whileInView={{ opacity: 1, y: 0 }}
                      viewport={{ once: true }}
                      transition={{ delay: 0.3 }}
                      className="flex gap-3 items-start justify-end"
                    >
                      <div className="bg-gradient-to-br from-emerald-50 to-emerald-100 border border-emerald-200 rounded-2xl rounded-tr-sm p-3">
                        <div className="flex items-center gap-2 mb-1.5">
                          <Sparkles className="h-3 w-3 text-emerald-600" />
                          <span className="text-[10px] font-medium text-emerald-700">via Data Analyst</span>
                        </div>
                        <p className="text-sm text-emerald-800">Found 3 key trends: 23% increase in enterprise deals, APAC outperformed by 15%, new product line contributed 40% of growth.</p>
                      </div>
                      <div className="h-8 w-8 rounded-full bg-gradient-to-br from-emerald-500 to-emerald-600 flex items-center justify-center shrink-0 shadow-md">
                        <Sparkles className="h-4 w-4 text-white" />
                      </div>
                    </motion.div>
                    <div className="flex gap-2">
                      {['Show details', 'Export report', 'Compare to Q3'].map((action) => (
                        <span key={action} className="px-3 py-1.5 rounded-full border border-zinc-200 bg-white text-xs text-zinc-600 hover:border-emerald-300 transition-colors cursor-pointer">
                          {action}
                        </span>
                      ))}
                    </div>
                  </div>
                </div>
              </div>
            </motion.div>

            {/* Feature 2: Smart Agents */}
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
                <h3 className="text-3xl font-bold text-zinc-900 mb-4">Your AI team, configured your way</h3>
                <p className="text-zinc-600 mb-6 leading-relaxed text-lg">
                  Deploy specialized AI agents for different roles - data analysis, content writing, 
                  research, and more. Each agent learns your business context and improves over time.
                </p>
                <ul className="space-y-3">
                  {['Pre-built agent templates', 'Custom capability configuration', 'Continuous learning', 'Role-based permissions'].map((item) => (
                    <li key={item} className="flex items-center gap-3 text-sm text-zinc-600">
                      <div className="h-5 w-5 rounded-full bg-blue-100 flex items-center justify-center">
                        <Check className="h-3 w-3 text-blue-600" />
                      </div>
                      {item}
                    </li>
                  ))}
                </ul>
              </div>
              <div className="lg:order-1 relative">
                <div className="absolute -inset-4 bg-gradient-to-r from-blue-100/60 to-indigo-100/60 rounded-3xl blur-2xl" />
                <div className="relative rounded-xl border border-zinc-200 bg-white shadow-2xl overflow-hidden">
                  <div className="flex items-center gap-2 px-4 py-3 bg-zinc-50 border-b border-zinc-200">
                    <div className="flex gap-1.5">
                      <div className="h-3 w-3 rounded-full bg-red-400" />
                      <div className="h-3 w-3 rounded-full bg-amber-400" />
                      <div className="h-3 w-3 rounded-full bg-emerald-400" />
                    </div>
                    <div className="flex-1 flex justify-center">
                      <div className="px-3 py-1 rounded-md bg-zinc-100 text-[10px] text-zinc-500">Agents</div>
                    </div>
                  </div>
                  <div className="p-5 space-y-3 bg-zinc-50/50 min-h-[280px]">
                    {[
                      { name: "Data Analyst", status: "Active", tasks: "1,247", color: "emerald" },
                      { name: "Content Writer", status: "Active", tasks: "892", color: "blue" },
                      { name: "Research Agent", status: "Active", tasks: "634", color: "purple" },
                    ].map((agent, i) => (
                      <motion.div
                        key={agent.name}
                        initial={{ opacity: 0, x: -20 }}
                        whileInView={{ opacity: 1, x: 0 }}
                        viewport={{ once: true }}
                        transition={{ delay: i * 0.1 }}
                        className="flex items-center justify-between p-4 rounded-xl border border-zinc-200 bg-white shadow-sm"
                      >
                        <div className="flex items-center gap-3">
                          <div className={`h-10 w-10 rounded-xl flex items-center justify-center ${
                            agent.color === 'emerald' ? 'bg-emerald-100' :
                            agent.color === 'blue' ? 'bg-blue-100' : 'bg-purple-100'
                          }`}>
                            <Bot className={`h-5 w-5 ${
                              agent.color === 'emerald' ? 'text-emerald-600' :
                              agent.color === 'blue' ? 'text-blue-600' : 'text-purple-600'
                            }`} />
                          </div>
                          <div>
                            <div className="text-sm font-medium text-zinc-900">{agent.name}</div>
                            <div className="text-[10px] text-zinc-500">{agent.tasks} tasks completed</div>
                          </div>
                        </div>
                        <span className="px-2 py-1 rounded-full bg-emerald-50 border border-emerald-200 text-[10px] text-emerald-700">{agent.status}</span>
                      </motion.div>
                    ))}
                  </div>
                </div>
              </div>
            </motion.div>

            {/* Feature 3: Visual Workflow Builder */}
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
                <h3 className="text-3xl font-bold text-zinc-900 mb-4">Visual automation, zero code</h3>
                <p className="text-zinc-600 mb-6 leading-relaxed text-lg">
                  Build sophisticated automation workflows with our drag-and-drop builder. 
                  Connect triggers, conditions, and actions without writing a single line of code.
                </p>
                <ul className="space-y-3">
                  {['Drag-and-drop interface', 'Conditional branching', 'Human-in-the-loop approvals', 'Version control'].map((item) => (
                    <li key={item} className="flex items-center gap-3 text-sm text-zinc-600">
                      <div className="h-5 w-5 rounded-full bg-purple-100 flex items-center justify-center">
                        <Check className="h-3 w-3 text-purple-600" />
                      </div>
                      {item}
                    </li>
                  ))}
                </ul>
              </div>
              <div className="relative">
                <div className="absolute -inset-4 bg-gradient-to-r from-purple-100/60 to-pink-100/60 rounded-3xl blur-2xl" />
                <div className="relative rounded-xl border border-zinc-200 bg-white shadow-2xl overflow-hidden">
                  <div className="flex items-center gap-2 px-4 py-3 bg-zinc-50 border-b border-zinc-200">
                    <div className="flex gap-1.5">
                      <div className="h-3 w-3 rounded-full bg-red-400" />
                      <div className="h-3 w-3 rounded-full bg-amber-400" />
                      <div className="h-3 w-3 rounded-full bg-emerald-400" />
                    </div>
                    <div className="flex-1 flex justify-center">
                      <div className="px-3 py-1 rounded-md bg-zinc-100 text-[10px] text-zinc-500">Workflow Builder</div>
                    </div>
                  </div>
                  <div className="p-5 bg-zinc-50/50 min-h-[280px]">
                    <div className="flex items-center justify-center gap-3">
                      {[
                        { icon: Zap, label: "Trigger", color: "amber" },
                        { icon: Bot, label: "AI Agent", color: "blue" },
                        { icon: GitBranch, label: "Condition", color: "purple" },
                        { icon: Send, label: "Action", color: "emerald" },
                      ].map((node, i) => (
                        <motion.div
                          key={node.label}
                          initial={{ opacity: 0, scale: 0.8 }}
                          whileInView={{ opacity: 1, scale: 1 }}
                          viewport={{ once: true }}
                          transition={{ delay: i * 0.1 }}
                          className="flex flex-col items-center"
                        >
                          <div className="flex items-center">
                            <div className={`h-14 w-14 rounded-xl flex items-center justify-center border-2 bg-white shadow-sm ${
                              node.color === 'amber' ? 'border-amber-300' :
                              node.color === 'blue' ? 'border-blue-300' :
                              node.color === 'purple' ? 'border-purple-300' : 'border-emerald-300'
                            }`}>
                              <node.icon className={`h-6 w-6 ${
                                node.color === 'amber' ? 'text-amber-500' :
                                node.color === 'blue' ? 'text-blue-500' :
                                node.color === 'purple' ? 'text-purple-500' : 'text-emerald-500'
                              }`} />
                            </div>
                            {i < 3 && <div className="w-4 h-0.5 bg-zinc-300" />}
                          </div>
                          <span className="text-[10px] text-zinc-500 mt-2">{node.label}</span>
                        </motion.div>
                      ))}
                    </div>
                    <motion.div 
                      initial={{ opacity: 0, y: 10 }}
                      whileInView={{ opacity: 1, y: 0 }}
                      viewport={{ once: true }}
                      transition={{ delay: 0.5 }}
                      className="mt-6 p-3 rounded-lg border border-emerald-200 bg-emerald-50"
                    >
                      <div className="flex items-center gap-2">
                        <Check className="h-4 w-4 text-emerald-600" />
                        <span className="text-xs text-emerald-700">Workflow saved and ready to deploy</span>
                      </div>
                    </motion.div>
                  </div>
                </div>
              </div>
            </motion.div>

            {/* Feature 4: Connected Integrations */}
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
                <h3 className="text-3xl font-bold text-zinc-900 mb-4">Connect to 100+ apps instantly</h3>
                <p className="text-zinc-600 mb-6 leading-relaxed text-lg">
                  One-click integrations with Salesforce, HubSpot, Slack, Google Workspace, and more. 
                  Your AI agents can read, write, and take actions across all your tools.
                </p>
                <ul className="space-y-3">
                  {['Pre-built connectors', 'OAuth authentication', 'Real-time sync', 'Custom API support'].map((item) => (
                    <li key={item} className="flex items-center gap-3 text-sm text-zinc-600">
                      <div className="h-5 w-5 rounded-full bg-amber-100 flex items-center justify-center">
                        <Check className="h-3 w-3 text-amber-600" />
                      </div>
                      {item}
                    </li>
                  ))}
                </ul>
              </div>
              <div className="lg:order-1 relative">
                <div className="absolute -inset-4 bg-gradient-to-r from-amber-100/60 to-orange-100/60 rounded-3xl blur-2xl" />
                <div className="relative rounded-xl border border-zinc-200 bg-white shadow-2xl overflow-hidden">
                  <div className="flex items-center gap-2 px-4 py-3 bg-zinc-50 border-b border-zinc-200">
                    <div className="flex gap-1.5">
                      <div className="h-3 w-3 rounded-full bg-red-400" />
                      <div className="h-3 w-3 rounded-full bg-amber-400" />
                      <div className="h-3 w-3 rounded-full bg-emerald-400" />
                    </div>
                    <div className="flex-1 flex justify-center">
                      <div className="px-3 py-1 rounded-md bg-zinc-100 text-[10px] text-zinc-500">Connectors</div>
                    </div>
                  </div>
                  <div className="p-5 bg-zinc-50/50 min-h-[280px]">
                    <div className="grid grid-cols-3 gap-3">
                      {[
                        { name: "Salesforce", status: "connected" },
                        { name: "Slack", status: "connected" },
                        { name: "HubSpot", status: "connected" },
                        { name: "Google", status: "connected" },
                        { name: "Notion", status: "connected" },
                        { name: "Jira", status: "available" },
                      ].map((app, i) => (
                        <motion.div
                          key={app.name}
                          initial={{ opacity: 0, scale: 0.9 }}
                          whileInView={{ opacity: 1, scale: 1 }}
                          viewport={{ once: true }}
                          transition={{ delay: i * 0.05 }}
                          className={`p-3 rounded-xl border text-center ${
                            app.status === 'connected' 
                              ? 'border-emerald-200 bg-emerald-50' 
                              : 'border-zinc-200 bg-white'
                          }`}
                        >
                          <div className="mx-auto mb-2">
                            <VendorLogo vendor={app.name} size="sm" />
                          </div>
                          <div className="text-[10px] font-medium text-zinc-700">{app.name}</div>
                          <div className={`text-[8px] mt-0.5 ${
                            app.status === 'connected' ? 'text-emerald-600' : 'text-zinc-400'
                          }`}>
                            {app.status === 'connected' ? 'Connected' : 'Available'}
                          </div>
                        </motion.div>
                      ))}
                    </div>
                  </div>
                </div>
              </div>
            </motion.div>

            {/* Feature 5: Enterprise Security */}
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
                <h3 className="text-3xl font-bold text-zinc-900 mb-4">Security you can trust</h3>
                <p className="text-zinc-600 mb-6 leading-relaxed text-lg">
                  Built with security-first principles including role-based access control, complete audit trails, 
                  encrypted data, and human-in-the-loop approvals for sensitive actions.
                </p>
                <ul className="space-y-3">
                  {['Role-based access control', 'Complete audit trails', 'End-to-end encryption', 'Human-in-the-loop approvals'].map((item) => (
                    <li key={item} className="flex items-center gap-3 text-sm text-zinc-600">
                      <div className="h-5 w-5 rounded-full bg-rose-100 flex items-center justify-center">
                        <Check className="h-3 w-3 text-rose-600" />
                      </div>
                      {item}
                    </li>
                  ))}
                </ul>
              </div>
              <div className="relative">
                <div className="absolute -inset-4 bg-gradient-to-r from-rose-100/60 to-red-100/60 rounded-3xl blur-2xl" />
                <div className="relative rounded-xl border border-zinc-200 bg-white shadow-2xl overflow-hidden">
                  <div className="flex items-center gap-2 px-4 py-3 bg-zinc-50 border-b border-zinc-200">
                    <div className="flex gap-1.5">
                      <div className="h-3 w-3 rounded-full bg-red-400" />
                      <div className="h-3 w-3 rounded-full bg-amber-400" />
                      <div className="h-3 w-3 rounded-full bg-emerald-400" />
                    </div>
                    <div className="flex-1 flex justify-center">
                      <div className="px-3 py-1 rounded-md bg-zinc-100 text-[10px] text-zinc-500">Security</div>
                    </div>
                  </div>
                  <div className="p-5 space-y-3 bg-zinc-50/50 min-h-[280px]">
                    {[
                      { icon: Lock, label: "Role-based access control", status: "Enabled" },
                      { icon: FileText, label: "Complete audit trail", status: "Active" },
                      { icon: Shield, label: "End-to-end encryption", status: "Active" },
                      { icon: Users, label: "Human-in-the-loop", status: "Enabled" },
                    ].map((item, i) => (
                      <motion.div
                        key={item.label}
                        initial={{ opacity: 0, x: -20 }}
                        whileInView={{ opacity: 1, x: 0 }}
                        viewport={{ once: true }}
                        transition={{ delay: i * 0.1 }}
                        className="flex items-center justify-between p-3 rounded-xl border border-zinc-200 bg-white shadow-sm"
                      >
                        <div className="flex items-center gap-3">
                          <div className="h-8 w-8 rounded-lg bg-rose-50 flex items-center justify-center">
                            <item.icon className="h-4 w-4 text-rose-500" />
                          </div>
                          <span className="text-sm text-zinc-700">{item.label}</span>
                        </div>
                        <div className="flex items-center gap-2">
                          <div className="h-2 w-2 rounded-full bg-emerald-500" />
                          <span className="text-[10px] text-emerald-600">{item.status}</span>
                        </div>
                      </motion.div>
                    ))}
                  </div>
                </div>
              </div>
            </motion.div>
          </div>
        </div>
      </section>

      {/* Detailed Features */}
      <section className="relative py-32 border-t border-zinc-200 bg-zinc-50">
        <div className="mx-auto max-w-7xl px-6">
          <motion.div
            initial={{ opacity: 0, y: 30 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            className="mx-auto max-w-2xl text-center mb-20"
          >
            <h2 className="text-4xl font-bold tracking-tight text-zinc-900">
              Capabilities that scale
            </h2>
            <p className="mt-4 text-lg text-zinc-600">
              Every feature designed for enterprise requirements.
            </p>
          </motion.div>

          <div className="grid gap-8 sm:grid-cols-2 lg:grid-cols-4">
            {[
              { icon: MessageSquare, title: "Natural Language", description: "Control everything with simple commands" },
              { icon: Eye, title: "Full Visibility", description: "See reasoning steps and data flows" },
              { icon: Bell, title: "Smart Alerts", description: "Proactive notifications when needed" },
              { icon: Clock, title: "Instant Insights", description: "Get answers in seconds, not hours" },
              { icon: Database, title: "100+ Integrations", description: "Connect all your tools instantly" },
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
                <div className="mx-auto mb-4 h-12 w-12 rounded-xl bg-white border border-zinc-200 shadow-sm flex items-center justify-center">
                  <feature.icon className="h-5 w-5 text-zinc-600" />
                </div>
                <h3 className="text-sm font-semibold text-zinc-900">{feature.title}</h3>
                <p className="mt-1 text-xs text-zinc-500">{feature.description}</p>
              </motion.div>
            ))}
          </div>
        </div>
      </section>

      {/* Integrations - Now with real logos */}
      <section className="relative py-32 border-t border-zinc-200">
        <div className="mx-auto max-w-7xl px-6">
          <motion.div
            initial={{ opacity: 0, y: 30 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            className="mx-auto max-w-2xl text-center mb-16"
          >
            <h2 className="text-4xl font-bold tracking-tight text-zinc-900">
              Connects to your entire stack
            </h2>
            <p className="mt-4 text-zinc-600">
              100+ pre-built integrations with the tools you already use.
            </p>
          </motion.div>

          <IntegrationsGrid theme="light" />
        </div>
      </section>

      {/* Testimonials */}
      <section className="relative py-32 border-t border-zinc-200 bg-zinc-50">
        <div className="mx-auto max-w-7xl px-6">
          <motion.div
            initial={{ opacity: 0, y: 30 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            className="mx-auto max-w-2xl text-center mb-16"
          >
            <span className="text-sm font-semibold text-emerald-600 tracking-wide uppercase">Testimonials</span>
            <h2 className="mt-4 text-4xl font-bold tracking-tight text-zinc-900">
              What our customers say
            </h2>
            <p className="mt-4 text-zinc-600">
              Join thousands of teams who have transformed their operations with Gravitre
            </p>
          </motion.div>

          <div className="max-w-4xl mx-auto">
            <TestimonialsCarouselFull />
          </div>
        </div>
      </section>

      {/* Social Proof Stats */}
      <SocialProofBanner />

      {/* CTA */}
      <section className="relative py-32 bg-white">
        <div className="absolute inset-0 bg-gradient-to-t from-emerald-50 via-transparent to-transparent" />
        <div className="relative mx-auto max-w-7xl px-6">
          <motion.div
            initial={{ opacity: 0, scale: 0.95 }}
            whileInView={{ opacity: 1, scale: 1 }}
            viewport={{ once: true }}
            className="mx-auto max-w-2xl text-center"
          >
            <h2 className="text-4xl font-bold tracking-tight text-zinc-900">
              Ready to get started?
            </h2>
            <p className="mt-4 text-zinc-600">
              Start your free trial today. No credit card required.
            </p>
            <div className="mt-10 flex items-center justify-center gap-4 flex-wrap">
              <Link
                href="/get-started"
                className="group inline-flex items-center gap-2 rounded-full bg-zinc-900 px-8 py-4 text-base font-semibold text-white transition-all hover:bg-zinc-800"
              >
                Start free trial
                <ArrowRight className="h-5 w-5 transition-transform group-hover:translate-x-1" />
              </Link>
              <Link
                href="/contact"
                className="inline-flex items-center gap-2 rounded-full border border-zinc-300 bg-white px-8 py-4 text-base font-semibold text-zinc-900 transition-all hover:bg-zinc-50"
              >
                Talk to sales
              </Link>
            </div>
          </motion.div>
        </div>
      </section>
    </div>
  )
}
