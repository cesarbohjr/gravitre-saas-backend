"use client"

import { Suspense, useState, useEffect, useRef } from "react"
import { useSearchParams, useRouter } from "next/navigation"
import { motion, AnimatePresence, useMotionValue, useTransform } from "framer-motion"
import { AppShell } from "@/components/gravitre/app-shell"
import { Button } from "@/components/ui/button"
import { Icon } from "@/lib/icons"
import { cn } from "@/lib/utils"

// Types
interface TrainingSection {
  id: string
  title: string
  description: string
  icon: string
  color: string
  progress: number
  status: "complete" | "in-progress" | "not-started"
  insights: number
}

interface KnowledgeSource {
  id: string
  name: string
  type: "drive" | "notion" | "crm" | "docs" | "custom"
  status: "connected" | "syncing" | "error"
  itemCount: number
  lastSync: string
  coverage: number
}

interface ChatMessage {
  id: string
  role: "user" | "agent" | "system"
  content: string
  timestamp: string
}

// Mock Data
const agents = [
  { id: "agent-001", name: "Atlas", role: "Marketing Agent", gradient: "from-emerald-500 to-teal-500", initials: "AT" },
  { id: "agent-002", name: "Nexus", role: "Sales Assistant", gradient: "from-blue-500 to-indigo-500", initials: "NX" },
  { id: "agent-003", name: "Sentinel", role: "Data Quality Agent", gradient: "from-amber-500 to-orange-500", initials: "SN" },
  { id: "agent-004", name: "Oracle", role: "Finance Reporter", gradient: "from-violet-500 to-purple-500", initials: "OR" },
]

const trainingSections: TrainingSection[] = [
  { id: "context", title: "Business Context", description: "ICP, positioning, messaging framework", icon: "target", color: "emerald", progress: 85, status: "complete", insights: 47 },
  { id: "knowledge", title: "Knowledge Sources", description: "Connected systems and documents", icon: "database", color: "blue", progress: 65, status: "in-progress", insights: 23 },
  { id: "examples", title: "Historical Work", description: "Past campaigns, emails, reports", icon: "history", color: "violet", progress: 40, status: "in-progress", insights: 12 },
  { id: "rules", title: "Rules & Constraints", description: "Compliance, tone, restrictions", icon: "shield", color: "amber", progress: 100, status: "complete", insights: 8 },
]

const knowledgeSources: KnowledgeSource[] = [
  { id: "src-1", name: "Google Drive", type: "drive", status: "connected", itemCount: 247, lastSync: "5 min ago", coverage: 92 },
  { id: "src-2", name: "Notion Workspace", type: "notion", status: "syncing", itemCount: 89, lastSync: "Syncing...", coverage: 67 },
  { id: "src-3", name: "HubSpot CRM", type: "crm", status: "connected", itemCount: 12450, lastSync: "1 hour ago", coverage: 98 },
  { id: "src-4", name: "Confluence Docs", type: "docs", status: "connected", itemCount: 156, lastSync: "2 hours ago", coverage: 78 },
]

// Neural Network Background Animation
function NeuralBackground() {
  return (
    <div className="absolute inset-0 overflow-hidden pointer-events-none">
      <svg className="absolute w-full h-full opacity-[0.03]" xmlns="http://www.w3.org/2000/svg">
        <defs>
          <pattern id="neural-grid" x="0" y="0" width="60" height="60" patternUnits="userSpaceOnUse">
            <circle cx="30" cy="30" r="1" fill="currentColor" />
          </pattern>
        </defs>
        <rect width="100%" height="100%" fill="url(#neural-grid)" />
      </svg>
      {[...Array(5)].map((_, i) => (
        <motion.div
          key={i}
          className="absolute w-96 h-96 rounded-full"
          style={{
            background: `radial-gradient(circle, ${i % 2 === 0 ? 'rgba(16, 185, 129, 0.05)' : 'rgba(59, 130, 246, 0.05)'} 0%, transparent 70%)`,
            left: `${20 + i * 15}%`,
            top: `${10 + (i % 3) * 25}%`,
          }}
          animate={{
            scale: [1, 1.2, 1],
            opacity: [0.3, 0.6, 0.3],
          }}
          transition={{
            duration: 8 + i * 2,
            repeat: Infinity,
            ease: "easeInOut",
          }}
        />
      ))}
    </div>
  )
}

