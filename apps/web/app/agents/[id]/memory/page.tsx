"use client"

import { useState, use, useMemo } from "react"
import Link from "next/link"
import { motion, AnimatePresence } from "framer-motion"
import useSWR from "swr"
import { toast } from "sonner"
import { AppShell } from "@/components/gravitre/app-shell"
import { Button } from "@/components/ui/button"
import { Icon, type IconName } from "@/lib/icons"
import { cn } from "@/lib/utils"
import { useAuth } from "@/lib/auth-context"
import { agentsApi } from "@/lib/api"
import type { Agent, AgentMemory } from "@/types/api"
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog"
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"

type MemoryCategory = AgentMemory["category"]

interface DisplayMemory {
  id: string
  content: string
  category: MemoryCategory
  source: string
  confidence: number
  createdAt: string
  usageCount: number
  editable: boolean
}

const categoryConfig = {
  fact: { label: "Fact", icon: "database", color: "blue", glow: "shadow-blue-500/20" },
  preference: { label: "Preference", icon: "heart", color: "rose", glow: "shadow-destructive/20" },
  pattern: { label: "Pattern", icon: "sparkles", color: "signal", glow: "shadow-[var(--g-glow-signal)]" },
  rule: { label: "Rule", icon: "shield", color: "amber", glow: "shadow-warning/20" },
}

function formatDate(value?: string): string {
  if (!value) return "Recently"
  const parsed = new Date(value)
  if (Number.isNaN(parsed.getTime())) return "Recently"
  return parsed.toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" })
}

function toDisplayMemory(memory: AgentMemory): DisplayMemory {
  return {
    id: memory.id,
    content: memory.content,
    category: memory.category,
    source: memory.source || memory.provenance || "Manual entry",
    confidence: Math.round(memory.confidence),
    createdAt: formatDate(memory.createdAt),
    usageCount: memory.usageCount,
    editable: memory.editable,
  }
}

