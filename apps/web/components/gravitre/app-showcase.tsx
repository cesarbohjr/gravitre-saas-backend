"use client"

import { useState, useEffect, useRef } from "react"
import { motion, AnimatePresence, useScroll, useTransform } from "framer-motion"
import { Play, Pause, ChevronLeft, ChevronRight, Sparkles, Zap, Users, BarChart3, Workflow, Bot } from "lucide-react"
import { AgentAvatar, UserAvatar } from "./chat-avatars"

interface Feature {
  id: string
  title: string
  description: string
  icon: React.ElementType
  color: string
}

const features: Feature[] = [
  {
    id: "operator",
    title: "AI Operator",
    description: "Natural language interface to execute complex tasks across your entire tech stack.",
    icon: Bot,
    color: "emerald",
  },
  {
    id: "agents",
    title: "Smart Agents",
    description: "Pre-trained agents for marketing, sales, and ops that understand your business.",
    icon: Users,
    color: "blue",
  },
  {
    id: "workflows",
    title: "Workflow Builder",
    description: "Visual automation builder with approvals, conditions, and integrations.",
    icon: Workflow,
    color: "purple",
  },
  {
    id: "analytics",
    title: "Live Analytics",
    description: "Real-time metrics and insights on agent performance and task completion.",
    icon: BarChart3,
    color: "amber",
  },
]