// Animated Progress Ring
function ProgressRing({ progress, size = 120, strokeWidth = 8, color = "emerald" }: { progress: number; size?: number; strokeWidth?: number; color?: string }) {
  const radius = (size - strokeWidth) / 2
  const circumference = radius * 2 * Math.PI
  const offset = circumference - (progress / 100) * circumference

  const colorMap: Record<string, string> = {
    emerald: "#10b981",
    blue: "#3b82f6",
    violet: "#8b5cf6",
    amber: "#f59e0b",
  }

  return (
    <div className="relative" style={{ width: size, height: size }}>
      <svg width={size} height={size} className="transform -rotate-90">
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          fill="none"
          stroke="currentColor"
          strokeWidth={strokeWidth}
          className="text-secondary"
        />
        <motion.circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          fill="none"
          stroke={colorMap[color]}
          strokeWidth={strokeWidth}
          strokeLinecap="round"
          strokeDasharray={circumference}
          initial={{ strokeDashoffset: circumference }}
          animate={{ strokeDashoffset: offset }}
          transition={{ duration: 1.5, ease: "easeOut" }}
        />
      </svg>
      <div className="absolute inset-0 flex flex-col items-center justify-center">
        <motion.span
          className="text-2xl font-bold text-foreground"
          initial={{ opacity: 0, scale: 0.5 }}
          animate={{ opacity: 1, scale: 1 }}
          transition={{ delay: 0.5 }}
        >
          {progress}%
        </motion.span>
        <span className="text-[10px] text-muted-foreground uppercase tracking-wider">Complete</span>
      </div>
    </div>
  )
}

// Training DNA Helix Visualization
function TrainingDNA({ sections }: { sections: TrainingSection[] }) {
  return (
    <div className="relative h-64 flex items-center justify-center">
      <div className="absolute inset-0 flex items-center justify-center">
        {sections.map((section, i) => (
          <motion.div
            key={section.id}
            className="absolute"
            initial={{ opacity: 0, scale: 0 }}
            animate={{ 
              opacity: 1, 
              scale: 1,
              rotate: [0, 360],
            }}
            transition={{
              opacity: { delay: i * 0.2 },
              scale: { delay: i * 0.2 },
              rotate: { duration: 60, repeat: Infinity, ease: "linear" },
            }}
            style={{
              width: 160 + i * 40,
              height: 160 + i * 40,
            }}
          >
            <div 
              className={cn(
                "w-full h-full rounded-full border-2 border-dashed",
                section.status === "complete" && "border-emerald-500/30",
                section.status === "in-progress" && "border-blue-500/30",
                section.status === "not-started" && "border-muted/30",
              )}
              style={{ 
                animationDirection: i % 2 === 0 ? "normal" : "reverse",
              }}
            />
          </motion.div>
        ))}
      </div>
      <motion.div
        className="relative z-10 h-32 w-32 rounded-2xl bg-gradient-to-br from-emerald-500 to-teal-500 flex items-center justify-center shadow-2xl shadow-emerald-500/25"
        animate={{
          boxShadow: [
            "0 25px 50px -12px rgba(16, 185, 129, 0.25)",
            "0 25px 50px -12px rgba(16, 185, 129, 0.4)",
            "0 25px 50px -12px rgba(16, 185, 129, 0.25)",
          ],
        }}
        transition={{ duration: 2, repeat: Infinity }}
      >
        <Icon name="brain" size="2xl" className="text-white" />
      </motion.div>
    </div>
  )
}

