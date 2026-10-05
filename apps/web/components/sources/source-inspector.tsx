"use client"

import Link from "next/link"
import { Database, RefreshCw, Workflow, Loader2 } from "lucide-react"
import { ConnectorIcon } from "@/components/gravitre/connector-icon"
import { Button } from "@/components/ui/button"
import { sourceTypeVendorKey } from "@/lib/brand-vendor"
import { buildWorkflowFromSourceUrl } from "@/lib/source-workflow-handoff"
import { formatReportedCount, type Source } from "@/lib/source-inventory"
import { cn } from "@/lib/utils"

function SourceHealthGauge({ health }: { health: number }) {
  const circumference = 2 * Math.PI * 18
  return <div role="img" aria-label={`Reported source health: ${health}%`} className="relative h-11 w-11 shrink-0">
    <svg width="44" height="44" viewBox="0 0 44 44" className="-rotate-90" aria-hidden>
      <circle cx="22" cy="22" r="18" strokeWidth="3" fill="none" className="stroke-[color:var(--g-border-subtle)]" />
      <circle cx="22" cy="22" r="18" strokeWidth="3" fill="none" strokeLinecap="round" strokeDasharray={circumference} strokeDashoffset={circumference * (1 - Math.min(100, Math.max(0, health)) / 100)} className={health >= 90 ? "stroke-[color:var(--g-brand)]" : health >= 70 ? "stroke-[color:var(--g-warmth)]" : "stroke-destructive"} />
    </svg>
    <span className="absolute inset-0 flex items-center justify-center text-[10px] font-medium tabular-nums">{health}%</span>
  </div>
}

function SourceStatus({ source }: { source: Source }) {
  return <span className="inline-flex items-center gap-2 text-xs capitalize">
    <span aria-hidden className={cn("h-1.5 w-1.5 shrink-0 rounded-full",
      source.status === "connected" ? "bg-[color:var(--g-brand)]" :
      source.status === "syncing" ? "bg-[color:var(--g-electric)]" :
      source.status === "error" ? "bg-destructive" : "bg-muted-foreground/50")} />
    {source.status === "unknown" ? "Status not reported" : source.status}
  </span>
}

export function SourceInventoryRow({ source, selected, onSelect }: { source: Source; selected: boolean; onSelect: () => void }) {
  return <button type="button" aria-pressed={selected} onClick={onSelect}
    className={cn("flex min-h-11 w-full items-center gap-3 px-4 py-3 text-left transition-colors hover:bg-[color:var(--g-surface-2)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-ring", selected && "bg-[color:var(--g-surface-active)]")}>
    <ConnectorIcon vendor={sourceTypeVendorKey(source.type)} name={source.name} size="sm" showStatusIndicator={false} />
    <span className="flex min-w-0 flex-1 flex-col gap-1">
      <span className="flex min-w-0 items-center justify-between gap-3">
        <span className="truncate text-sm font-semibold text-foreground">{source.name}</span>
        <SourceStatus source={source} />
      </span>
      <span className="truncate text-xs tabular-nums text-muted-foreground">
        {source.type} · {source.environment} · {formatReportedCount(source.tables)} tables · {source.records} records · {source.status === "syncing" ? "syncing now" : `synced ${source.lastSync}`}
      </span>
    </span>
  </button>
}

export function SourceInspector({ source, onSync, onDelete, isMutating }: {
  source: Source
  onSync: (id: string) => Promise<void>
  onDelete: (id: string) => Promise<void>
  isMutating: boolean
}) {
  return <section aria-label={`${source.name} source context`} className="space-y-4 rounded-[var(--np-radius-lg)] border border-divide bg-[color:var(--g-surface-1)] p-4">
    <div className="flex items-start gap-3">
      <ConnectorIcon vendor={sourceTypeVendorKey(source.type)} name={source.name} size="md" showStatusIndicator={false} />
      <div className="min-w-0 flex-1"><h3 className="break-words font-sans text-xl text-foreground">{source.name}</h3><p className="text-xs text-muted-foreground">{source.type} · {source.environment}</p></div>
      {source.health != null ? <SourceHealthGauge health={source.health} /> : null}
    </div>
    <SourceStatus source={source} />
    <p className="break-words text-sm text-muted-foreground">{source.description}</p>
    <dl className="grid grid-cols-2 gap-3 border-y border-divide py-3 text-sm">
      {[['Tables', formatReportedCount(source.tables)], ['Records', source.records], ['Workflows', formatReportedCount(source.workflowsUsing)], ['Operators', formatReportedCount(source.operatorsUsing)], ['Health', source.health == null ? 'Not reported' : `${source.health}%`], ['Last sync', source.lastSync]].map(([label, value]) => <div key={label}><dt className="text-xs text-muted-foreground">{label}</dt><dd className="mt-1 break-words font-medium tabular-nums text-foreground">{value}</dd></div>)}
    </dl>
    <details className="rounded-md border border-divide">
      <summary className="min-h-11 cursor-pointer px-3 py-3 text-sm font-medium focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring">Schema preview · {source.topTables?.length ?? 0} reported names</summary>
      {source.topTables?.length ? <ul className="space-y-1 border-t border-divide p-3">{source.topTables.map((table) => <li key={table} className="break-all font-mono text-xs text-muted-foreground">{table}</li>)}</ul> : <p className="p-3 text-xs text-muted-foreground">No table names reported. Open source details to inspect schema.</p>}
    </details>
    <Button className="min-h-11 w-full gap-2" onClick={() => void onSync(source.id)} disabled={isMutating}>{isMutating ? <Loader2 className="h-4 w-4 animate-spin" /> : <RefreshCw className="h-4 w-4" />}Sync source</Button>
    <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
      <Button asChild variant="outline" className="min-h-11 gap-2"><Link href={`/sources/${source.id}`}><Database className="h-4 w-4" />Source details</Link></Button>
      <Button asChild variant="outline" className="min-h-11 gap-2"><Link href={buildWorkflowFromSourceUrl(source)}><Workflow className="h-4 w-4" />Use in workflow</Link></Button>
    </div>
    <Button variant="ghost" className="min-h-11 text-destructive" onClick={() => void onDelete(source.id)} disabled={isMutating}>Delete source</Button>
  </section>
}
