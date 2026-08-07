"use client"

import { createElement } from "react"
import { Download, FileSpreadsheet, FileText, FileType2 } from "lucide-react"
import { Button } from "@/components/ui/button"
import { cn } from "@/lib/utils"
import type { ChatArtifact } from "@/components/gravitre/assistant/chat-execution-panel"

export type HostedFileRef = {
  id?: string
  filename?: string
  mime_type?: string
  mimeType?: string
  byte_size?: number
  byteSize?: number
  role?: string
  download_url?: string | null
  downloadUrl?: string | null
  durable?: boolean
}

function fileIcon(role?: string, mime?: string) {
  const r = (role || "").toLowerCase()
  const m = (mime || "").toLowerCase()
  if (r === "csv" || m.includes("csv")) return FileSpreadsheet
  if (r === "pdf" || m.includes("pdf")) return FileType2
  return FileText
}

function formatBytes(n?: number | null) {
  if (n == null || Number.isNaN(n)) return ""
  if (n < 1024) return `${n} B`
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KB`
  return `${(n / (1024 * 1024)).toFixed(1)} MB`
}

export function hostedFilesFromUnknown(value: unknown): HostedFileRef[] {
  if (!value || typeof value !== "object") return []
  const row = value as Record<string, unknown>
  const list = row.hostedFiles || row.hosted_files
  if (!Array.isArray(list)) return []
  return list.filter((item) => item && typeof item === "object") as HostedFileRef[]
}

export function FileReferenceChip({
  file,
  className,
}: {
  file: HostedFileRef | ChatArtifact
  className?: string
}) {
  const filename =
    ("filename" in file && file.filename) ||
    ("title" in file && file.title) ||
    "Download"
  const mime =
    ("mime_type" in file && (file.mime_type || file.mimeType)) ||
    ("mimeType" in file ? file.mimeType : null) ||
    null
  const metadata = "metadata" in file ? file.metadata : undefined
  const role =
    ("role" in file && file.role) ||
    (metadata && typeof metadata === "object" && "role" in metadata
      ? String((metadata as { role?: unknown }).role || "")
      : "") ||
    undefined
  const bytes =
    ("byte_size" in file && (file.byte_size ?? file.byteSize)) ||
    (metadata && typeof metadata === "object" && "byteSize" in metadata
      ? Number((metadata as { byteSize?: number }).byteSize)
      : undefined)
  const href =
    ("download_url" in file && (file.download_url || file.downloadUrl)) ||
    ("result_url" in file && (file.result_url || file.resultUrl)) ||
    null
  const meta = [role?.toUpperCase(), formatBytes(typeof bytes === "number" ? bytes : undefined)]
    .filter(Boolean)
    .join(" · ")

  return (
    <div
      className={cn(
        "flex items-center gap-2 rounded-lg border border-border/70 bg-background/80 px-2.5 py-2 text-xs",
        className,
      )}
      data-testid="file-reference-chip"
      data-file-role={role || undefined}
    >
      {createElement(fileIcon(role, mime || undefined), {
        className: "h-4 w-4 shrink-0 text-muted-foreground",
      })}
      <div className="min-w-0 flex-1">
        <p className="truncate font-medium text-foreground">{filename}</p>
        {meta ? <p className="truncate text-[10px] text-muted-foreground">{meta}</p> : null}
      </div>
      {href ? (
        <Button asChild size="sm" variant="outline" className="h-7 shrink-0 text-xs">
          <a href={href} target="_blank" rel="noopener noreferrer" download={filename}>
            <Download className="mr-1 h-3 w-3" />
            Download
          </a>
        </Button>
      ) : (
        <span className="text-[10px] text-muted-foreground">Preview only</span>
      )}
    </div>
  )
}

export function FileReferenceChipRow({
  files,
  className,
}: {
  files: HostedFileRef[]
  className?: string
}) {
  if (!files.length) return null
  return (
    <div className={cn("mt-2 space-y-1.5", className)} data-testid="file-reference-chip-row">
      <p className="text-[11px] font-medium uppercase tracking-wide text-muted-foreground">Files</p>
      {files.map((file) => (
        <FileReferenceChip key={file.id || file.filename || file.download_url || JSON.stringify(file)} file={file} />
      ))}
    </div>
  )
}
