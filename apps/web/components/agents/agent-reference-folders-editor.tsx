"use client"

import { useMemo, useState } from "react"
import Link from "next/link"
import useSWR from "swr"
import { FolderOpen, Plus, Trash2, Cloud, ArrowRight } from "lucide-react"
import { Button } from "@/components/ui/button"
import { cn } from "@/lib/utils"
import { connectorsApi } from "@/lib/api"
import {
  CLOUD_FOLDER_VENDORS,
  REFERENCE_FOLDER_TAG_OPTIONS,
  createReferenceFolder,
  formatReferenceFolderBreadcrumb,
  inferTagsFromFolderPath,
  tagLabel,
  type AgentReferenceFolder,
  type AgentReferenceFolderTag,
} from "@/lib/agent-reference-folders"
import type { Connector } from "@/types/api"

type AgentReferenceFoldersEditorProps = {
  value: AgentReferenceFolder[]
  onChange: (folders: AgentReferenceFolder[]) => void
  className?: string
}

function vendorKey(connector: Connector): string {
  return String(connector.vendor ?? connector.type ?? "").toLowerCase().replace(/\s+/g, "_")
}

export function AgentReferenceFoldersEditor({
  value,
  onChange,
  className,
}: AgentReferenceFoldersEditorProps) {
  const { data: connectorsPayload } = useSWR("/api/connectors", () => connectorsApi.list(), {
    revalidateOnFocus: false,
  })

  const storageConnectors = useMemo(() => {
    const connectors = connectorsPayload?.connectors ?? []
    const allowed = new Set(CLOUD_FOLDER_VENDORS.map((entry) => entry.vendor))
    return connectors.filter((connector) => {
      const key = vendorKey(connector)
      return allowed.has(key) && String(connector.status ?? "").toLowerCase() === "connected"
    })
  }, [connectorsPayload])

  const [connectorId, setConnectorId] = useState("")
  const [folderPath, setFolderPath] = useState("")
  const [label, setLabel] = useState("")
  const [tags, setTags] = useState<AgentReferenceFolderTag[]>([])

  const selectedConnector = storageConnectors.find((entry) => entry.id === connectorId)

  const toggleTag = (tag: AgentReferenceFolderTag) => {
    setTags((prev) => (prev.includes(tag) ? prev.filter((item) => item !== tag) : [...prev, tag]))
  }

  const handlePathChange = (nextPath: string) => {
    setFolderPath(nextPath)
    if (tags.length === 0) {
      setTags(inferTagsFromFolderPath(nextPath))
    }
  }

  const handleAdd = () => {
    if (!selectedConnector || !folderPath.trim()) return
    const folder = createReferenceFolder({
      connectorId: selectedConnector.id,
      connectorVendor: vendorKey(selectedConnector),
      connectorName: selectedConnector.name || selectedConnector.vendor,
      folderPath,
      label,
      tags: tags.length > 0 ? tags : inferTagsFromFolderPath(folderPath),
    })
    onChange([...value, folder])
    setFolderPath("")
    setLabel("")
    setTags([])
  }

  const handleRemove = (id: string) => {
    onChange(value.filter((folder) => folder.id !== id))
  }

  return (
    <div className={cn("space-y-4", className)}>
      <div className="rounded-lg border border-border bg-card p-4">
        <div className="mb-3 flex items-start gap-3">
          <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-info/10">
            <FolderOpen className="h-4 w-4 text-info" />
          </div>
          <div>
            <p className="text-sm font-medium text-foreground">Reference cloud folders</p>
            <p className="text-xs text-muted-foreground text-pretty">
              Link folders from Google Drive, OneDrive, Dropbox, and other cloud storage. Gravitre reads
              from existing folders — nothing is uploaded.
            </p>
          </div>
        </div>

        {storageConnectors.length === 0 ? (
          <div className="rounded-md border border-dashed border-border bg-muted/30 px-4 py-3 text-sm text-muted-foreground">
            Connect a cloud storage app first, then add folder paths here.
            <Link href="/connectors" className="ml-1 inline-flex items-center gap-1 text-foreground hover:underline">
              Manage connectors
              <ArrowRight className="h-3 w-3" />
            </Link>
          </div>
        ) : (
          <div className="space-y-3">
            <div>
              <label className="text-xs font-medium text-foreground">Cloud app</label>
              <select
                value={connectorId}
                onChange={(event) => setConnectorId(event.target.value)}
                className="mt-1 w-full rounded-md border border-border bg-secondary px-3 py-2 text-sm text-foreground"
              >
                <option value="">Select connected storage…</option>
                {storageConnectors.map((connector) => (
                  <option key={connector.id} value={connector.id}>
                    {connector.name || connector.vendor}
                  </option>
                ))}
              </select>
            </div>

            <div>
              <label className="text-xs font-medium text-foreground">Folder path</label>
              <input
                type="text"
                value={folderPath}
                onChange={(event) => handlePathChange(event.target.value)}
                placeholder="e.g. /Marketing/Brand Guidelines or /HR/Employee Handbook"
                className="mt-1 w-full rounded-md border border-border bg-secondary px-3 py-2 text-sm text-foreground placeholder:text-muted-foreground"
              />
              <p className="mt-1 text-[11px] text-muted-foreground">
                Use the folder path as it appears in your cloud drive. Subfolders are supported.
              </p>
            </div>

            <div>
              <label className="text-xs font-medium text-foreground">Display label (optional)</label>
              <input
                type="text"
                value={label}
                onChange={(event) => setLabel(event.target.value)}
                placeholder="e.g. Brand guidelines"
                className="mt-1 w-full rounded-md border border-border bg-secondary px-3 py-2 text-sm text-foreground placeholder:text-muted-foreground"
              />
            </div>

            <div>
              <label className="text-xs font-medium text-foreground">Department tags</label>
              <div className="mt-2 flex flex-wrap gap-2">
                {REFERENCE_FOLDER_TAG_OPTIONS.map((option) => {
                  const active = tags.includes(option.id)
                  return (
                    <button
                      key={option.id}
                      type="button"
                      onClick={() => toggleTag(option.id)}
                      className={cn(
                        "rounded-full border px-2.5 py-1 text-xs font-medium transition-colors",
                        active
                          ? "border-primary bg-primary/10 text-primary"
                          : "border-border bg-secondary text-muted-foreground hover:text-foreground",
                      )}
                    >
                      {option.label}
                    </button>
                  )
                })}
              </div>
            </div>

            <Button
              type="button"
              variant="outline"
              size="sm"
              className="gap-2"
              disabled={!selectedConnector || folderPath.trim().length < 2}
              onClick={handleAdd}
            >
              <Plus className="h-3.5 w-3.5" />
              Add folder reference
            </Button>
          </div>
        )}
      </div>

      {value.length > 0 ? (
        <div className="space-y-2">
          {value.map((folder) => (
            <div
              key={folder.id}
              className="flex items-start justify-between gap-3 rounded-lg border border-border bg-card p-3"
            >
              <div className="min-w-0">
                <p className="truncate text-sm font-medium text-foreground">
                  {folder.label || folder.folderName}
                </p>
                <p className="mt-0.5 truncate font-mono text-[11px] text-muted-foreground">
                  {formatReferenceFolderBreadcrumb(folder)}
                </p>
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
              <Button
                type="button"
                variant="ghost"
                size="icon"
                className="h-8 w-8 shrink-0 text-muted-foreground hover:text-destructive"
                onClick={() => handleRemove(folder.id)}
                aria-label="Remove folder reference"
              >
                <Trash2 className="h-4 w-4" />
              </Button>
            </div>
          ))}
        </div>
      ) : null}

      <div className="rounded-md border border-border/70 bg-muted/20 px-3 py-2">
        <p className="mb-2 text-[11px] font-medium uppercase tracking-wide text-muted-foreground">
          Supported cloud apps
        </p>
        <div className="flex flex-wrap gap-2">
          {CLOUD_FOLDER_VENDORS.map((entry) => {
            const connected = storageConnectors.some((connector) => vendorKey(connector) === entry.vendor)
            return (
              <span
                key={entry.vendor}
                className={cn(
                  "inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-[10px]",
                  connected
                    ? "border-success/30 bg-success/10 text-success"
                    : "border-border text-muted-foreground",
                )}
              >
                <Cloud className="h-3 w-3" />
                {entry.label}
              </span>
            )
          })}
        </div>
      </div>
    </div>
  )
}
