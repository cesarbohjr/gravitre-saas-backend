"use client"

import useSWR from "swr"
import { BookOpen } from "lucide-react"
import { Badge } from "@/components/ui/badge"
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
  recommended?: boolean
  recommended_for_department?: string | null
}

type Props = {
  value: KnowledgePackSelection[]
  onChange: (packs: KnowledgePackSelection[]) => void
  /** Agent department from Purpose step — drives server-side recommendations */
  department?: string | null
  className?: string
}

export function AgentKnowledgePacksEditor({ value, onChange, department, className }: Props) {
  const dept = (department || "").trim()
  const qs = dept ? `?department=${encodeURIComponent(dept)}` : ""
  const { data } = useSWR<{ packs: PackRow[]; recommended_pack_ids?: string[] }>(
    `/api/knowledge-fabric/packs${qs}`,
    fetcher,
    { revalidateOnFocus: false },
  )
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

  const recommended = packs.filter((p) => p.recommended)
  const other = packs.filter((p) => !p.recommended)

  const renderPack = (pack: PackRow) => {
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
            : pack.recommended
              ? "border-emerald-500/40 bg-emerald-500/5 hover:border-emerald-500/60"
              : "border-border hover:border-foreground/40",
        )}
      >
        <div className="flex flex-wrap items-center gap-2">
          <span className="font-medium">{pack.label}</span>
          {pack.recommended ? (
            <Badge
              variant="outline"
              className="border-emerald-500/30 bg-emerald-500/10 font-normal text-emerald-700 dark:text-emerald-300"
            >
              Recommended for {pack.recommended_for_department || dept}
            </Badge>
          ) : null}
        </div>
        <div className="text-xs text-muted-foreground capitalize">{pack.department}</div>
        {pack.hold ? (
          <div className="mt-1 text-[11px] text-amber-700 dark:text-amber-400">
            Content sourcing on hold
          </div>
        ) : null}
      </button>
    )
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
        {dept ? (
          <>
            {" "}
            Recommendations for <span className="font-medium text-foreground">{dept}</span> are
            highlighted first — you can still assign any pack.
          </>
        ) : null}
      </p>
      {recommended.length > 0 ? (
        <div className="space-y-2">
          <p className="text-xs font-medium text-foreground">Recommended for {dept}</p>
          <div className="grid gap-2 sm:grid-cols-2">{recommended.map(renderPack)}</div>
        </div>
      ) : null}
      <div className="space-y-2">
        {recommended.length > 0 ? (
          <p className="text-xs font-medium text-muted-foreground">All packs</p>
        ) : null}
        <div className="grid gap-2 sm:grid-cols-2">
          {(recommended.length > 0 ? other : packs).map(renderPack)}
        </div>
      </div>
    </div>
  )
}
