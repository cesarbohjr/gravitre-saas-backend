"use client"

import { useState } from "react"
import ReactMarkdown from "react-markdown"
import remarkGfm from "remark-gfm"
import { cn } from "@/lib/utils"

export type PreviewCodePaneProps = {
  title?: string
  code?: string | null
  previewHtml?: string | null
  /** When format is markdown and no previewHtml, render code as markdown preview. */
  previewFormat?: string | null
  className?: string
  defaultTab?: "preview" | "code"
}

export function PreviewCodePane({
  title,
  code,
  previewHtml,
  previewFormat,
  className,
  defaultTab = "preview",
}: PreviewCodePaneProps) {
  const hasCode = Boolean(code && String(code).trim())
  const hasHtml = Boolean(previewHtml && String(previewHtml).trim())
  const markdownPreview =
    !hasHtml && hasCode && (previewFormat === "markdown" || previewFormat === "md")
  const [tab, setTab] = useState<"preview" | "code">(
    defaultTab === "code" && hasCode ? "code" : hasHtml || markdownPreview ? "preview" : "code",
  )
  if (!hasCode && !hasHtml) return null

  return (
    <div
      className={cn(
        "mt-2 overflow-hidden rounded-lg border border-border/70 bg-background/80",
        className,
      )}
      data-testid="preview-code-pane"
    >
      <div className="flex items-center justify-between gap-2 border-b border-border/60 px-2.5 py-1.5">
        <p className="truncate text-[11px] font-medium text-muted-foreground">
          {title || "Preview"}
        </p>
        <div className="flex shrink-0 rounded-md bg-muted/60 p-0.5 text-[11px]">
          <button
            type="button"
            className={cn(
              "rounded px-2 py-0.5",
              tab === "preview" ? "bg-background text-foreground shadow-sm" : "text-muted-foreground",
            )}
            onClick={() => setTab("preview")}
            disabled={!hasHtml && !markdownPreview}
          >
            Preview
          </button>
          <button
            type="button"
            className={cn(
              "rounded px-2 py-0.5",
              tab === "code" ? "bg-background text-foreground shadow-sm" : "text-muted-foreground",
            )}
            onClick={() => setTab("code")}
            disabled={!hasCode}
          >
            Code
          </button>
        </div>
      </div>
      {tab === "preview" ? (
        hasHtml ? (
          <iframe
            title={title || "Preview"}
            sandbox=""
            srcDoc={previewHtml || ""}
            className="h-64 w-full bg-white"
            data-testid="preview-code-iframe"
          />
        ) : markdownPreview ? (
          <div
            className="prose prose-sm dark:prose-invert max-h-64 overflow-auto px-3 py-2"
            data-testid="preview-code-markdown"
          >
            <ReactMarkdown remarkPlugins={[remarkGfm]}>{code || ""}</ReactMarkdown>
          </div>
        ) : (
          <p className="px-3 py-2 text-xs text-muted-foreground">No preview available.</p>
        )
      ) : (
        <pre
          className="max-h-64 overflow-auto whitespace-pre-wrap px-3 py-2 font-mono text-[11px] text-foreground/90"
          data-testid="preview-code-source"
        >
          {code}
        </pre>
      )}
    </div>
  )
}

export function previewPropsFromToolResult(result: unknown): PreviewCodePaneProps | null {
  if (!result || typeof result !== "object") return null
  const data = result as Record<string, unknown>
  const code =
    (typeof data.code === "string" && data.code) ||
    (typeof data.content === "string" && data.content) ||
    (typeof data.preview === "string" && data.preview) ||
    null
  const previewHtml =
    (typeof data.previewHtml === "string" && data.previewHtml) ||
    (typeof data.preview_html === "string" && data.preview_html) ||
    null
  const previewFormat =
    (typeof data.previewFormat === "string" && data.previewFormat) ||
    (typeof data.preview_format === "string" && data.preview_format) ||
    (typeof data.format === "string" && data.format) ||
    null
  if (!code && !previewHtml) return null
  return {
    title: typeof data.title === "string" ? data.title : undefined,
    code,
    previewHtml,
    previewFormat,
  }
}
