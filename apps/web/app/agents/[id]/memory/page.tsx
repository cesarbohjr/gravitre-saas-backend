"use client"

import { useState, use, useMemo } from "react"
import Link from "next/link"
import { motion, AnimatePresence } from "framer-motion"
import useSWR from "swr"
import { toast } from "sonner"
import { AppShell } from "@/components/gravitre/app-shell"
import {
  GravitreEmpty,
  GravitreMetric,
  GravitrePageHeader,
} from "@/components/gravitre/nodus-product"
import { Button } from "@/components/ui/button"
import { Icon, type IconName } from "@/lib/icons"
import { NucleoIntelligence } from "@/components/icons/nucleo/semantic"
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
  const confidenceStroke =
    memory.confidence >= 90
      ? "var(--g-brand)"
      : memory.confidence >= 70
        ? "var(--warning)"
        : "var(--destructive)"

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: index * 0.05 }}
      onHoverStart={() => setIsHovered(true)}
      onHoverEnd={() => setIsHovered(false)}
      className={cn(
        "group relative rounded-[var(--np-radius-lg)] border border-divide bg-[color:var(--g-surface-1)] p-5 shadow-[var(--np-shadow)] transition-colors",
        "hover:bg-[color:var(--g-surface-2)]",
      )}
    >
      <motion.div
        className={cn(
          "absolute inset-0 rounded-[var(--np-radius-lg)] opacity-0 transition-opacity",
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
            <circle cx="20" cy="20" r="16" fill="none" stroke="currentColor" strokeWidth="3" className="text-[color:var(--g-surface-2)]" />
            <motion.circle
              cx="20"
              cy="20"
              r="16"
              fill="none"
              stroke={confidenceStroke}
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
      <div className="flex h-full min-h-0 w-full flex-col bg-[color:var(--g-canvas)]">
        <GravitrePageHeader
          eyebrow="AI Team"
          title={`${agent?.name || "Agent"}'s Memory`}
          description="Facts, preferences, patterns, and rules this agent uses in future work."
          icon={<NucleoIntelligence className="h-5 w-5" />}
          actions={
            <div className="flex flex-wrap items-center gap-2">
              <Button variant="outline" asChild>
                <Link href={`/agents/${id}`}>Back to profile</Link>
              </Button>
              <Button
                className="gap-2"
                onClick={() => { setEditingMemory(null); setEditorOpen(true) }}
              >
                <Icon name="add" size="sm" />
                Add Memory
              </Button>
            </div>
          }
        />

        <div className="flex-1 px-[var(--np-page-pad-sm)] py-6 sm:px-[var(--np-page-pad)]">
          <section className="mb-6 grid grid-cols-2 gap-[var(--np-kpi-gap)] lg:grid-cols-4">
            <GravitreMetric label="Total Memories" value={stats.total} />
            <GravitreMetric label="Avg Confidence" value={`${stats.avgConfidence}%`} />
            <GravitreMetric label="Total Usage" value={stats.totalUsage} />
            <GravitreMetric label="Protected Rules" value={stats.protected} />
          </section>

          <div className="mb-6 flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
            <div className="flex flex-wrap items-center gap-1 rounded-[var(--np-radius-lg)] border border-divide bg-[color:var(--g-surface-2)] p-1">
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
                    "flex items-center gap-2 rounded-[var(--np-radius-md)] px-4 py-2 text-sm font-medium transition-all",
                    activeCategory === cat.id
                      ? "bg-[color:var(--g-surface-1)] text-foreground shadow-[var(--np-shadow)]"
                      : "text-muted-foreground hover:text-foreground"
                  )}
                >
                  {cat.icon && <Icon name={cat.icon as IconName} size="sm" />}
                  {cat.label}
                  <span className={cn(
                    "rounded-[var(--np-radius-sm)] px-1.5 py-0.5 text-xs",
                    activeCategory === cat.id ? "bg-[color:var(--g-surface-2)]" : "bg-transparent"
                  )}>
                    {categoryCounts[cat.id as keyof typeof categoryCounts]}
                  </span>
                </button>
              ))}
            </div>

            <div className="relative w-full max-w-sm">
              <Icon name="search" size="sm" className="absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground" />
              <input
                type="text"
                placeholder="Search memories..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="w-full rounded-[var(--np-radius-lg)] border border-divide bg-[color:var(--g-surface-1)] py-2.5 pl-10 pr-4 text-sm text-foreground placeholder:text-muted-foreground focus:border-[color:var(--g-brand-border)] focus:outline-none focus:ring-2 focus:ring-[color:var(--g-brand)]/30"
              />
            </div>
          </div>

          {isLoading ? (
            <div className="py-12 text-center text-sm text-muted-foreground">Loading memories...</div>
          ) : (
            <AnimatePresence mode="popLayout">
              <motion.div layout className="grid grid-cols-1 gap-4 md:grid-cols-2">
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
            <GravitreEmpty
              icon={<Icon name="search" size="sm" />}
              title="No memories found"
              hint="Try adjusting your search or add a new memory"
              action={
                <Button
                  className="gap-2"
                  onClick={() => { setEditingMemory(null); setEditorOpen(true) }}
                >
                  <Icon name="add" size="sm" />
                  Add Memory
                </Button>
              }
            />
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
