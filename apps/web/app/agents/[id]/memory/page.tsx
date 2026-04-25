"use client"

import { useState, use } from "react"
import Link from "next/link"
import { motion, AnimatePresence } from "framer-motion"
import { AppShell } from "@/components/gravitre/app-shell"
import { Button } from "@/components/ui/button"
import { Icon } from "@/lib/icons"
import { cn } from "@/lib/utils"

// Types
interface Memory {
  id: string
  content: string
  category: "fact" | "preference" | "pattern" | "rule"
  source: string
  confidence: number
  createdAt: string
  usageCount: number
  editable: boolean
}

// Mock Data
const memories: Memory[] = [
  { id: "mem-1", content: "Primary ICP is mid-market B2B SaaS companies with 50-500 employees", category: "fact", source: "Training Session", confidence: 98, createdAt: "2 weeks ago", usageCount: 47, editable: true },
  { id: "mem-2", content: "Brand voice should be professional but approachable, avoiding jargon", category: "preference", source: "Brand Guidelines", confidence: 95, createdAt: "1 month ago", usageCount: 156, editable: true },
  { id: "mem-3", content: "Email campaigns perform 23% better when sent on Tuesday mornings", category: "pattern", source: "Performance Analysis", confidence: 87, createdAt: "1 week ago", usageCount: 12, editable: true },
  { id: "mem-4", content: "Always include compliance disclaimer in financial-related content", category: "rule", source: "Compliance Training", confidence: 100, createdAt: "2 months ago", usageCount: 89, editable: false },
  { id: "mem-5", content: "Healthcare vertical requires HIPAA-compliant messaging", category: "rule", source: "Vertical Training", confidence: 100, createdAt: "3 weeks ago", usageCount: 34, editable: false },
  { id: "mem-6", content: "Competitor Acme Corp focuses on enterprise segment, not direct competition", category: "fact", source: "Competitive Analysis", confidence: 91, createdAt: "1 week ago", usageCount: 8, editable: true },
  { id: "mem-7", content: "Users prefer shorter email subject lines (under 50 characters)", category: "pattern", source: "A/B Test Results", confidence: 82, createdAt: "3 days ago", usageCount: 5, editable: true },
  { id: "mem-8", content: "Quarterly reports should include YoY comparison by default", category: "preference", source: "User Feedback", confidence: 88, createdAt: "2 weeks ago", usageCount: 23, editable: true },
]

const categoryConfig = {
  fact: { label: "Fact", icon: "database", color: "blue", glow: "shadow-blue-500/20" },
  preference: { label: "Preference", icon: "heart", color: "rose", glow: "shadow-rose-500/20" },
  pattern: { label: "Pattern", icon: "sparkles", color: "violet", glow: "shadow-violet-500/20" },
  rule: { label: "Rule", icon: "shield", color: "amber", glow: "shadow-amber-500/20" },
}

const agent = {
  id: "agent-001",
  name: "Atlas",
  role: "Marketing Agent",
  gradient: "from-emerald-500 to-teal-500",
}

// Neural Network Brain Visualization
function BrainVisualization() {
  return (
    <div className="relative h-48 flex items-center justify-center">
      {/* Orbiting rings */}
      {[0, 1, 2].map((i) => (
        <motion.div
          key={i}
          className="absolute rounded-full border border-emerald-500/20"
          style={{
            width: 120 + i * 60,
            height: 120 + i * 60,
          }}
          animate={{ rotate: 360 }}
          transition={{
            duration: 20 + i * 10,
            repeat: Infinity,
            ease: "linear",
            direction: i % 2 === 0 ? "normal" : "reverse",
          }}
        >
          {/* Orbiting dots */}
          <motion.div
            className="absolute h-2 w-2 rounded-full bg-emerald-500"
            style={{
              top: "50%",
              left: -4,
              transform: "translateY(-50%)",
            }}
            animate={{ opacity: [0.3, 1, 0.3] }}
            transition={{ duration: 2, repeat: Infinity, delay: i * 0.3 }}
          />
        </motion.div>
      ))}

      {/* Central brain */}
      <motion.div
        className="relative z-10 h-24 w-24 rounded-2xl bg-gradient-to-br from-emerald-500 to-teal-500 flex items-center justify-center shadow-2xl shadow-emerald-500/30"
        animate={{
          boxShadow: [
            "0 0 40px rgba(16, 185, 129, 0.3)",
            "0 0 60px rgba(16, 185, 129, 0.5)",
            "0 0 40px rgba(16, 185, 129, 0.3)",
          ],
        }}
        transition={{ duration: 3, repeat: Infinity }}
      >
        <Icon name="brain" size="xl" className="text-white" />
        
        {/* Pulse effect */}
        <motion.div
          className="absolute inset-0 rounded-2xl bg-gradient-to-br from-emerald-500 to-teal-500"
          animate={{ scale: [1, 1.2, 1], opacity: [0.5, 0, 0.5] }}
          transition={{ duration: 2, repeat: Infinity }}
        />
      </motion.div>

      {/* Floating memory nodes */}
      {[
        { x: -80, y: -40, delay: 0, color: "blue" },
        { x: 80, y: -30, delay: 0.2, color: "rose" },
        { x: -70, y: 50, delay: 0.4, color: "violet" },
        { x: 90, y: 40, delay: 0.6, color: "amber" },
      ].map((node, i) => (
        <motion.div
          key={i}
          className={cn(
            "absolute h-4 w-4 rounded-full",
            node.color === "blue" && "bg-blue-500",
            node.color === "rose" && "bg-rose-500",
            node.color === "violet" && "bg-violet-500",
            node.color === "amber" && "bg-amber-500",
          )}
          style={{ x: node.x, y: node.y }}
          animate={{
            y: [node.y - 5, node.y + 5, node.y - 5],
            opacity: [0.5, 1, 0.5],
          }}
          transition={{ duration: 3, repeat: Infinity, delay: node.delay }}
        />
      ))}
    </div>
  )
}