// Section Card with Depth
function SectionCard({ section, isActive, onClick }: { section: TrainingSection; isActive: boolean; onClick: () => void }) {
  const colorClasses: Record<string, { bg: string; border: string; text: string; glow: string }> = {
    emerald: { bg: "bg-emerald-500/10", border: "border-emerald-500/30", text: "text-emerald-400", glow: "shadow-emerald-500/20" },
    blue: { bg: "bg-blue-500/10", border: "border-blue-500/30", text: "text-blue-400", glow: "shadow-blue-500/20" },
    violet: { bg: "bg-violet-500/10", border: "border-violet-500/30", text: "text-violet-400", glow: "shadow-violet-500/20" },
    amber: { bg: "bg-amber-500/10", border: "border-amber-500/30", text: "text-amber-400", glow: "shadow-amber-500/20" },
  }
  
  const colors = colorClasses[section.color]

  return (
    <motion.button
      onClick={onClick}
      className={cn(
        "relative group text-left rounded-2xl border p-5 transition-all duration-300",
        isActive 
          ? cn(colors.bg, colors.border, "shadow-lg", colors.glow)
          : "bg-card/50 border-border hover:bg-secondary/50 hover:border-muted-foreground/20"
      )}
      whileHover={{ scale: 1.02, y: -2 }}
      whileTap={{ scale: 0.98 }}
    >
      {/* Progress indicator */}
      <div className="absolute top-0 left-0 right-0 h-1 rounded-t-2xl overflow-hidden bg-secondary">
        <motion.div
          className={cn(
            "h-full",
            section.color === "emerald" && "bg-emerald-500",
            section.color === "blue" && "bg-blue-500",
            section.color === "violet" && "bg-violet-500",
            section.color === "amber" && "bg-amber-500",
          )}
          initial={{ width: 0 }}
          animate={{ width: `${section.progress}%` }}
          transition={{ duration: 1, delay: 0.2 }}
        />
      </div>

      <div className="flex items-start gap-4">
        <div className={cn(
          "h-12 w-12 rounded-xl flex items-center justify-center shrink-0 transition-all",
          isActive ? colors.bg : "bg-secondary"
        )}>
          <Icon 
            name={section.icon as any} 
            size="md" 
            className={isActive ? colors.text : "text-muted-foreground"} 
          />
        </div>
        
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-1">
            <h4 className="font-semibold text-foreground">{section.title}</h4>
            {section.status === "complete" && (
              <motion.div
                initial={{ scale: 0 }}
                animate={{ scale: 1 }}
                className="h-4 w-4 rounded-full bg-emerald-500 flex items-center justify-center"
              >
                <Icon name="check" size="xs" className="text-white" />
              </motion.div>
            )}
          </div>
          <p className="text-xs text-muted-foreground mb-3">{section.description}</p>
          
          <div className="flex items-center gap-4 text-xs">
            <div className="flex items-center gap-1.5">
              <span className={cn("font-semibold", colors.text)}>{section.progress}%</span>
              <span className="text-muted-foreground">trained</span>
            </div>
            <div className="flex items-center gap-1.5">
              <Icon name="sparkles" size="xs" className="text-muted-foreground" />
              <span className="text-muted-foreground">{section.insights} insights</span>
            </div>
          </div>
        </div>
      </div>
    </motion.button>
  )
}

