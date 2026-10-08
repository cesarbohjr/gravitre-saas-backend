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
    title: "Gravitre AI",
    description: "Natural language interface to execute complex tasks across your entire tech stack.",
    icon: Bot,
    color: "emerald",
  },
  {
    id: "agents",
    title: "Smart agents",
    description: "Pre-trained agents for marketing, sales, and ops that understand your business.",
    icon: Users,
    color: "blue",
  },
  {
    id: "workflows",
    title: "Workflow builder",
    description: "Visual automation builder with approvals, conditions, and integrations.",
    icon: Workflow,
    color: "purple",
  },
  {
    id: "analytics",
    title: "Live analytics",
    description: "Real-time metrics and insights on agent performance and task completion.",
    icon: BarChart3,
    color: "amber",
  },
]

// Feature accents resolve to global theme tokens so the showcase follows light/dark themes.
const toneVar: Record<string, string> = {
  emerald: "var(--brand)",
  blue: "var(--info)",
  purple: "var(--g-intelligence)",
  amber: "var(--warning)",
}

function tone(color: string, percent?: number) {
  const base = toneVar[color] ?? toneVar.emerald
  return percent === undefined ? base : `color-mix(in srgb, ${base} ${percent}%, transparent)`
}

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
    <div className="h-full bg-card rounded-lg overflow-hidden">
      {/* App Header */}
      <div className="flex items-center justify-between border-b border-border/50 px-4 py-3">
        <div className="flex items-center gap-3">
          <div className="h-8 w-8 rounded-lg flex items-center justify-center" style={{ backgroundColor: tone(color, 20) }}>
            <Sparkles className="h-4 w-4" style={{ color: tone(color) }} />
          </div>
          <div>
            <div className="h-2 w-24 bg-muted-foreground/40 rounded" />
            <div className="h-1.5 w-16 bg-muted rounded mt-1" />
          </div>
        </div>
        <div className="flex items-center gap-2">
          <div className="h-6 w-6 rounded-full bg-muted" />
          <div className="h-6 w-6 rounded-full bg-muted" />
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
                  <span className="text-[9px] text-muted-foreground">Sarah Chen</span>
                  <span className="text-[8px] text-muted-foreground/80">2m ago</span>
                </div>
                <div className="bg-brand text-brand-foreground text-[10px] px-2.5 py-1.5 rounded-xl rounded-br-sm">
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
                  <span className="text-[9px] text-brand-text">Gravitre AI</span>
                  <span className="text-[8px] text-muted-foreground/80">2m ago</span>
                </div>
                <div className="bg-muted text-foreground text-[10px] px-2.5 py-1.5 rounded-xl rounded-bl-sm">
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
                <div className="bg-brand text-brand-foreground text-[10px] px-2.5 py-1.5 rounded-xl rounded-br-sm">
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
              <div className="bg-muted text-muted-foreground text-[10px] px-3 py-2 rounded-xl rounded-bl-sm flex items-center gap-1">
                <motion.div className="h-1 w-1 rounded-full bg-muted-foreground" animate={{ opacity: [0.4, 1, 0.4] }} transition={{ duration: 1, repeat: Infinity, delay: 0 }} />
                <motion.div className="h-1 w-1 rounded-full bg-muted-foreground" animate={{ opacity: [0.4, 1, 0.4] }} transition={{ duration: 1, repeat: Infinity, delay: 0.2 }} />
                <motion.div className="h-1 w-1 rounded-full bg-muted-foreground" animate={{ opacity: [0.4, 1, 0.4] }} transition={{ duration: 1, repeat: Infinity, delay: 0.4 }} />
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
                className="flex items-center gap-3 p-3 rounded-lg border border-border bg-secondary/50"
                initial={{ opacity: 0, x: -20 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ delay: i * 0.15 }}
              >
                <AgentAvatar agent={item.agent} size="sm" showPulse={i === 0} />
                <div className="flex-1 min-w-0">
                  <div className="text-[11px] font-medium text-foreground truncate">{item.name}</div>
                  <div className="text-[9px] text-muted-foreground truncate">{item.desc}</div>
                </div>
                <div className={`px-2 py-1 rounded-full text-[9px] font-medium shrink-0 ${i === 0 ? 'bg-success/20 text-success-text' : 'bg-muted text-muted-foreground'}`}>
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
                  className={`h-12 w-12 rounded-xl border ${i === 2 ? 'border-[color:var(--g-intelligence)]/50 bg-[color:var(--g-intelligence)]/10' : 'border-border bg-muted/50'} flex items-center justify-center`}
                  initial={{ scale: 0 }}
                  animate={{ scale: 1 }}
                  transition={{ delay: i * 0.1, type: "spring" }}
                >
                  <Zap className={`h-5 w-5 ${i === 2 ? 'text-intelligence-text' : 'text-muted-foreground'}`} />
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
                stroke="var(--g-text-muted)"
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
                  className="flex-1 bg-gradient-to-t from-warning to-warning/80 rounded-t"
                  initial={{ height: 0 }}
                  animate={{ height: `${height}%` }}
                  transition={{ delay: i * 0.1, duration: 0.5 }}
                />
              ))}
            </div>
            {/* Stats row */}
            <div className="grid grid-cols-3 gap-3">
              {[
                { label: "Success", value: "Live ops" },
                { label: "Tasks", value: "Tracked" },
                { label: "Hours saved", value: "Estimate" },
              ].map((stat, i) => (
                <div key={i} className="p-2 rounded-lg bg-muted/50 text-center">
                  <div className="text-xs text-muted-foreground">{stat.label}</div>
                  <div className="text-sm font-semibold text-foreground">{stat.value}</div>
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
      <div className="absolute -inset-20 blur-3xl rounded-full transition-colors duration-500" style={{ backgroundColor: tone(currentFeature.color, 10) }} />
      
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
                    ? ""
                    : "border-border bg-muted/30 hover:border-border hover:bg-muted/60"
                }`}
                style={isActive ? { 
                  borderColor: tone(feature.color, 50),
                  backgroundColor: tone(feature.color, 10)
                } : {}}
                whileHover={{ scale: 1.02 }}
                whileTap={{ scale: 0.98 }}
              >
                <div className="flex items-start gap-4">
                  <div className={`h-12 w-12 rounded-xl flex items-center justify-center transition-colors ${
                    isActive 
                      ? "" 
                      : "bg-muted"
                  }`}
                  style={isActive ? { backgroundColor: tone(feature.color, 20) } : {}}
                  >
                    <Icon className={`h-6 w-6 transition-colors ${
                      isActive 
                        ? "" 
                        : "text-muted-foreground"
                    }`}
                    style={isActive ? { color: tone(feature.color) } : {}}
                    />
                  </div>
                  <div className="flex-1">
                    <h3 className={`font-semibold transition-colors ${
                      isActive ? "text-foreground" : "text-muted-foreground"
                    }`}>
                      {feature.title}
                    </h3>
                    <p className={`mt-1 text-sm transition-colors ${
                      isActive ? "text-muted-foreground" : "text-muted-foreground/80"
                    }`}>
                      {feature.description}
                    </p>
                  </div>
                  {isActive && (
                    <motion.div
                      layoutId="activeIndicator"
                      className="h-full w-1 rounded-full"
                      style={{ backgroundColor: tone(feature.color) }}
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
                className="relative h-1 flex-1 bg-muted rounded-full overflow-hidden"
              >
                {index === activeFeature && isAutoPlaying && (
                  <motion.div
                    className="absolute inset-y-0 left-0"
                    style={{ backgroundColor: tone(currentFeature.color) }}
                    initial={{ width: "0%" }}
                    animate={{ width: "100%" }}
                    transition={{ duration: 4, ease: "linear" }}
                  />
                )}
                {index <= activeFeature && !isAutoPlaying && (
                  <div 
                    className="absolute inset-0"
                    style={{ backgroundColor: tone(features[index].color) }}
                  />
                )}
              </button>
            ))}
            <button
              onClick={() => setIsAutoPlaying(!isAutoPlaying)}
              className="ml-2 p-2 rounded-full bg-muted hover:bg-secondary transition-colors"
            >
              {isAutoPlaying ? (
                <Pause className="h-4 w-4 text-muted-foreground" />
              ) : (
                <Play className="h-4 w-4 text-muted-foreground" />
              )}
            </button>
          </div>
        </div>

        {/* App preview */}
        <motion.div style={{ y }} className="relative">
          <div className="relative rounded-2xl border border-border bg-card/80 p-2 shadow-2xl backdrop-blur-xl overflow-hidden">
            {/* Browser chrome */}
            <div className="flex items-center gap-2 border-b border-border px-4 py-3">
              <div className="flex gap-1.5">
                <div className="h-3 w-3 rounded-full bg-destructive/80" />
                <div className="h-3 w-3 rounded-full bg-warning/80" />
                <div className="h-3 w-3 rounded-full bg-success/80" />
              </div>
              <div className="flex-1 text-center">
                <span className="text-xs text-muted-foreground font-mono">gravitre.app/{currentFeature.id}</span>
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
            className="absolute -top-4 -right-4 px-3 py-1.5 rounded-full bg-[color:var(--brand)] text-background text-xs font-semibold shadow-lg"
            style={{ backgroundColor: tone(currentFeature.color) }}
            initial={{ scale: 0 }}
            animate={{ scale: 1 }}
            transition={{ type: "spring", delay: 0.2 }}
          >
            Live preview
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
      <div className="absolute -inset-4 rounded-3xl bg-gradient-to-b from-brand/20 via-transparent to-transparent blur-2xl" />
      <div className="relative rounded-2xl border border-border bg-card/80 p-2 shadow-2xl backdrop-blur-xl overflow-hidden">
        {/* Browser chrome */}
        <div className="flex items-center gap-2 border-b border-border px-4 py-3">
          <div className="flex gap-1.5">
            <div className="h-3 w-3 rounded-full bg-destructive/80" />
            <div className="h-3 w-3 rounded-full bg-warning/80" />
            <div className="h-3 w-3 rounded-full bg-success/80" />
          </div>
          <div className="flex-1 text-center">
            <span className="text-xs text-muted-foreground font-mono">gravitre.app</span>
          </div>
        </div>
        
        {/* Placeholder for actual screenshot */}
        <div className="aspect-[16/9] bg-gradient-to-br from-secondary to-card flex items-center justify-center">
          <div className="text-center text-muted-foreground">
            <Sparkles className="h-12 w-12 mx-auto mb-2" />
            <p className="text-sm">App screenshot</p>
          </div>
        </div>
      </div>
      
      {caption && (
        <p className="mt-4 text-center text-sm text-muted-foreground">{caption}</p>
      )}
    </motion.div>
  )
}