// Stat Card with Glow
function StatCard({ label, value, icon, color, suffix }: { label: string; value: string | number; icon: string; color: string; suffix?: string }) {
  return (
    <motion.div
      initial={{ opacity: 0, scale: 0.95 }}
      animate={{ opacity: 1, scale: 1 }}
      className={cn(
        "relative overflow-hidden rounded-2xl border p-5",
        "bg-card/50 border-border backdrop-blur-sm"
      )}
    >
      <div className="absolute -top-8 -right-8 h-24 w-24 rounded-full opacity-20" style={{
        background: color === "emerald" ? "radial-gradient(circle, #10b981 0%, transparent 70%)" :
                   color === "blue" ? "radial-gradient(circle, #3b82f6 0%, transparent 70%)" :
                   color === "violet" ? "radial-gradient(circle, #8b5cf6 0%, transparent 70%)" :
                   "radial-gradient(circle, #f59e0b 0%, transparent 70%)"
      }} />
      
      <div className={cn(
        "h-10 w-10 rounded-xl flex items-center justify-center mb-3",
        color === "emerald" && "bg-emerald-500/10",
        color === "blue" && "bg-blue-500/10",
        color === "violet" && "bg-violet-500/10",
        color === "amber" && "bg-amber-500/10",
      )}>
        <Icon 
          name={icon as any} 
          size="sm" 
          className={cn(
            color === "emerald" && "text-emerald-400",
            color === "blue" && "text-blue-400",
            color === "violet" && "text-violet-400",
            color === "amber" && "text-amber-400",
          )} 
        />
      </div>
      <p className="text-3xl font-bold text-foreground">
        {value}
        {suffix && <span className="text-lg text-muted-foreground ml-0.5">{suffix}</span>}
      </p>
      <p className="text-sm text-muted-foreground">{label}</p>
    </motion.div>
  )
}

