"use client"

import { useState, use, useMemo } from "react"
import Link from "next/link"
import { MemoryCard, type DisplayMemory } from "@/components/agents/agent-memory-row"
import { WorkSectionErrorCard } from "@/components/gravitre/work-section-error-card"
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


function formatDate(value?: string): string {
  if (!value) return "Not reported"
  const parsed = new Date(value)
  if (Number.isNaN(parsed.getTime())) return "Not reported"
  return parsed.toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" })
}

function toDisplayMemory(memory: AgentMemory): DisplayMemory {
  return {
    id: memory.id,
    content: memory.content,
    category: memory.category,
    source: memory.source || memory.provenance || "Not reported",
    confidence: typeof memory.confidence === "number" && Number.isFinite(memory.confidence) && memory.confidence >= 0 && memory.confidence <= 100 ? Math.round(memory.confidence) : null,
    createdAt: formatDate(memory.createdAt),
    usageCount: typeof memory.usageCount === "number" && Number.isFinite(memory.usageCount) && memory.usageCount >= 0 ? memory.usageCount : null,
    editable: memory.editable,
  }
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
    <Dialog open={open} onOpenChange={(next) => { if (saving) return; onOpenChange(next); if (!next) resetFromInitial() }}>
      <DialogContent className="max-h-[85dvh] overflow-y-auto sm:max-w-lg">
        <DialogHeader>
          <DialogTitle>{initial ? "Edit memory" : "Add memory"}</DialogTitle>
        </DialogHeader>
        <div className="space-y-4">
          <textarea
            aria-label="Memory content"
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
            disabled={saving || !content.trim() || !Number.isFinite(confidence) || confidence < 0 || confidence > 100}
            onClick={async () => {
              try {
                await onSave({ content: content.trim(), category, source: source.trim(), confidence, editable })
                onOpenChange(false)
              } catch { /* Keep the draft open after an API failure. */ }
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

  const { data: memoriesData, mutate, isLoading, error } = useSWR(
    user && id ? `agent/${id}/memories` : null,
    () => agentsApi.listMemories(id),
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
      ? Math.round(memories.filter(m => m.confidence != null).reduce((sum, m) => sum + m.confidence!, 0) / memories.filter(m => m.confidence != null).length)
      : null,
    totalUsage: memories.some(m => m.usageCount == null) ? null : memories.reduce((sum, m) => sum + m.usageCount!, 0),
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
    if (saving) return
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
    if (!deleteTarget || saving) return
    try {
      setSaving(true)
      await agentsApi.deleteMemory(id, deleteTarget.id)
      toast.success("Memory deleted")
      setDeleteTarget(null)
      await mutate()
    } catch (error) {
      console.error("[memory] delete failed:", error)
      toast.error("Failed to delete memory")
    } finally {
      setSaving(false)
    }
  }

  return (
    <AppShell title="Agent memory">
      <div className="flex h-full min-h-0 w-full flex-col bg-[color:var(--g-canvas)]">
        <GravitrePageHeader
          eyebrow="AI Team"
          title={`${agent?.name || "Agent"}'s Memory`}
          description="Facts, preferences, patterns, and rules this agent uses in future work."
          icon={<NucleoIntelligence className="h-5 w-5" />}
          actions={
            <div className="flex flex-wrap items-center gap-2">
              <Button variant="outline" className="min-h-11" asChild>
                <Link href={`/agents/${id}`}>Back to profile</Link>
              </Button>
              <Button
                className="min-h-11 gap-2"
                onClick={() => { setEditingMemory(null); setEditorOpen(true) }}
              >
                <Icon name="add" size="sm" />
                Add memory
              </Button>
            </div>
          }
        />

        <div data-composition="manage" className="flex-1 pb-28 px-[var(--np-page-pad-sm)] py-6 sm:px-[var(--np-page-pad)]">
          <section className="mb-6 grid grid-cols-1 gap-[var(--np-kpi-gap)] sm:grid-cols-2 lg:grid-cols-4">
            <GravitreMetric label="Total memories" value={memoriesData ? stats.total : "Not reported"} />
            <GravitreMetric label="Avg confidence" value={stats.avgConfidence != null && Number.isFinite(stats.avgConfidence) ? `${stats.avgConfidence}%` : "Not reported"} />
            <GravitreMetric label="Total usage" value={memoriesData ? stats.totalUsage ?? "Not reported" : "Not reported"} />
            <GravitreMetric label="Protected rules" value={memoriesData ? stats.protected : "Not reported"} />
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
                    "flex min-h-11 items-center gap-2 rounded-[var(--np-radius-md)] px-4 py-2 text-sm font-medium transition-all",
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
                aria-label="Search memories"
                placeholder="Search memories..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="w-full rounded-[var(--np-radius-lg)] border border-divide bg-[color:var(--g-surface-1)] py-2.5 pl-10 pr-4 text-sm text-foreground placeholder:text-muted-foreground focus:border-[color:var(--g-brand-border)] focus:outline-none focus:ring-2 focus:ring-[color:var(--g-brand)]/30"
              />
            </div>
          </div>

          {error ? <WorkSectionErrorCard title="Could not refresh memories" error={error} onRetry={() => void mutate()} /> : null}
          {isLoading && !memoriesData ? <p className="py-12 text-sm text-muted-foreground">Loading memories…</p> : <div className="border-t border-[color:var(--g-border-default)]">
            {filteredMemories.map(memory => <MemoryCard key={memory.id} memory={memory} onEdit={m => { setEditingMemory(m); setEditorOpen(true) }} onDelete={memoryId => { const target = memories.find(m => m.id === memoryId); if (target) setDeleteTarget(target) }} />)}
          </div>}

          {!isLoading && !error && filteredMemories.length === 0 && (
            <GravitreEmpty
              icon={<Icon name="search" size="sm" />}
              title="No memories found"
              hint="Try adjusting your search or add a new memory"
              action={
                <Button
                  className="min-h-11 gap-2"
                  onClick={() => { setEditingMemory(null); setEditorOpen(true) }}
                >
                  <Icon name="add" size="sm" />
                  Add memory
                </Button>
              }
            />
          )}
        </div>
      </div>

      <MemoryEditorDialog
        key={`${editingMemory?.id || "new"}-${editorOpen}`}
        open={editorOpen}
        onOpenChange={setEditorOpen}
        initial={editingMemory}
        onSave={handleSaveMemory}
        saving={saving}
      />

      <AlertDialog open={Boolean(deleteTarget)} onOpenChange={(open) => !open && !saving && setDeleteTarget(null)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Delete memory?</AlertDialogTitle>
            <AlertDialogDescription>
              This removes the memory from vector search and future agent tasks.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel disabled={saving}>Cancel</AlertDialogCancel>
            <AlertDialogAction onClick={event => { event.preventDefault(); void handleDelete() }} disabled={saving}>Delete</AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </AppShell>
  )
}
