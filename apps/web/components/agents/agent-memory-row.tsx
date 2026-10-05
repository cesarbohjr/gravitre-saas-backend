"use client"

import { Button } from "@/components/ui/button"
import { Icon, type IconName } from "@/lib/icons"
import type { AgentMemory } from "@/types/api"
type MemoryCategory = AgentMemory["category"]

export interface DisplayMemory {
  id: string
  content: string
  category: MemoryCategory
  source: string
  confidence: number | null
  createdAt: string
  usageCount: number | null
  editable: boolean
}

const categoryConfig = {
  fact: { label: "Fact", icon: "database", color: "blue" },
  preference: { label: "Preference", icon: "heart", color: "rose" },
  pattern: { label: "Pattern", icon: "sparkles", color: "signal" },
  rule: { label: "Rule", icon: "shield", color: "amber" },
}

export function MemoryCard({
  memory,
  onEdit,
  onDelete,
}: {
  memory: DisplayMemory
  onEdit: (m: DisplayMemory) => void
  onDelete: (id: string) => void
}) {
  const category = categoryConfig[memory.category]
  return (
    <article className="border-b border-[color:var(--g-border-default)] py-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <span className="flex items-center gap-2 text-xs font-medium text-muted-foreground">
          <Icon name={(category?.icon || "database") as IconName} size="xs" />
          {category?.label || "Not reported"}
        </span>
        <span className="text-xs text-muted-foreground">
          Reported confidence:{" "}
          {memory.confidence == null ? "Not reported" : `${memory.confidence}%`}
        </span>
      </div>
      <p className="my-3 whitespace-pre-wrap break-words text-sm leading-relaxed">
        {memory.content}
      </p>
      <div className="flex flex-wrap items-start justify-between gap-3">
        <dl className="flex min-w-0 flex-wrap gap-x-5 gap-y-2 text-xs text-muted-foreground">
          <div className="min-w-0">
            <dt>Source</dt>
            <dd className="break-words">{memory.source}</dd>
          </div>
          <div>
            <dt>Usage</dt>
            <dd>
              {memory.usageCount == null
                ? "Not reported"
                : `${memory.usageCount} times`}
            </dd>
          </div>
          <div>
            <dt>Created</dt>
            <dd>{memory.createdAt}</dd>
          </div>
        </dl>
        <div className="flex flex-wrap gap-2">
          {memory.editable ? (
            <>
              <Button
                variant="outline"
                className="min-h-11"
                onClick={() => onEdit(memory)}
              >
                Edit
              </Button>
              <Button
                variant="ghost"
                className="min-h-11 text-destructive"
                onClick={() => onDelete(memory.id)}
              >
                Delete
              </Button>
            </>
          ) : (
            <span className="inline-flex min-h-11 items-center gap-2 text-xs text-muted-foreground">
              <Icon name="lock" size="xs" />
              Protected
            </span>
          )}
        </div>
      </div>
    </article>
  )
}