// Memory Card with Rich Interactions
function MemoryCard({ memory, index, onEdit, onDelete }: { 
  memory: Memory; 
  index: number; 
  onEdit: (m: Memory) => void;
  onDelete: (id: string) => void;
}) {
  const category = categoryConfig[memory.category]
  const [isHovered, setIsHovered] = useState(false)

  const colorClasses: Record<string, { bg: string; border: string; text: string; ring: string }> = {
    blue: { bg: "bg-blue-500/10", border: "border-blue-500/30", text: "text-blue-400", ring: "ring-blue-500/20" },
    rose: { bg: "bg-rose-500/10", border: "border-rose-500/30", text: "text-rose-400", ring: "ring-rose-500/20" },
    violet: { bg: "bg-violet-500/10", border: "border-violet-500/30", text: "text-violet-400", ring: "ring-violet-500/20" },
    amber: { bg: "bg-amber-500/10", border: "border-amber-500/30", text: "text-amber-400", ring: "ring-amber-500/20" },
  }

  const colors = colorClasses[category.color]

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: index * 0.05 }}
      onHoverStart={() => setIsHovered(true)}
      onHoverEnd={() => setIsHovered(false)}
      className={cn(
        "group relative rounded-2xl border p-5 transition-all duration-300",
        "bg-card/50 border-border hover:border-muted-foreground/30",
        isHovered && "shadow-lg shadow-black/10"
      )}
    >
      {/* Animated border gradient on hover */}
      <motion.div
        className={cn(
          "absolute inset-0 rounded-2xl opacity-0 transition-opacity",
          colors.ring, "ring-2"
        )}
        animate={{ opacity: isHovered ? 1 : 0 }}
      />

      {/* Category badge */}
      <div className="flex items-start justify-between mb-3">
        <div className={cn(
          "flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium",
          colors.bg, colors.text
        )}>
          <Icon name={category.icon as any} size="xs" />
          {category.label}
        </div>
        
        {/* Confidence ring */}
        <div className="relative h-10 w-10">
          <svg className="h-10 w-10 -rotate-90">
            <circle
              cx="20"
              cy="20"
              r="16"
              fill="none"
              stroke="currentColor"
              strokeWidth="3"
              className="text-secondary"
            />
            <motion.circle
              cx="20"
              cy="20"
              r="16"
              fill="none"
              stroke={memory.confidence >= 90 ? "#10b981" : memory.confidence >= 70 ? "#f59e0b" : "#ef4444"}
              strokeWidth="3"
              strokeLinecap="round"
              strokeDasharray={100}
              initial={{ strokeDashoffset: 100 }}
              animate={{ strokeDashoffset: 100 - memory.confidence }}
              transition={{ duration: 1, delay: index * 0.05 }}
            />
          </svg>
          <span className="absolute inset-0 flex items-center justify-center text-[10px] font-bold text-foreground">
            {memory.confidence}
          </span>
        </div>
      </div>

      {/* Content */}
      <p className="text-sm text-foreground leading-relaxed mb-4 pr-4">{memory.content}</p>

      {/* Meta row */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-4 text-xs text-muted-foreground">
          <div className="flex items-center gap-1.5">
            <Icon name="link" size="xs" />
            <span>{memory.source}</span>
          </div>
          <div className="flex items-center gap-1.5">
            <Icon name="activity" size="xs" />
            <span>Used {memory.usageCount}x</span>
          </div>
          <div className="flex items-center gap-1.5">
            <Icon name="clock" size="xs" />
            <span>{memory.createdAt}</span>
          </div>
        </div>

        {/* Actions */}
        <div className="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
          {memory.editable ? (
            <>
              <Button 
                variant="ghost" 
                size="sm" 
                className="h-8 w-8 p-0"
                onClick={() => onEdit(memory)}
              >
                <Icon name="edit" size="sm" className="text-muted-foreground" />
              </Button>
              <Button 
                variant="ghost" 
                size="sm" 
                className="h-8 w-8 p-0 text-destructive hover:text-destructive"
                onClick={() => onDelete(memory.id)}
              >
                <Icon name="trash" size="sm" />
              </Button>
            </>
          ) : (
            <span className="flex items-center gap-1 px-2 py-1 rounded-md bg-amber-500/10 text-amber-400 text-[10px] font-medium">
              <Icon name="lock" size="xs" />
              Protected
            </span>
          )}
        </div>
      </div>
    </motion.div>
  )
}