// Knowledge Source Row
function KnowledgeSourceRow({ source, index }: { source: KnowledgeSource; index: number }) {
  const statusColors = {
    connected: "bg-emerald-500",
    syncing: "bg-blue-500 animate-pulse",
    error: "bg-red-500",
  }

  return (
    <motion.div
      initial={{ opacity: 0, x: -20 }}
      animate={{ opacity: 1, x: 0 }}
      transition={{ delay: index * 0.1 }}
      className="group flex items-center gap-4 p-4 rounded-xl border border-border bg-card/50 hover:bg-secondary/50 transition-all"
    >
      <div className="h-10 w-10 rounded-lg bg-secondary flex items-center justify-center">
        <Icon name="database" size="sm" className="text-muted-foreground" />
      </div>
      
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2 mb-0.5">
          <h4 className="font-medium text-foreground">{source.name}</h4>
          <div className={cn("h-1.5 w-1.5 rounded-full", statusColors[source.status])} />
        </div>
        <div className="flex items-center gap-3 text-xs text-muted-foreground">
          <span>{source.itemCount.toLocaleString()} items</span>
          <span className="text-muted-foreground/50">|</span>
          <span>{source.lastSync}</span>
        </div>
      </div>

      {/* Coverage meter */}
      <div className="w-24">
        <div className="flex items-center justify-between mb-1">
          <span className="text-[10px] text-muted-foreground">Coverage</span>
          <span className="text-xs font-medium text-foreground">{source.coverage}%</span>
        </div>
        <div className="h-1.5 rounded-full bg-secondary overflow-hidden">
          <motion.div
            className="h-full bg-emerald-500"
            initial={{ width: 0 }}
            animate={{ width: `${source.coverage}%` }}
            transition={{ duration: 1, delay: 0.3 + index * 0.1 }}
          />
        </div>
      </div>

      <Button variant="ghost" size="sm" className="opacity-0 group-hover:opacity-100 transition-opacity">
        <Icon name="settings" size="sm" />
      </Button>
    </motion.div>
  )
}