// Mock app screen content based on feature
function AppScreen({ featureId }: { featureId: string }) {
  const colorMap: Record<string, string> = {
    operator: "emerald",
    agents: "blue",
    workflows: "purple",
    analytics: "amber",
  }
  
  const color = colorMap[featureId] || "emerald"
  
  return (
    <div className="h-full bg-zinc-950 rounded-lg overflow-hidden">
      {/* App Header */}
      <div className="flex items-center justify-between border-b border-zinc-800/50 px-4 py-3">
        <div className="flex items-center gap-3">
          <div className={`h-8 w-8 rounded-lg bg-${color}-500/20 flex items-center justify-center`}>
            <Sparkles className={`h-4 w-4 text-${color}-400`} />
          </div>
          <div>
            <div className="h-2 w-24 bg-zinc-700 rounded" />
            <div className="h-1.5 w-16 bg-zinc-800 rounded mt-1" />
          </div>
        </div>
        <div className="flex items-center gap-2">
          <div className="h-6 w-6 rounded-full bg-zinc-800" />
          <div className="h-6 w-6 rounded-full bg-zinc-800" />
        </div>
      </div>
      
      {/* App Content */}
      <div className="p-4 space-y-4">
        {/* Feature-specific content */}
        {featureId === "operator" && (
          <div className="space-y-3">
            {/* User message */}
            <motion.div 
              className="flex items-start gap-2 justify-end"
              initial={{ opacity: 0, x: 20 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ delay: 0.1 }}
            >
              <div className="max-w-[75%]">
                <div className="flex items-center gap-1.5 mb-1 justify-end">
                  <span className="text-[9px] text-zinc-500">Sarah Chen</span>
                  <span className="text-[8px] text-zinc-600">2m ago</span>
                </div>
                <div className="bg-emerald-600 text-white text-[10px] px-2.5 py-1.5 rounded-xl rounded-br-sm">
                  Why did the last customer sync fail?
                </div>
              </div>
              <UserAvatar name="Sarah Chen" size="xs" />
            </motion.div>
            
            {/* Agent response */}
            <motion.div 
              className="flex items-start gap-2"
              initial={{ opacity: 0, x: -20 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ delay: 0.3 }}
            >
              <AgentAvatar agent="operator" size="xs" showPulse />
              <div className="max-w-[75%]">
                <div className="flex items-center gap-1.5 mb-1">
                  <span className="text-[9px] text-emerald-400">AI Operator</span>
                  <span className="text-[8px] text-zinc-600">2m ago</span>
                </div>
                <div className="bg-zinc-800 text-zinc-200 text-[10px] px-2.5 py-1.5 rounded-xl rounded-bl-sm">
                  The sync failed at step 3 due to a connection timeout after 30s during peak hours.
                </div>
              </div>
            </motion.div>
            
            {/* User follow-up */}
            <motion.div 
              className="flex items-start gap-2 justify-end"
              initial={{ opacity: 0, x: 20 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ delay: 0.5 }}
            >
              <div className="max-w-[75%]">
                <div className="bg-emerald-600 text-white text-[10px] px-2.5 py-1.5 rounded-xl rounded-br-sm">
                  Can you fix it and retry?
                </div>
              </div>
              <UserAvatar name="Sarah Chen" size="xs" />
            </motion.div>
            
            {/* Agent typing indicator */}
            <motion.div 
              className="flex items-start gap-2"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              transition={{ delay: 0.7 }}
            >
              <AgentAvatar agent="operator" size="xs" showPulse />
              <div className="bg-zinc-800 text-zinc-400 text-[10px] px-3 py-2 rounded-xl rounded-bl-sm flex items-center gap-1">
                <motion.div className="h-1 w-1 rounded-full bg-zinc-500" animate={{ opacity: [0.4, 1, 0.4] }} transition={{ duration: 1, repeat: Infinity, delay: 0 }} />
                <motion.div className="h-1 w-1 rounded-full bg-zinc-500" animate={{ opacity: [0.4, 1, 0.4] }} transition={{ duration: 1, repeat: Infinity, delay: 0.2 }} />
                <motion.div className="h-1 w-1 rounded-full bg-zinc-500" animate={{ opacity: [0.4, 1, 0.4] }} transition={{ duration: 1, repeat: Infinity, delay: 0.4 }} />
              </div>
            </motion.div>
          </div>
        )}
        
        {featureId === "agents" && (
          <div className="space-y-3">
            {([
              { agent: "marketing" as const, name: "Marketing Agent", desc: "Campaign optimization", status: "Active" },
              { agent: "sales" as const, name: "Sales Agent", desc: "Lead qualification", status: "Ready" },
              { agent: "data" as const, name: "Data Agent", desc: "ETL pipelines", status: "Ready" },
            ]).map((item, i) => (
              <motion.div 
                key={i}
                className="flex items-center gap-3 p-3 rounded-lg border border-zinc-800 bg-zinc-900/50"
                initial={{ opacity: 0, x: -20 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ delay: i * 0.15 }}
              >
                <AgentAvatar agent={item.agent} size="sm" showPulse={i === 0} />
                <div className="flex-1 min-w-0">
                  <div className="text-[11px] font-medium text-white truncate">{item.name}</div>
                  <div className="text-[9px] text-zinc-500 truncate">{item.desc}</div>
                </div>
                <div className={`px-2 py-1 rounded-full text-[9px] font-medium shrink-0 ${i === 0 ? 'bg-emerald-500/20 text-emerald-400' : 'bg-zinc-700 text-zinc-400'}`}>
                  {item.status}
                </div>
              </motion.div>
            ))}
          </div>
        )}
        
        {featureId === "workflows" && (
          <div className="relative">
            {/* Workflow nodes */}
            <div className="flex items-center justify-between">
              {[1, 2, 3, 4].map((i) => (
                <motion.div
                  key={i}
                  className={`h-12 w-12 rounded-xl border ${i === 2 ? 'border-purple-500/50 bg-purple-500/10' : 'border-zinc-700 bg-zinc-800/50'} flex items-center justify-center`}
                  initial={{ scale: 0 }}
                  animate={{ scale: 1 }}
                  transition={{ delay: i * 0.1, type: "spring" }}
                >
                  <Zap className={`h-5 w-5 ${i === 2 ? 'text-purple-400' : 'text-zinc-500'}`} />
                </motion.div>
              ))}
            </div>
            {/* Connection lines */}
            <svg className="absolute top-6 left-12 right-12 h-1" style={{ width: 'calc(100% - 96px)' }}>
              <motion.line
                x1="0"
                y1="50%"
                x2="100%"
                y2="50%"
                stroke="rgb(113 113 122)"
                strokeWidth="2"
                strokeDasharray="8 4"
                initial={{ pathLength: 0 }}
                animate={{ pathLength: 1 }}
                transition={{ duration: 1, delay: 0.5 }}
              />
            </svg>
          </div>
        )}
        
        {featureId === "analytics" && (
          <div className="space-y-4">
            {/* Chart bars */}
            <div className="flex items-end justify-between h-24 gap-2">
              {[40, 65, 45, 80, 55, 70, 90].map((height, i) => (
                <motion.div
                  key={i}
                  className="flex-1 bg-gradient-to-t from-amber-500 to-amber-400 rounded-t"
                  initial={{ height: 0 }}
                  animate={{ height: `${height}%` }}
                  transition={{ delay: i * 0.1, duration: 0.5 }}
                />
              ))}
            </div>
            {/* Stats row */}
            <div className="grid grid-cols-3 gap-3">
              {[
                { label: "Success", value: "98.5%" },
                { label: "Tasks", value: "1,234" },
                { label: "Saved", value: "42h" },
              ].map((stat, i) => (
                <div key={i} className="p-2 rounded-lg bg-zinc-800/50 text-center">
                  <div className="text-xs text-zinc-500">{stat.label}</div>
                  <div className="text-sm font-semibold text-white">{stat.value}</div>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  )
}

export function AppShowcase() {
  const [activeFeature, setActiveFeature] = useState(0)
  const [isAutoPlaying, setIsAutoPlaying] = useState(true)
  const containerRef = useRef<HTMLDivElement>(null)
  
  const { scrollYProgress } = useScroll({
    target: containerRef,
    offset: ["start end", "end start"]
  })
  
  const y = useTransform(scrollYProgress, [0, 1], [50, -50])
  const opacity = useTransform(scrollYProgress, [0, 0.2, 0.8, 1], [0, 1, 1, 0])

  useEffect(() => {
    if (!isAutoPlaying) return
    
    const interval = setInterval(() => {
      setActiveFeature((prev) => (prev + 1) % features.length)
    }, 4000)
    
    return () => clearInterval(interval)
  }, [isAutoPlaying])

  const currentFeature = features[activeFeature]

  return (
    <motion.div 
      ref={containerRef}
      style={{ opacity }}
      className="relative"
    >
      {/* Background glow */}
      <div className={`absolute -inset-20 bg-${currentFeature.color}-500/10 blur-3xl rounded-full transition-colors duration-500`} />
      
      <div className="relative grid lg:grid-cols-2 gap-8 lg:gap-12 items-center">
        {/* Feature list */}
        <div className="space-y-4">
          {features.map((feature, index) => {
            const Icon = feature.icon
            const isActive = index === activeFeature
            
            return (
              <motion.button
                key={feature.id}
                onClick={() => {
                  setActiveFeature(index)
                  setIsAutoPlaying(false)
                }}
                className={`w-full text-left p-4 rounded-2xl border transition-all duration-300 ${
                  isActive
                    ? `border-${feature.color}-500/50 bg-${feature.color}-500/10`
                    : "border-white/10 bg-white/5 hover:border-white/20 hover:bg-white/10"
                }`}
                style={isActive ? { 
                  borderColor: `rgb(${feature.color === 'emerald' ? '16 185 129' : feature.color === 'blue' ? '59 130 246' : feature.color === 'purple' ? '168 85 247' : '245 158 11'} / 0.5)`,
                  backgroundColor: `rgb(${feature.color === 'emerald' ? '16 185 129' : feature.color === 'blue' ? '59 130 246' : feature.color === 'purple' ? '168 85 247' : '245 158 11'} / 0.1)`
                } : {}}
                whileHover={{ scale: 1.02 }}
                whileTap={{ scale: 0.98 }}
              >
                <div className="flex items-start gap-4">
                  <div className={`h-12 w-12 rounded-xl flex items-center justify-center transition-colors ${
                    isActive 
                      ? `bg-${feature.color}-500/20` 
                      : "bg-zinc-800"
                  }`}
                  style={isActive ? { backgroundColor: `rgb(${feature.color === 'emerald' ? '16 185 129' : feature.color === 'blue' ? '59 130 246' : feature.color === 'purple' ? '168 85 247' : '245 158 11'} / 0.2)` } : {}}
                  >
                    <Icon className={`h-6 w-6 transition-colors ${
                      isActive 
                        ? `text-${feature.color}-400` 
                        : "text-zinc-500"
                    }`}
                    style={isActive ? { color: `rgb(${feature.color === 'emerald' ? '52 211 153' : feature.color === 'blue' ? '96 165 250' : feature.color === 'purple' ? '192 132 252' : '251 191 36'})` } : {}}
                    />
                  </div>
                  <div className="flex-1">
                    <h3 className={`font-semibold transition-colors ${
                      isActive ? "text-white" : "text-zinc-400"
                    }`}>
                      {feature.title}
                    </h3>
                    <p className={`mt-1 text-sm transition-colors ${
                      isActive ? "text-zinc-300" : "text-zinc-500"
                    }`}>
                      {feature.description}
                    </p>
                  </div>
                  {isActive && (
                    <motion.div
                      layoutId="activeIndicator"
                      className={`h-full w-1 rounded-full bg-${feature.color}-500`}
                      style={{ backgroundColor: `rgb(${feature.color === 'emerald' ? '16 185 129' : feature.color === 'blue' ? '59 130 246' : feature.color === 'purple' ? '168 85 247' : '245 158 11'})` }}
                    />
                  )}
                </div>
              </motion.button>
            )
          })}
          
          {/* Progress indicators */}
          <div className="flex items-center gap-2 pt-4">
            {features.map((_, index) => (
              <button
                key={index}
                onClick={() => {
                  setActiveFeature(index)
                  setIsAutoPlaying(false)
                }}
                className="relative h-1 flex-1 bg-zinc-800 rounded-full overflow-hidden"
              >
                {index === activeFeature && isAutoPlaying && (
                  <motion.div
                    className={`absolute inset-y-0 left-0 bg-${currentFeature.color}-500`}
                    style={{ backgroundColor: `rgb(${currentFeature.color === 'emerald' ? '16 185 129' : currentFeature.color === 'blue' ? '59 130 246' : currentFeature.color === 'purple' ? '168 85 247' : '245 158 11'})` }}
                    initial={{ width: "0%" }}
                    animate={{ width: "100%" }}
                    transition={{ duration: 4, ease: "linear" }}
                  />
                )}
                {index <= activeFeature && !isAutoPlaying && (
                  <div 
                    className={`absolute inset-0 bg-${currentFeature.color}-500`}
                    style={{ backgroundColor: `rgb(${features[index].color === 'emerald' ? '16 185 129' : features[index].color === 'blue' ? '59 130 246' : features[index].color === 'purple' ? '168 85 247' : '245 158 11'})` }}
                  />
                )}
              </button>
            ))}
            <button
              onClick={() => setIsAutoPlaying(!isAutoPlaying)}
              className="ml-2 p-2 rounded-full bg-zinc-800 hover:bg-zinc-700 transition-colors"
            >
              {isAutoPlaying ? (
                <Pause className="h-4 w-4 text-zinc-400" />
              ) : (
                <Play className="h-4 w-4 text-zinc-400" />
              )}
            </button>
          </div>
        </div>

        {/* App preview */}
        <motion.div style={{ y }} className="relative">
          <div className="relative rounded-2xl border border-white/10 bg-zinc-900/80 p-2 shadow-2xl backdrop-blur-xl overflow-hidden">
            {/* Browser chrome */}
            <div className="flex items-center gap-2 border-b border-zinc-800 px-4 py-3">
              <div className="flex gap-1.5">
                <div className="h-3 w-3 rounded-full bg-red-500/80" />
                <div className="h-3 w-3 rounded-full bg-yellow-500/80" />
                <div className="h-3 w-3 rounded-full bg-green-500/80" />
              </div>
              <div className="flex-1 text-center">
                <span className="text-xs text-zinc-500 font-mono">app.gravitre.com/{currentFeature.id}</span>
              </div>
            </div>
            
            {/* App content with animation */}
            <AnimatePresence mode="wait">
              <motion.div
                key={currentFeature.id}
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -20 }}
                transition={{ duration: 0.3 }}
                className="aspect-[4/3]"
              >
                <AppScreen featureId={currentFeature.id} />
              </motion.div>
            </AnimatePresence>
          </div>
          
          {/* Floating badge */}
          <motion.div
            className={`absolute -top-4 -right-4 px-3 py-1.5 rounded-full bg-${currentFeature.color}-500 text-white text-xs font-semibold shadow-lg`}
            style={{ backgroundColor: `rgb(${currentFeature.color === 'emerald' ? '16 185 129' : currentFeature.color === 'blue' ? '59 130 246' : currentFeature.color === 'purple' ? '168 85 247' : '245 158 11'})` }}
            initial={{ scale: 0 }}
            animate={{ scale: 1 }}
            transition={{ type: "spring", delay: 0.2 }}
          >
            Live Preview
          </motion.div>
        </motion.div>
      </div>
    </motion.div>
  )
}

// Simple screenshot component with parallax
export function ProductScreenshot({ 
  className = "",
  caption = ""
}: { 
  className?: string
  caption?: string
}) {
  const ref = useRef<HTMLDivElement>(null)
  const { scrollYProgress } = useScroll({
    target: ref,
    offset: ["start end", "end start"]
  })
  
  const y = useTransform(scrollYProgress, [0, 1], [60, -60])
  const opacity = useTransform(scrollYProgress, [0, 0.2, 0.8, 1], [0, 1, 1, 0])

  return (
    <motion.div 
      ref={ref}
      style={{ y, opacity }}
      className={`relative ${className}`}
    >
      <div className="absolute -inset-4 rounded-3xl bg-gradient-to-b from-emerald-500/20 via-transparent to-transparent blur-2xl" />
      <div className="relative rounded-2xl border border-white/10 bg-zinc-900/80 p-2 shadow-2xl backdrop-blur-xl overflow-hidden">
        {/* Browser chrome */}
        <div className="flex items-center gap-2 border-b border-zinc-800 px-4 py-3">
          <div className="flex gap-1.5">
            <div className="h-3 w-3 rounded-full bg-red-500/80" />
            <div className="h-3 w-3 rounded-full bg-yellow-500/80" />
            <div className="h-3 w-3 rounded-full bg-green-500/80" />
          </div>
          <div className="flex-1 text-center">
            <span className="text-xs text-zinc-500 font-mono">app.gravitre.com</span>
          </div>
        </div>
        
        {/* Placeholder for actual screenshot */}
        <div className="aspect-[16/9] bg-gradient-to-br from-zinc-900 to-zinc-950 flex items-center justify-center">
          <div className="text-center text-zinc-600">
            <Sparkles className="h-12 w-12 mx-auto mb-2" />
            <p className="text-sm">App Screenshot</p>
          </div>
        </div>
      </div>
      
      {caption && (
        <p className="mt-4 text-center text-sm text-zinc-500">{caption}</p>
      )}
    </motion.div>
  )
}
