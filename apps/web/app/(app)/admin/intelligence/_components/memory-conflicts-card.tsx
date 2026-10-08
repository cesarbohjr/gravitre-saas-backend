"use client"

import { WorkSectionErrorCard } from "@/components/gravitre/work-section-error-card"
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
  const { data, isLoading, error, mutate } = useSWR(enabled ? "admin/intelligence/memory-conflicts" : null, () =>
    intelligenceApi.memoryConflicts(),
  )
  if (!enabled) return null
  if (isLoading && !data) {
    return (
      <SectionCard
        title={SURFACE_COPY.learningAdmin.memoryConflictsTitle}
        description="Scanning agent memories…"
      >
        <p className="text-sm text-muted-foreground">Checking for opposing statements…</p>
      </SectionCard>
    )
  }
  if (error && !data) {
    return (
      <SectionCard
        title={SURFACE_COPY.learningAdmin.memoryConflictsTitle}
        description="Unable to load conflict scan."
      >
        <WorkSectionErrorCard error={error} onRetry={() => void mutate()} />
      </SectionCard>
    )
  }

  const conflictCount = typeof data?.conflict_count === "number" ? data.conflict_count : null
  const scanned = typeof data?.scanned_memories === "number" ? data.scanned_memories : null
  const conflicts = (data?.conflicts as ConflictRow[]) || []

  return (
    <SectionCard
      title={SURFACE_COPY.learningAdmin.memoryConflictsTitle}
      description="When two agent memories disagree, they show up here for a human decision."
      action={
        <Badge variant={conflictCount !== null && conflictCount > 0 ? "destructive" : "outline"} className="font-normal">
          {conflictCount ?? "Not reported"} conflict{conflictCount === 1 ? "" : "s"}
        </Badge>
      }
    >
      {error ? <WorkSectionErrorCard error={error} onRetry={() => void mutate()} /> : null}
      {scanned === null || conflictCount === null ? <NotYetPopulated>Scan counts not reported.</NotYetPopulated> : scanned === 0 ? (
        <NotYetPopulated>No agent memories scanned yet.</NotYetPopulated>
      ) : conflictCount === 0 ? (
        <p className="text-sm text-muted-foreground">
          Scanned {scanned} memories. No opposing pairs detected.
        </p>
      ) : (
        <div className="space-y-3">
          {conflicts.slice(0, 5).map((row) => (
            <div key={`${row.agentId}-${row.memory_a_id}-${row.memory_b_id}`} className="rounded-[8px] border border-divide bg-[color:var(--g-surface-2)] p-3 text-sm">
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