// Chat Interface
function TrainingChat({ agentName }: { agentName: string }) {
  const [messages, setMessages] = useState<ChatMessage[]>([
    { id: "1", role: "system", content: `Training session started with ${agentName}. Teach me about your business.`, timestamp: "Just now" },
  ])
  const [input, setInput] = useState("")
  const [isTyping, setIsTyping] = useState(false)

  const handleSend = () => {
    if (!input.trim()) return
    
    const userMsg: ChatMessage = {
      id: Date.now().toString(),
      role: "user",
      content: input,
      timestamp: "Just now",
    }
    setMessages(prev => [...prev, userMsg])
    setInput("")
    setIsTyping(true)

    setTimeout(() => {
      const agentMsg: ChatMessage = {
        id: (Date.now() + 1).toString(),
        role: "agent",
        content: `Got it! I've learned that ${input.slice(0, 50)}... I'll incorporate this into my understanding of your business.`,
        timestamp: "Just now",
      }
      setMessages(prev => [...prev, agentMsg])
      setIsTyping(false)
    }, 1500)
  }

  return (
    <div className="flex flex-col h-[400px] rounded-2xl border border-border bg-card overflow-hidden">
      {/* Header */}
      <div className="flex items-center gap-3 px-4 py-3 border-b border-border bg-secondary/30">
        <div className="relative">
          <div className="h-8 w-8 rounded-lg bg-gradient-to-br from-emerald-500 to-teal-500 flex items-center justify-center">
            <Icon name="brain" size="sm" className="text-white" />
          </div>
          <div className="absolute -bottom-0.5 -right-0.5 h-2.5 w-2.5 rounded-full bg-emerald-500 border-2 border-card" />
        </div>
        <div>
          <h4 className="text-sm font-semibold text-foreground">Train {agentName}</h4>
          <p className="text-[10px] text-muted-foreground">Teach through conversation</p>
        </div>
        <div className="ml-auto flex items-center gap-1 px-2 py-1 rounded-full bg-emerald-500/10 text-emerald-400">
          <div className="h-1.5 w-1.5 rounded-full bg-emerald-500 animate-pulse" />
          <span className="text-[10px] font-medium">Learning</span>
        </div>
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        <AnimatePresence mode="popLayout">
          {messages.map((msg) => (
            <motion.div
              key={msg.id}
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0 }}
              className={cn(
                "flex gap-3",
                msg.role === "user" && "flex-row-reverse"
              )}
            >
              {msg.role !== "user" && (
                <div className={cn(
                  "h-7 w-7 rounded-lg flex items-center justify-center shrink-0",
                  msg.role === "agent" && "bg-gradient-to-br from-emerald-500 to-teal-500",
                  msg.role === "system" && "bg-secondary"
                )}>
                  <Icon 
                    name={msg.role === "agent" ? "brain" : "info"} 
                    size="xs" 
                    className={msg.role === "agent" ? "text-white" : "text-muted-foreground"} 
                  />
                </div>
              )}
              <div className={cn(
                "max-w-[80%] rounded-2xl px-4 py-2.5",
                msg.role === "user" && "bg-blue-500 text-white",
                msg.role === "agent" && "bg-secondary text-foreground",
                msg.role === "system" && "bg-secondary/50 text-muted-foreground text-xs italic"
              )}>
                <p className="text-sm">{msg.content}</p>
              </div>
            </motion.div>
          ))}
        </AnimatePresence>
        
        {isTyping && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            className="flex gap-3"
          >
            <div className="h-7 w-7 rounded-lg bg-gradient-to-br from-emerald-500 to-teal-500 flex items-center justify-center">
              <Icon name="brain" size="xs" className="text-white" />
            </div>
            <div className="bg-secondary rounded-2xl px-4 py-3">
              <div className="flex gap-1">
                {[0, 1, 2].map((i) => (
                  <motion.div
                    key={i}
                    className="h-2 w-2 rounded-full bg-muted-foreground"
                    animate={{ opacity: [0.3, 1, 0.3] }}
                    transition={{ duration: 1, repeat: Infinity, delay: i * 0.2 }}
                  />
                ))}
              </div>
            </div>
          </motion.div>
        )}
      </div>

      {/* Input */}
      <div className="p-4 border-t border-border bg-secondary/30">
        <div className="flex gap-2">
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && handleSend()}
            placeholder="Teach me something about your business..."
            className="flex-1 bg-background border border-border rounded-xl px-4 py-2.5 text-sm text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-emerald-500/50 focus:border-emerald-500"
          />
          <Button 
            onClick={handleSend}
            disabled={!input.trim()}
            className="bg-gradient-to-r from-emerald-500 to-teal-500 hover:from-emerald-600 hover:to-teal-600 text-white"
          >
            <Icon name="send" size="sm" />
          </Button>
        </div>
        <div className="flex items-center gap-4 mt-3">
          <button className="flex items-center gap-1.5 text-xs text-muted-foreground hover:text-foreground transition-colors">
            <Icon name="upload" size="xs" />
            Upload file
          </button>
          <button className="flex items-center gap-1.5 text-xs text-muted-foreground hover:text-foreground transition-colors">
            <Icon name="link" size="xs" />
            Add URL
          </button>
          <button className="flex items-center gap-1.5 text-xs text-muted-foreground hover:text-foreground transition-colors">
            <Icon name="database" size="xs" />
            Connect source
          </button>
        </div>
      </div>
    </div>
  )
}

