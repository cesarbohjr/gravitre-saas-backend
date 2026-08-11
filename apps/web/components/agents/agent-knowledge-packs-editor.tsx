"use client"

import useSWR from "swr"
import { BookOpen } from "lucide-react"
import { cn } from "@/lib/utils"
import { fetcher } from "@/lib/fetcher"

export type KnowledgePackSelection = {
  id: string
  name: string
  department?: string
}

type PackRow = {
  pack_id: string
  label: string
  department: string
  ingestible?: boolean
  hold?: boolean
}

type Props = {
  value: KnowledgePackSelection[]
  onChange: (packs: KnowledgePackSelection[]) => void
  className?: string
}

export function AgentKnowledgePacksEditor({ value, onChange, className }: Props) {
  const { data } = useSWR<{ packs: PackRow[] }>("/api/knowledge-fabric/packs", fetcher, {
    revalidateOnFocus: false,
  })
  const packs = data?.packs ?? []
  const selected = new Set(value.map((p) => p.id))

  const toggle = (pack: PackRow) => {
    if (selected.has(pack.pack_id)) {
      onChange(value.filter((p) => p.id !== pack.pack_id))
      return
    }
    onChange([
      ...value,
      { id: pack.pack_id, name: pack.label, department: pack.department },
    ])
  }

  return (
    <div className={cn("space-y-3", className)}>
      <div className="flex items-center gap-2 text-sm font-medium text-foreground">
        <BookOpen className="h-4 w-4" />
        Expert knowledge packs
      </div>
      <p className="text-xs text-muted-foreground">
        Assign department knowledge packs alongside company knowledge. Shared packs are
        platform-curated and never mixed into private company files.
      </p>
      <div className="grid gap-2 sm:grid-cols-2">
        {packs.map((pack) => {
          const on = selected.has(pack.pack_id)
          return (
            <button
              key={pack.pack_id}
              type="button"
              onClick={() => toggle(pack)}
              className={cn(
                "rounded-md border px-3 py-2 text-left text-sm transition-colors",
                on
                  ? "border-foreground bg-muted/60"
                  : "border-border hover:border-foreground/40",
              )}
            >
              <div className="font-medium">{pack.label}</div>
              <div className="text-xs text-muted-foreground capitalize">{pack.department}</div>
              {pack.hold ? (
                <div className="mt-1 text-[11px] text-amber-700 dark:text-amber-400">
                  Content sourcing on hold
                </div>
              ) : null}
            </button>
          )
        })}
      </div>
    </div>
  )
}
