"use client"

import Link from "next/link"
import { FolderOpen, ExternalLink } from "lucide-react"
import { cn } from "@/lib/utils"
import {
  formatReferenceFolderBreadcrumb,
  formatReferenceFolderPathOnly,
  tagLabel,
  type AgentReferenceFolder,
} from "@/lib/agent-reference-folders"

type AgentReferenceFoldersPanelProps = {
  folders: AgentReferenceFolder[]
  title?: string
  description?: string
  compact?: boolean
  className?: string
  editHref?: string
  /** "ruled": borderless section for a secondary rail. */
  variant?: "card" | "ruled"
}

export function AgentReferenceFoldersPanel({
  folders,
  title = "Reference folders",
  description = "Cloud folders this agent reads for department-specific knowledge. No files are uploaded — Gravitre pulls from your connected drives.",
  compact = false,
  className,
  editHref,
  variant = "card",
}: AgentReferenceFoldersPanelProps) {
  if (variant === "ruled") {
    return (
      <section aria-labelledby="agent-reference-heading" className={cn("border-t border-[color:var(--g-border-default)] pt-3", className)}>
        <div className="flex items-baseline justify-between gap-3">
          <h3 id="agent-reference-heading" className="text-[13px] font-semibold text-foreground">
            {title}
          </h3>
          {editHref ? (
            <Link href={editHref} className="inline-flex min-h-11 items-center gap-1 text-[12px] text-primary hover:underline sm:min-h-0">
              {folders.length === 0 ? "Link cloud folders" : "Manage"}
              <ExternalLink className="h-3 w-3" aria-hidden />
            </Link>
          ) : null}
        </div>
        {folders.length === 0 ? (
          <p className="mt-1 text-[12px] text-muted-foreground">{description}</p>
        ) : (
          <ul className="mt-1">
            {folders.map((folder) => (
              <li key={folder.id} className="flex items-start gap-2.5 border-b border-[color:var(--g-border-subtle)] py-2.5 last:border-b-0">
                <FolderOpen className="mt-0.5 h-3.5 w-3.5 shrink-0 text-muted-foreground" aria-hidden />
                <div className="min-w-0 flex-1">
                  <p className="text-[13px] font-medium text-foreground">{folder.label || folder.folderName}</p>
                  <p className="mt-0.5 break-all font-mono text-[11px] text-muted-foreground">
                    {formatReferenceFolderBreadcrumb(folder)}
                  </p>
                  {folder.tags.length ? (
                    <p className="mt-1 text-[11.5px] text-muted-foreground">{folder.tags.map((tag) => tagLabel(tag)).join(" · ")}</p>
                  ) : null}
                </div>
              </li>
            ))}
          </ul>
        )}
      </section>
    )
  }

  if (folders.length === 0) {
    return (
      <div className={cn("rounded-xl border border-dashed border-border bg-card/40 p-4", className)}>
        <div className="flex items-start gap-3">
          <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-muted">
            <FolderOpen className="h-4 w-4 text-muted-foreground" />
          </div>
          <div>
            <p className="text-sm font-medium text-foreground">{title}</p>
            <p className="mt-1 text-xs text-muted-foreground">{description}</p>
            {editHref ? (
              <Link href={editHref} className="mt-2 inline-flex min-h-11 items-center gap-1 text-xs text-primary hover:underline sm:min-h-0">
                Link cloud folders
                <ExternalLink className="h-3 w-3" />
              </Link>
            ) : null}
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className={cn("rounded-xl border border-border bg-card", className)}>
      <div className="flex items-start justify-between gap-3 border-b border-border px-4 py-3">
        <div>
          <p className="text-sm font-semibold text-foreground">{title}</p>
          {!compact ? <p className="mt-0.5 text-xs text-muted-foreground">{description}</p> : null}
        </div>
        {editHref ? (
          <Link href={editHref} className="inline-flex items-center gap-1 text-xs text-primary hover:underline">
            Manage
            <ExternalLink className="h-3 w-3" />
          </Link>
        ) : null}
      </div>

      <div className="divide-y divide-border">
        {folders.map((folder) => (
          <div key={folder.id} className="px-4 py-3">
            <div className="flex items-start gap-3">
              <div className="mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-info/10">
                <FolderOpen className="h-4 w-4 text-info" />
              </div>
              <div className="min-w-0 flex-1">
                <p className="text-sm font-medium text-foreground">
                  {folder.label || folder.folderName}
                </p>
                <p className="mt-1 font-mono text-[11px] text-muted-foreground break-all">
                  {formatReferenceFolderBreadcrumb(folder)}
                </p>
                {!compact ? (
                  <p className="mt-1 text-[11px] text-muted-foreground">
                    Path: {formatReferenceFolderPathOnly(folder)}
                  </p>
                ) : null}
                <div className="mt-2 flex flex-wrap gap-1.5">
                  {folder.tags.map((tag) => (
                    <span
                      key={tag}
                      className="rounded-full bg-secondary px-2 py-0.5 text-[10px] font-medium text-muted-foreground"
                    >
                      {tagLabel(tag)}
                    </span>
                  ))}
                </div>
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}