function TrainingPageContent() {
  const router = useRouter()
  const searchParams = useSearchParams()
  const [selectedAgent, setSelectedAgent] = useState(agents[0])
  const [activeSection, setActiveSection] = useState("context")
  const [mounted, setMounted] = useState(false)
  const [agentDropdownOpen, setAgentDropdownOpen] = useState(false)
  const dropdownRef = useRef<HTMLDivElement>(null)

  // Close dropdown when clicking outside
  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
        setAgentDropdownOpen(false)
      }
    }
    document.addEventListener("mousedown", handleClickOutside)
    return () => document.removeEventListener("mousedown", handleClickOutside)
  }, [])

  useEffect(() => {
    setMounted(true)
    const agentId = searchParams.get("agent")
    if (agentId) {
      const agent = agents.find(a => a.id === agentId)
      if (agent) setSelectedAgent(agent)
    }
  }, [searchParams])

  const totalProgress = Math.round(trainingSections.reduce((sum, s) => sum + s.progress, 0) / trainingSections.length)

  if (!mounted) return null

  return (
    <AppShell title="Training Hub">
      <div className="relative min-h-full">
        <NeuralBackground />
        
        <div className="relative z-10 p-4 md:p-8">
          {/* Hero Header */}
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            className="mb-6 md:mb-8"
          >
            <div className="flex flex-col gap-4 md:flex-row md:items-start md:justify-between mb-6 md:mb-8">
              <div>
                <div className="flex items-center gap-3 mb-2">
                  <div className="h-9 w-9 md:h-10 md:w-10 rounded-xl bg-gradient-to-br from-emerald-500/20 to-teal-500/20 flex items-center justify-center ring-1 ring-emerald-500/20">
                    <Icon name="brain" size="md" className="text-emerald-400" />
                  </div>
                  <h1 className="text-xl md:text-2xl font-bold text-foreground">Training Hub</h1>
                </div>
                <p className="text-sm md:text-base text-muted-foreground max-w-lg">
                  Teach your AI agents about your business. The more they know, the better they perform.
                </p>
              </div>

              {/* Agent Selector */}
              <div className="flex items-center gap-4">
                <div className="flex items-center gap-2">
                  <span className="text-xs md:text-sm text-muted-foreground">Training:</span>
                  <div className="relative" ref={dropdownRef}>
                    <button
                      onClick={() => setAgentDropdownOpen(!agentDropdownOpen)}
                      className="flex items-center gap-2 px-2 md:px-3 py-1.5 md:py-2 rounded-xl bg-card border border-border hover:bg-secondary/50 transition-colors"
                    >
                      <div className={cn("h-5 w-5 md:h-6 md:w-6 rounded-lg bg-gradient-to-br flex items-center justify-center text-[9px] md:text-[10px] font-bold text-white", selectedAgent.gradient)}>
                        {selectedAgent.initials}
                      </div>
                      <span className="text-sm md:text-base font-medium text-foreground">{selectedAgent.name}</span>
                      <Icon 
                        name="chevronDown" 
                        size="sm" 
                        className={cn("text-muted-foreground transition-transform", agentDropdownOpen && "rotate-180")} 
                      />
                    </button>
                    
                    <AnimatePresence>
                      {agentDropdownOpen && (
                        <motion.div
                          initial={{ opacity: 0, y: -8, scale: 0.95 }}
                          animate={{ opacity: 1, y: 0, scale: 1 }}
                          exit={{ opacity: 0, y: -8, scale: 0.95 }}
                          transition={{ duration: 0.15 }}
                          className="absolute top-full right-0 mt-2 w-64 rounded-xl border border-border bg-card shadow-xl z-50 overflow-hidden"
                        >
                          <div className="p-2">
                            <p className="text-[10px] uppercase tracking-wider text-muted-foreground px-2 py-1.5">Select Agent</p>
                            {agents.map((agent) => (
                              <button
                                key={agent.id}
                                onClick={() => {
                                  setSelectedAgent(agent)
                                  setAgentDropdownOpen(false)
                                }}
                                className={cn(
                                  "w-full flex items-center gap-3 px-2 py-2.5 rounded-lg transition-colors text-left",
                                  selectedAgent.id === agent.id 
                                    ? "bg-emerald-500/10 text-foreground" 
                                    : "hover:bg-secondary/50 text-muted-foreground hover:text-foreground"
                                )}
                              >
                                <div className={cn("h-8 w-8 rounded-lg bg-gradient-to-br flex items-center justify-center text-[10px] font-bold text-white", agent.gradient)}>
                                  {agent.initials}
                                </div>
                                <div className="flex-1 min-w-0">
                                  <p className="font-medium text-sm">{agent.name}</p>
                                  <p className="text-xs text-muted-foreground truncate">{agent.role}</p>
                                </div>
                                {selectedAgent.id === agent.id && (
                                  <Icon name="check" size="sm" className="text-emerald-500 shrink-0" />
                                )}
                              </button>
                            ))}
                          </div>
                        </motion.div>
                      )}
                    </AnimatePresence>
                  </div>
                </div>
              </div>
            </div>

            {/* Stats Row */}
            <div className="grid grid-cols-2 md:grid-cols-4 gap-3 md:gap-4">
              {[
                { label: "Overall Progress", value: `${totalProgress}%`, icon: "chart", color: "emerald" },
                { label: "Knowledge Sources", value: knowledgeSources.length.toString(), icon: "database", color: "blue" },
                { label: "Total Insights", value: trainingSections.reduce((sum, s) => sum + s.insights, 0).toString(), icon: "sparkles", color: "violet" },
                { label: "Last Training", value: "2 hours ago", icon: "clock", color: "amber" },
              ].map((stat, i) => (
                <motion.div
                  key={stat.label}
                  initial={{ opacity: 0, y: 20 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ delay: i * 0.1 }}
                  className={cn(
                    "rounded-xl border p-4 transition-all",
                    "border-border bg-card/50 hover:bg-secondary/30"
                  )}
                >
                  <div className="flex items-center gap-3">
                    <div className={cn(
                      "h-10 w-10 rounded-lg flex items-center justify-center",
                      stat.color === "emerald" && "bg-emerald-500/10",
                      stat.color === "blue" && "bg-blue-500/10",
                      stat.color === "violet" && "bg-violet-500/10",
                      stat.color === "amber" && "bg-amber-500/10",
                    )}>
                      <Icon 
                        name={stat.icon as any} 
                        size="sm" 
                        className={cn(
                          stat.color === "emerald" && "text-emerald-400",
                          stat.color === "blue" && "text-blue-400",
                          stat.color === "violet" && "text-violet-400",
                          stat.color === "amber" && "text-amber-400",
                        )} 
                      />
                    </div>
                    <div>
                      <p className="text-xl font-bold text-foreground">{stat.value}</p>
                      <p className="text-xs text-muted-foreground">{stat.label}</p>
                    </div>
                  </div>
                </motion.div>
              ))}
            </div>
          </motion.div>

          {/* Main Content */}
          <div className="grid grid-cols-1 lg:grid-cols-12 gap-4 md:gap-6">
            {/* Left Column - Sections */}
            <div className="lg:col-span-4 space-y-3 md:space-y-4">
              <div className="flex items-center justify-between mb-2">
                <h3 className="text-sm md:text-base font-semibold text-foreground">Training Areas</h3>
                <span className="text-xs text-muted-foreground">{trainingSections.filter(s => s.status === "complete").length}/{trainingSections.length} complete</span>
              </div>
              
              {trainingSections.map((section) => (
                <SectionCard
                  key={section.id}
                  section={section}
                  isActive={activeSection === section.id}
                  onClick={() => setActiveSection(section.id)}
                />
              ))}
            </div>

            {/* Right Column - Detail Panel */}
            <div className="lg:col-span-8 space-y-4 md:space-y-6">
              <AnimatePresence mode="wait">
                {activeSection === "context" && (
                  <motion.div
                    key="context"
                    initial={{ opacity: 0, x: 20 }}
                    animate={{ opacity: 1, x: 0 }}
                    exit={{ opacity: 0, x: -20 }}
                  >
                    <TrainingChat agentName={selectedAgent.name} />
                  </motion.div>
                )}

                {activeSection === "knowledge" && (
                  <motion.div
                    key="knowledge"
                    initial={{ opacity: 0, x: 20 }}
                    animate={{ opacity: 1, x: 0 }}
                    exit={{ opacity: 0, x: -20 }}
                    className="space-y-4"
                  >
                    <div className="flex items-center justify-between">
                      <h3 className="font-semibold text-foreground">Connected Sources</h3>
                      <Button variant="outline" size="sm" className="gap-2">
                        <Icon name="add" size="sm" />
                        Add Source
                      </Button>
                    </div>
                    
                    <div className="space-y-3">
                      {knowledgeSources.map((source, i) => (
                        <KnowledgeSourceRow key={source.id} source={source} index={i} />
                      ))}
                    </div>
                  </motion.div>
                )}

                {activeSection === "examples" && (
                  <motion.div
                    key="examples"
                    initial={{ opacity: 0, x: 20 }}
                    animate={{ opacity: 1, x: 0 }}
                    exit={{ opacity: 0, x: -20 }}
                    className="rounded-2xl border border-dashed border-border p-12 text-center"
                  >
                    <div className="h-16 w-16 rounded-2xl bg-violet-500/10 flex items-center justify-center mx-auto mb-4">
                      <Icon name="upload" size="lg" className="text-violet-400" />
                    </div>
                    <h3 className="text-lg font-semibold text-foreground mb-2">Upload Historical Work</h3>
                    <p className="text-sm text-muted-foreground mb-6 max-w-md mx-auto">
                      Upload past campaigns, emails, reports, or any work samples to help your agent learn your style.
                    </p>
                    <Button className="gap-2 bg-gradient-to-r from-violet-500 to-purple-500 hover:from-violet-600 hover:to-purple-600 text-white border-0">
                      <Icon name="upload" size="sm" />
                      Upload Files
                    </Button>
                  </motion.div>
                )}

                {activeSection === "rules" && (
                  <motion.div
                    key="rules"
                    initial={{ opacity: 0, x: 20 }}
                    animate={{ opacity: 1, x: 0 }}
                    exit={{ opacity: 0, x: -20 }}
                    className="rounded-2xl border border-border bg-card p-6"
                  >
                    <h3 className="font-semibold text-foreground mb-4">Rules & Constraints</h3>
                    <div className="space-y-3">
                      {[
                        { rule: "Never share pricing unless explicitly approved", type: "restriction" },
                        { rule: "Always include compliance disclaimer in financial content", type: "compliance" },
                        { rule: "Maintain professional but friendly tone", type: "style" },
                        { rule: "Get approval for campaigns over $10k", type: "approval" },
                      ].map((item, i) => (
                        <motion.div
                          key={i}
                          initial={{ opacity: 0, x: -10 }}
                          animate={{ opacity: 1, x: 0 }}
                          transition={{ delay: i * 0.1 }}
                          className="flex items-center gap-3 p-3 rounded-xl bg-secondary/50"
                        >
                          <div className={cn(
                            "h-8 w-8 rounded-lg flex items-center justify-center",
                            item.type === "restriction" && "bg-red-500/10",
                            item.type === "compliance" && "bg-amber-500/10",
                            item.type === "style" && "bg-blue-500/10",
                            item.type === "approval" && "bg-violet-500/10",
                          )}>
                            <Icon 
                              name="shield" 
                              size="sm" 
                              className={cn(
                                item.type === "restriction" && "text-red-400",
                                item.type === "compliance" && "text-amber-400",
                                item.type === "style" && "text-blue-400",
                                item.type === "approval" && "text-violet-400",
                              )} 
                            />
                          </div>
                          <span className="text-sm text-foreground">{item.rule}</span>
                        </motion.div>
                      ))}
                    </div>
                    <Button variant="outline" size="sm" className="mt-4 gap-2">
                      <Icon name="add" size="sm" />
                      Add Rule
                    </Button>
                  </motion.div>
                )}
              </AnimatePresence>
            </div>
          </div>
        </div>
      </div>
    </AppShell>
  )
}

export default function TrainingPage() {
  return (
    <Suspense fallback={<AppShell title="Training Hub" />}>
      <TrainingPageContent />
    </Suspense>
  )
}