export default function AgentMemoryPage({
  params,
}: {
  params: Promise<{ id: string }>
}) {
  const { id } = use(params)
  const [activeCategory, setActiveCategory] = useState<string>("all")
  const [searchQuery, setSearchQuery] = useState("")
  const [editingMemory, setEditingMemory] = useState<Memory | null>(null)

  const filteredMemories = memories.filter(m => {
    const matchesCategory = activeCategory === "all" || m.category === activeCategory
    const matchesSearch = m.content.toLowerCase().includes(searchQuery.toLowerCase())
    return matchesCategory && matchesSearch
  })

  const stats = {
    total: memories.length,
    avgConfidence: Math.round(memories.reduce((sum, m) => sum + m.confidence, 0) / memories.length),
    totalUsage: memories.reduce((sum, m) => sum + m.usageCount, 0),
    protected: memories.filter(m => !m.editable).length,
  }

  const categoryCounts = {
    all: memories.length,
    fact: memories.filter(m => m.category === "fact").length,
    preference: memories.filter(m => m.category === "preference").length,
    pattern: memories.filter(m => m.category === "pattern").length,
    rule: memories.filter(m => m.category === "rule").length,
  }

  return (
    <AppShell title="Agent Memory">
      <div className="flex flex-col min-h-full">
        {/* Header */}
        <div className="relative overflow-hidden border-b border-border">
          <div className="absolute inset-0 bg-gradient-to-br from-emerald-500/5 via-transparent to-teal-500/5" />
          <div className="absolute top-0 right-0 w-[500px] h-[500px] bg-gradient-to-br from-emerald-500/10 to-transparent rounded-full blur-3xl -translate-y-1/2 translate-x-1/3" />
          
          <div className="relative px-8 py-6">
            {/* Breadcrumb */}
            <div className="flex items-center gap-2 text-sm mb-6">
              <Link href="/agents" className="text-muted-foreground hover:text-foreground transition-colors">
                AI Team
              </Link>
              <Icon name="chevronRight" size="xs" className="text-muted-foreground/50" />
              <Link href={`/agents/${id}`} className="text-muted-foreground hover:text-foreground transition-colors">
                {agent.name}
              </Link>
              <Icon name="chevronRight" size="xs" className="text-muted-foreground/50" />
              <span className="text-foreground">Memory</span>
            </div>

            <div className="grid grid-cols-12 gap-8">
              {/* Left: Brain Visualization */}
              <div className="col-span-4 flex flex-col items-center justify-center">
                <BrainVisualization />
                <motion.div
                  initial={{ opacity: 0, y: 10 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ delay: 0.3 }}
                  className="text-center mt-4"
                >
                  <h1 className="text-2xl font-bold text-foreground">{agent.name}&apos;s Memory</h1>
                  <p className="text-sm text-muted-foreground">Everything the agent has learned</p>
                </motion.div>
              </div>

              {/* Right: Stats */}
              <div className="col-span-8 grid grid-cols-4 gap-4 content-center">
                <StatCard label="Total Memories" value={stats.total} icon="brain" color="emerald" />
                <StatCard label="Avg Confidence" value={stats.avgConfidence} icon="target" color="blue" suffix="%" />
                <StatCard label="Total Usage" value={stats.totalUsage} icon="activity" color="violet" />
                <StatCard label="Protected Rules" value={stats.protected} icon="shield" color="amber" />
              </div>
            </div>
          </div>
        </div>

        {/* Content */}
        <div className="flex-1 px-8 py-6">
          {/* Filters & Search */}
          <div className="flex items-center justify-between mb-6">
            <div className="flex items-center gap-2 p-1 rounded-xl bg-secondary/50">
              {[
                { id: "all", label: "All", icon: null },
                { id: "fact", label: "Facts", icon: "database", color: "blue" },
                { id: "preference", label: "Preferences", icon: "heart", color: "rose" },
                { id: "pattern", label: "Patterns", icon: "sparkles", color: "violet" },
                { id: "rule", label: "Rules", icon: "shield", color: "amber" },
              ].map((cat) => (
                <button
                  key={cat.id}
                  onClick={() => setActiveCategory(cat.id)}
                  className={cn(
                    "flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-all",
                    activeCategory === cat.id
                      ? "bg-card text-foreground shadow-sm"
                      : "text-muted-foreground hover:text-foreground"
                  )}
                >
                  {cat.icon && <Icon name={cat.icon as any} size="sm" />}
                  {cat.label}
                  <span className={cn(
                    "px-1.5 py-0.5 rounded-md text-xs",
                    activeCategory === cat.id ? "bg-secondary" : "bg-transparent"
                  )}>
                    {categoryCounts[cat.id as keyof typeof categoryCounts]}
                  </span>
                </button>
              ))}
            </div>

            <div className="flex items-center gap-3">
              <div className="relative w-72">
                <Icon name="search" size="sm" className="absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground" />
                <input
                  type="text"
                  placeholder="Search memories..."
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  className="w-full pl-10 pr-4 py-2.5 rounded-xl border border-border bg-card text-sm text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-emerald-500/50 focus:border-emerald-500"
                />
              </div>
              <Button className="gap-2 bg-gradient-to-r from-emerald-500 to-teal-500 hover:from-emerald-600 hover:to-teal-600 text-white border-0">
                <Icon name="add" size="sm" />
                Add Memory
              </Button>
            </div>
          </div>

          {/* Memory Grid */}
          <AnimatePresence mode="popLayout">
            <motion.div layout className="grid grid-cols-2 gap-4">
              {filteredMemories.map((memory, i) => (
                <MemoryCard
                  key={memory.id}
                  memory={memory}
                  index={i}
                  onEdit={setEditingMemory}
                  onDelete={(id) => console.log("Delete:", id)}
                />
              ))}
            </motion.div>
          </AnimatePresence>

          {filteredMemories.length === 0 && (
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              className="flex flex-col items-center justify-center py-20"
            >
              <div className="h-20 w-20 rounded-2xl bg-secondary flex items-center justify-center mb-4">
                <Icon name="search" size="xl" className="text-muted-foreground" />
              </div>
              <h3 className="text-lg font-semibold text-foreground mb-2">No memories found</h3>
              <p className="text-sm text-muted-foreground">Try adjusting your search or category filter</p>
            </motion.div>
          )}
        </div>
      </div>
    </AppShell>
  )
}
