"use client"

import useSWR from "swr"
import { Badge } from "@/components/ui/badge"
import { intelligenceApi } from "@/lib/api"
import { SURFACE_COPY } from "@/lib/surface-copy"
import { NotYetPopulated, SectionCard } from "./shared"

type ConflictRow = {
  agentId?: string
  memory_a_id?: string
  memory_b_id?: string
  memory_a_preview?: string
  memory_b_preview?: string
  requires_human_review?: boolean
}

export function MemoryConflictsCard({ enabled }: { enabled: boolean }) {
  const { data, isLoading, error } = useSWR(enabled ? "admin/intelligence/memory-conflicts" : null, () =>
    intelligenceApi.memoryConflicts(),
  )
  if (!enabled) return null
  if (isLoading) {
    return (
      <SectionCard
        title={SURFACE_COPY.learningAdmin.memoryConflictsTitle}
        description="Scanning agent memories…"
      >
        <p className="text-sm text-muted-foreground">Checking for opposing statements…</p>
      </SectionCard>
    )
  }
  if (error) {
    return (
      <SectionCard
        title={SURFACE_COPY.learningAdmin.memoryConflictsTitle}
        description="Unable to load conflict scan."
      >
        <p className="text-sm text-muted-foreground">Try refreshing the page.</p>
      </SectionCard>
    )
  }

  const conflictCount = Number(data?.conflict_count ?? 0)
  const scanned = Number(data?.scanned_memories ?? 0)
  const conflicts = (data?.conflicts as ConflictRow[]) || []

  return (
    <SectionCard
      title={SURFACE_COPY.learningAdmin.memoryConflictsTitle}
      description="When two agent memories disagree, they show up here for a human decision."
      action={
        <Badge variant={conflictCount > 0 ? "destructive" : "outline"} className="font-normal">
          {conflictCount} conflict{conflictCount === 1 ? "" : "s"}
        </Badge>
      }
    >
      {scanned === 0 ? (
        <NotYetPopulated>No agent memories scanned yet.</NotYetPopulated>
      ) : conflictCount === 0 ? (
        <p className="text-sm text-muted-foreground">
          Scanned {scanned} memories. No opposing pairs detected.
        </p>
      ) : (
        <div className="space-y-3">
          {conflicts.slice(0, 5).map((row) => (
            <div key={`${row.agentId}-${row.memory_a_id}-${row.memory_b_id}`} className="rounded-lg border border-border/60 p-3 text-sm">
              <p className="font-medium text-foreground">Agent {row.agentId}</p>
              <p className="mt-1 text-xs text-muted-foreground line-clamp-2">{row.memory_a_preview}</p>
              <p className="mt-1 text-xs text-muted-foreground line-clamp-2">{row.memory_b_preview}</p>
              {row.requires_human_review ? (
                <Badge variant="outline" className="mt-2 font-normal">
                  Requires review
                </Badge>
              ) : null}
            </div>
          ))}
        </div>
      )}
    </SectionCard>
  )
}
