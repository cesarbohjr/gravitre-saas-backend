"use client"

import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { knowledgeNodeTypeLabel } from "@/lib/learning-ui-copy"
import type { EntityMatchCandidate } from "@/lib/relationships-graph/match-candidates"
import { Warning } from "@phosphor-icons/react"

export function DuplicateMatchPanel({
  matches,
  onUseExisting,
  onCreateSeparate,
}: {
  matches: EntityMatchCandidate[]
  onUseExisting: (match: EntityMatchCandidate) => void
  onCreateSeparate: () => void
}) {
  if (matches.length === 0) return null

  return (
    <div
      className="space-y-3 rounded-[var(--np-radius-md)] border border-amber-500/30 bg-amber-500/5 p-3"
      data-testid="duplicate-match-panel"
    >
      <div className="flex items-start gap-2">
        <Warning className="mt-0.5 h-4 w-4 shrink-0 text-amber-600 dark:text-amber-400" weight="duotone" aria-hidden />
        <div className="min-w-0 space-y-1">
          <p className="text-sm font-medium text-[color:var(--g-text-primary)]">Possible match found</p>
          <p className="text-xs leading-relaxed text-[color:var(--g-text-muted)]">
            Gravitre found similar names in your graph. Review before creating a separate entity.
          </p>
        </div>
      </div>
      <ul className="space-y-2">
        {matches.map((match) => (
          <li
            key={match.id}
            className="flex flex-col gap-2 rounded-md border border-divide bg-[color:var(--g-surface-1)] p-2.5 sm:flex-row sm:items-center sm:justify-between"
          >
            <div className="min-w-0">
              <p className="truncate text-sm font-medium">{match.name}</p>
              <div className="mt-1 flex flex-wrap gap-1.5">
                {match.nodeType ? (
                  <Badge variant="outline" className="text-[10px] font-normal">
                    {knowledgeNodeTypeLabel(match.nodeType)}
                  </Badge>
                ) : null}
                <Badge variant="outline" className="text-[10px] font-normal tabular-nums">
                  {match.matchScore}% match
                </Badge>
                {match.source === "learned_relationship" && match.evidenceCount != null ? (
                  <Badge variant="outline" className="text-[10px] font-normal tabular-nums">
                    {match.evidenceCount} observations
                  </Badge>
                ) : null}
                {match.source === "confirmed_knowledge" ? (
                  <Badge variant="secondary" className="text-[10px] font-normal">
                    Confirmed knowledge
                  </Badge>
                ) : (
                  <Badge variant="secondary" className="text-[10px] font-normal">
                    Learned entity
                  </Badge>
                )}
              </div>
            </div>
            <Button type="button" size="sm" variant="outline" className="shrink-0" onClick={() => onUseExisting(match)}>
              Use existing
            </Button>
          </li>
        ))}
      </ul>
      <Button type="button" size="sm" variant="ghost" className="w-full" onClick={onCreateSeparate}>
        Create separate entity anyway
      </Button>
    </div>
  )
}