function BrainVisualization() {
  return (
    <div className="relative h-48 flex items-center justify-center">
      {[0, 1, 2].map((i) => (
        <motion.div
          key={i}
          className="absolute rounded-full border border-success/20"
          style={{
            width: 120 + i * 60,
            height: 120 + i * 60,
          }}
          animate={{ rotate: 360 }}
          transition={{
            duration: 20 + i * 10,
            repeat: Infinity,
            ease: "linear",
          }}
        >
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

      <motion.div
        className="relative z-10 h-24 w-24 rounded-2xl bg-gradient-to-br from-emerald-500 to-teal-500 flex items-center justify-center shadow-2xl shadow-success/30"
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
        <motion.div
          className="absolute inset-0 rounded-2xl bg-gradient-to-br from-emerald-500 to-teal-500"
          animate={{ scale: [1, 1.2, 1], opacity: [0.5, 0, 0.5] }}
          transition={{ duration: 2, repeat: Infinity }}
        />
      </motion.div>

      {[
        { x: -80, y: -40, delay: 0, color: "blue" },
        { x: 80, y: -30, delay: 0.2, color: "rose" },
        { x: -70, y: 50, delay: 0.4, color: "signal" },
        { x: 90, y: 40, delay: 0.6, color: "amber" },
      ].map((node, i) => (
        <motion.div
          key={i}
          className={cn(
            "absolute h-4 w-4 rounded-full",
            node.color === "blue" && "bg-blue-500",
            node.color === "rose" && "bg-rose-500",
            node.color === "signal" && "bg-[color:var(--g-signal)]",
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
                   color === "signal" ? "radial-gradient(circle, color-mix(in oklch, var(--g-signal) 55%, transparent) 0%, transparent 70%)" :
                   "radial-gradient(circle, #f59e0b 0%, transparent 70%)"
      }} />

      <div className={cn(
        "h-10 w-10 rounded-xl flex items-center justify-center mb-3",
        color === "emerald" && "bg-success/10",
        color === "blue" && "bg-blue-500/10",
        color === "signal" && "bg-[color:var(--g-signal-surface)]",
        color === "amber" && "bg-warning/10",
      )}>
        <Icon
          name={icon as IconName}
          size="sm"
          className={cn(
            color === "emerald" && "text-success",
            color === "blue" && "text-blue-400",
            color === "signal" && "text-[color:var(--g-signal)]",
            color === "amber" && "text-warning",
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

function MemoryCard({ memory, index, onEdit, onDelete }: {
  memory: DisplayMemory
  index: number
  onEdit: (m: DisplayMemory) => void
  onDelete: (id: string) => void
}) {
  const category = categoryConfig[memory.category]
  const [isHovered, setIsHovered] = useState(false)

  const colorClasses: Record<string, { bg: string; border: string; text: string; ring: string }> = {
    blue: { bg: "bg-blue-500/10", border: "border-blue-500/30", text: "text-blue-400", ring: "ring-blue-500/20" },
    rose: { bg: "bg-destructive/10", border: "border-destructive/30", text: "text-destructive", ring: "ring-destructive/20" },
    signal: { bg: "bg-[color:var(--g-signal-surface)]", border: "border-[color:var(--g-signal)]/30", text: "text-[color:var(--g-signal)]", ring: "ring-[color:var(--g-signal)]/20" },
    amber: { bg: "bg-warning/10", border: "border-warning/30", text: "text-warning", ring: "ring-warning/20" },
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
      <motion.div
        className={cn(
          "absolute inset-0 rounded-2xl opacity-0 transition-opacity",
          colors.ring, "ring-2"
        )}
        animate={{ opacity: isHovered ? 1 : 0 }}
      />

      <div className="flex items-start justify-between mb-3">
        <div className={cn(
          "flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium",
          colors.bg, colors.text
        )}>
          <Icon name={category.icon as IconName} size="xs" />
          {category.label}
        </div>

        <div className="relative h-10 w-10">
          <svg className="h-10 w-10 -rotate-90">
            <circle cx="20" cy="20" r="16" fill="none" stroke="currentColor" strokeWidth="3" className="text-secondary" />
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

      <p className="text-sm text-foreground leading-relaxed mb-4 pr-4">{memory.content}</p>

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

        <div className="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
          {memory.editable ? (
            <>
              <Button variant="ghost" size="sm" className="h-8 w-8 p-0" onClick={() => onEdit(memory)}>
                <Icon name="edit" size="sm" className="text-muted-foreground" />
              </Button>
              <Button variant="ghost" size="sm" className="h-8 w-8 p-0 text-destructive hover:text-destructive" onClick={() => onDelete(memory.id)}>
                <Icon name="trash" size="sm" />
              </Button>
            </>
          ) : (
            <span className="flex items-center gap-1 px-2 py-1 rounded-md bg-warning/10 text-warning text-[10px] font-medium">
              <Icon name="lock" size="xs" />
              Protected
            </span>
          )}
        </div>
      </div>
    </motion.div>
  )
}

function MemoryEditorDialog({
  open,
  onOpenChange,
  initial,
  onSave,
  saving,
}: {
  open: boolean
  onOpenChange: (open: boolean) => void
  initial?: DisplayMemory | null
  onSave: (values: { content: string; category: MemoryCategory; source: string; confidence: number; editable: boolean }) => Promise<void>
  saving: boolean
}) {
  const [content, setContent] = useState(initial?.content || "")
  const [category, setCategory] = useState<MemoryCategory>(initial?.category || "fact")
  const [source, setSource] = useState(initial?.source || "")
  const [confidence, setConfidence] = useState(initial?.confidence ?? 90)
  const [editable, setEditable] = useState(initial?.editable ?? true)

  const resetFromInitial = () => {
    setContent(initial?.content || "")
    setCategory(initial?.category || "fact")
    setSource(initial?.source || "")
    setConfidence(initial?.confidence ?? 90)
    setEditable(initial?.editable ?? true)
  }

  return (
    <Dialog open={open} onOpenChange={(next) => { onOpenChange(next); if (!next) resetFromInitial() }}>
      <DialogContent className="sm:max-w-lg">
        <DialogHeader>
          <DialogTitle>{initial ? "Edit memory" : "Add memory"}</DialogTitle>
        </DialogHeader>
        <div className="space-y-4">
          <textarea
            value={content}
            onChange={(e) => setContent(e.target.value)}
            placeholder="What should this agent remember?"
            className="w-full min-h-28 rounded-xl border border-border bg-card px-3 py-2 text-sm"
          />
          <div className="grid grid-cols-2 gap-3">
            <label className="text-sm space-y-1">
              <span className="text-muted-foreground">Category</span>
              <select
                value={category}
                onChange={(e) => setCategory(e.target.value as MemoryCategory)}
                className="w-full rounded-lg border border-border bg-card px-3 py-2 text-sm"
              >
                <option value="fact">Fact</option>
                <option value="preference">Preference</option>
                <option value="pattern">Pattern</option>
                <option value="rule">Rule</option>
              </select>
            </label>
            <label className="text-sm space-y-1">
              <span className="text-muted-foreground">Confidence</span>
              <input
                type="number"
                min={0}
                max={100}
                value={confidence}
                onChange={(e) => setConfidence(Number(e.target.value))}
                className="w-full rounded-lg border border-border bg-card px-3 py-2 text-sm"
              />
            </label>
          </div>
          <label className="text-sm space-y-1 block">
            <span className="text-muted-foreground">Source / provenance</span>
            <input
              value={source}
              onChange={(e) => setSource(e.target.value)}
              placeholder="Training session, brand guidelines, etc."
              className="w-full rounded-lg border border-border bg-card px-3 py-2 text-sm"
            />
          </label>
          <label className="flex items-center gap-2 text-sm">
            <input type="checkbox" checked={editable} onChange={(e) => setEditable(e.target.checked)} />
            <span>Allow edits and deletion</span>
          </label>
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)} disabled={saving}>Cancel</Button>
          <Button
            disabled={saving || !content.trim()}
            onClick={async () => {
              await onSave({ content: content.trim(), category, source: source.trim(), confidence, editable })
              onOpenChange(false)
            }}
          >
            {saving ? "Saving..." : initial ? "Save changes" : "Add memory"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

export default function AgentMemoryPage({
  params,
}: {
  params: Promise<{ id: string }>
}) {
  const { id } = use(params)
  const { user } = useAuth()
  const [activeCategory, setActiveCategory] = useState<string>("all")
  const [searchQuery, setSearchQuery] = useState("")
  const [editingMemory, setEditingMemory] = useState<DisplayMemory | null>(null)
  const [editorOpen, setEditorOpen] = useState(false)
  const [deleteTarget, setDeleteTarget] = useState<DisplayMemory | null>(null)
  const [saving, setSaving] = useState(false)

  const { data: agentData } = useSWR(
    user && id ? `agent/${id}` : null,
    () => agentsApi.get(id),
  )
  const agent = agentData as Agent | undefined

  const { data: memoriesData, mutate, isLoading } = useSWR(
    user && id ? `agent/${id}/memories` : null,
    () => agentsApi.listMemories(id),
    { fallbackData: [] as AgentMemory[] },
  )

  const memories = useMemo(
    () => (memoriesData || []).map(toDisplayMemory),
    [memoriesData],
  )

  const filteredMemories = memories.filter((m) => {
    const matchesCategory = activeCategory === "all" || m.category === activeCategory
    const matchesSearch = m.content.toLowerCase().includes(searchQuery.toLowerCase())
    return matchesCategory && matchesSearch
  })

  const stats = useMemo(() => ({
    total: memories.length,
    avgConfidence: memories.length
      ? Math.round(memories.reduce((sum, m) => sum + m.confidence, 0) / memories.length)
      : 0,
    totalUsage: memories.reduce((sum, m) => sum + m.usageCount, 0),
    protected: memories.filter((m) => !m.editable).length,
  }), [memories])

  const categoryCounts = useMemo(() => ({
    all: memories.length,
    fact: memories.filter((m) => m.category === "fact").length,
    preference: memories.filter((m) => m.category === "preference").length,
    pattern: memories.filter((m) => m.category === "pattern").length,
    rule: memories.filter((m) => m.category === "rule").length,
  }), [memories])

  const handleSaveMemory = async (values: {
    content: string
    category: MemoryCategory
    source: string
    confidence: number
    editable: boolean
  }) => {
    try {
      setSaving(true)
      if (editingMemory) {
        await agentsApi.updateMemory(id, editingMemory.id, {
          content: values.content,
          category: values.category,
          provenance: values.source || undefined,
          confidence: values.confidence,
          editable: values.editable,
        })
        toast.success("Memory updated")
      } else {
        await agentsApi.createMemory(id, {
          content: values.content,
          category: values.category,
          provenance: values.source || undefined,
          confidence: values.confidence,
          editable: values.editable,
        })
        toast.success("Memory added")
      }
      await mutate()
      setEditingMemory(null)
    } catch (error) {
      console.error("[memory] save failed:", error)
      toast.error("Failed to save memory")
      throw error
    } finally {
      setSaving(false)
    }
  }

  const handleDelete = async () => {
    if (!deleteTarget) return
    try {
      setSaving(true)
      await agentsApi.deleteMemory(id, deleteTarget.id)
      toast.success("Memory deleted")
      await mutate()
    } catch (error) {
      console.error("[memory] delete failed:", error)
      toast.error("Failed to delete memory")
    } finally {
      setSaving(false)
      setDeleteTarget(null)
    }
  }

  return (
    <AppShell title="Agent Memory">
      <div className="flex flex-col min-h-full">
        <div className="relative overflow-hidden border-b border-border">
          <div className="absolute inset-0 bg-gradient-to-br from-emerald-500/5 via-transparent to-teal-500/5" />
          <div className="absolute top-0 right-0 w-[500px] h-[500px] bg-gradient-to-br from-emerald-500/10 to-transparent rounded-full blur-3xl -translate-y-1/2 translate-x-1/3" />

          <div className="relative px-8 py-6">
            <div className="flex items-center gap-2 text-sm mb-6">
              <Link href="/agents" className="text-muted-foreground hover:text-foreground transition-colors">
                AI Team
              </Link>
              <Icon name="chevronRight" size="xs" className="text-muted-foreground/50" />
              <Link href={`/agents/${id}`} className="text-muted-foreground hover:text-foreground transition-colors">
                {agent?.name || "Agent"}
              </Link>
              <Icon name="chevronRight" size="xs" className="text-muted-foreground/50" />
              <span className="text-foreground">Memory</span>
            </div>

            <div className="grid grid-cols-1 gap-8 lg:grid-cols-12">
              <div className="lg:col-span-4 flex flex-col items-center justify-center">
                <BrainVisualization />
                <motion.div
                  initial={{ opacity: 0, y: 10 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ delay: 0.3 }}
                  className="text-center mt-4"
                >
                  <h1 className="text-xl font-semibold text-foreground">{agent?.name || "Agent"}&apos;s Memory</h1>
                  <p className="text-sm text-muted-foreground">Everything the agent has learned</p>
                </motion.div>
              </div>

              <div className="lg:col-span-8 grid grid-cols-2 gap-4 content-center sm:grid-cols-4">
                <StatCard label="Total Memories" value={stats.total} icon="brain" color="emerald" />
                <StatCard label="Avg Confidence" value={stats.avgConfidence} icon="target" color="blue" suffix="%" />
                <StatCard label="Total Usage" value={stats.totalUsage} icon="activity" color="signal" />
                <StatCard label="Protected Rules" value={stats.protected} icon="shield" color="amber" />
              </div>
            </div>
          </div>
        </div>

        <div className="flex-1 px-8 py-6">
          <div className="flex items-center justify-between mb-6">
            <div className="flex items-center gap-2 p-1 rounded-xl bg-secondary/50">
              {[
                { id: "all", label: "All", icon: null },
                { id: "fact", label: "Facts", icon: "database", color: "blue" },
                { id: "preference", label: "Preferences", icon: "heart", color: "rose" },
                { id: "pattern", label: "Patterns", icon: "sparkles", color: "signal" },
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
                  {cat.icon && <Icon name={cat.icon as IconName} size="sm" />}
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
                  className="w-full pl-10 pr-4 py-2.5 rounded-xl border border-border bg-card text-sm text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-success/50 focus:border-success"
                />
              </div>
              <Button
                className="gap-2 bg-gradient-to-r from-emerald-500 to-teal-500 hover:from-emerald-600 hover:to-teal-600 text-white border-0"
                onClick={() => { setEditingMemory(null); setEditorOpen(true) }}
              >
                <Icon name="add" size="sm" />
                Add Memory
              </Button>
            </div>
          </div>

          {isLoading ? (
            <div className="text-sm text-muted-foreground py-12 text-center">Loading memories...</div>
          ) : (
            <AnimatePresence mode="popLayout">
              <motion.div layout className="grid grid-cols-2 gap-4">
                {filteredMemories.map((memory, i) => (
                  <MemoryCard
                    key={memory.id}
                    memory={memory}
                    index={i}
                    onEdit={(m) => { setEditingMemory(m); setEditorOpen(true) }}
                    onDelete={(memoryId) => {
                      const target = memories.find((m) => m.id === memoryId)
                      if (target) setDeleteTarget(target)
                    }}
                  />
                ))}
              </motion.div>
            </AnimatePresence>
          )}

          {!isLoading && filteredMemories.length === 0 && (
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              className="flex flex-col items-center justify-center py-20"
            >
              <div className="h-20 w-20 rounded-2xl bg-secondary flex items-center justify-center mb-4">
                <Icon name="search" size="xl" className="text-muted-foreground" />
              </div>
              <h3 className="text-lg font-semibold text-foreground mb-2">No memories found</h3>
              <p className="text-sm text-muted-foreground">Try adjusting your search or add a new memory</p>
            </motion.div>
          )}
        </div>
      </div>

      <MemoryEditorDialog
        key={editingMemory?.id || "new"}
        open={editorOpen}
        onOpenChange={setEditorOpen}
        initial={editingMemory}
        onSave={handleSaveMemory}
        saving={saving}
      />

      <AlertDialog open={Boolean(deleteTarget)} onOpenChange={(open) => !open && setDeleteTarget(null)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Delete memory?</AlertDialogTitle>
            <AlertDialogDescription>
              This removes the memory from vector search and future agent tasks.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel disabled={saving}>Cancel</AlertDialogCancel>
            <AlertDialogAction onClick={handleDelete} disabled={saving}>Delete</AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </AppShell>
  )
}
