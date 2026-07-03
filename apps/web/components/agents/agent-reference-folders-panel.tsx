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
}

export function AgentReferenceFoldersPanel({
  folders,
  title = "Reference folders",
  description = "Cloud folders this agent reads for department-specific knowledge. No files are uploaded — Gravitre pulls from your connected drives.",
  compact = false,
  className,
  editHref,
}: AgentReferenceFoldersPanelProps) {
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
              <Link href={editHref} className="mt-2 inline-flex items-center gap-1 text-xs text-primary hover:underline">
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
