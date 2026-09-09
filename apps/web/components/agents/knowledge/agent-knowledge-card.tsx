"use client"

import Link from "next/link"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import { cn } from "@/lib/utils"
import { Database, DotsThreeVertical, Plugs, Sparkle } from "@phosphor-icons/react"
import type { AgentKnowledgeAssignment } from "@/lib/api"
import { SourceIngestionIndicator, type SourceIngestionSnapshot } from "./source-ingestion-indicator"

function SourceTypeIcon({ sourceType, className }: { sourceType: string; className?: string }) {
  const props = { className, weight: "duotone" as const, "aria-hidden": true as const }
  if (sourceType === "knowledge_pack") return <Sparkle {...props} />
  if (sourceType === "rag_source") return <Database {...props} />
  return <Plugs {...props} />
}

function statusBadge(status?: string) {
  const s = (status ?? "unknown").toLowerCase()
  if (s === "fresh" || s === "ready") return "border-emerald-500/30 bg-emerald-500/10 text-emerald-700 dark:text-emerald-300"
  if (s === "stale") return "border-amber-500/30 bg-amber-500/10 text-amber-700 dark:text-amber-300"
  if (s === "failed" || s === "expired") return "border-red-500/30 bg-red-500/10 text-red-700 dark:text-red-300"
  return "border-border bg-secondary text-muted-foreground"
}

export function AgentKnowledgeCard({
  title,
  description,
  sourceType,
  status,
  meta,
  assigned,
  recommended,
  disabled,
  busy,
  onAssign,
  onRemove,
  onSync,
  ingestion,
  detailHref,
}: {
  title: string
  description?: string
  sourceType: string
  status?: string
  meta?: string
  assigned?: boolean
  recommended?: boolean
  disabled?: boolean
  busy?: boolean
  ingestion?: SourceIngestionSnapshot
  detailHref?: string
  onAssign?: () => void
  onRemove?: () => void
  onSync?: () => void
}) {
  return (
    <article
      className={cn(
        "group flex flex-col gap-3 rounded-[var(--np-radius-lg)] border p-4 shadow-[var(--np-shadow)] transition-all",
        assigned
          ? "border-emerald-500/30 bg-[color:var(--g-surface-1)]"
          : recommended
            ? "border-violet-500/20 bg-violet-500/[0.03]"
            : "border-divide bg-[color:var(--g-surface-1)] hover:border-[color:var(--g-brand)]/25 hover:shadow-md",
      )}
    >
      <div className="flex items-start gap-3">
        <span
          className={cn(
            "flex h-12 w-12 shrink-0 items-center justify-center rounded-[var(--np-radius-md)]",
            assigned ? "bg-emerald-500/10 text-emerald-600" : "bg-[color:var(--g-surface-2)] text-[color:var(--g-brand)]",
          )}
        >
          <SourceTypeIcon sourceType={sourceType} className="h-5 w-5" />
        </span>
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <h3 className="text-sm font-semibold text-[color:var(--g-text-primary)]">{title}</h3>
            {assigned ? (
              <Badge variant="outline" className="border-emerald-500/30 bg-emerald-500/10 text-[10px] font-normal text-emerald-700 dark:text-emerald-300">
                Assigned
              </Badge>
            ) : null}
            {recommended ? (
              <Badge variant="outline" className="border-violet-500/30 bg-violet-500/10 text-[10px] font-normal">
                Recommended
              </Badge>
            ) : null}
            {status ? (
              <Badge variant="outline" className={cn("text-[10px] font-normal capitalize", statusBadge(status))}>
                {status}
              </Badge>
            ) : null}
          </div>
          {description ? (
            <p className="mt-1 line-clamp-2 text-xs leading-relaxed text-[color:var(--g-text-muted)]">{description}</p>
          ) : null}
          {meta ? <p className="mt-1 text-[10px] text-[color:var(--g-text-muted)]">{meta}</p> : null}
          {ingestion ? <div className="mt-2"><SourceIngestionIndicator snapshot={ingestion} /></div> : null}
        </div>
        {(onRemove || onSync) && assigned ? (
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button type="button" variant="ghost" size="icon-sm" aria-label="More actions">
                <DotsThreeVertical className="h-4 w-4" weight="bold" />
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end">
              {onSync ? <DropdownMenuItem onClick={onSync}>Sync now</DropdownMenuItem> : null}
              {onRemove ? (
                <DropdownMenuItem className="text-destructive focus:text-destructive" onClick={onRemove}>
                  Remove from agent
                </DropdownMenuItem>
              ) : null}
            </DropdownMenuContent>
          </DropdownMenu>
        ) : null}
      </div>
      <div className="flex flex-wrap gap-2">
        {!assigned && onAssign ? (
          <Button type="button" size="sm" className="w-full sm:w-auto" disabled={disabled || busy} onClick={onAssign}>
            {busy ? "Assigning…" : "+ Assign"}
          </Button>
        ) : null}
        {detailHref ? (
          <Button type="button" size="sm" variant="outline" asChild>
            <Link href={detailHref}>Manage agents</Link>
          </Button>
        ) : null}
      </div>
    </article>
  )
}

export function AssignmentKnowledgeCard({
  assignment,
  busy,
  onRemove,
  onSync,
  ingestion,
}: {
  assignment: AgentKnowledgeAssignment
  busy?: boolean
  onRemove: () => void
  onSync?: () => void
  ingestion?: SourceIngestionSnapshot
}) {
  const detailHref =
    assignment.sourceType === "rag_source" && assignment.sourceId
      ? `/sources/${encodeURIComponent(assignment.sourceId)}/agents`
      : undefined
  return (
    <AgentKnowledgeCard
      title={assignment.label}
      description={assignment.sourceId}
      sourceType={assignment.sourceType}
      status={assignment.freshnessStatus ?? (assignment.fromConfig ? "legacy" : "unknown")}
      meta={
        assignment.lastSyncedAt
          ? `Last synced ${new Date(assignment.lastSyncedAt).toLocaleString()}`
          : assignment.fromConfig
            ? "Legacy config — re-assign for managed sync"
            : undefined
      }
      ingestion={ingestion}
      detailHref={detailHref}
      assigned
      busy={busy}
      onRemove={onRemove}
      onSync={onSync}
    />
  )
}

export function ExpertPackCard({
  pack,
  assigned,
  recommended,
  recommendationReason,
  busy,
  disabled,
  onAssign,
}: {
  pack: {
    pack_id: string
    label: string
    department: string
    hold?: boolean
    ingestible?: boolean
    customerStatus?: string
  }
  assigned: boolean
  recommended?: boolean
  recommendationReason?: string
  busy?: boolean
  disabled?: boolean
  onAssign: () => void
}) {
  return (
    <AgentKnowledgeCard
      title={pack.label}
      description={recommendationReason}
      sourceType="knowledge_pack"
      status={pack.customerStatus}
      meta={`${pack.department} · Expert pack`}
      assigned={assigned}
      recommended={recommended}
      disabled={disabled}
      busy={busy}
      onAssign={assigned ? undefined : onAssign}
    />
  )
}
